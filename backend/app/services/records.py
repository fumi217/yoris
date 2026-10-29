"""記録の保存・押し直し（spec 001 の 001-T026）。

- 押し直したら value を上書きし、前の値を care_record_histories に残す（FR-005）
- 「今日」は日本時間で決める。タブレットの時計は使わない（research.md R-14）
- 新しく付けられるのは、今日から 3 日前までの日付。押し直し（直すこと）は今日の記録だけ
  （spec 001 の Edge Cases、Session 2026-10-23）
- 取り消し（delete_record）も今日の記録だけ。行は消さずに deleted_at・deleted_by を入れ、
  前の値を履歴に残す（new_value は空）。取り消した記録は、家族の連絡帳・職員の画面のどれにも出ない。
  取り消したあとは、同じ欄に新しく付け直せる（一意制約は取り消していないものだけ。research.md R-04）
- 保存・押し直し・取り消しのあとに、変化の目印を同じセッションで付け直す（spec 006 の 006-T008。
  記録と目印が同じトランザクションで確定する。spec 006 の research.md R-03）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import today_jst
from app.models.records import DAY_SLOT, MEAL_SLOTS, VALUES, CareRecord, CareRecordHistory
from app.services.change_detection import evaluate_change_flags

# 付け忘れを、何日前の分まで新しく付けられるか
BACKFILL_DAYS = 3


class RecordError(Exception):
    """記録を保存できないとき。code は spec 001 contracts のエラーのコード。"""

    code = "validation_error"


class InvalidRecord(RecordError):
    """項目・区分・値の組み合わせや日付が決まりの外（422）。"""

    code = "validation_error"


class NotToday(RecordError):
    """今日でない記録を押し直そうとした（409）。"""

    code = "not_today"


class RecordNotFound(RecordError):
    """取り消す記録がない・もう取り消してある（404）。"""

    code = "not_found"


def _validate(item: str, slot: str, value: str) -> None:
    if item not in VALUES:
        raise InvalidRecord(f"item: {item}")
    slots = MEAL_SLOTS if item == "meal" else (DAY_SLOT,)
    if slot not in slots:
        raise InvalidRecord(f"slot: {slot}")
    if value not in VALUES[item]:
        raise InvalidRecord(f"value: {value}")


def save_record(
    session: Session,
    *,
    resident_id: int,
    staff_id: int,
    record_date: date,
    item: str,
    slot: str,
    value: str,
    now: datetime | None = None,
) -> CareRecord:
    """記録を付ける。同じ入居者×日付×項目×区分の記録があれば押し直す（上書き）。

    入居者が施設にいるか・職員の役割は、呼ぶ API の側で確かめる。
    """
    _validate(item, slot, value)
    today = today_jst(now)
    if not (today - timedelta(days=BACKFILL_DAYS) <= record_date <= today):
        raise InvalidRecord(f"record_date: {record_date}")

    for _ in range(2):
        existing = session.scalars(
            select(CareRecord)
            .where(
                CareRecord.resident_id == resident_id,
                CareRecord.date == record_date,
                CareRecord.item == item,
                CareRecord.slot == slot,
                CareRecord.deleted_at.is_(None),
            )
            # 2 人がほぼ同時に押し直したとき、順番に処理して履歴を取りこぼさないように
            .with_for_update()
        ).one_or_none()

        if existing is not None:
            record = _overwrite(session, existing, staff_id=staff_id, value=value, today=today)
            # 押し直しで、目印が付く・消えることがある（spec 006 の 006-T008）
            evaluate_change_flags(session, resident_id)
            return record

        record = CareRecord(
            resident_id=resident_id,
            date=record_date,
            item=item,
            slot=slot,
            value=value,
            recorded_by=staff_id,
        )
        try:
            # ほぼ同時に 2 人が新しく付けたときは、後の人の保存が一意制約で止まる。
            # その分だけ取り消して、もう一度読み直し、押し直しとして扱う
            with session.begin_nested():
                session.add(record)
                session.flush()
        except IntegrityError:
            continue
        # 記録と目印が同じトランザクションで確定するよう、同じセッションで調べ直す（006-T008・R-03）
        evaluate_change_flags(session, resident_id)
        return record

    # 入力のまちがいではなく、起きるはずのないこと
    # （API では 500 になり、ログに残る。PR #158 ようこ）
    raise RuntimeError("同時に保存された記録を読み直せなかった")


def _overwrite(
    session: Session, record: CareRecord, *, staff_id: int, value: str, today: date
) -> CareRecord:
    if record.date != today:
        raise NotToday(f"record_date: {record.date}")
    if record.value == value:
        return record
    session.add(
        CareRecordHistory(
            care_record_id=record.id,
            old_value=record.value,
            new_value=value,
            changed_by=staff_id,
        )
    )
    record.value = value
    record.recorded_by = staff_id
    record.recorded_at = datetime.now(UTC)
    session.flush()
    return record


def delete_record(
    session: Session, *, record_id: int, staff_id: int, now: datetime | None = None
) -> CareRecord:
    """今日の記録を取り消す（spec 001 の 001-T034・Edge Cases「誤って別の入居者に記録した」）。

    2 人がほぼ同時に取り消したり、押し直したりしても、行を押さえて順番に処理する。
    職員の役割は、呼ぶ API の側で確かめる。
    施設は確かめない（施設は 1 つの決まり。spec 002 の R-04）。
    """
    record = session.scalars(
        select(CareRecord)
        .where(CareRecord.id == record_id, CareRecord.deleted_at.is_(None))
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise RecordNotFound(f"record_id: {record_id}")
    if record.date != today_jst(now):
        raise NotToday(f"record_date: {record.date}")
    session.add(
        CareRecordHistory(
            care_record_id=record.id, old_value=record.value, new_value=None, changed_by=staff_id
        )
    )
    record.deleted_at = now or datetime.now(UTC)
    record.deleted_by = staff_id
    session.flush()
    # 取り消しで当てはまらなくなれば、目印が消える（006-T008）
    evaluate_change_flags(session, record.resident_id)
    return record
