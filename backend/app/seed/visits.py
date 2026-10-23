"""面会予約の初期データ（spec 003 の 003-T004）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。施設・入居者を入れたあとに呼ぶこと。
施設にすでに設定があれば足さない（何度流しても同じになるように）。
デモ用の予約は、架空の家族（入居者）で、来週の平日に入れる。
"""

from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.visits import VisitReservation, VisitSetting, VisitStartTime
from app.services.visit_rules import visit_range

# 開始時刻の候補の初期値
# （昼ごはん 12:00〜13:00 にかからず、17:00 までに終わる時刻。spec 003 の Clarifications）
START_TIMES = [
    time(10, 0),
    time(10, 30),
    time(13, 0),
    time(13, 30),
    time(14, 0),
    time(14, 30),
    time(15, 0),
    time(15, 30),
]
DAILY_LIMIT = 2


def add_visit_settings(session: Session, *, facility_id: int) -> None:
    """面会の設定（1 日 2 組）と開始時刻の候補 8 つを足す。commit は呼んだ側が行う。"""
    if session.get(VisitSetting, facility_id) is None:
        session.add(VisitSetting(facility_id=facility_id, daily_limit=DAILY_LIMIT))
    existing = set(
        session.scalars(
            select(VisitStartTime.start_time).where(VisitStartTime.facility_id == facility_id)
        )
    )
    for start_time in START_TIMES:
        if start_time not in existing:
            session.add(VisitStartTime(facility_id=facility_id, start_time=start_time, active=True))
    session.flush()


def add_sample_reservations(
    session: Session, *, facility_id: int, resident_ids: list[int], today: date
) -> int:
    """来週の平日（月曜・水曜）に、デモ用の予約を 1 件ずつ足す。足した件数を返す。"""
    next_monday = today + timedelta(days=7 - today.weekday())
    samples = [
        (next_monday, time(10, 30), 2),
        (next_monday + timedelta(days=2), time(14, 0), 1),
    ]
    count = 0
    for resident_id, (visit_date, start_time, party_size) in zip(
        resident_ids, samples, strict=False
    ):
        starts_at, ends_at = visit_range(visit_date, start_time)
        session.add(
            VisitReservation(
                facility_id=facility_id,
                resident_id=resident_id,
                visit_date=visit_date,
                start_time=start_time,
                starts_at=starts_at,
                ends_at=ends_at,
                party_size=party_size,
            )
        )
        count += 1
    session.flush()
    return count
