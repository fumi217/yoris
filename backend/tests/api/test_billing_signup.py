"""申し込みの API（spec 002 の T014・US1。FR-006・FR-016・FR-025・FR-027）。

Stripe は偽物（`fake_stripe`）。施設がまだない状態（`no_facility`）から始める。
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.clock import now
from app.models.billing import BillingApplication
from app.models.core import Facility

PASSWORD = "garden-lantern-42"


def body(**changes):
    data = {
        "idempotency_key": "key-0001",
        "facility_name": "さくら苑",
        "director_name": "架空 太郎",
        "email": "director@example.test",
        "email_confirm": "director@example.test",
        "password": PASSWORD,
    }
    return {**data, **changes}


def count_applications(session) -> int:
    return session.scalar(select(func.count()).select_from(BillingApplication))


@pytest.fixture(autouse=True)
def _ready(fake_stripe, no_facility):
    return fake_stripe


def test_get_returns_plan(client):
    response = client.get("/api/billing/signup")

    assert response.status_code == 200
    assert response.json() == {"plan_name": "月額プラン", "amount_jpy": 10000}


def test_post_creates_application_and_returns_checkout_url(client, session, fake_stripe):
    response = client.post("/api/billing/signup", json=body())

    assert response.status_code == 200
    assert response.json() == {"checkout_url": "https://checkout.stripe.test/c/pay/cs_test_1"}
    application = session.scalars(select(BillingApplication)).one()
    assert application.status == "pending"
    assert application.stripe_checkout_session_id == "cs_test_1"
    # Stripe には申し込みの id を渡す（client_reference_id になる）
    assert fake_stripe.created[0]["application_id"] == application.id


def test_email_mismatch_is_422(client, session):
    response = client.post("/api/billing/signup", json=body(email_confirm="other@example.test"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_mismatch"
    assert count_applications(session) == 0


@pytest.mark.parametrize(
    "password",
    ["short1!", "a" * 65, "ぱすわーど12345678", "password123"],
    ids=["too_short", "too_long", "full_width", "too_common"],
)
def test_password_outside_rule_is_422(client, session, password):
    response = client.post("/api/billing/signup", json=body(password=password))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert count_applications(session) == 0


def test_missing_field_is_422(client):
    data = body()
    del data["facility_name"]

    assert client.post("/api/billing/signup", json=data).status_code == 422


def test_same_key_twice_makes_one_application_and_one_checkout(client, session, fake_stripe):
    first = client.post("/api/billing/signup", json=body())
    second = client.post("/api/billing/signup", json=body())

    assert second.status_code == 200
    assert second.json() == first.json()
    assert count_applications(session) == 1
    # 二度目は Stripe に頼み直さない（SC-009）
    assert len(fake_stripe.created) == 1


def test_key_taken_by_other_request_returns_same_url_without_calling_stripe(
    client, session, fake_stripe
):
    """ほぼ同時に届いた 2 つ目：行の追加が先の確定を待ち、読み直して同じ URL を返す（R-12）。

    PostgreSQL では、待ったあとの 2 つ目は「すでに同じ値の行がある」状態になる。
    ここでは、先に確定した行がある状態で送って、同じ道（ON CONFLICT のあと読み直す）を通す。
    """
    session.add(
        BillingApplication(
            idempotency_key="key-0001",
            facility_name="さくら苑",
            director_name="架空 太郎",
            contact_email="director@example.test",
            password_hash="x",
            status="pending",
            stripe_checkout_session_id="cs_other",
            checkout_url="https://checkout.stripe.test/c/pay/cs_other",
            expires_at=now() + timedelta(minutes=20),
        )
    )
    session.flush()

    response = client.post("/api/billing/signup", json=body())

    assert response.status_code == 200
    assert response.json() == {"checkout_url": "https://checkout.stripe.test/c/pay/cs_other"}
    assert fake_stripe.created == []


def test_expired_key_is_recreated_with_new_stripe_key(client, session, fake_stripe):
    client.post("/api/billing/signup", json=body())
    old = session.scalars(select(BillingApplication)).one()
    old_id = old.id
    session.execute(
        text("UPDATE billing_applications SET expires_at = :t"),
        {"t": now() - timedelta(minutes=1)},
    )
    session.expire_all()  # 生の SQL で変えたので、読み直させる（本番は 1 リクエスト 1 セッション）

    response = client.post("/api/billing/signup", json=body())

    assert response.status_code == 200
    application = session.scalars(select(BillingApplication)).one()
    assert application.id != old_id
    # Stripe の冪等キーは申し込みの行ごとに別（signup-<id>-<時刻>）なので、申し込みの id が違う
    assert [call["application_id"] for call in fake_stripe.created] == [old_id, application.id]


def test_stripe_failure_removes_application_and_returns_502(client, session, fake_stripe):
    fake_stripe.fail_create = True

    response = client.post("/api/billing/signup", json=body())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "payment_service_unavailable"
    assert count_applications(session) == 0


def test_stripe_failure_log_has_no_personal_data(client, fake_stripe, caplog):
    fake_stripe.fail_create = True
    fake_stripe.fail_message = "invalid email director@example.test"

    client.post("/api/billing/signup", json=body())

    # ログには、エラーの種類と番号だけ（送った値が入りうる文やスタックトレースは出さない。R-13）
    logged = "\n".join(f"{r.getMessage()} {r.exc_text or ''}" for r in caplog.records)
    assert "APIConnectionError" in logged
    assert "director@example.test" not in logged
    assert "Traceback" not in logged


def test_cancel_expires_checkout_and_removes_pending_application(client, session, fake_stripe):
    client.post("/api/billing/signup", json=body())

    response = client.post("/api/billing/signup/cancel", json={"idempotency_key": "key-0001"})

    assert response.status_code == 204
    assert fake_stripe.expired == ["cs_test_1"]
    assert count_applications(session) == 0


def test_cancel_does_nothing_for_completed_application(client, session, fake_stripe):
    client.post("/api/billing/signup", json=body())
    session.execute(text("UPDATE billing_applications SET status = 'completed'"))

    response = client.post("/api/billing/signup/cancel", json={"idempotency_key": "key-0001"})

    assert response.status_code == 204
    assert fake_stripe.expired == []
    assert count_applications(session) == 1


def test_cancel_unknown_key_is_204(client, fake_stripe):
    response = client.post("/api/billing/signup/cancel", json={"idempotency_key": "nothing"})

    assert response.status_code == 204
    assert fake_stripe.expired == []


def test_get_and_post_are_404_when_facility_exists(client, session, fake_stripe):
    # no_facility のあとに施設を足す（施設が 1 つある状態）
    session.add(Facility(name="先にある施設"))
    session.flush()

    assert client.get("/api/billing/signup").status_code == 404
    response = client.post("/api/billing/signup", json=body())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert fake_stripe.created == []


def test_post_without_fetch_header_is_rejected(client):
    client.headers.pop("X-Requested-With")

    response = client.post("/api/billing/signup", json=body())

    assert response.status_code == 403


def test_password_is_not_stored_as_plain_text(client, session):
    client.post("/api/billing/signup", json=body())

    rows = session.execute(text("SELECT to_jsonb(b)::text FROM billing_applications b")).scalars()
    dumped = " ".join(rows)
    assert PASSWORD not in dumped
    application = session.scalars(select(BillingApplication)).one()
    assert application.password_hash.startswith("$2")


def test_stripe_receives_only_email_for_contact(client, fake_stripe):
    client.post("/api/billing/signup", json=body())

    # 渡すのは申し込みの id・メールアドレス・ブラウザの値だけ（名前・パスワードは渡さない）
    assert fake_stripe.created == [
        {
            "application_id": fake_stripe.created[0]["application_id"],
            "idempotency_key": "key-0001",
            "contact_email": "director@example.test",
        }
    ]
