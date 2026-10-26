"""初期データの施設の契約（spec 002 の T013・data-model.md「初期データ」）。

初期データの施設は、Stripe とつながっていない「契約中」にする
（Stripe の契約の ID・次の請求日は空）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing import FacilitySubscription, SubscriptionStatusHistory


def add_subscription(session: Session, *, facility_id: int) -> bool:
    """施設に契約がなければ「契約中」で作り、履歴も 1 行足す。作ったら True。

    申し込みで作った施設には契約があるので、何もしない（何度流しても同じ）。
    契約のない施設（このタスクより前に初期データを入れた手元の DB）にも足す。
    """
    exists = session.scalar(
        select(FacilitySubscription.id).where(FacilitySubscription.facility_id == facility_id)
    )
    if exists is not None:
        return False
    session.add_all(
        [
            FacilitySubscription(facility_id=facility_id, status="active"),
            SubscriptionStatusHistory(facility_id=facility_id, to_status="active"),
        ]
    )
    session.flush()
    return True
