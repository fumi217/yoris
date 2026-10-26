"""家族の面会予約の API（spec 003 の 003-T011。contracts の「家族」）。

入居者は送らせない（本文に入居者の欄を持たず、余分な項目は 422）。
ログイン中の家族から決める（R-05）。
"""

from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.services.visit_rules import VisitRuleError
from app.services.visits import book_visit, get_availability

router = APIRouter(prefix="/api/family/visits", tags=["family"])


class StartTimeOut(BaseModel):
    start_time: time
    selectable: bool


class DayOut(BaseModel):
    date: date
    closed: bool
    mine: bool
    start_times: list[StartTimeOut]


class AvailabilityResponse(BaseModel):
    days: list[DayOut]


class BookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visit_date: date
    start_time: time
    party_size: int = Field(ge=1)  # 1 以上、上限なし（FR-002）


class ReservationResponse(BaseModel):
    id: int
    visit_date: date
    start_time: time
    party_size: int
    status: str


def _app_error(error: VisitRuleError) -> AppError:
    return AppError(ErrorCode(error.code))


@router.get("/availability")
def availability(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> AvailabilityResponse:
    """日付ごとの開始時刻の候補と、選べるかどうか（ほかの家族の情報・選べない理由は返さない）。"""
    try:
        days = get_availability(session, user, date_from, date_to)
    except VisitRuleError as error:
        raise _app_error(error) from error
    return AvailabilityResponse(
        days=[
            DayOut(
                date=day.date,
                closed=day.closed,
                mine=day.mine,
                start_times=[
                    StartTimeOut(start_time=slot.start_time, selectable=slot.selectable)
                    for slot in day.start_times
                ],
            )
            for day in days
        ]
    )


@router.post("", status_code=201)
def book(
    body: BookRequest,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> ReservationResponse:
    """面会を予約する。その場で確定する（施設の承認は待たない）。"""
    try:
        reservation = book_visit(session, user, body.visit_date, body.start_time, body.party_size)
    except VisitRuleError as error:
        raise _app_error(error) from error
    session.commit()
    return ReservationResponse(
        id=reservation.id,
        visit_date=reservation.visit_date,
        start_time=reservation.start_time,
        party_size=reservation.party_size,
        status=reservation.status,
    )
