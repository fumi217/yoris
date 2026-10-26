"""Stripe の契約の状態 → アプリの状態の対応表（spec 002 の T011・research.md R-05）。"""

import logging
from dataclasses import dataclass

import pytest

from app.services.billing import to_app_status


@dataclass
class FakeSubscription:
    status: str
    cancel_at_period_end: bool = False


@pytest.mark.parametrize(
    ("stripe_status", "app_status"),
    [
        ("active", "active"),
        ("past_due", "payment_failed"),
        ("unpaid", "payment_failed"),
        ("canceled", "canceled"),
        ("incomplete_expired", "canceled"),
    ],
)
def test_status_map(stripe_status, app_status):
    assert to_app_status(FakeSubscription(stripe_status)) == app_status


def test_active_with_cancel_at_period_end_is_cancel_scheduled():
    assert to_app_status(FakeSubscription("active", cancel_at_period_end=True)) == (
        "cancel_scheduled"
    )


@pytest.mark.parametrize("stripe_status", ["incomplete", "trialing", "paused", "something_new"])
def test_other_statuses_do_not_change_and_log_only_the_code(stripe_status, caplog):
    with caplog.at_level(logging.WARNING):
        assert to_app_status(FakeSubscription(stripe_status)) is None

    assert stripe_status in caplog.text
