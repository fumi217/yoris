"""Stripe を呼ぶところ（spec 002 の T010）。

本物の Stripe は呼ばず、ライブラリのクライアントを偽物にする。
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import stripe

from app.services import stripe_client
from app.services.stripe_client import (
    InvalidWebhookError,
    StripeNotConfiguredError,
    cancel_subscription,
    create_checkout_session,
    verify_webhook,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock()
    fake.v1.prices.list.return_value.data = [MagicMock(id="price_123")]
    monkeypatch.setattr(stripe_client, "_client", lambda: fake)
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.test")
    return fake


def test_checkout_session_params(client):
    client.v1.checkout.sessions.create.return_value = MagicMock(
        id="cs_test_1", url="https://checkout.stripe.test/cs_test_1"
    )
    now = datetime(2026, 10, 26, 3, 0, tzinfo=UTC)

    session = create_checkout_session(
        application_id=7, idempotency_key="key-abc", contact_email="d@example.test", now=now
    )

    kwargs = client.v1.checkout.sessions.create.call_args.kwargs
    params = kwargs["params"]
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_123", "quantity": 1}]
    assert params["client_reference_id"] == "7"
    # 施設長の情報はメールアドレスだけ（施設名は支払いのあとに顧客の名前にする。FR-025・R-04）
    assert params["customer_email"] == "d@example.test"
    assert params["cancel_url"] == "https://app.example.test/signup?canceled=1&key=key-abc"
    assert params["success_url"].endswith("/signup/complete?session_id={CHECKOUT_SESSION_ID}")
    # 30 分後（R-07）
    assert params["expires_at"] == int(now.timestamp()) + 30 * 60
    # ブラウザの値ではなく、申し込みの id と頼む時刻のキー（R-12）
    assert kwargs["options"] == {"idempotency_key": f"signup-7-{int(now.timestamp())}"}
    assert session.id == "cs_test_1"
    assert client.v1.prices.list.call_args.kwargs["params"]["lookup_keys"] == ["monthly_standard"]


def test_idempotency_key_differs_when_the_same_id_is_used_again(client):
    """DB を作り直して同じ id が使われても、別の時刻なら別のキーになる（R-12）。"""
    client.v1.checkout.sessions.create.return_value = MagicMock(id="cs_test_1", url="https://x")
    first = datetime(2026, 10, 26, 3, 0, tzinfo=UTC)
    second = datetime(2026, 10, 26, 4, 0, tzinfo=UTC)

    for now in (first, second):
        create_checkout_session(
            application_id=1, idempotency_key="key", contact_email="d@example.test", now=now
        )

    keys = [
        call.kwargs["options"]["idempotency_key"]
        for call in client.v1.checkout.sessions.create.call_args_list
    ]
    assert len(set(keys)) == 2
    assert all(key.startswith("signup-1-") for key in keys)


def test_missing_price_is_an_error(client):
    client.v1.prices.list.return_value.data = []

    with pytest.raises(LookupError):
        stripe_client.find_price_id()


def test_cancel_skips_already_canceled_subscription(client):
    client.v1.subscriptions.retrieve.return_value = MagicMock(status="canceled")

    cancel_subscription("sub_1")

    client.v1.subscriptions.cancel.assert_not_called()


def test_cancel_error_is_ok_when_it_is_canceled_after_all(client):
    # 解約は Stripe で済んでいたのに、DB の確定だけが失敗して再送されたとき（R-04）
    client.v1.subscriptions.retrieve.side_effect = [
        MagicMock(status="active"),
        MagicMock(status="canceled"),
    ]
    client.v1.subscriptions.cancel.side_effect = stripe.InvalidRequestError("canceled", None)

    cancel_subscription("sub_1")


def test_cancel_error_is_raised_when_still_active(client):
    client.v1.subscriptions.retrieve.return_value = MagicMock(status="active")
    client.v1.subscriptions.cancel.side_effect = stripe.InvalidRequestError("nope", None)

    with pytest.raises(stripe.InvalidRequestError):
        cancel_subscription("sub_1")


def test_webhook_with_bad_signature_is_invalid(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    with pytest.raises(InvalidWebhookError):
        verify_webhook(b'{"id": "evt_1"}', "t=1,v1=bad")


def test_webhook_without_secret_or_signature_is_invalid(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

    with pytest.raises(InvalidWebhookError):
        verify_webhook(b"{}", "t=1,v1=bad")


def test_no_secret_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    stripe_client._client.cache_clear()

    with pytest.raises(StripeNotConfiguredError):
        stripe_client._client()
