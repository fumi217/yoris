"""申し込みと Stripe からの知らせの API（spec 002 の T017・T018・T021。contracts/api.md）。

ログインなし。`POST /api/billing/signup` などの書き込みは、ほかの API と同じく
`X-Requested-With: fetch` を確かめる（FR-027）。`/api/billing/webhook` だけは Stripe が
ヘッダーを付けないので対象外（app/auth/csrf.py）で、代わりに署名で確かめる（R-03）。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import clock
from app.config import PLAN_AMOUNT_JPY, PLAN_NAME
from app.db import get_session
from app.errors import AppError, ErrorCode, error_response
from app.services import billing, stripe_client

logger = logging.getLogger(__name__)

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


class CompleteResponse(BaseModel):
    status: str
    login_id: str | None = None


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


@router.get("/signup/complete", response_model_exclude_none=True)
def get_signup_complete(
    session_id: Annotated[str, Query(min_length=1, max_length=200)],
    session: Annotated[Session, Depends(get_session)],
) -> CompleteResponse:
    """支払い後に戻った画面が、アカウントができたかを数秒ごとに聞く。"""
    status, login_id = billing.signup_status(session, session_id, clock.now())
    return CompleteResponse(status=status, login_id=login_id)


@router.post("/webhook")
async def post_webhook(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> Response:
    """Stripe からの知らせ。本文を JSON に直す前に、そのまま署名の確認にかける（R-03）。"""
    payload = await request.body()
    try:
        event = stripe_client.verify_webhook(payload, request.headers.get("Stripe-Signature"))
    except stripe_client.InvalidWebhookError:
        logger.warning("Webhook の署名を確かめられなかった")
        return error_response(ErrorCode.VALIDATION_ERROR, status_code=400)
    try:
        # Stripe を呼ぶ処理が入るので、イベントループを止めないよう別のスレッドで動かす
        await run_in_threadpool(_process, session, event)
    except Exception:
        # 失敗したら取り消して 500（Stripe が送り直す）
        session.rollback()
        raise
    return Response(status_code=200)


def _process(session: Session, event: object) -> None:
    billing.handle_event(session, event)
    session.commit()
