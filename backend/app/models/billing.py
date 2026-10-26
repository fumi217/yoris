"""決済（J：システム利用料）のテーブル（spec 002 の data-model.md、002-T009）。

契約の状態は、Stripe から読み直した契約に合わせて上書きする（research.md R-03）。
状態が変わったら、同じトランザクションで subscription_status_histories に 1 行足す。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

# アプリの契約の状態（R-05。Stripe の状態からの対応は services/billing.py の to_app_status）
SUBSCRIPTION_STATUSES = ("active", "payment_failed", "cancel_scheduled", "canceled")
APPLICATION_STATUSES = ("pending", "completed", "rejected")


class FacilitySubscription(Base):
    """施設の契約（施設に 1 つ。FR-015）。"""

    __tablename__ = "facility_subscriptions"
    __table_args__ = (check_in("status", SUBSCRIPTION_STATUSES, "status"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), unique=True)
    status: Mapped[str]
    # Stripe の契約の ID と次の請求日。初期データの施設（Stripe とつながっていない）は空
    stripe_subscription_id: Mapped[str | None]
    current_period_end: Mapped[datetime | None]
    # 解約予定のとき、使える最後の日時
    cancel_at: Mapped[datetime | None]
    # 申し込み直しで開いている支払い画面とその期限（R-10。作り込み）
    open_checkout_session_id: Mapped[str | None]
    open_checkout_expires_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SubscriptionStatusHistory(Base):
    """契約の状態の変更履歴（FR-019）。"""

    __tablename__ = "subscription_status_histories"
    __table_args__ = (
        check_in("from_status", SUBSCRIPTION_STATUSES, "from_status"),
        check_in("to_status", SUBSCRIPTION_STATUSES, "to_status"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    # 初めて作ったときは空
    from_status: Mapped[str | None]
    to_status: Mapped[str]
    # 変わるきっかけになった Stripe の知らせ（初期データは空）
    stripe_event_id: Mapped[str | None]
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BillingApplication(Base):
    """申し込みページからの申し込み（支払いが確かめられるまで。R-04・R-12）。

    `completed`・`rejected` になったら、施設名・施設長の名前・連絡先・パスワードのハッシュを消し、
    id・状態・Stripe の支払い画面の ID・作った施設とアカウントの id だけを残す。
    期限切れ・取り消しの申し込みは、行ごと消す（FR-006）。
    """

    __tablename__ = "billing_applications"
    __table_args__ = (check_in("status", APPLICATION_STATUSES, "status"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # 申し込みページが開いたときに作る値（二度押し対策。R-12）
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    facility_name: Mapped[str | None]
    director_name: Mapped[str | None]
    contact_email: Mapped[str | None]
    password_hash: Mapped[str | None]
    status: Mapped[str]
    # Stripe の支払い画面。作る前に行を足すので、はじめは空（R-12）
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(unique=True)
    # 二度押しのときに同じ画面を返すため
    checkout_url: Mapped[str | None]
    # 支払い画面の期限（30 分。R-07）
    expires_at: Mapped[datetime | None]
    created_facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    # 完了の画面でログイン用の ID を出すため
    created_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BillingEvent(Base):
    """受け取った Stripe の知らせ（同じ知らせを 2 回処理しないため。FR-011）。

    本文は保存しない（メールアドレスなどが入るため）。処理と同じトランザクションで足す。
    """

    __tablename__ = "billing_events"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(unique=True)
    type: Mapped[str]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())
