"""Stripe からの知らせの API と、申し込み完了の確認（spec 002 の T015・T021・US1。FR-016）。

Stripe は偽物（`fake_stripe`）。署名は、テスト用の秘密で本物と同じやり方で作って送る。
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.auth.passwords import verify_password
from app.clock import now
from app.models.billing import (
    BillingApplication,
    BillingEvent,
    FacilitySubscription,
    SubscriptionStatusHistory,
)
from app.models.core import Facility, Staff, User
from tests.fakes.stripe import (
    completed_object,
    event_body,
    invoice_object,
    signed_headers,
    subscription_object,
)

PASSWORD = "garden-lantern-42"


@pytest.fixture(autouse=True)
def _ready(fake_stripe, no_facility):
    return fake_stripe


def signup(client, key="key-0001", name="さくら苑", director="架空 太郎") -> None:
    """申し込みを 1 つ作る（Stripe の支払い画面の id は cs_test_<順番>）。"""
    response = client.post(
        "/api/billing/signup",
        json={
            "idempotency_key": key,
            "facility_name": name,
            "director_name": director,
            "email": "director@example.test",
            "email_confirm": "director@example.test",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200


def send(client, body: bytes, headers=None):
    # Stripe は X-Requested-With を付けない
    client.headers.pop("X-Requested-With", None)
    return client.post(
        "/api/billing/webhook",
        content=body,
        headers=headers if headers is not None else signed_headers(body),
    )


def completed(client, application_id, *, event="evt_1", session="cs_test_1", n=1):
    body = event_body(
        event,
        "checkout.session.completed",
        completed_object(session, application_id, f"cus_test_{n}", f"sub_test_{n}"),
    )
    return send(client, body)


def application_id(session, key="key-0001") -> int:
    return session.scalar(
        select(BillingApplication.id).where(BillingApplication.idempotency_key == key)
    )


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_bad_signature_is_400_and_changes_nothing(client, session):
    signup(client)
    body = event_body(
        "evt_1",
        "checkout.session.completed",
        completed_object("cs_test_1", application_id(session), "cus_test_1", "sub_test_1"),
    )

    response = send(client, body, headers=signed_headers(body, secret="whsec_wrong"))

    assert response.status_code == 400
    assert count(session, Facility) == 0
    assert count(session, BillingEvent) == 0
    assert session.scalars(select(BillingApplication)).one().status == "pending"


def test_missing_signature_is_400(client):
    assert send(client, b"{}", headers={}).status_code == 400


def test_completed_creates_facility_account_and_subscription(client, session, fake_stripe):
    signup(client)

    response = completed(client, application_id(session))

    assert response.status_code == 200
    facility = session.scalars(select(Facility)).one()
    assert facility.name == "さくら苑"
    assert facility.billing_email == "director@example.test"
    assert facility.stripe_customer_id == "cus_test_1"
    staff = session.scalars(select(Staff)).one()
    assert (staff.role, staff.display_name, staff.facility_id) == (
        "director",
        "架空 太郎",
        facility.id,
    )
    user = session.get(User, staff.user_id)
    assert user.kind == "staff"
    assert user.login_id.startswith("s") and len(user.login_id) == 6
    # 申し込みのときのパスワードでログインできるハッシュ
    assert verify_password(PASSWORD, user.password_hash)
    subscription = session.scalars(select(FacilitySubscription)).one()
    assert (subscription.status, subscription.stripe_subscription_id) == ("active", "sub_test_1")
    assert subscription.current_period_end is not None
    history = session.scalars(select(SubscriptionStatusHistory)).one()
    assert (history.from_status, history.to_status) == (None, "active")
    assert history.stripe_event_id == "evt_1"
    assert fake_stripe.customer_names == {"cus_test_1": "さくら苑"}
    application = session.scalars(select(BillingApplication)).one()
    assert application.status == "completed"
    assert application.created_facility_id == facility.id
    assert application.created_user_id == user.id


def test_paid_without_application_cancels_subscription(client, session, fake_stripe):
    # 「戻る」の取り消しと支払いが競合して、申し込みの行がない
    obj = completed_object("cs_test_9", 999999, "cus_test_9", "sub_test_9")

    response = send(client, event_body("evt_1", "checkout.session.completed", obj))

    assert response.status_code == 200
    assert count(session, Facility) == 0
    assert fake_stripe.cancelled == ["sub_test_9"]


def test_completed_but_unpaid_does_not_create_facility(client, session):
    signup(client)
    obj = completed_object("cs_test_1", application_id(session), "cus_test_1", "sub_test_1")
    obj["payment_status"] = "unpaid"

    response = send(client, event_body("evt_1", "checkout.session.completed", obj))

    assert response.status_code == 200
    assert count(session, Facility) == 0
    assert session.scalars(select(BillingApplication)).one().status == "pending"


def test_same_event_three_times_changes_once(client, session):
    signup(client)
    app_id = application_id(session)

    statuses = [completed(client, app_id).status_code for _ in range(3)]

    assert statuses == [200, 200, 200]
    for model in (Facility, Staff, FacilitySubscription, SubscriptionStatusHistory, BillingEvent):
        assert count(session, model) == 1, model


def test_different_event_id_for_same_application_creates_once(client, session, fake_stripe):
    signup(client)
    app_id = application_id(session)

    completed(client, app_id, event="evt_1")
    response = completed(client, app_id, event="evt_2")

    assert response.status_code == 200
    assert count(session, Facility) == 1
    assert count(session, Staff) == 1
    # 同じ申し込みなので、解約もしない
    assert fake_stripe.cancelled == []


def test_second_paid_application_is_rejected_and_its_subscription_cancelled(
    client, session, fake_stripe
):
    signup(client, key="key-a", name="施設A")
    signup(client, key="key-b", name="施設B")
    a, b = application_id(session, "key-a"), application_id(session, "key-b")

    completed(client, a, event="evt_a", session="cs_test_1", n=1)
    response = completed(client, b, event="evt_b", session="cs_test_2", n=2)

    assert response.status_code == 200
    assert count(session, Facility) == 1
    assert session.scalars(select(Facility)).one().name == "施設A"
    assert session.get(BillingApplication, b).status == "rejected"
    assert fake_stripe.cancelled == ["sub_test_2"]
    assert fake_stripe.customer_names == {"cus_test_1": "施設A"}


@pytest.mark.parametrize("second_is_rejected", [False, True])
def test_personal_data_is_cleared_after_completed_or_rejected(client, session, second_is_rejected):
    signup(client, key="key-a")
    signup(client, key="key-b")
    a, b = application_id(session, "key-a"), application_id(session, "key-b")
    completed(client, a, event="evt_a", session="cs_test_1", n=1)
    if second_is_rejected:
        completed(client, b, event="evt_b", session="cs_test_2", n=2)

    target = session.get(BillingApplication, b if second_is_rejected else a)
    session.refresh(target)

    assert target.status == ("rejected" if second_is_rejected else "completed")
    assert target.password_hash is None
    assert target.facility_name is None
    assert target.director_name is None
    assert target.contact_email is None


def test_expired_removes_pending_application(client, session):
    signup(client)

    body = event_body(
        "evt_x", "checkout.session.expired", {"id": "cs_test_1", "object": "checkout.session"}
    )
    response = send(client, body)

    assert response.status_code == 200
    assert count(session, BillingApplication) == 0
    assert count(session, Facility) == 0


def test_expired_keeps_completed_application(client, session):
    signup(client)
    completed(client, application_id(session))

    body = event_body(
        "evt_x", "checkout.session.expired", {"id": "cs_test_1", "object": "checkout.session"}
    )
    send(client, body)

    assert count(session, BillingApplication) == 1


def test_unknown_event_type_is_recorded_and_ignored(client, session):
    body = event_body("evt_u", "customer.created", {"id": "cus_1", "object": "customer"})

    assert send(client, body).status_code == 200
    assert count(session, BillingEvent) == 1


def test_failure_in_stripe_returns_500_and_can_be_retried(
    client, session, fake_stripe, monkeypatch
):
    signup(client)
    app_id = application_id(session)

    def broken(customer_id, name):
        raise RuntimeError("stripe down")

    monkeypatch.setattr("app.services.stripe_client.set_customer_name", broken)
    from fastapi.testclient import TestClient

    # 例外をそのまま上げず、500 の応答にして確かめる
    failing = TestClient(client.app, base_url="https://testserver", raise_server_exceptions=False)
    body = event_body(
        "evt_1",
        "checkout.session.completed",
        completed_object("cs_test_1", app_id, "cus_test_1", "sub_test_1"),
    )
    response = failing.post("/api/billing/webhook", content=body, headers=signed_headers(body))
    assert response.status_code == 500

    # 取り消されて何も残らない。Stripe が送り直したら、そのとき処理できる
    assert count(session, Facility) == 0
    assert count(session, BillingEvent) == 0
    monkeypatch.setattr(
        "app.services.stripe_client.set_customer_name", fake_stripe.set_customer_name
    )
    assert send(client, body).status_code == 200
    assert count(session, Facility) == 1


# 契約の状態の変化（T033・T034。US2・FR-009・FR-012・FR-019）


def contracted(client, session) -> FacilitySubscription:
    """申し込みを済ませ、契約中（sub_test_1）の施設を 1 つ作る。"""
    signup(client)
    completed(client, application_id(session))
    return session.scalars(select(FacilitySubscription)).one()


def histories(session) -> list[tuple[str | None, str, str | None]]:
    rows = session.scalars(
        select(SubscriptionStatusHistory).order_by(SubscriptionStatusHistory.id)
    ).all()
    return [(row.from_status, row.to_status, row.stripe_event_id) for row in rows]


def test_subscription_updated_reads_stripe_again_and_records_history(client, session, fake_stripe):
    subscription = contracted(client, session)
    fake_stripe.subscription_states["sub_test_1"] = "past_due"
    # 知らせの中身は「active」のまま。アプリは信じずに Stripe から読み直す（R-03）
    body = event_body(
        "evt_u1", "customer.subscription.updated", subscription_object("sub_test_1", "active")
    )

    assert send(client, body).status_code == 200

    session.refresh(subscription)
    assert subscription.status == "payment_failed"
    assert fake_stripe.retrieved[-1] == "sub_test_1"
    assert histories(session)[-1] == ("active", "payment_failed", "evt_u1")


def test_cancel_scheduled_sets_last_day(client, session, fake_stripe):
    subscription = contracted(client, session)
    fake_stripe.cancel_at_period_end.add("sub_test_1")
    body = event_body("evt_u1", "customer.subscription.updated", subscription_object("sub_test_1"))

    send(client, body)

    session.refresh(subscription)
    assert subscription.status == "cancel_scheduled"
    assert subscription.cancel_at is not None


def test_portal_style_cancel_is_scheduled_and_undo_returns_to_active(client, session, fake_stripe):
    # Customer Portal の解約は cancel_at だけが入る形で届く。取り消すと契約中に戻る（R-05）
    subscription = contracted(client, session)
    fake_stripe.cancel_at_only.add("sub_test_1")
    update = event_body(
        "evt_u1", "customer.subscription.updated", subscription_object("sub_test_1")
    )
    send(client, update)

    session.refresh(subscription)
    assert subscription.status == "cancel_scheduled"
    assert subscription.cancel_at is not None

    fake_stripe.cancel_at_only.clear()
    undo = event_body("evt_u2", "customer.subscription.updated", subscription_object("sub_test_1"))
    send(client, undo)

    session.refresh(subscription)
    assert subscription.status == "active"
    assert subscription.cancel_at is None
    assert [(a, b) for a, b, _ in histories(session)] == [
        (None, "active"),
        ("active", "cancel_scheduled"),
        ("cancel_scheduled", "active"),
    ]


def test_failure_in_reading_subscription_returns_500_and_can_be_retried(
    client, session, fake_stripe, monkeypatch
):
    # Stripe から契約を読み直せなかったら 500 を返し、知らせの記録も取り消す。
    # Stripe が送り直したら、そのとき処理できる（R-03）
    subscription = contracted(client, session)
    body = event_body(
        "evt_u1", "customer.subscription.updated", subscription_object("sub_test_1", "active")
    )

    def broken(subscription_id):
        raise RuntimeError("stripe down")

    monkeypatch.setattr("app.services.stripe_client.retrieve_subscription", broken)
    from fastapi.testclient import TestClient

    failing = TestClient(client.app, base_url="https://testserver", raise_server_exceptions=False)
    response = failing.post("/api/billing/webhook", content=body, headers=signed_headers(body))
    assert response.status_code == 500
    assert (
        session.scalar(select(BillingEvent).where(BillingEvent.stripe_event_id == "evt_u1")) is None
    )

    monkeypatch.setattr(
        "app.services.stripe_client.retrieve_subscription", fake_stripe.retrieve_subscription
    )
    fake_stripe.subscription_states["sub_test_1"] = "past_due"
    assert send(client, body).status_code == 200
    session.refresh(subscription)
    assert subscription.status == "payment_failed"


def test_invoice_event_finds_subscription_under_parent(client, session, fake_stripe):
    subscription = contracted(client, session)
    fake_stripe.subscription_states["sub_test_1"] = "past_due"

    send(client, event_body("evt_i1", "invoice.payment_failed", invoice_object("sub_test_1")))

    session.refresh(subscription)
    assert subscription.status == "payment_failed"


def test_invoice_event_in_old_api_shape_finds_subscription(client, session, fake_stripe):
    # Webhook の受け口が古い API の版だと、契約の ID は請求書の直下にある
    subscription = contracted(client, session)
    fake_stripe.subscription_states["sub_test_1"] = "past_due"

    body = event_body("evt_i1", "invoice.payment_failed", invoice_object("sub_test_1", legacy=True))
    send(client, body)

    session.refresh(subscription)
    assert subscription.status == "payment_failed"


def test_invoice_without_subscription_is_ignored(client, session, fake_stripe):
    # 契約につながらない請求書（1 回きりの請求など）は、何もせず 200
    contracted(client, session)
    body = event_body(
        "evt_i2", "invoice.paid", {"id": "in_test_2", "object": "invoice", "parent": None}
    )

    assert send(client, body).status_code == 200
    assert fake_stripe.retrieved == ["sub_test_1"]  # 申し込みのときの 1 回だけ


def test_old_paid_after_deleted_does_not_bring_back_active(client, session, fake_stripe):
    # SC-008：「解約」の知らせのあとに、古い「支払い完了」が届いても戻らない
    subscription = contracted(client, session)
    fake_stripe.subscription_states["sub_test_1"] = "canceled"

    send(
        client,
        event_body(
            "evt_d1", "customer.subscription.deleted", subscription_object("sub_test_1", "canceled")
        ),
    )
    send(client, event_body("evt_old", "invoice.paid", invoice_object("sub_test_1")))

    session.refresh(subscription)
    assert subscription.status == "canceled"
    assert histories(session) == [(None, "active", "evt_1"), ("active", "canceled", "evt_d1")]


def test_history_grows_only_when_status_changes(client, session, fake_stripe):
    subscription = contracted(client, session)
    before = subscription.current_period_end

    # 毎月の支払いが済んだ（状態は契約中のまま）。次の請求日だけ上書きする
    response = send(client, event_body("evt_p1", "invoice.paid", invoice_object("sub_test_1")))

    assert response.status_code == 200
    session.refresh(subscription)
    assert subscription.status == "active"
    assert subscription.current_period_end >= before
    assert len(histories(session)) == 1


def test_unmapped_stripe_status_keeps_current_status(client, session, fake_stripe):
    subscription = contracted(client, session)
    fake_stripe.subscription_states["sub_test_1"] = "paused"

    send(
        client,
        event_body("evt_u1", "customer.subscription.updated", subscription_object("sub_test_1")),
    )

    session.refresh(subscription)
    assert subscription.status == "active"
    assert len(histories(session)) == 1


def test_subscription_event_for_unknown_subscription_is_ignored(client, session, fake_stripe):
    # 施設を作る前に届く created や、断った申し込みの契約。何もせず 200
    contracted(client, session)
    body = event_body("evt_c9", "customer.subscription.created", subscription_object("sub_test_9"))

    assert send(client, body).status_code == 200
    assert session.scalars(select(FacilitySubscription)).one().status == "active"
    assert "sub_test_9" not in fake_stripe.retrieved


# 申し込み完了の確認（T021）


def test_complete_confirming_then_completed_with_login_id(client, session):
    signup(client)

    waiting = client.get("/api/billing/signup/complete", params={"session_id": "cs_test_1"})
    assert waiting.status_code == 200
    assert waiting.json() == {"status": "confirming"}

    completed(client, application_id(session))
    done = client.get("/api/billing/signup/complete", params={"session_id": "cs_test_1"})

    login_id = session.scalar(select(User.login_id).join(Staff, Staff.user_id == User.id))
    assert login_id is not None
    assert done.json() == {"status": "completed", "login_id": login_id}


def test_complete_does_not_return_login_id_after_one_hour(client, session):
    signup(client)
    completed(client, application_id(session))
    session.execute(text("UPDATE users SET created_at = :t"), {"t": now() - timedelta(hours=2)})

    response = client.get("/api/billing/signup/complete", params={"session_id": "cs_test_1"})

    assert response.json() == {"status": "completed"}


def test_complete_unknown_session_is_not_completed(client):
    response = client.get("/api/billing/signup/complete", params={"session_id": "cs_nothing"})

    assert response.json() == {"status": "not_completed"}


def test_complete_rejected_is_not_completed(client, session):
    signup(client, key="key-a")
    signup(client, key="key-b")
    completed(client, application_id(session, "key-a"), event="evt_a", session="cs_test_1", n=1)
    completed(client, application_id(session, "key-b"), event="evt_b", session="cs_test_2", n=2)

    response = client.get("/api/billing/signup/complete", params={"session_id": "cs_test_2"})

    assert response.json() == {"status": "not_completed"}
