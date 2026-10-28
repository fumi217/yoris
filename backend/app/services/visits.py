"""面会予約の処理（spec 003 の 003-T009・T010。research.md R-01・R-03）。

- 予約を作る道は book_visit の 1 つだけ。ほかの場所で visit_reservations に行を足さない
- 入居者は、ログイン中の家族の CurrentUser.resident_id から決める（送られた値は使わない。R-05）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）。
  順番待ち（pg_advisory_xact_lock）は、その commit で外れる
- 休みの日（visit_closed_days）は予約できず、空きも選べない（003-T021・FR-010）。
  休みにする処理（close_day）も同じその日だけの順番待ちを取るので、
  休みにした瞬間に予約が入ることはない
- 施設の設定（開始時刻の候補・1 日の組数・休みの日）と、職員の取り消し・予約の一覧は 003-T022〜T024
- 家族へのお知らせ（さとこの create_visit_notice。003-T030）は、
  予約の確定（book_visit_with_notice）と職員の取り消し（cancel_by_staff。休みにするときも）で、
  同じトランザクションの中で作る（R-07）。
  家族が自分で取り消したときは作らない
- 家族の自分の予約の一覧（list_my_reservations）と取り消し（cancel_by_family）は 003-T016。
  ほかの家族の予約は、ないものと同じ 404 にする（存在するかも知らせない。FR-015・SC-004）。
  家族が自分で取り消したときは、お知らせを作らない（research.md R-07）
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import now_jst
from app.models.core import FamilyAccount, Resident
from app.models.notifications import Notification
from app.models.visits import VisitClosedDay, VisitReservation, VisitSetting, VisitStartTime
from app.services.notifications import create_visit_notice
from app.services.visit_rules import (
    VisitRuleError,
    check_bookable_date,
    check_family_cancel,
    check_start_time,
    is_before_deadline,
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


class VisitClosedDayError(VisitError):
    """休みの日（409）。"""

    code = "visit_closed_day"


class VisitDayHasReservations(VisitError):
    """予約が入っている日を、取り消すと決めずに休みにしようとした（409。件数を返す。R-08）。"""

    code = "visit_day_has_reservations"

    def __init__(self, count: int) -> None:
        super().__init__(f"reservations: {count}")
        self.count = count


class VisitNotFound(VisitError):
    """自分の入居者の予約でない・もう取り消してある（404。存在するかも知らせない）。"""

    code = "not_found"


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


def _wait_for_day(session: Session, visit_date: date) -> None:
    """その日の予約・休みにする処理だけを順番待ちにする（ほかの日は待たない）。commit で外れる。"""
    session.execute(
        select(func.pg_advisory_xact_lock(VISIT_LOCK_NAMESPACE, visit_date.toordinal()))
    )


def _closed_dates(session: Session, facility_id: int, date_from: date, date_to: date) -> set[date]:
    return set(
        session.scalars(
            select(VisitClosedDay.closed_date).where(
                VisitClosedDay.facility_id == facility_id,
                VisitClosedDay.closed_date >= date_from,
                VisitClosedDay.closed_date <= date_to,
            )
        )
    )


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
    _wait_for_day(session, visit_date)
    # 休みの日（順番待ちの中で確かめるので、休みにした瞬間の予約も通さない）
    if _closed_dates(session, facility_id, visit_date, visit_date):
        raise VisitClosedDayError(f"visit_date: {visit_date}")

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


def book_visit_with_notice(
    session: Session,
    current_user: CurrentUser,
    visit_date: date,
    start_time: time,
    party_size: int,
    at: datetime | None = None,
) -> tuple[VisitReservation, int]:
    """面会を予約し、家族へのお知らせ（予約が確定）とメールの送る予定も作る（003-T032）。

    予約と email_outbox の id を返す。commit は呼んだ側が行い、そのあとに send_email_now で送る。
    予約できなければ book_visit がエラーにするので、お知らせはできない。
    """
    reservation = book_visit(session, current_user, visit_date, start_time, party_size, at)
    return reservation, create_visit_notice(session, reservation.id, "visit_confirmed")


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
    closed = _closed_dates(session, facility_id, date_from, date_to)
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
            day_open = not mine and len(booked) < limit and day not in closed
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
        days.append(
            DayAvailability(date=day, closed=day in closed, mine=mine, start_times=start_times)
        )
        day += timedelta(days=1)
    return days


@dataclass(frozen=True)
class MyReservation:
    id: int
    visit_date: date
    start_time: time
    party_size: int
    status: str  # booked / cancelled_by_family / cancelled_by_staff
    # 施設が取り消したときだけ入る理由（文字としてだけ出す。FR-016）
    cancel_reason: str | None
    # 今アプリで取り消せるか（予約済みで、前日 17 時より前）。過ぎていれば画面で電話を案内する
    can_cancel: bool


def list_my_reservations(
    session: Session, current_user: CurrentUser, at: datetime | None = None
) -> list[MyReservation]:
    """自分の入居者の、これからの予約（今日を含む）を、日時の順に返す（003-T017・FR-006）。

    取り消した予約も、状態がわかるように返す（施設が取り消したときは理由も）。
    """
    resident_id = _resident_id(current_user)
    rows = session.scalars(
        select(VisitReservation)
        .where(
            VisitReservation.resident_id == resident_id,
            VisitReservation.visit_date >= now_jst(at).date(),
        )
        .order_by(VisitReservation.visit_date, VisitReservation.start_time, VisitReservation.id)
    )
    return [
        MyReservation(
            id=row.id,
            visit_date=row.visit_date,
            start_time=row.start_time,
            party_size=row.party_size,
            status=row.status,
            cancel_reason=row.cancel_reason if row.status == "cancelled_by_staff" else None,
            can_cancel=row.status == "booked" and is_before_deadline(row.visit_date, at),
        )
        for row in rows
    ]


# 面会のお知らせの種類（予約の確定・施設からの取り消し・前日の知らせ。R-07）
VISIT_NOTICE_KINDS = ("visit_confirmed", "visit_cancelled", "visit_reminder")


def mark_visit_notices_read(session: Session, current_user: CurrentUser) -> int:
    """自分の家族アカウントの、まだ読んでいない面会のお知らせを、まとめて読んだことにする（#272）。

    面会の画面を開いたときに呼ぶ。面会のお知らせの中身は、どれも「これからの予約」に出ているため。
    ほかの家族と、面会以外のお知らせには触らない。読んだことにした件数を返す。commit しない。
    """
    resident_id = _resident_id(current_user)
    family_account_id = (
        select(FamilyAccount.id).where(FamilyAccount.resident_id == resident_id).scalar_subquery()
    )
    result = session.execute(
        update(Notification)
        .where(
            Notification.family_account_id == family_account_id,
            Notification.kind.in_(VISIT_NOTICE_KINDS),
            Notification.read_at.is_(None),
        )
        .values(read_at=func.now())
    )
    return result.rowcount


def cancel_by_family(
    session: Session, current_user: CurrentUser, reservation_id: int, at: datetime | None = None
) -> VisitReservation:
    """家族が自分の予約を取り消す（003-T016・FR-007）。取り消すと、その時間がまた選べる。

    自分の入居者の予約済み（booked）でなければ 404。前日 17 時を過ぎていたら
    visit_deadline_passed。お知らせは作らない（R-07）。commit しない。
    """
    resident_id = _resident_id(current_user)
    reservation = session.scalars(
        select(VisitReservation)
        .where(
            VisitReservation.id == reservation_id,
            VisitReservation.resident_id == resident_id,
            VisitReservation.status == "booked",
        )
        .with_for_update()
    ).one_or_none()
    if reservation is None:
        raise VisitNotFound(f"reservation_id: {reservation_id}")
    check_family_cancel(reservation.visit_date, at)
    reservation.status = "cancelled_by_family"
    reservation.cancelled_at = func.now()
    session.flush()
    return reservation


# --- 施設の設定・休みの日・職員の取り消し・予約の一覧（003-T021〜T024。User Story 3） ---

# 面会の時間帯（10〜17 時。spec 003 の前提）と、開始時刻の刻み（30 分。Clarifications）
VISIT_OPEN = time(10, 0)
VISIT_CLOSE = time(17, 0)
START_STEP_MINUTES = 30
VISIT_MINUTES = 90
# 職員の取り消しの理由の上限（家族の画面に文字として出す。FR-012・FR-016）
CANCEL_REASON_MAX = 200


def get_visit_settings(session: Session, facility_id: int) -> tuple[int, list[time]]:
    """1 日に受け付ける組数と、今の開始時刻の候補（早い順）。"""
    return _daily_limit(session, facility_id), _active_start_times(session, facility_id)


def _check_candidate(start: time) -> None:
    """開始時刻の候補の決まり（FR-009）。

    30 分刻み、10:00 から、終わり（＋1 時間 30 分）が 17:00 まで。
    """
    minutes = start.hour * 60 + start.minute
    open_minutes = VISIT_OPEN.hour * 60
    close_minutes = VISIT_CLOSE.hour * 60
    if start.second or minutes % START_STEP_MINUTES:
        raise VisitInvalidInput(f"start_time: {start}")
    if minutes < open_minutes or minutes + VISIT_MINUTES > close_minutes:
        raise VisitInvalidInput(f"start_time: {start}")


def update_visit_settings(
    session: Session, facility_id: int, staff_id: int, daily_limit: int, start_times: list[time]
) -> None:
    """組数と開始時刻の候補を変える（003-T022）。決まりの外があれば何も変えない（422）。

    候補から外した時刻は active を false にするだけで、
    すでに入っている予約はそのまま残す（FR-009）。
    commit しない。
    """
    if daily_limit < 1 or not start_times:
        raise VisitInvalidInput(f"daily_limit: {daily_limit}, start_times: {len(start_times)}")
    for start in start_times:
        _check_candidate(start)
    wanted = set(start_times)

    setting = session.get(VisitSetting, facility_id)
    if setting is None:
        setting = VisitSetting(facility_id=facility_id)
        session.add(setting)
    setting.daily_limit = daily_limit
    setting.updated_by = staff_id
    setting.updated_at = func.now()

    existing = {
        row.start_time: row
        for row in session.scalars(
            select(VisitStartTime).where(VisitStartTime.facility_id == facility_id)
        )
    }
    for start, row in existing.items():
        row.active = start in wanted
    for start in wanted - set(existing):
        session.add(VisitStartTime(facility_id=facility_id, start_time=start, active=True))
    session.flush()


def list_closed_days(
    session: Session, facility_id: int, date_from: date, date_to: date
) -> list[VisitClosedDay]:
    """休みの日の一覧（日付の順）。"""
    if date_to < date_from:
        raise VisitInvalidInput(f"range: {date_from}..{date_to}")
    return list(
        session.scalars(
            select(VisitClosedDay)
            .where(
                VisitClosedDay.facility_id == facility_id,
                VisitClosedDay.closed_date >= date_from,
                VisitClosedDay.closed_date <= date_to,
            )
            .order_by(VisitClosedDay.closed_date)
        )
    )


def _clean_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip()
    if not cleaned or len(cleaned) > CANCEL_REASON_MAX:
        raise VisitInvalidInput("reason")
    return cleaned


def cancel_by_staff(
    session: Session,
    facility_id: int,
    staff_id: int,
    reservation_id: int,
    reason: str | None,
    at: datetime | None = None,
) -> tuple[VisitReservation, int]:
    """職員が予約を取り消す（理由は必須。締め切りはない。FR-012・003-T031）。

    予約済みでなければ 404。

    同じトランザクションで、家族へのお知らせ（施設が取り消し）とメールの送る予定を作り、
    予約と email_outbox の id を返す（R-07）。メールに理由は入れない（FR-014）。commit しない。
    """
    cleaned = _clean_reason(reason)
    reservation = session.scalars(
        select(VisitReservation)
        .where(
            VisitReservation.id == reservation_id,
            VisitReservation.facility_id == facility_id,
            VisitReservation.status == "booked",
        )
        .with_for_update()
    ).one_or_none()
    if reservation is None:
        raise VisitNotFound(f"reservation_id: {reservation_id}")
    reservation.status = "cancelled_by_staff"
    reservation.cancel_reason = cleaned
    reservation.cancelled_by_staff_id = staff_id
    reservation.cancelled_at = at or func.now()
    session.flush()
    return reservation, create_visit_notice(session, reservation.id, "visit_cancelled")


def close_day(
    session: Session,
    facility_id: int,
    staff_id: int,
    closed_date: date,
    *,
    confirm_cancel: bool = False,
    reason: str | None = None,
    at: datetime | None = None,
) -> tuple[VisitClosedDay, list[tuple[VisitReservation, int]]]:
    """その日を休みにする（003-T023・FR-010・R-08）。

    休みの日と、取り消した予約（と email_outbox の id）を返す。

    その日に予約済みがあれば、confirm_cancel を付けないと 409（件数つき）。
    付けたら、理由を必須にして、その日の予約をすべて職員の取り消しにしてから休みにする
    （1 つのトランザクション）。
    今日より前の日は 422。もう休みの日なら、そのまま返す。commit しない。
    """
    if closed_date < now_jst(at).date():
        raise VisitInvalidInput(f"closed_date: {closed_date}")
    # 予約（book_visit）と同じ、その日だけの順番待ち
    _wait_for_day(session, closed_date)
    existing = session.scalars(
        select(VisitClosedDay).where(
            VisitClosedDay.facility_id == facility_id, VisitClosedDay.closed_date == closed_date
        )
    ).one_or_none()
    if existing is not None:
        return existing, []

    booked = _booked(session, facility_id, closed_date, closed_date)
    if booked and not confirm_cancel:
        raise VisitDayHasReservations(len(booked))
    cancelled = [
        cancel_by_staff(session, facility_id, staff_id, reservation.id, reason, at)
        for reservation in booked
    ]
    closed_day = VisitClosedDay(
        facility_id=facility_id, closed_date=closed_date, created_by=staff_id
    )
    session.add(closed_day)
    session.flush()
    return closed_day, cancelled


def open_day(session: Session, facility_id: int, closed_day_id: int) -> None:
    """休みを取り消す（003-T023）。取り消した予約は戻さない。ない休みの日は 404。commit しない。"""
    closed_day = session.scalars(
        select(VisitClosedDay).where(
            VisitClosedDay.id == closed_day_id, VisitClosedDay.facility_id == facility_id
        )
    ).one_or_none()
    if closed_day is None:
        raise VisitNotFound(f"closed_day_id: {closed_day_id}")
    session.delete(closed_day)
    session.flush()


@dataclass(frozen=True)
class StaffReservation:
    id: int
    visit_date: date
    start_time: time
    resident_id: int
    resident_name: str  # 入居者の呼び名（職員向け）
    room: str
    party_size: int
    status: str
    created_at: datetime  # 予約した日時
    cancel_reason: str | None


def list_reservations(
    session: Session,
    facility_id: int,
    date_from: date,
    date_to: date,
    *,
    booked_only: bool = False,
) -> list[StaffReservation]:
    """職員向けの予約の一覧（日時の順。003-T024・FR-011）。期間は 31 日まで。"""
    if date_to < date_from or (date_to - date_from).days >= MAX_AVAILABILITY_DAYS:
        raise VisitInvalidInput(f"range: {date_from}..{date_to}")
    query = (
        select(VisitReservation, Resident.display_name, Resident.room)
        .join(Resident, Resident.id == VisitReservation.resident_id)
        .where(
            VisitReservation.facility_id == facility_id,
            VisitReservation.visit_date >= date_from,
            VisitReservation.visit_date <= date_to,
        )
        .order_by(VisitReservation.visit_date, VisitReservation.start_time, VisitReservation.id)
    )
    if booked_only:
        query = query.where(VisitReservation.status == "booked")
    return [
        StaffReservation(
            id=row.id,
            visit_date=row.visit_date,
            start_time=row.start_time,
            resident_id=row.resident_id,
            resident_name=name,
            room=room,
            party_size=row.party_size,
            status=row.status,
            created_at=row.created_at,
            cancel_reason=row.cancel_reason,
        )
        for row, name, room in session.execute(query)
    ]
