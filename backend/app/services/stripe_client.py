"""Stripe を呼ぶところ（spec 002 の T010。research.md R-01・R-03・R-04・R-07・R-12、FR-025）。

Stripe を呼ぶのは、このモジュールだけにする。テストでは、このモジュールの関数をモックにする
（本物の Stripe を呼ばない。CLAUDE.md）。
Stripe に渡す施設長の情報は、施設名とメールアドレスだけ（FR-025）。

呼べなかったとき（通信の失敗・待ち時間の上限を超えた・Stripe のエラー）は、
ライブラリの `stripe.StripeError` がそのまま上がる。呼んだ側で 502 などにする。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from urllib.parse import urlencode

import stripe

from app.config import PLAN_LOOKUP_KEY, get_settings

# Stripe を呼ぶときの待ち時間の上限（秒）。ライブラリの初期値（80 秒）は長く、
# 申し込みのトランザクションが接続をつかみ続けてしまうため（R-12）
TIMEOUT_SECONDS = 10
# 支払い画面の期限（Stripe で選べる最短。R-07）
CHECKOUT_LIFETIME = timedelta(minutes=30)


class StripeNotConfiguredError(RuntimeError):
    """STRIPE_SECRET_KEY がない（決済を試さない人の手元・テストでモックにし忘れたとき）。"""


class InvalidWebhookError(Exception):
    """Webhook の署名を確かめられなかった（R-03。受け口で 400 にする）。"""


# Stripe を呼べなかったときに上がるもの（呼んだ側が 502 などにする）。
# 通信の失敗・Stripe のエラー、価格が見つからない、鍵がない
CALL_ERRORS = (stripe.StripeError, LookupError, StripeNotConfiguredError)


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str
    expires_at: datetime


@cache
def _client() -> stripe.StripeClient:
    api_key = get_settings().stripe_secret_key
    if not api_key:
        raise StripeNotConfiguredError("STRIPE_SECRET_KEY がありません（env.example）")
    return stripe.StripeClient(
        api_key, http_client=stripe.new_default_http_client(timeout=TIMEOUT_SECONDS)
    )


def find_price_id(lookup_key: str = PLAN_LOOKUP_KEY) -> str:
    """lookup key で、使える価格の ID を探す（価格の ID を環境変数に書かない。R-01）。"""
    prices = _client().v1.prices.list(params={"lookup_keys": [lookup_key], "active": True})
    if not prices.data:
        raise LookupError(f"Stripe に lookup key {lookup_key} の価格がありません（T004）")
    return prices.data[0].id


def create_checkout_session(
    *, application_id: int, idempotency_key: str, contact_email: str, now: datetime
) -> CheckoutSession:
    """申し込みの支払い画面（Checkout Session。subscription モード）を作る。

    - Stripe の冪等キーは `signup-<申し込みの id>-<頼む時刻（秒）>`
      （ブラウザの idempotency_key は渡さない。R-12）。時刻を足すのは、DB を作り直したときに
      id が数え直しになり、24 時間以内に同じキーを別の中身で使うと Stripe に断られるため。
      1 回の依頼の中では同じキーなので、通信の失敗の自動の送り直しには効く
    - 支払い画面の期限は 30 分後（R-07）
    - 「戻る」で戻る先は `/signup?canceled=1&key=<idempotency_key>`（R-07）
    """
    base_url = get_settings().app_base_url or ""
    expires_at = now + CHECKOUT_LIFETIME
    session = _client().v1.checkout.sessions.create(
        params={
            "mode": "subscription",
            "line_items": [{"price": find_price_id(), "quantity": 1}],
            "client_reference_id": str(application_id),
            "customer_email": contact_email,
            # {CHECKOUT_SESSION_ID} は Stripe が本物の ID に置き換える
            "success_url": f"{base_url}/signup/complete?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": (
                f"{base_url}/signup?{urlencode({'canceled': 1, 'key': idempotency_key})}"
            ),
            "expires_at": int(expires_at.timestamp()),
        },
        options={"idempotency_key": f"signup-{application_id}-{int(now.timestamp())}"},
    )
    return CheckoutSession(id=session.id, url=session.url or "", expires_at=expires_at)


def expire_checkout_session(session_id: str) -> None:
    """支払い画面を失効させる（「戻る」で取り消したとき。R-07）。"""
    _client().v1.checkout.sessions.expire(session_id)


def retrieve_subscription(subscription_id: str) -> stripe.Subscription:
    """契約の今の状態を Stripe から読む（知らせの中身は信じず、読み直して合わせる。R-03）。"""
    return _client().v1.subscriptions.retrieve(subscription_id)


def cancel_subscription(subscription_id: str) -> None:
    """契約をすぐに解約する（施設がすでにあったときの 2 つ目の申し込み。R-04）。

    知らせの再送で何度呼ばれてもよいように、すでに解約済みなら呼ばず、
    解約のエラーが返っても、読み直して解約済みなら成功として扱う（PR #25 みさき）。
    """
    if retrieve_subscription(subscription_id).status == "canceled":
        return
    try:
        _client().v1.subscriptions.cancel(subscription_id)
    except stripe.InvalidRequestError:
        if retrieve_subscription(subscription_id).status != "canceled":
            raise


def set_customer_name(customer_id: str, name: str) -> None:
    """Stripe の顧客の名前を施設名にする（Checkout では名前が入らないため。R-04）。"""
    _client().v1.customers.update(customer_id, params={"name": name})


def verify_webhook(payload: bytes, signature: str | None) -> stripe.Event:
    """Webhook の本文を、JSON に直す前にそのまま署名の確認にかける（R-03）。"""
    secret = get_settings().stripe_webhook_secret
    if not secret or not signature:
        raise InvalidWebhookError
    try:
        return stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as error:
        raise InvalidWebhookError from error
