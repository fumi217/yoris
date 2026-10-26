"""決済の処理（spec 002）。

いまは Stripe の契約の状態からアプリの状態を決める対応表（T011・research.md R-05）だけ。
申し込み・Webhook の処理（T017〜T021）も、ここに足す。
"""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class SubscriptionLike(Protocol):
    """Stripe の Subscription のうち、状態を決めるのに使うところ。"""

    status: str
    cancel_at_period_end: bool


# Stripe の状態 → アプリの状態（R-05）。ここにない状態は「変えない」
_STATUS_MAP = {
    "active": "active",
    "past_due": "payment_failed",
    "unpaid": "payment_failed",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}


def to_app_status(subscription: SubscriptionLike) -> str | None:
    """アプリの契約の状態を返す。変えないときは None。

    - `active` で、期間の終わりに解約する予定なら `cancel_scheduled`
    - `incomplete`・`trialing`・`paused`・表にない状態は、変えない
      （WARNING で状態のコードだけを出す）
    """
    status = _STATUS_MAP.get(subscription.status)
    if status is None:
        logger.warning("アプリの状態に当てはめない Stripe の契約の状態: %s", subscription.status)
        return None
    if status == "active" and subscription.cancel_at_period_end:
        return "cancel_scheduled"
    return status
