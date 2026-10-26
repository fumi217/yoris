"""初期データの施設の契約（spec 002 の T013）。DB を使う（なければ手元では飛ばす）。"""

from sqlalchemy import select

from app.models.billing import FacilitySubscription, SubscriptionStatusHistory
from app.models.core import Facility
from app.seed.billing import add_subscription


def _new_facility(session) -> Facility:
    # 契約のない施設（テストの中だけ。最後に取り消される）
    facility = Facility(name="テスト施設（契約）")
    session.add(facility)
    session.flush()
    return facility


def test_adds_active_subscription_without_stripe(session):
    facility = _new_facility(session)

    assert add_subscription(session, facility_id=facility.id) is True

    subscription = session.scalars(
        select(FacilitySubscription).where(FacilitySubscription.facility_id == facility.id)
    ).one()
    assert subscription.status == "active"
    # Stripe とつながっていない
    assert subscription.stripe_subscription_id is None
    assert subscription.current_period_end is None
    history = session.scalars(
        select(SubscriptionStatusHistory).where(
            SubscriptionStatusHistory.facility_id == facility.id
        )
    ).one()
    assert (history.from_status, history.to_status, history.stripe_event_id) == (
        None,
        "active",
        None,
    )


def test_does_nothing_when_subscription_exists(session):
    # 申し込みで作った施設・2 回目に流したとき
    facility = _new_facility(session)
    add_subscription(session, facility_id=facility.id)

    assert add_subscription(session, facility_id=facility.id) is False

    count = len(
        session.scalars(
            select(FacilitySubscription).where(FacilitySubscription.facility_id == facility.id)
        ).all()
    )
    assert count == 1
