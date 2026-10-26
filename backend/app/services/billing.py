"""決済の処理（spec 002）。

- Stripe の契約の状態からアプリの状態を決める対応表（T011・research.md R-05）
- 申し込み（T017）・利用料の画面（T022）。
  Webhook の知らせの処理・完了の確認（T019〜T021）は、続きの PR で足す

サービスの関数は commit しない（API の最後で 1 回 commit する。app/db.py）。
Stripe を呼ぶときは `stripe_client.関数名()` の形で呼ぶ
（`from ... import 関数` で取り込むと、テストの偽物に差し替わらない）。
ログには、申し込みの id・施設の id・知らせの id と種類・状態のコードだけを出す（R-13・FR-023）。
"""

import logging
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, validate_password
from app.config import PLAN_AMOUNT_JPY, PLAN_NAME
from app.errors import AppError, ErrorCode
from app.models.billing import (
    BillingApplication,
    FacilitySubscription,
)
from app.models.core import Facility, Staff
from app.services import stripe_client

logger = logging.getLogger(__name__)


class SubscriptionLike(Protocol):
    """Stripe の Subscription のうち、状態を決めるのに使うところ。"""

    status: str
    cancel_at_period_end: bool


# Stripe の状態 → アプリの状態（R-05）。ここにない状態は「変えない」
_STATUS_MAP = {
    "active": "active",
    "past_due": "payment_failed",
    "unpaid": "payment_failed",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}


def to_app_status(subscription: SubscriptionLike) -> str | None:
    """アプリの契約の状態を返す。変えないときは None。

    - `active` で、期間の終わりに解約する予定なら `cancel_scheduled`
    - `incomplete`・`trialing`・`paused`・表にない状態は、変えない
      （WARNING で状態のコードだけを出す）
    """
    status = _STATUS_MAP.get(subscription.status)
    if status is None:
        logger.warning("アプリの状態に当てはめない Stripe の契約の状態: %s", subscription.status)
        return None
    if status == "active" and subscription.cancel_at_period_end:
        return "cancel_scheduled"
    return status


# 申し込み（T017。research.md R-02・R-07・R-12）


def _error_summary(error: Exception) -> str:
    """ログに出すのは、エラーの種類と HTTP の番号だけ。

    Stripe のエラーの文には、送った値（メールアドレスなど）が入ることがあるので、
    文やスタックトレース（exc_info）は出さない（R-13・FR-023）。
    """
    return f"error={type(error).__name__} status={getattr(error, 'http_status', None)}"


def facility_exists(session: Session) -> bool:
    """施設がすでにあるか（複数施設に対応するまでは、1 つだけ。FR-016）。"""
    return session.scalar(select(Facility.id).limit(1)) is not None


def create_signup(
    session: Session,
    *,
    idempotency_key: str,
    facility_name: str,
    director_name: str,
    email: str,
    email_confirm: str,
    password: str,
    at: datetime,
) -> str:
    """申し込みを作り、Stripe の支払い画面の URL を返す。

    同じ `idempotency_key` なら、新しく作らず同じ URL を返す（期限が過ぎていれば作り直す）。
    行の追加は `INSERT ... ON CONFLICT DO NOTHING`。ほぼ同時に同じ値が届いたときは、
    PostgreSQL が先の確定を待たせるので、待ったあとに行を読み直して同じ URL を返す
    （Stripe には頼み直さない。R-12）。呼んだ API が、最後に commit する。
    """
    if facility_exists(session):
        raise AppError(ErrorCode.NOT_FOUND)  # 理由は出さない
    if email != email_confirm:
        raise AppError(ErrorCode.EMAIL_MISMATCH)
    validate_password(password)

    password_hash = hash_password(password)
    expires_at = at + stripe_client.CHECKOUT_LIFETIME
    application_id = None
    for _ in range(3):
        application_id = session.scalar(
            insert(BillingApplication)
            .values(
                idempotency_key=idempotency_key,
                facility_name=facility_name,
                director_name=director_name,
                contact_email=email,
                password_hash=password_hash,
                status="pending",
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(BillingApplication.id)
        )
        if application_id is not None:
            break
        existing = session.scalars(
            select(BillingApplication)
            .where(BillingApplication.idempotency_key == idempotency_key)
            .with_for_update()
        ).one_or_none()
        if existing is None:
            continue  # 先の人が失敗して行が消えていた。もう一度足す
        if existing.status != "pending":
            raise AppError(ErrorCode.NOT_FOUND)
        if existing.checkout_url and existing.expires_at and existing.expires_at > at:
            return existing.checkout_url
        # 期限が過ぎている（expired の知らせがまだ届いていない）。消して作り直す
        session.delete(existing)
        session.flush()
    if application_id is None:
        raise AppError(ErrorCode.SERVER_ERROR)

    try:
        checkout = stripe_client.create_checkout_session(
            application_id=application_id,
            idempotency_key=idempotency_key,
            contact_email=email,
            now=at,
        )
    except stripe_client.CALL_ERRORS as error:
        logger.warning(
            "支払い画面を作れなかった: application=%s %s",
            application_id,
            _error_summary(error),
        )
        session.execute(delete(BillingApplication).where(BillingApplication.id == application_id))
        raise AppError(ErrorCode.PAYMENT_SERVICE_UNAVAILABLE) from None

    application = session.get(BillingApplication, application_id)
    application.stripe_checkout_session_id = checkout.id
    application.checkout_url = checkout.url
    session.flush()
    return checkout.url


def cancel_signup(session: Session, idempotency_key: str) -> None:
    """「戻る」で戻ったとき、`pending` の申し込みの支払い画面を失効させて行を消す（R-07）。

    `completed`・`rejected`・行がないときは何もしない。
    Stripe で失効させられなかったとき（別のタブで払い終えたなど）は、行を残す
    （残さないと、そのあとの知らせでアカウントを作れなくなる）。
    """
    application = session.scalars(
        select(BillingApplication)
        .where(
            BillingApplication.idempotency_key == idempotency_key,
            BillingApplication.status == "pending",
        )
        .with_for_update()
    ).one_or_none()
    if application is None:
        return
    if application.stripe_checkout_session_id:
        try:
            stripe_client.expire_checkout_session(application.stripe_checkout_session_id)
        except stripe_client.CALL_ERRORS as error:
            logger.warning(
                "支払い画面を失効させられなかった: application=%s %s",
                application.id,
                _error_summary(error),
            )
            return
    session.delete(application)
    session.flush()


# 利用料の画面（T022）


def billing_overview(session: Session, staff_id: int) -> dict[str, Any]:
    """施設長・事務員の施設の契約の状態（ミニマム版。contracts/api.md）。"""
    row = session.execute(
        select(Facility, FacilitySubscription)
        .join(Staff, Staff.facility_id == Facility.id)
        .join(FacilitySubscription, FacilitySubscription.facility_id == Facility.id)
        .where(Staff.id == staff_id)
    ).one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    facility, subscription = row
    return {
        "status": subscription.status,
        "plan_name": PLAN_NAME,
        "amount_jpy": PLAN_AMOUNT_JPY,
        "current_period_end": subscription.current_period_end,
        "cancel_at": subscription.cancel_at,
        "can_subscribe": subscription.status == "canceled",
        "can_manage": facility.stripe_customer_id is not None,
    }
