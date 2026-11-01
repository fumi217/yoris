"""面会予約の処理（003-T009・T010）のテスト（003-T006・T007 の中身を、処理の単位で確かめる）。

ふつうのテストは tests/conftest.py の session を使う（テストごとに取り消す）。
同時の予約のテストだけは、2 本のスレッドが本当に commit するので、最後に作った行を消す。
"""

import threading
from collections.abc import Iterator
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import JST
from app.models.core import Facility, Resident
from app.models.visits import VisitReservation, VisitSetting, VisitStartTime
from app.seed.visits import add_visit_settings
from app.services.visit_rules import VisitDeadlinePassed, VisitInvalidStartTime, VisitOutOfRange
from app.services.visits import (
    VisitAlreadyBookedDay,
    VisitDayFull,
    VisitError,
    VisitInvalidInput,
    VisitOverlap,
    book_visit,
    get_availability,
)

# 日本時間の 2026-10-23（金）12:00
AT = datetime(2026, 10, 23, 12, 0, tzinfo=JST).astimezone(UTC)
DAY = date(2026, 10, 28)  # 予約する日（水）


def _family(resident_id: int) -> CurrentUser:
    return CurrentUser(
        user_id=resident_id,
        kind="family",
        role=None,
        staff_id=None,
        resident_id=resident_id,
        language="ja",
        display_name="x",
    )


@pytest.fixture
def families(session: Session) -> dict[str, CurrentUser]:
    """架空の施設（1 日 2 組・開始時刻 8 つ）と、入居者 3 人の家族を作る。"""
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    add_visit_settings(session, facility_id=facility.id)
    residents = [
        Resident(
            facility_id=facility.id,
            name=f"架空 {n}",
            name_kana="かくう",
            name_romaji="Kaku",
            room=f"20{n}",
        )
        for n in (1, 2, 3)
    ]
    session.add_all(residents)
    session.flush()
    return {name: _family(r.id) for name, r in zip(("a", "b", "c"), residents, strict=True)}


def _book(session, user, start, day=DAY, party_size=1):
    return book_visit(session, user, day, start, party_size, at=AT)


# --- 予約（003-T009） ---


def test_booking_is_confirmed(session, families):
    reservation = _book(session, families["a"], time(10, 30), party_size=3)

    assert reservation.status == "booked"
    assert reservation.resident_id == families["a"].resident_id
    assert reservation.ends_at - reservation.starts_at == (
        datetime(2026, 1, 1, 12, 0) - datetime(2026, 1, 1, 10, 30)
    )


def test_overlap_is_rejected(session, families):
    _book(session, families["a"], time(10, 30))

    # 10:00〜11:30 は 10:30〜12:00 と重なる
    with pytest.raises(VisitOverlap):
        _book(session, families["b"], time(10, 0))


def test_same_family_twice_a_day_is_rejected(session, families):
    _book(session, families["a"], time(10, 0))

    with pytest.raises(VisitAlreadyBookedDay):
        _book(session, families["a"], time(14, 0))


def test_third_group_of_the_day_is_rejected(session, families):
    _book(session, families["a"], time(10, 0))
    _book(session, families["b"], time(13, 0))

    with pytest.raises(VisitDayFull):
        _book(session, families["c"], time(15, 0))


@pytest.mark.parametrize(
    ("day", "error"),
    [
        (date(2026, 10, 23), VisitOutOfRange),  # 今日
        (date(2026, 11, 21), VisitOutOfRange),  # 4 週間より先
    ],
)
def test_out_of_range_is_rejected(session, families, day, error):
    with pytest.raises(error):
        _book(session, families["a"], time(10, 0), day=day)


def test_tomorrow_after_17_is_rejected(session, families):
    after_17 = datetime(2026, 10, 23, 17, 0, tzinfo=JST)

    with pytest.raises(VisitDeadlinePassed):
        book_visit(session, families["a"], date(2026, 10, 24), time(10, 0), 1, at=after_17)


def test_start_time_must_be_a_candidate(session, families):
    with pytest.raises(VisitInvalidStartTime):
        _book(session, families["a"], time(11, 0))


def test_party_size_must_be_positive(session, families):
    with pytest.raises(VisitInvalidInput):
        _book(session, families["a"], time(10, 0), party_size=0)


def test_inactive_start_time_cannot_be_booked(session, families):
    facility_id = session.get(Resident, families["a"].resident_id).facility_id
    session.query(VisitStartTime).filter_by(facility_id=facility_id, start_time=time(10, 0)).update(
        {"active": False}
    )
    session.flush()

    with pytest.raises(VisitInvalidStartTime):
        _book(session, families["a"], time(10, 0))


def test_daily_limit_follows_the_setting(session, families):
    facility_id = session.get(Resident, families["a"].resident_id).facility_id
    session.get(VisitSetting, facility_id).daily_limit = 1
    session.flush()
    _book(session, families["a"], time(10, 0))

    with pytest.raises(VisitDayFull):
        _book(session, families["b"], time(15, 0))


# --- 選べるかどうか（003-T010） ---


def _day(session, user, day=DAY):
    [availability] = get_availability(session, user, day, day, at=AT)
    return availability


def test_availability_marks_overlaps_and_mine(session, families):
    _book(session, families["a"], time(10, 30))

    other = _day(session, families["b"])
    selectable = {s.start_time: s.selectable for s in other.start_times}
    # 10:30 の予約と重なる 10:00・10:30 は選べない。13:00 は選べる
    assert selectable[time(10, 0)] is False
    assert selectable[time(10, 30)] is False
    assert selectable[time(13, 0)] is True
    assert other.mine is False

    # 予約した家族には mine: true で、その日はどれも選べない（1 家族 1 日 1 回）
    mine = _day(session, families["a"])
    assert mine.mine is True
    assert not any(s.selectable for s in mine.start_times)


def test_full_day_has_nothing_selectable(session, families):
    _book(session, families["a"], time(10, 0))
    _book(session, families["b"], time(13, 0))

    assert not any(s.selectable for s in _day(session, families["c"]).start_times)


def test_out_of_range_days_are_not_selectable(session, families):
    days = get_availability(session, families["a"], date(2026, 10, 23), date(2026, 10, 24), at=AT)

    # 今日は選べない。明日は 17 時前なので選べる
    assert [any(s.selectable for s in d.start_times) for d in days] == [False, True]


def test_availability_range_is_limited(session, families):
    with pytest.raises(VisitInvalidInput):
        get_availability(session, families["a"], date(2026, 10, 24), date(2026, 11, 30), at=AT)


# --- 同時の予約（R-01。2 本のスレッドが本当に commit する） ---


@pytest.fixture
def committed_families(engine) -> Iterator[tuple[object, dict[str, CurrentUser], int]]:
    # conftest の engine（テストの取り消しの外）で、本当に commit する
    with Session(engine) as db:
        facility = Facility(name="テスト施設（同時の予約）")
        db.add(facility)
        db.flush()
        add_visit_settings(db, facility_id=facility.id)
        residents = [
            Resident(
                facility_id=facility.id,
                name=f"架空 {n}",
                name_kana="かくう",
                name_romaji="Kaku",
                room="300",
            )
            for n in (1, 2, 3)
        ]
        db.add_all(residents)
        db.commit()
        facility_id = facility.id
        users = {name: _family(r.id) for name, r in zip(("a", "b", "c"), residents, strict=True)}
    try:
        yield engine, users, facility_id
    finally:
        with Session(engine) as db:
            db.execute(delete(VisitReservation).where(VisitReservation.facility_id == facility_id))
            db.execute(delete(VisitStartTime).where(VisitStartTime.facility_id == facility_id))
            db.execute(delete(VisitSetting).where(VisitSetting.facility_id == facility_id))
            db.execute(delete(Resident).where(Resident.facility_id == facility_id))
            db.execute(delete(Facility).where(Facility.id == facility_id))
            db.commit()


def _book_at_once(engine, requests: list[tuple[CurrentUser, time]]) -> list[object]:
    """requests をスレッドでほぼ同時に予約し、それぞれの結果（予約の id か、エラー）を返す。"""
    barrier = threading.Barrier(len(requests))
    results: list[object] = [None] * len(requests)

    def run(index: int, user: CurrentUser, start: time) -> None:
        with Session(engine) as db:
            barrier.wait()
            try:
                reservation = book_visit(db, user, DAY, start, 1, at=AT)
                db.commit()
                results[index] = reservation.id
            except VisitError as error:
                db.rollback()
                results[index] = error

    threads = [
        threading.Thread(target=run, args=(n, user, start))
        for n, (user, start) in enumerate(requests)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_simultaneous_overlapping_bookings_confirm_only_one(committed_families):
    engine, users, _ = committed_families

    # 13:00 と 13:30 は重なる
    results = _book_at_once(engine, [(users["a"], time(13, 0)), (users["b"], time(13, 30))])

    assert sum(isinstance(r, int) for r in results) == 1
    assert [type(r) for r in results if not isinstance(r, int)] == [VisitOverlap]


def test_simultaneous_bookings_on_a_nearly_full_day_confirm_only_one(committed_families):
    engine, users, _ = committed_families
    [first] = _book_at_once(engine, [(users["a"], time(10, 0))])
    assert isinstance(first, int)

    # 13:00 と 15:00 は重ならないが、どちらも入ると 1 日 3 組になる
    results = _book_at_once(engine, [(users["b"], time(13, 0)), (users["c"], time(15, 0))])

    assert sum(isinstance(r, int) for r in results) == 1
    assert [type(r) for r in results if not isinstance(r, int)] == [VisitDayFull]
