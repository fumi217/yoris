"""利用料の画面の API（施設長・事務員。spec 002 の T022。FR-007）。"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.services import billing

router = APIRouter(prefix="/api/admin", tags=["admin"])

DIRECTOR_OR_CLERK = require_staff(("director", "clerk"))


class BillingResponse(BaseModel):
    status: str
    plan_name: str
    amount_jpy: int
    current_period_end: datetime | None
    cancel_at: datetime | None
    can_subscribe: bool
    can_manage: bool


@router.get("/billing")
def get_billing(
    user: Annotated[CurrentUser, Depends(DIRECTOR_OR_CLERK)],
    session: Annotated[Session, Depends(get_session)],
) -> BillingResponse:
    """契約の状態。`can_manage` は Stripe とつながっているとき true（初期データの施設は false）。"""
    return BillingResponse(**billing.billing_overview(session, user.staff_id))
