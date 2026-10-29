"""変化の決まりの初期データ（spec 006 の 006-T004）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。
3 つの決まりを、すべてオンで入れる。すでにある決まりは足さない（オン／オフを変えていても戻さない）。
デモ用の目印（006-T009）は、記録のサンプルを入れたあとに呼ぶ。
"""

from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.change_flags import ChangeRule
from app.models.records import CareRecord
from app.services.change_detection import evaluate_change_flags
from app.services.change_rules import RULE_CODES

# デモで目印が付く入居者（入居者の順番。0 は先頭）。
# 前の日の夜ごはん「少し」・今日の朝ごはん「食べていない」にする（朝の時点の記録にそろえる）
DEMO_RESIDENT_INDEX = 0


def add_change_rules(session: Session) -> None:
    """足りない決まりをオンで足す。commit は呼んだ側が行う。"""
    existing = set(session.scalars(select(ChangeRule.code)))
    for code in RULE_CODES:
        if code not in existing:
            session.add(ChangeRule(code=code, enabled=True))
    session.flush()


def add_sample_change_flags(
    session: Session, *, resident_ids: list[int], staff_id: int, today: date
) -> None:
    """デモ用に 1 人の記録を「2 食続けて少し以下」にしてから、全員の目印を付ける。

    commit は呼んだ側が行う。

    記録のサンプル（seed/records.py）を入れたあとに呼ぶ。同じ欄の記録があれば値を直し、なければ足す。
    いちばん新しい食事の記録が「少し」以下でないと目印が付かないので、今日の朝より後の
    食事（昼・夜）の記録は、デモの入居者だけ入れない。
    """
    resident_id = resident_ids[DEMO_RESIDENT_INDEX]
    for record_date, slot, value in [
        (today - timedelta(days=1), "dinner", "2"),
        (today, "breakfast", "0"),
    ]:
        record = session.scalars(
            select(CareRecord).where(
                CareRecord.resident_id == resident_id,
                CareRecord.date == record_date,
                CareRecord.item == "meal",
                CareRecord.slot == slot,
                CareRecord.deleted_at.is_(None),
            )
        ).one_or_none()
        if record is None:
            session.add(
                CareRecord(
                    resident_id=resident_id,
                    date=record_date,
                    item="meal",
                    slot=slot,
                    value=value,
                    recorded_by=staff_id,
                )
            )
        else:
            record.value = value
    session.execute(
        delete(CareRecord).where(
            CareRecord.resident_id == resident_id,
            CareRecord.date == today,
            CareRecord.item == "meal",
            CareRecord.slot.in_(["lunch", "dinner"]),
        )
    )
    session.flush()
    for each_id in resident_ids:
        evaluate_change_flags(session, each_id)
