"""初期データを入れる（spec 001 の T015）。`docker compose exec backend python -m app.seed`

何度流しても同じになる（すでにあるものは足さない）。施設がすでにあれば（決済の申し込みで作ったあと）、その施設に足す。
入れ直したいときは、DB を空にしてから流す（README の「初期データ」）。

自分の機能の初期データを足す人は、下の seed() に 1 行足す。足す関数は app/seed/ に置き、
- commit しない（最後に 1 回だけ、ここで commit する。途中で失敗したら何も入らない）
- 何度呼んでも同じになるようにする（すでにあれば足さない）か、`fresh` のときだけ呼ぶ
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today_jst
from app.config import get_settings
from app.db import get_engine
from app.models.core import Resident
from app.models.disclosure import Theme
from app.seed.album import add_sample_photos
from app.seed.billing import add_subscription
from app.seed.change_rules import add_change_rules, add_sample_change_flags
from app.seed.inquiry import add_staff_message_templates
from app.seed.people import add_people, get_or_add_facility, set_seed_passwords
from app.seed.records import add_sample_records
from app.seed.requests import add_sample_requests
from app.seed.themes import add_disclosure_settings, add_themes
from app.seed.visits import add_sample_reservations, add_visit_settings


def seed(session: Session, *, today: date) -> bool:
    """初期データを入れる。人を新しく入れたら True。

    そのときだけ、デモ用の記録・予約・リクエストも入れる。
    """
    facility = get_or_add_facility(session)
    # 契約がなければ「契約中」（Stripe とつながっていない）で作る（spec 002 の T013）
    add_subscription(session, facility_id=facility.id)
    added_staff = add_people(session, facility_id=facility.id)
    fresh = bool(added_staff)

    # 何度呼んでも同じになるもの
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    add_visit_settings(session, facility_id=facility.id)
    add_staff_message_templates(session)
    add_change_rules(session)

    # 人を新しく入れたときだけ（同じ日の記録・予約が 2 回入らないように）
    if fresh:
        resident_ids = list(
            session.scalars(
                select(Resident.id).where(Resident.facility_id == facility.id).order_by(Resident.id)
            )
        )
        # デモの記録は、いま入れた介護職員の最初の人（田中）が付けたことにする
        care_worker_id = next(s.id for s in added_staff if s.role == "care_worker")
        add_sample_records(session, resident_ids=resident_ids, staff_id=care_worker_id, today=today)
        # 記録を入れたあとに、変化の目印を付ける（spec 006 の 006-T009）
        add_sample_change_flags(
            session, resident_ids=resident_ids, staff_id=care_worker_id, today=today
        )
        add_sample_reservations(
            session, facility_id=facility.id, resident_ids=resident_ids, today=today
        )
        theme_ids = list(session.scalars(select(Theme.id).order_by(Theme.sort_order)))
        add_sample_requests(
            session, resident_ids=resident_ids, theme_ids=theme_ids, staff_id=care_worker_id
        )
        # アルバムのデモの写真は、最初の入居者（A）にだけ（B の家族には見えないことを確かめるため）
        add_sample_photos(session, resident_id=resident_ids[0], staff_id=care_worker_id)
    return fresh


def main() -> None:
    with Session(get_engine()) as session:
        fresh = seed(session, today=today_jst())
        with_password = set_seed_passwords(session, get_settings().seed_password)
        session.commit()
    # 名前などは出さない（ログに個人情報を出さない決まり。架空でも同じにしておく）
    print("初期データを入れました" if fresh else "人はもう入っていたので、足りないものを足しました")
    if with_password:
        print(f"{with_password} 人に SEED_PASSWORD のパスワードを入れました")


if __name__ == "__main__":
    main()
