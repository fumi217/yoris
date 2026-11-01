"""記録の保存・押し直し（001-T026）のテスト。

DB を使うテストは、tests/conftest.py の session を使う
（テストごとに取り消すので、開発の DB は変わらない）。
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Facility, Resident, Staff, User
from app.models.records import CareRecord, CareRecordHistory
from app.services.records import InvalidRecord, NotToday, save_record, today_jst

# 日本時間の 2026-10-23 12:00
NOW = datetime(2026, 10, 23, 3, 0, tzinfo=UTC)
TODAY = date(2026, 10, 23)


# --- DB を使わないテスト（CI でも動く） ---


def test_today_is_decided_in_japan_time():
    # UTC の 10/22 15:00 は、日本時間の 10/23 0:00
    assert today_jst(datetime(2026, 10, 22, 14, 59, tzinfo=UTC)) == date(2026, 10, 22)
    assert today_jst(datetime(2026, 10, 22, 15, 0, tzinfo=UTC)) == date(2026, 10, 23)


@pytest.mark.parametrize(
    ("item", "slot", "value"),
    [
        ("meal", "day", "8"),  # 食事は食事区分で
        ("mood", "lunch", "smile"),  # 機嫌は day だけ
        ("meal", "lunch", "smile"),  # 食事の値ではない
        ("sleep", "day", "8"),  # 眠りの値ではない
        ("bath", "day", "good"),  # 決まりの外の項目
    ],
)
def test_invalid_item_slot_value_is_rejected(item, slot, value):
    # 組み合わせの確認は DB を読む前に行うので、セッションは使われない
    with pytest.raises(InvalidRecord):
        save_record(
            None,  # type: ignore[arg-type]
            resident_id=1,
            staff_id=1,
            record_date=TODAY,
            item=item,
            slot=slot,
            value=value,
            now=NOW,
        )


@pytest.mark.parametrize("record_date", [TODAY + timedelta(days=1), TODAY - timedelta(days=4)])
def test_date_out_of_range_is_rejected(record_date):
    # 明日の分と、4 日前より前の分は付けられない（3 日前まで）
    with pytest.raises(InvalidRecord):
        save_record(
            None,  # type: ignore[arg-type]
            resident_id=1,
            staff_id=1,
            record_date=record_date,
            item="meal",
            slot="lunch",
            value="8",
            now=NOW,
        )


# --- DB を使うテスト ---


@pytest.fixture
def ids(session: Session) -> dict[str, int]:
    """架空の施設・入居者・職員 2 人を作る。"""
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    resident = Resident(
        facility_id=facility.id,
        name="架空 花子",
        name_kana="かくう",
        name_romaji="Kaku",
        room="101",
    )
    staff = []
    for n in (1, 2):
        user = User(kind="staff", login_id=f"s9{n:04d}", password_hash="x")
        session.add(user)
        session.flush()
        staff.append(
            Staff(
                user_id=user.id,
                facility_id=facility.id,
                display_name=f"職員{n}",
                role="care_worker",
            )
        )
    session.add_all([resident, *staff])
    session.flush()
    return {"resident": resident.id, "staff1": staff[0].id, "staff2": staff[1].id}


def _save(session: Session, ids: dict[str, int], **kwargs) -> CareRecord:
    values = {
        "resident_id": ids["resident"],
        "staff_id": ids["staff1"],
        "record_date": TODAY,
        "item": "meal",
        "slot": "lunch",
        "value": "8",
        "now": NOW,
    }
    values.update(kwargs)
    return save_record(session, **values)


def _active_count(session: Session, resident_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(CareRecord)
        .where(CareRecord.resident_id == resident_id, CareRecord.deleted_at.is_(None))
    )


def _histories(session: Session, record_id: int) -> list[CareRecordHistory]:
    return list(
        session.scalars(
            select(CareRecordHistory).where(CareRecordHistory.care_record_id == record_id)
        )
    )


def test_new_record_is_saved_with_recorder(session, ids):
    record = _save(session, ids)

    assert record.id is not None
    assert (record.item, record.slot, record.value) == ("meal", "lunch", "8")
    assert record.recorded_by == ids["staff1"]
    assert _histories(session, record.id) == []


def test_pressing_again_overwrites_and_keeps_history(session, ids):
    first = _save(session, ids, value="8")
    second = _save(session, ids, value="5", staff_id=ids["staff2"])

    # 同じ「入居者×日付×項目×区分」は 1 つだけで、上書きされる
    assert second.id == first.id
    assert second.value == "5"
    assert second.recorded_by == ids["staff2"]
    assert _active_count(session, ids["resident"]) == 1
    # 前の値が履歴に残る（FR-005）
    [history] = _histories(session, first.id)
    assert (history.old_value, history.new_value, history.changed_by) == ("8", "5", ids["staff2"])


def test_pressing_the_same_value_adds_no_history(session, ids):
    record = _save(session, ids, value="8")
    _save(session, ids, value="8")

    assert _histories(session, record.id) == []


def test_different_slots_are_separate_records(session, ids):
    _save(session, ids, slot="breakfast")
    _save(session, ids, slot="lunch")
    _save(session, ids, item="mood", slot="day", value="smile")

    assert _active_count(session, ids["resident"]) == 3


def test_forgotten_record_can_be_added_up_to_three_days_ago(session, ids):
    record = _save(session, ids, record_date=TODAY - timedelta(days=3))

    assert record.date == TODAY - timedelta(days=3)


def test_past_record_cannot_be_pressed_again(session, ids):
    # 過去の日の記録を新しく付けるのはよいが、付いている記録を直すのは今日の分だけ
    _save(session, ids, record_date=TODAY - timedelta(days=1), value="8")

    with pytest.raises(NotToday):
        _save(session, ids, record_date=TODAY - timedelta(days=1), value="5")


def test_record_can_be_added_again_after_cancel(session, ids):
    record = _save(session, ids)
    # 取り消し（001-T034）の代わりに、取り消した状態を作る
    record.deleted_at = NOW
    record.deleted_by = ids["staff1"]
    session.flush()

    again = _save(session, ids, value="2")

    assert again.id != record.id
    assert _active_count(session, ids["resident"]) == 1


def test_sample_records_follow_the_rules(session, ids):
    from app.seed.records import add_sample_records

    count = add_sample_records(
        session, resident_ids=[ids["resident"]], staff_id=ids["staff1"], today=TODAY
    )

    # 今日は 4 件（夜ごはん・おやつは未記録のまま）、前の 2 日は 6 件ずつ
    assert count == 4 + 6 + 6
    assert _active_count(session, ids["resident"]) == count
