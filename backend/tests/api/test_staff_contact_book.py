"""職員の連絡帳の見返しの API（001-T029）のテスト。

tests/conftest.py の client・session・make_staff・make_family・login_as を使う。
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.clock import today_jst
from app.models.disclosure import DisclosureSetting, ReplyTemplate, Theme
from app.models.records import CareRecord
from app.models.requests import Request
from app.seed.themes import add_themes
from app.services.replies import save_reply


def _url(resident_id):
    return f"/api/staff/residents/{resident_id}/contact-book"


def _record(session, resident_id, staff_id, item, slot, value, day=None):
    record = CareRecord(
        resident_id=resident_id,
        date=day or today_jst(),
        item=item,
        slot=slot,
        value=value,
        recorded_by=staff_id,
    )
    session.add(record)
    session.flush()
    return record


@pytest.fixture
def world(session, make_staff, make_family, login_as):
    family = make_family(name="テスト 花子")
    staff = make_staff(display_name="職員A")
    login_as(staff.user_id)
    return {"family": family, "staff": staff}


def test_records_of_the_day_in_time_order(client, session, world):
    resident, staff = world["family"].resident_id, world["staff"].id
    first = _record(session, resident, staff, "meal", "breakfast", "8")
    second = _record(session, resident, staff, "mood", "day", "smile")
    # ほかの日・取り消した記録は出ない
    _record(session, resident, staff, "meal", "lunch", "5", day=today_jst() - timedelta(days=1))
    deleted = _record(session, resident, staff, "meal", "dinner", "0")
    deleted.deleted_at = deleted.recorded_at
    session.flush()

    response = client.get(_url(resident))

    assert response.status_code == 200
    data = response.json()
    assert data["date"] == today_jst().isoformat()
    assert data["resident"]["display_name"] == "テスト 花子"
    assert [r["id"] for r in data["records"]] == [first.id, second.id]
    assert data["records"][0]["recorded_by_name"] == "職員A"


def test_hidden_items_are_shown_to_staff(client, session, world):
    # 家族には見せない設定の項目も、職員には出す（R-06）
    resident, staff = world["family"].resident_id, world["staff"].id
    session.execute(
        DisclosureSetting.__table__.update()
        .where(DisclosureSetting.target_type == "item")
        .values(visible=False)
    )
    record = _record(session, resident, staff, "sleep", "day", "poor")

    data = client.get(_url(resident)).json()

    assert [r["id"] for r in data["records"]] == [record.id]


def test_replies_of_the_day(client, session, world):
    add_themes(session)
    theme = session.scalars(select(Theme).where(Theme.code == "theme.meals")).one()
    template = session.scalars(
        select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id)
    ).first()
    request = Request(resident_id=world["family"].resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    save_reply(
        session,
        request_id=request.id,
        staff_id=world["staff"].id,
        template_ids=[template],
        note="<b>よく召し上がっていました</b>",
    )

    data = client.get(_url(world["family"].resident_id)).json()

    [reply] = data["replies"]
    assert reply["theme_code"] == "theme.meals"
    assert reply["replied_by_name"] == "職員A"
    # 書き足した文は、文字としてそのまま返る
    assert reply["note"] == "<b>よく召し上がっていました</b>"


def test_other_day_by_query(client, session, world):
    resident, staff = world["family"].resident_id, world["staff"].id
    yesterday = today_jst() - timedelta(days=1)
    record = _record(session, resident, staff, "meal", "lunch", "5", day=yesterday)

    data = client.get(_url(resident), params={"date": yesterday.isoformat()}).json()

    assert data["date"] == yesterday.isoformat()
    assert [r["id"] for r in data["records"]] == [record.id]


def test_unknown_resident_is_404(client, world):
    assert client.get(_url(999_999_999)).status_code == 404


def test_clerk_and_family_cannot_open(client, world, make_staff, login_as):
    login_as(make_staff(role="clerk").user_id)
    assert client.get(_url(world["family"].resident_id)).status_code == 403

    login_as(world["family"].user_id)
    assert client.get(_url(world["family"].resident_id)).status_code == 403
