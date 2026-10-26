"""申し込みの API（spec 002 の T017。contracts/api.md）。

ログインなし。`POST /api/billing/signup` などの書き込みは、ほかの API と同じく
`X-Requested-With: fetch` を確かめる（FR-027）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import clock
from app.config import PLAN_AMOUNT_JPY, PLAN_NAME
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.services import billing

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PlanResponse(BaseModel):
    plan_name: str
    amount_jpy: int


class SignupRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    facility_name: str = Field(min_length=1, max_length=100)
    director_name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    email_confirm: str = Field(max_length=254)
    password: str = Field(max_length=200)


class SignupResponse(BaseModel):
    checkout_url: str


class CancelRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)


@router.get("/signup")
def get_signup(session: Annotated[Session, Depends(get_session)]) -> PlanResponse:
    """申し込みページに出すプラン名と月額。施設がすでにあれば 404。"""
    if billing.facility_exists(session):
        raise AppError(ErrorCode.NOT_FOUND)
    return PlanResponse(plan_name=PLAN_NAME, amount_jpy=PLAN_AMOUNT_JPY)


@router.post("/signup")
def post_signup(
    data: SignupRequest, session: Annotated[Session, Depends(get_session)]
) -> SignupResponse:
    """申し込みを作り、支払い画面の URL を返す（パスワード・メールアドレスは返さない。FR-006）。"""
    url = billing.create_signup(
        session,
        idempotency_key=data.idempotency_key,
        facility_name=data.facility_name,
        director_name=data.director_name,
        email=data.email,
        email_confirm=data.email_confirm,
        password=data.password,
        at=clock.now(),
    )
    session.commit()
    return SignupResponse(checkout_url=url)


@router.post("/signup/cancel", status_code=204)
def post_signup_cancel(
    data: CancelRequest, session: Annotated[Session, Depends(get_session)]
) -> Response:
    billing.cancel_signup(session, data.idempotency_key)
    session.commit()
    return Response(status_code=204)
