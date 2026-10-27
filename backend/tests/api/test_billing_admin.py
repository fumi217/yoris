"""利用料の画面の API（spec 002 の T016・US1。FR-007・SC-006）。"""

import pytest
from sqlalchemy import select

from app.models.billing import FacilitySubscription


@pytest.fixture
def subscription(session, facility) -> FacilitySubscription:
    """施設の契約を、テストごとに決まった状態にする（手元の初期データの契約を書き換える）。"""
    facility.stripe_customer_id = None
    row = session.scalars(
        select(FacilitySubscription).where(FacilitySubscription.facility_id == facility.id)
    ).one_or_none()
    if row is None:
        row = FacilitySubscription(facility_id=facility.id, status="active")
        session.add(row)
    row.status = "active"
    row.stripe_subscription_id = None
    row.current_period_end = None
    row.cancel_at = None
    session.flush()
    return row


@pytest.mark.parametrize("role", ["director", "clerk"])
def test_director_and_clerk_can_see(client, make_staff, login_as, subscription, role):
    login_as(make_staff(role=role).user_id)

    response = client.get("/api/admin/billing")

    assert response.status_code == 200
    assert response.json() == {
        "status": "active",
        "plan_name": "月額プラン",
        "amount_jpy": 10000,
        "current_period_end": None,
        "cancel_at": None,
        "can_subscribe": False,
        # 初期データの施設は Stripe とつながっていない
        "can_manage": False,
    }


@pytest.mark.parametrize("role", ["care_worker", "leader", "counselor"])
def test_other_staff_are_forbidden(client, make_staff, login_as, subscription, role):
    login_as(make_staff(role=role).user_id)

    response = client.get("/api/admin/billing")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_family_is_forbidden(client, make_family, login_as, subscription):
    login_as(make_family().user_id)

    assert client.get("/api/admin/billing").status_code == 403


def test_not_logged_in_is_401(client, subscription):
    assert client.get("/api/admin/billing").status_code == 401


@pytest.mark.parametrize("status", ["payment_failed", "canceled"])
def test_family_and_staff_can_use_app_whatever_the_status(
    client, make_staff, make_family, login_as, subscription, session, status
):
    # FR-017・US2 のシナリオ 3：支払いに失敗・解約済みでも、家族と職員は今までどおり使える
    subscription.status = status
    session.flush()

    login_as(make_family().user_id)
    assert client.get("/api/family/contact-book").status_code == 200
    login_as(make_staff(role="care_worker").user_id)
    assert client.get("/api/staff/residents").status_code == 200


def test_connected_facility_can_manage_and_canceled_can_subscribe(
    client, make_staff, login_as, subscription, facility, session
):
    facility.stripe_customer_id = "cus_test_admin"
    subscription.status = "canceled"
    session.flush()
    login_as(make_staff(role="director").user_id)

    data = client.get("/api/admin/billing").json()

    assert data["status"] == "canceled"
    assert data["can_subscribe"] is True
    assert data["can_manage"] is True
