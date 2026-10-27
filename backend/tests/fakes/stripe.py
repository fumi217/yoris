"""Stripe の偽物（spec 002 の research.md R-11）。

`app.services.stripe_client` の関数を差し替え、本物の Stripe を呼ばない。
呼ばれた中身は、リストや辞書に残るので、テストで確かめられる。
Webhook の署名の確認は本物の `verify_webhook` を使い、テスト用の秘密で署名を作って送る
（`signed_headers`）。
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace

import stripe

from app.services.stripe_client import CHECKOUT_LIFETIME, CheckoutSession

TEST_SIGNING_KEY = "whsec_test_key"


def signed_headers(payload: bytes, secret: str = TEST_SIGNING_KEY) -> dict[str, str]:
    """Stripe と同じやり方で、本文の署名のヘッダーを作る。"""
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}"}


def event_body(event_id: str, event_type: str, obj: dict) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "api_version": stripe.api_version,
            "data": {"object": obj},
        }
    ).encode()


def completed_object(session_id: str, application_id: int, customer: str, subscription: str):
    return {
        "id": session_id,
        "object": "checkout.session",
        "client_reference_id": str(application_id),
        "customer": customer,
        "subscription": subscription,
        "payment_status": "paid",
        "mode": "subscription",
    }


def subscription_object(subscription: str, status: str = "active") -> dict:
    """`customer.subscription.*` の知らせの中身。アプリはこの status を信じず、読み直す。"""
    return {"id": subscription, "object": "subscription", "status": status}


def invoice_object(subscription: str, *, legacy: bool = False) -> dict:
    """`invoice.*` の知らせの中身。契約の ID は parent の下にある（2025 年以降の API）。

    `legacy=True` は、古い API の版の形（請求書の直下の `subscription`）。
    """
    if legacy:
        return {"id": "in_test_1", "object": "invoice", "subscription": subscription}
    return {
        "id": "in_test_1",
        "object": "invoice",
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": subscription},
        },
    }


@dataclass
class FakeStripe:
    # 作った支払い画面（呼ばれた引数）
    created: list[dict] = field(default_factory=list)
    expired: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    customer_names: dict[str, str] = field(default_factory=dict)
    # 契約の ID → 状態。テストで足す。なければ契約中（active）で返す
    subscription_states: dict[str, str] = field(default_factory=dict)
    # 期間の終わりに解約する予定の契約の ID（cancel_at_period_end が true で、cancel_at も入る）
    cancel_at_period_end: set[str] = field(default_factory=set)
    # Customer Portal の「請求期間の終了時にキャンセル」と同じ形（実機で確かめた。R-05）：
    # cancel_at_period_end は false のまま、cancel_at だけに期間の終わりが入る
    cancel_at_only: set[str] = field(default_factory=set)
    # 読み直した契約の ID（知らせの中身でなく、Stripe から読み直したかを確かめる）
    retrieved: list[str] = field(default_factory=list)
    # True にすると、支払い画面を作るときに Stripe を呼べなかったことにする
    fail_create: bool = False
    # 失敗させるときの Stripe のエラーの文（送った値が入ることがある）
    fail_message: str = "接続できません"

    def create_checkout_session(
        self, *, application_id: int, idempotency_key: str, contact_email: str, now: datetime
    ) -> CheckoutSession:
        if self.fail_create:
            raise stripe.APIConnectionError(self.fail_message)
        self.created.append(
            {
                "application_id": application_id,
                "idempotency_key": idempotency_key,
                "contact_email": contact_email,
            }
        )
        number = len(self.created)
        return CheckoutSession(
            id=f"cs_test_{number}",
            url=f"https://checkout.stripe.test/c/pay/cs_test_{number}",
            expires_at=now + CHECKOUT_LIFETIME,
        )

    def expire_checkout_session(self, session_id: str) -> None:
        self.expired.append(session_id)

    def retrieve_subscription(self, subscription_id: str):
        self.retrieved.append(subscription_id)
        status = self.subscription_states.get(subscription_id, "active")
        period_end = int(time.time()) + 30 * 24 * 3600
        flagged = subscription_id in self.cancel_at_period_end
        dated = flagged or subscription_id in self.cancel_at_only
        return SimpleNamespace(
            id=subscription_id,
            status=status,
            cancel_at_period_end=flagged,
            cancel_at=period_end if dated else None,
            items=SimpleNamespace(data=[SimpleNamespace(current_period_end=period_end)]),
        )

    def cancel_subscription(self, subscription_id: str) -> None:
        self.cancelled.append(subscription_id)

    def set_customer_name(self, customer_id: str, name: str) -> None:
        self.customer_names[customer_id] = name
