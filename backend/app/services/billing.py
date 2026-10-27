"""決済の処理（spec 002）。

- Stripe の契約の状態からアプリの状態を決める対応表（T011・research.md R-05）
- 申し込み（T017）・Webhook の知らせの処理（T019・T020・T034）・完了の確認（T021）・
  利用料の画面（T022）

サービスの関数は commit しない（API の最後で 1 回 commit する。app/db.py）。
Stripe を呼ぶときは `stripe_client.関数名()` の形で呼ぶ
（`from ... import 関数` で取り込むと、テストの偽物に差し替わらない）。
ログには、申し込みの id・施設の id・知らせの id と種類・状態のコードだけを出す（R-13・FR-023）。
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.login_ids import next_login_ids
from app.auth.passwords import hash_password, validate_password
from app.config import PLAN_AMOUNT_JPY, PLAN_NAME, get_settings
from app.errors import AppError, ErrorCode
from app.models.billing import (
    BillingApplication,
    BillingEvent,
    FacilitySubscription,
    SubscriptionStatusHistory,
)
from app.models.core import Facility, Staff, User
from app.services import stripe_client

logger = logging.getLogger(__name__)

# 施設を作る処理を 1 つずつにするアドバイザリーロックの番号（R-04。ほかの用途と重ならない値）
FACILITY_CREATE_LOCK = 20020001
# 完了の画面で、ログイン用の ID を出す期間（アカウントを作ってから。contracts/api.md）
LOGIN_ID_VISIBLE_FOR = timedelta(hours=1)
# 支払い画面の期限のあと、「知らせ待ち」から「支払われていない」に変えるまでの余裕。
# 期限の直前に払った人の知らせが少し遅れても、「支払われていない」と出さないため
CONFIRMING_GRACE = timedelta(minutes=10)


class SubscriptionLike(Protocol):
    """Stripe の Subscription のうち、状態を決めるのに使うところ。"""

    status: str
    cancel_at_period_end: bool
    cancel_at: int | None


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

    - `active` で、解約する予定（`cancel_at_period_end`、または `cancel_at` に日付）なら
      `cancel_scheduled`。Customer Portal の「請求期間の終了時にキャンセル」は、
      `cancel_at_period_end` を立てず `cancel_at` だけを入れる（R-05）
    - `incomplete`・`trialing`・`paused`・表にない状態は、変えない
      （WARNING で状態のコードだけを出す）
    """
    status = _STATUS_MAP.get(subscription.status)
    if status is None:
        logger.warning("アプリの状態に当てはめない Stripe の契約の状態: %s", subscription.status)
        return None
    if status == "active" and (subscription.cancel_at_period_end or subscription.cancel_at):
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


# Webhook の知らせの処理（T018〜T020。research.md R-03・R-04・R-07）


def handle_event(session: Session, event: Any) -> None:
    """知らせを 1 回だけ処理する。同じ id の知らせなら何もしない。

    知らせの id を足す処理と中身の処理は、同じトランザクション（呼んだ API が commit する）。
    途中で失敗したら、どちらも取り消されて、Stripe の再送で処理し直せる。
    """
    inserted = session.scalar(
        insert(BillingEvent)
        .values(stripe_event_id=event.id, type=event.type)
        .on_conflict_do_nothing(index_elements=["stripe_event_id"])
        .returning(BillingEvent.id)
    )
    if inserted is None:
        logger.info("すでに処理した知らせ: event=%s", event.id)
        return
    if event.type == "checkout.session.completed":
        _on_checkout_completed(session, event)
    elif event.type == "checkout.session.expired":
        _on_checkout_expired(session, event)
    elif event.type in _SUBSCRIPTION_EVENTS:
        _on_subscription_changed(session, event)
    else:
        logger.info("扱わない知らせ: event=%s type=%s", event.id, event.type)


def _clear_personal_data(application: BillingApplication) -> None:
    application.password_hash = None
    application.facility_name = None
    application.director_name = None
    application.contact_email = None


def _on_checkout_completed(session: Session, event: Any) -> None:
    obj = event.data.object
    # 施設を作る処理を 1 つずつにする（トランザクションの終わりで外れる）
    session.execute(select(func.pg_advisory_xact_lock(FACILITY_CREATE_LOCK)))

    reference = getattr(obj, "client_reference_id", None)
    application = None
    if reference and str(reference).isdigit():
        application = session.scalars(
            select(BillingApplication)
            .where(BillingApplication.id == int(reference))
            .with_for_update()
        ).one_or_none()
    if application is None:
        # 支払いは済んだのにアカウントを作れない。翌月から請求されないよう解約する（R-04）
        subscription_id = getattr(obj, "subscription", None)
        paid = getattr(obj, "payment_status", None) in ("paid", "no_payment_required")
        if subscription_id and paid:
            stripe_client.cancel_subscription(subscription_id)
        logger.warning("申し込みが見つからない支払い完了: event=%s", event.id)
        return
    if application.status != "pending":
        return  # 同じ申し込みの知らせが別の id で来た（SC-003）

    # 支払いがまだ済んでいない完了（遅れて払う方法）では作らない。申し込みは残す
    if getattr(obj, "payment_status", None) not in ("paid", "no_payment_required"):
        logger.warning("支払いが済んでいない完了の知らせ: application=%s", application.id)
        return

    customer_id = getattr(obj, "customer", None)
    subscription_id = getattr(obj, "subscription", None)

    if facility_exists(session):
        # 2 つ目の申し込み。翌月から請求されないよう、その契約を解約する（FR-016）
        if subscription_id:
            stripe_client.cancel_subscription(subscription_id)
        application.status = "rejected"
        _clear_personal_data(application)
        logger.warning("施設がすでにあるので申し込みを断った: application=%s", application.id)
        return

    subscription = stripe_client.retrieve_subscription(subscription_id)
    stripe_client.set_customer_name(customer_id, application.facility_name)

    facility = Facility(
        name=application.facility_name,
        billing_email=application.contact_email,
        stripe_customer_id=customer_id,
    )
    session.add(facility)
    session.flush()
    user = User(
        kind="staff",
        login_id=next_login_ids(session)[0],
        password_hash=application.password_hash,
    )
    session.add(user)
    session.flush()
    status = to_app_status(subscription) or "active"
    session.add_all(
        [
            Staff(
                user_id=user.id,
                facility_id=facility.id,
                display_name=application.director_name,
                role="director",
            ),
            FacilitySubscription(
                facility_id=facility.id,
                status=status,
                stripe_subscription_id=subscription_id,
                current_period_end=_period_end(subscription),
                cancel_at=_from_timestamp(subscription.cancel_at),
            ),
            SubscriptionStatusHistory(
                facility_id=facility.id,
                from_status=None,
                to_status=status,
                stripe_event_id=event.id,
            ),
        ]
    )
    application.status = "completed"
    application.created_facility_id = facility.id
    application.created_user_id = user.id
    _clear_personal_data(application)
    session.flush()
    logger.info("施設を作った: application=%s facility=%s", application.id, facility.id)


def _on_checkout_expired(session: Session, event: Any) -> None:
    """支払われなかった申し込みの行を消す（パスワードのハッシュも消える。FR-006）。"""
    session.execute(
        delete(BillingApplication).where(
            BillingApplication.stripe_checkout_session_id == getattr(event.data.object, "id", None),
            BillingApplication.status == "pending",
        )
    )


# 契約の状態を読み直して合わせる知らせ（T034。R-03・R-05）
_SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "invoice.paid",
}


def _subscription_id_of(event: Any) -> str | None:
    """知らせから契約の ID を取り出す。

    請求書（invoice）では、契約の ID は `parent.subscription_details` の下にある
    （Stripe の 2025 年以降の API）。Webhook の受け口を古い API の版で作ってあると、
    請求書の直下の `subscription` で届くので、そちらも読む。
    """
    obj = event.data.object
    if event.type.startswith("customer.subscription."):
        return getattr(obj, "id", None)
    parent = getattr(obj, "parent", None)
    details = getattr(parent, "subscription_details", None) if parent else None
    return (getattr(details, "subscription", None) if details else None) or getattr(
        obj, "subscription", None
    )


def _on_subscription_changed(session: Session, event: Any) -> None:
    """Stripe から契約を読み直し、状態・次の請求日・使える最後の日を上書きする。

    知らせの中身の状態は信じない。順番が入れ替わって古い知らせがあとから届いても、
    読み直した結果は今の状態なので、戻らない（FR-012・SC-008）。
    状態が変わったときだけ履歴を足す（FR-019）。

    - 対応表にない状態（`incomplete` など）のときは、状態は変えないが、次の請求日と
      解約予定日は、Stripe の今の値に合わせる（日付は状態とは別に、正しく保つため）
    - Stripe を呼ぶあいだ、契約の行を `FOR UPDATE` で押さえている。施設が 1 つで知らせも少ないので
      今は問題ない。複数の施設に広げるときは、Stripe を呼んでから行を押さえる形に見直す
    """
    subscription_id = _subscription_id_of(event)
    row = None
    if subscription_id:
        row = session.scalars(
            select(FacilitySubscription)
            .where(FacilitySubscription.stripe_subscription_id == subscription_id)
            .with_for_update()
        ).one_or_none()
    if row is None:
        # 施設を作る前に届いた created や、断った申し込みの契約。施設を作るときに読み直す
        logger.info("施設につながっていない契約の知らせ: event=%s type=%s", event.id, event.type)
        return

    subscription = stripe_client.retrieve_subscription(subscription_id)
    row.current_period_end = _period_end(subscription)
    row.cancel_at = _from_timestamp(subscription.cancel_at)
    status = to_app_status(subscription)
    if status is not None and status != row.status:
        session.add(
            SubscriptionStatusHistory(
                facility_id=row.facility_id,
                from_status=row.status,
                to_status=status,
                stripe_event_id=event.id,
            )
        )
        logger.info(
            "契約の状態が変わった: facility=%s %s→%s event=%s",
            row.facility_id,
            row.status,
            status,
            event.id,
        )
        row.status = status
    session.flush()


def _from_timestamp(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def _period_end(subscription: Any) -> datetime | None:
    """次の請求日。Stripe の新しい API では、契約の明細（items）のほうにある。"""
    items = subscription.items.data
    return _from_timestamp(items[0].current_period_end) if items else None


# 申し込み完了の確認（T021）


def signup_status(
    session: Session, checkout_session_id: str, at: datetime
) -> tuple[str, str | None]:
    """`(confirming／completed／not_completed, login_id)` を返す。

    login_id は completed で、アカウントを作ってから 1 時間までのときだけ。
    """
    application = session.scalars(
        select(BillingApplication).where(
            BillingApplication.stripe_checkout_session_id == checkout_session_id
        )
    ).one_or_none()
    if application is None or application.status == "rejected":
        return "not_completed", None
    if application.status == "pending":
        if application.expires_at and at > application.expires_at + CONFIRMING_GRACE:
            return "not_completed", None
        return "confirming", None
    row = session.execute(
        select(User.login_id, User.created_at).where(User.id == application.created_user_id)
    ).one_or_none()
    if row is None or at - row.created_at > LOGIN_ID_VISIBLE_FOR:
        return "completed", None
    return "completed", row.login_id


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


def portal_url(session: Session, staff_id: int) -> str:
    """カードの変更・解約・請求の履歴の画面（Stripe の Customer Portal）の入口の URL（T038）。

    決済サービスとつながっていない施設（初期データ）は 409。Stripe を呼べなければ 502。
    戻り先は、アプリの利用料の画面。
    """
    facility = session.scalars(
        select(Facility).join(Staff, Staff.facility_id == Facility.id).where(Staff.id == staff_id)
    ).one_or_none()
    if facility is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if facility.stripe_customer_id is None:
        raise AppError(ErrorCode.BILLING_NOT_CONNECTED)
    base_url = get_settings().app_base_url
    if not base_url:
        # 戻り先が相対パスになり、Stripe に断られる。設定漏れだと分かるように残す
        logger.warning("APP_BASE_URL がありません（ポータルの戻り先を作れない）")
    return_url = f"{base_url or ''}/admin/billing"
    try:
        return stripe_client.create_portal_session(facility.stripe_customer_id, return_url)
    except stripe_client.CALL_ERRORS as error:
        logger.warning(
            "ポータルの入口を作れなかった: facility=%s %s", facility.id, _error_summary(error)
        )
        raise AppError(ErrorCode.PAYMENT_SERVICE_UNAVAILABLE) from None
