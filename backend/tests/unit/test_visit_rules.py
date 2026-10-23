"""面会予約の判定（003-T005）。DB を使わないので CI でも動く。

時刻は、関数に at を渡して固定する（app.clock の now を差し替える形でも同じ）。
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.clock import JST
from app.services.visit_rules import (
    VisitDeadlinePassed,
    VisitInvalidStartTime,
    VisitOutOfRange,
    check_bookable_date,
    check_family_cancel,
    check_start_time,
    overlaps,
    visit_range,
)

TODAY = date(2026, 10, 23)
TOMORROW = TODAY + timedelta(days=1)
CANDIDATES = [
    time(h, m)
    for h, m in [(10, 0), (10, 30), (13, 0), (13, 30), (14, 0), (14, 30), (15, 0), (15, 30)]
]


def jst(hour: int, minute: int = 0, day: date = TODAY) -> datetime:
    """日本時間の日時（関数には UTC に直して渡す）。"""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=JST).astimezone(UTC)


# --- 予約できる日（明日 ≦ 日付 ≦ 今日＋28 日。FR-008） ---


@pytest.mark.parametrize("visit_date", [TOMORROW, TODAY + timedelta(days=28)])
def test_bookable_dates(visit_date):
    check_bookable_date(visit_date, jst(10))


@pytest.mark.parametrize(
    "visit_date", [TODAY - timedelta(days=1), TODAY, TODAY + timedelta(days=29)]
)
def test_out_of_range_dates(visit_date):
    # 過去・今日・4 週間より先は 422 visit_out_of_range
    with pytest.raises(VisitOutOfRange):
        check_bookable_date(visit_date, jst(10))


# --- 明日の予約は今日の 17:00 より前だけ（FR-007） ---


def test_tomorrow_can_be_booked_until_just_before_17():
    check_bookable_date(TOMORROW, jst(16, 59))


def test_tomorrow_cannot_be_booked_at_or_after_17():
    with pytest.raises(VisitDeadlinePassed):
        check_bookable_date(TOMORROW, jst(17, 0))


def test_day_after_tomorrow_can_be_booked_after_17():
    check_bookable_date(TODAY + timedelta(days=2), jst(20))


def test_deadline_uses_japan_time():
    # UTC では 10/23 7:59 でも、日本時間では 10/23 16:59 なので、まだ予約できる
    check_bookable_date(TOMORROW, datetime(2026, 10, 23, 7, 59, tzinfo=UTC))
    with pytest.raises(VisitDeadlinePassed):
        check_bookable_date(TOMORROW, datetime(2026, 10, 23, 8, 0, tzinfo=UTC))


def test_family_cancel_deadline():
    check_family_cancel(TOMORROW, jst(16, 59))
    with pytest.raises(VisitDeadlinePassed):
        check_family_cancel(TOMORROW, jst(17, 0))


# --- 面会の時間の範囲と重なり（FR-003・FR-004） ---


def test_visit_lasts_one_hour_thirty_minutes():
    starts_at, ends_at = visit_range(TOMORROW, time(10, 30))

    assert starts_at == datetime(2026, 10, 24, 10, 30, tzinfo=JST)
    assert ends_at - starts_at == timedelta(hours=1, minutes=30)


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (time(10, 0), True),  # 10:00〜11:30 は 10:30〜12:00 と重なる
        (time(10, 30), True),  # 同じ時刻
        (time(11, 30), True),  # 候補にはないが、11:30〜13:00 も重なる
        (time(13, 0), False),  # 13:00〜14:30 は重ならない
        (time(9, 0), False),  # 9:00〜10:30 は、終わりと始まりがちょうど同じなので重ならない
    ],
)
def test_overlap_with_1030(other, expected):
    assert overlaps(TOMORROW, time(10, 30), other) is expected
    assert overlaps(TOMORROW, other, time(10, 30)) is expected


# --- 開始時刻が候補にないとき ---


def test_start_time_in_candidates():
    check_start_time(time(13, 0), CANDIDATES)


@pytest.mark.parametrize("start_time", [time(11, 0), time(13, 15), time(16, 0)])
def test_start_time_not_in_candidates(start_time):
    with pytest.raises(VisitInvalidStartTime):
        check_start_time(start_time, CANDIDATES)
