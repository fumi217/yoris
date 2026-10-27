"""Stripe の契約の状態 → アプリの状態の対応表（spec 002 の T011・research.md R-05）。"""

import logging
from dataclasses import dataclass

import pytest

from app.services.billing import to_app_status


@dataclass
class FakeSubscription:
    status: str
    cancel_at_period_end: bool = False
    cancel_at: int | None = None


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


def test_active_with_only_cancel_at_is_cancel_scheduled():
    # Customer Portal の「請求期間の終了時にキャンセル」は、cancel_at_period_end を立てず、
    # cancel_at に日付を入れる（実機で確かめた。R-05）
    assert to_app_status(FakeSubscription("active", cancel_at=1795747944)) == "cancel_scheduled"


def test_cancel_at_does_not_change_other_statuses():
    assert to_app_status(FakeSubscription("past_due", cancel_at=1795747944)) == "payment_failed"
    assert to_app_status(FakeSubscription("canceled", cancel_at=1795747944)) == "canceled"


@pytest.mark.parametrize("stripe_status", ["incomplete", "trialing", "paused", "something_new"])
def test_other_statuses_do_not_change_and_log_only_the_code(stripe_status, caplog):
    with caplog.at_level(logging.WARNING):
        assert to_app_status(FakeSubscription(stripe_status)) is None

    assert stripe_status in caplog.text
