"""面会予約のテーブルの決まり（003-T001）が DB で効くかのテスト。

予約を作る処理（book_visit、003-T009）にバグがあっても、DB が受け付けないことを確かめる
（research.md R-01）。
DB は tests/conftest.py の session を使う（テストごとに取り消す）。
"""

from datetime import date, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.core import Facility, Resident
from app.models.visits import VisitReservation, VisitSetting, VisitStartTime
from app.seed.visits import START_TIMES, add_sample_reservations, add_visit_settings
from app.services.visit_rules import visit_range

VISIT_DATE = date(2026, 10, 28)


@pytest.fixture
def ids(session: Session) -> dict[str, int]:
    """架空の施設と入居者 2 人を作る。"""
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    residents = [
        Resident(
            facility_id=facility.id, name=f"架空 {n}", display_name=f"テスト{n}", room=f"10{n}"
        )
        for n in (1, 2)
    ]
    session.add_all(residents)
    session.flush()
    return {"facility": facility.id, "a": residents[0].id, "b": residents[1].id}


def _reservation(ids, resident: str, start: time, status: str = "booked") -> VisitReservation:
    starts_at, ends_at = visit_range(VISIT_DATE, start)
    return VisitReservation(
        facility_id=ids["facility"],
        resident_id=ids[resident],
        visit_date=VISIT_DATE,
        start_time=start,
        starts_at=starts_at,
        ends_at=ends_at,
        party_size=1,
        status=status,
    )


def _add(session: Session, reservation: VisitReservation) -> None:
    with session.begin_nested():
        session.add(reservation)
        session.flush()


def test_overlapping_reservations_are_rejected(session, ids):
    _add(session, _reservation(ids, "a", time(10, 30)))

    # 10:00〜11:30 は 10:30〜12:00 と重なる
    with pytest.raises(IntegrityError):
        _add(session, _reservation(ids, "b", time(10, 0)))


def test_back_to_back_reservations_are_allowed(session, ids):
    # 10:30〜12:00 と 13:00〜14:30 は重ならない
    _add(session, _reservation(ids, "a", time(10, 30)))
    _add(session, _reservation(ids, "b", time(13, 0)))


def test_same_family_twice_a_day_is_rejected(session, ids):
    _add(session, _reservation(ids, "a", time(10, 0)))

    with pytest.raises(IntegrityError):
        _add(session, _reservation(ids, "a", time(14, 0)))


def test_cancelled_reservations_free_the_time(session, ids):
    # 取り消した予約は、重なりにも 1 日 1 回にも数えない
    _add(session, _reservation(ids, "a", time(10, 30), status="cancelled_by_family"))
    _add(session, _reservation(ids, "a", time(10, 30)))


def test_party_size_must_be_positive(session, ids):
    reservation = _reservation(ids, "a", time(10, 0))
    reservation.party_size = 0

    with pytest.raises(IntegrityError):
        _add(session, reservation)


def test_staff_cancel_needs_reason(session, ids):
    reservation = _reservation(ids, "a", time(10, 0), status="cancelled_by_staff")

    with pytest.raises(IntegrityError):
        _add(session, reservation)


def test_seed_settings_and_start_times(session, ids):
    add_visit_settings(session, facility_id=ids["facility"])
    # 2 回流しても増えない
    add_visit_settings(session, facility_id=ids["facility"])

    assert session.get(VisitSetting, ids["facility"]).daily_limit == 2
    times = session.scalars(
        select(VisitStartTime.start_time)
        .where(VisitStartTime.facility_id == ids["facility"])
        .order_by(VisitStartTime.start_time)
    ).all()
    assert times == START_TIMES


def test_seed_sample_reservations(session, ids):
    count = add_sample_reservations(
        session,
        facility_id=ids["facility"],
        resident_ids=[ids["a"], ids["b"]],
        today=date(2026, 10, 23),
    )

    assert count == 2
    assert session.scalar(select(func.count()).select_from(VisitReservation)) >= 2
