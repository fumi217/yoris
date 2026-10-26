"""面会予約の処理（spec 003 の 003-T009・T010。research.md R-01・R-03）。

- 予約を作る道は book_visit の 1 つだけ。ほかの場所で visit_reservations に行を足さない
- 入居者は、ログイン中の家族の CurrentUser.resident_id から決める（送られた値は使わない。R-05）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）。
  順番待ち（pg_advisory_xact_lock）は、その commit で外れる
- 休みの日（visit_closed_days）は作り込み（003-T019 など）で足す。今は休みの日はない扱い
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.models.core import Resident
from app.models.visits import VisitReservation, VisitSetting, VisitStartTime
from app.services.visit_rules import (
    VisitRuleError,
    check_bookable_date,
    check_start_time,
    overlaps,
    visit_range,
)

# 順番待ちのキーの 1 つ目
# （ほかの用途の advisory lock とぶつからないように、spec 003 の番号から決めた）
VISIT_LOCK_NAMESPACE = 3003
# 1 日に受け付ける組数の設定がないとき（初期値。FR-009）
DEFAULT_DAILY_LIMIT = 2
# 選べるかどうかを、一度に何日分まで返すか（画面は 1 週間ずつ。4 週間先まで予約できる）
MAX_AVAILABILITY_DAYS = 31


class VisitError(VisitRuleError):
    """予約の決まりの外。code は spec 003 contracts のエラーのコード。"""


class VisitDayFull(VisitError):
    code = "visit_day_full"


class VisitAlreadyBookedDay(VisitError):
    code = "visit_already_booked_day"


class VisitOverlap(VisitError):
    code = "visit_overlap"


class VisitInvalidInput(VisitError):
    """人数が 1 未満・期間の指定が逆、など（422）。"""

    code = "validation_error"


# DB の決まりに引っかかったときに、どのエラーにするか（R-01 の最後の守り）
_CONSTRAINT_ERRORS: dict[str, type[VisitError]] = {
    "uq_visit_reservations_resident_day": VisitAlreadyBookedDay,
    "ex_visit_reservations_no_overlap": VisitOverlap,
}


def _resident_id(current_user: CurrentUser) -> int:
    if current_user.kind != "family" or current_user.resident_id is None:
        # 家族の API（require_family）からしか呼ばない
        raise VisitInvalidInput("家族のログインではない")
    return current_user.resident_id


def _facility_id(session: Session, resident_id: int) -> int:
    return session.scalars(select(Resident.facility_id).where(Resident.id == resident_id)).one()


def _active_start_times(session: Session, facility_id: int) -> list[time]:
    return list(
        session.scalars(
            select(VisitStartTime.start_time)
            .where(VisitStartTime.facility_id == facility_id, VisitStartTime.active.is_(True))
            .order_by(VisitStartTime.start_time)
        )
    )


def _daily_limit(session: Session, facility_id: int) -> int:
    setting = session.get(VisitSetting, facility_id)
    return setting.daily_limit if setting is not None else DEFAULT_DAILY_LIMIT


def _booked(session: Session, facility_id: int, date_from: date, date_to: date):
    return list(
        session.scalars(
            select(VisitReservation).where(
                VisitReservation.facility_id == facility_id,
                VisitReservation.visit_date >= date_from,
                VisitReservation.visit_date <= date_to,
                VisitReservation.status == "booked",
            )
        )
    )


def book_visit(
    session: Session,
    current_user: CurrentUser,
    visit_date: date,
    start_time: time,
    party_size: int,
    at: datetime | None = None,
) -> VisitReservation:
    """面会を予約する（R-01 の順）。at はテスト用（タイムゾーン付きの日時）。

    1. その日だけの順番待ち 2. 1 日の組数 3. 同じ家族のその日の予約 4. 時間の重なり 5. 追加。
    """
    resident_id = _resident_id(current_user)
    if party_size < 1:
        raise VisitInvalidInput(f"party_size: {party_size}")
    check_bookable_date(visit_date, at)
    facility_id = _facility_id(session, resident_id)
    check_start_time(start_time, _active_start_times(session, facility_id))

    # 1. 同じ日の予約だけを順番待ちにする（ほかの日の予約は待たない）。commit で外れる
    session.execute(
        select(func.pg_advisory_xact_lock(VISIT_LOCK_NAMESPACE, visit_date.toordinal()))
    )

    booked = _booked(session, facility_id, visit_date, visit_date)
    # 2. 1 日に受け付ける組数
    if len(booked) >= _daily_limit(session, facility_id):
        raise VisitDayFull(f"visit_date: {visit_date}")
    # 3. 同じ家族（入居者）のその日の予約
    if any(reservation.resident_id == resident_id for reservation in booked):
        raise VisitAlreadyBookedDay(f"visit_date: {visit_date}")
    # 4. 時間の重なり
    if any(overlaps(visit_date, reservation.start_time, start_time) for reservation in booked):
        raise VisitOverlap(f"start_time: {start_time}")

    # 5. 追加する
    starts_at, ends_at = visit_range(visit_date, start_time)
    reservation = VisitReservation(
        facility_id=facility_id,
        resident_id=resident_id,
        visit_date=visit_date,
        start_time=start_time,
        starts_at=starts_at,
        ends_at=ends_at,
        party_size=party_size,
    )
    try:
        with session.begin_nested():
            session.add(reservation)
            session.flush()
    except IntegrityError as error:
        # 処理にバグがあっても、DB の決まりが受け付けない（R-01）。決まりの名前でエラーを決める
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        raise _CONSTRAINT_ERRORS.get(constraint, VisitOverlap)(str(constraint)) from error
    return reservation


# --- 選べるかどうか（003-T010） ---


@dataclass(frozen=True)
class StartTimeAvailability:
    start_time: time
    selectable: bool


@dataclass(frozen=True)
class DayAvailability:
    date: date
    closed: bool
    mine: bool  # その家族が、その日にすでに予約している
    start_times: list[StartTimeAvailability]


def get_availability(
    session: Session,
    current_user: CurrentUser,
    date_from: date,
    date_to: date,
    at: datetime | None = None,
) -> list[DayAvailability]:
    """日付ごとに、開始時刻の候補と選べるかどうかを返す（R-03）。

    選べない理由や、ほかの家族の情報（名前・人数・時刻ごとの理由）は返さない。
    最終の判定は book_visit で行う（画面を開いてから予約するまでに、状況が変わることがあるため）。
    """
    resident_id = _resident_id(current_user)
    if date_to < date_from or (date_to - date_from).days >= MAX_AVAILABILITY_DAYS:
        raise VisitInvalidInput(f"range: {date_from}..{date_to}")
    facility_id = _facility_id(session, resident_id)
    candidates = _active_start_times(session, facility_id)
    limit = _daily_limit(session, facility_id)
    booked_by_day: dict[date, list[VisitReservation]] = {}
    for reservation in _booked(session, facility_id, date_from, date_to):
        booked_by_day.setdefault(reservation.visit_date, []).append(reservation)

    days = []
    day = date_from
    while day <= date_to:
        booked = booked_by_day.get(day, [])
        mine = any(reservation.resident_id == resident_id for reservation in booked)
        try:
            check_bookable_date(day, at)
            day_open = not mine and len(booked) < limit
        except VisitRuleError:
            day_open = False
        start_times = [
            StartTimeAvailability(
                start_time=candidate,
                selectable=day_open
                and not any(overlaps(day, r.start_time, candidate) for r in booked),
            )
            for candidate in candidates
        ]
        days.append(DayAvailability(date=day, closed=False, mine=mine, start_times=start_times))
        day += timedelta(days=1)
    return days
