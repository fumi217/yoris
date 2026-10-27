"""今日の面会予定（spec 003 の 003-T024・FR-011）。`GET /api/staff/visits/today`

職員のすべてが見られる（R-06）。今日（日本時間）の予約済みを、時刻の順に返す。
施設は、ログイン中の職員の施設から決める。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.admin.visits import STAFF, StaffReservationOut, facility_of, reservation_out
from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.db import get_session
from app.services.visits import list_reservations

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("/visits/today")
def today_visits(
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
) -> list[StaffReservationOut]:
    today = today_jst()
    rows = list_reservations(session, facility_of(session, user), today, today, booked_only=True)
    return [reservation_out(row) for row in rows]
