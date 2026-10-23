"""リクエストのサンプル（001-T058）のテスト。DB を使う（なければ手元では飛ばす）。"""

from sqlalchemy import func, select

from app.models.disclosure import Theme
from app.models.requests import Request
from app.seed.requests import add_sample_requests


def _themes(session, count=3) -> list[int]:
    base = session.scalar(select(func.coalesce(func.max(Theme.sort_order), 0))) + 1
    themes = [
        Theme(code=f"theme.seed_{base}_{n}", emoji="😊", sort_order=base + n) for n in range(count)
    ]
    session.add_all(themes)
    session.flush()
    return [theme.id for theme in themes]


def test_sample_has_waiting_and_cancelled_but_no_answered(session, make_family):
    family = make_family()

    added = add_sample_requests(
        session, resident_ids=[family.resident_id], theme_ids=_themes(session)
    )

    statuses = sorted(
        session.scalars(select(Request.status).where(Request.resident_id == family.resident_id))
    )
    assert added == 3
    assert statuses == ["cancelled", "waiting", "waiting"]


def test_sample_respects_the_rules(session, make_family):
    # 返事待ちは 3 件まで・同じテーマは 1 件まで。サンプルも決まりの中に収まる
    family = make_family()
    add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=_themes(session))

    waiting = list(
        session.scalars(
            select(Request).where(
                Request.resident_id == family.resident_id, Request.status == "waiting"
            )
        )
    )
    assert len(waiting) <= 3
    assert len({request.theme_id for request in waiting}) == len(waiting)


def test_sample_is_not_added_twice(session, make_family):
    family = make_family()
    theme_ids = _themes(session)
    add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=theme_ids)

    assert add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=theme_ids) == 0


def test_sample_needs_enough_themes(session, make_family):
    family = make_family()

    assert add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=[1, 2]) == 0
