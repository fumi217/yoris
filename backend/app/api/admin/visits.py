"""面会予約の施設側の API（spec 003 の 003-T022〜T024。User Story 3。contracts の「施設」）。

- 開始時刻の候補・1 日の組数・休みの日を変えられるのは、事務員・生活相談員・施設長だけ（R-06）
- 予約の一覧を見られるのは、職員のすべて（FR-011）
- 施設は、ログイン中の職員の施設から決める（画面からは受け取らない）
- 職員の取り消し（`POST /api/admin/visits/{id}/cancel`。職員のすべて。003-T031）と、
  休みにするときの取り消しは、同じトランザクションで家族へのお知らせを作り、
  commit のあとにメールを送る（R-07）
"""

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import Staff
from app.services.mail import send_email_now
from app.services.visit_rules import VisitRuleError
from app.services.visits import (
    CANCEL_REASON_MAX,
    VisitDayHasReservations,
    cancel_by_staff,
    close_day,
    get_visit_settings,
    list_closed_days,
    list_reservations,
    open_day,
    update_visit_settings,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# 設定を変えられる役割（R-06）。予約の一覧は職員のすべて
VISIT_EDITORS = require_staff(("clerk", "counselor", "director"))
STAFF = require_staff()


def facility_of(session: Session, user: CurrentUser) -> int:
    return session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()


def app_error(error: VisitRuleError) -> AppError:
    if isinstance(error, VisitDayHasReservations):
        # 画面が「この日には予約が ◯ 件入っています」と出せるように、件数だけを返す（R-08）
        return AppError(ErrorCode(error.code), details={"count": error.count})
    return AppError(ErrorCode(error.code))


# --- 開始時刻の候補と、1 日の組数（003-T022・FR-009） ---


class VisitSettingsOut(BaseModel):
    daily_limit: int
    start_times: list[time]  # 今の候補（早い順）


class VisitSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_limit: int = Field(ge=1)
    # 30 分刻み、10:00 から、終わり（＋1 時間 30 分）が 17:00 まで。ほかは 422
    start_times: list[time] = Field(min_length=1)


@router.get("/visit-settings")
def get_settings(
    user: Annotated[CurrentUser, Depends(VISIT_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> VisitSettingsOut:
    daily_limit, start_times = get_visit_settings(session, facility_of(session, user))
    return VisitSettingsOut(daily_limit=daily_limit, start_times=start_times)


@router.put("/visit-settings")
def put_settings(
    body: VisitSettingsIn,
    user: Annotated[CurrentUser, Depends(VISIT_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> VisitSettingsOut:
    """変える。候補から外した時刻の、すでに入っている予約はそのまま残す（FR-009）。"""
    facility_id = facility_of(session, user)
    try:
        update_visit_settings(
            session, facility_id, user.staff_id, body.daily_limit, body.start_times
        )
    except VisitRuleError as error:
        raise app_error(error) from error
    session.commit()
    daily_limit, start_times = get_visit_settings(session, facility_id)
    return VisitSettingsOut(daily_limit=daily_limit, start_times=start_times)


# --- 休みの日（003-T023・FR-010・R-08） ---


class ClosedDayOut(BaseModel):
    id: int
    closed_date: date


class ClosedDayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    # 予約が入っている日を休みにするときだけ。true なら reason が必須（その日の予約を取り消す）
    confirm_cancel: StrictBool = False
    reason: str | None = Field(default=None, max_length=CANCEL_REASON_MAX)


class ClosedDayResult(ClosedDayOut):
    # 休みにするために取り消した予約の数（その家族には、施設が取り消したお知らせが届く）
    cancelled: int


@router.get("/visit-closed-days")
def get_closed_days(
    user: Annotated[CurrentUser, Depends(VISIT_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> list[ClosedDayOut]:
    try:
        rows = list_closed_days(session, facility_of(session, user), date_from, date_to)
    except VisitRuleError as error:
        raise app_error(error) from error
    return [ClosedDayOut(id=row.id, closed_date=row.closed_date) for row in rows]


@router.post("/visit-closed-days", status_code=201)
def post_closed_day(
    body: ClosedDayIn,
    user: Annotated[CurrentUser, Depends(VISIT_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
    background_tasks: BackgroundTasks,
) -> ClosedDayResult:
    """休みにする。予約があれば 409 visit_day_has_reservations（details.count に件数）。"""
    try:
        closed_day, cancelled = close_day(
            session,
            facility_of(session, user),
            user.staff_id,
            body.date,
            confirm_cancel=body.confirm_cancel,
            reason=body.reason,
        )
    except VisitRuleError as error:
        raise app_error(error) from error
    session.commit()
    for _, outbox_id in cancelled:
        background_tasks.add_task(send_email_now, outbox_id)
    return ClosedDayResult(
        id=closed_day.id, closed_date=closed_day.closed_date, cancelled=len(cancelled)
    )


@router.delete("/visit-closed-days/{closed_day_id}", status_code=204)
def delete_closed_day(
    closed_day_id: int,
    user: Annotated[CurrentUser, Depends(VISIT_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """休みを取り消す。休みにするときに取り消した予約は戻さない。"""
    try:
        open_day(session, facility_of(session, user), closed_day_id)
    except VisitRuleError as error:
        raise app_error(error) from error
    session.commit()


# --- 予約の一覧（003-T024・FR-011） ---


class StaffReservationOut(BaseModel):
    id: int
    visit_date: date
    start_time: time
    resident_id: int
    # 入居者の呼び名。画面では文字としてだけ出す
    resident_name: str
    room: str
    party_size: int
    status: str  # booked / cancelled_by_family / cancelled_by_staff
    created_at: datetime  # 予約した日時
    # 施設が取り消したときの理由（文字としてだけ出す。FR-016）
    cancel_reason: str | None


def reservation_out(row) -> StaffReservationOut:
    return StaffReservationOut(
        id=row.id,
        visit_date=row.visit_date,
        start_time=row.start_time,
        resident_id=row.resident_id,
        resident_name=row.resident_name,
        room=row.room,
        party_size=row.party_size,
        status=row.status,
        created_at=row.created_at,
        cancel_reason=row.cancel_reason,
    )


@router.get("/visits")
def get_reservations(
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> list[StaffReservationOut]:
    """予約の一覧（日時の順。取り消したものも状態つきで）。期間は 31 日まで。"""
    try:
        rows = list_reservations(session, facility_of(session, user), date_from, date_to)
    except VisitRuleError as error:
        raise app_error(error) from error
    return [reservation_out(row) for row in rows]


class StaffCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 理由は必須（家族の画面に文字としてだけ出す。メールには入れない。FR-012〜FR-014・FR-016）
    reason: str = Field(min_length=1, max_length=CANCEL_REASON_MAX)


@router.post("/visits/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    body: StaffCancelIn,
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
    background_tasks: BackgroundTasks,
) -> StaffReservationOut:
    """職員が予約を取り消す（003-T031・FR-012）。締め切りはない。予約済みでなければ 404。

    同じトランザクションで家族へのお知らせ（施設が取り消し）を作り、commit のあとにメールを送る。
    """
    facility_id = facility_of(session, user)
    try:
        reservation, outbox_id = cancel_by_staff(
            session, facility_id, user.staff_id, reservation_id, body.reason
        )
    except VisitRuleError as error:
        raise app_error(error) from error
    session.commit()
    background_tasks.add_task(send_email_now, outbox_id)
    [row] = [
        row
        for row in list_reservations(
            session, facility_id, reservation.visit_date, reservation.visit_date
        )
        if row.id == reservation.id
    ]
    return reservation_out(row)
