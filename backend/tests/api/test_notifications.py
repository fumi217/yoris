"""家族のお知らせの API（001-T056）のテスト。

001-T045 の「ほかの家族の返事の id では既読にできない（404）」を含む。

返事を保存すると、同じトランザクションでお知らせとメールができる（001-T045 の残り）は、
ゆうの返事の API が create_reply_notice（#198）を呼ぶようになってから、ここに足す。

DB と Redis を使う（conftest.py の client・session・redis・make_family・make_staff・login_as）。
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.models.disclosure import ReplyTemplate, Theme
from app.models.notifications import Notification
from app.models.replies import Reply
from app.models.requests import Request
from app.seed.themes import add_themes
from app.services.replies import save_reply


@pytest.fixture
def world(session: Session, make_family, make_staff, login_as, client):
    add_themes(session)
    mine = make_family()
    other = make_family(display_name="べつの入居者")
    staff = make_staff()
    login_as(mine.user_id)
    return {"client": client, "mine": mine, "other": other, "staff": staff}


def _reply_with_notice(session: Session, family, staff, note: str | None = None) -> Reply:
    theme = session.scalars(select(Theme).where(Theme.code == "theme.daily_life")).one()
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    template_id = session.scalars(
        select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id)
    ).first()
    reply = save_reply(
        session, request_id=request.id, staff_id=staff.id, template_ids=[template_id], note=note
    )
    # 返事のお知らせ（create_reply_notice が作るものと同じ行）を、直接作る
    session.add(Notification(family_account_id=family.id, kind="reply", reply_id=reply.id))
    session.commit()
    return reply


# --- ログイン・役割 ---


def test_not_logged_in_is_401(client):
    assert client.get("/api/family/notifications").status_code == 401
    assert client.post("/api/family/replies/1/read").status_code == 401


def test_staff_cannot_use_the_family_api(client, make_staff, login_as):
    login_as(make_staff("care_worker").user_id)

    assert client.get("/api/family/notifications").status_code == 403
    assert client.post("/api/family/replies/1/read").status_code == 403


# --- お知らせの一覧 ---


def test_list_has_only_my_notifications_newest_first(world, session):
    first = _reply_with_notice(session, world["mine"], world["staff"])
    second = _reply_with_notice(session, world["mine"], world["staff"])
    _reply_with_notice(session, world["other"], world["staff"])

    body = world["client"].get("/api/family/notifications").json()

    assert [item["reply_id"] for item in body] == [second.id, first.id]
    assert {item["kind"] for item in body} == {"reply"}
    assert [item["read"] for item in body] == [False, False]


def test_list_has_no_reply_content(world, session):
    _reply_with_notice(session, world["mine"], world["staff"], note="ひみつの書き足しの文")

    text = world["client"].get("/api/family/notifications").text

    # 一覧は、種類・日時・既読と id だけ。返事の中身・職員の名前は出さない（SC-010）
    assert "ひみつの書き足しの文" not in text
    assert world["staff"].display_name not in text


# --- 返事を読んだ ---


def test_reading_a_reply_marks_the_reply_and_its_notice_read(world, session):
    reply = _reply_with_notice(session, world["mine"], world["staff"])

    assert world["client"].post(f"/api/family/replies/{reply.id}/read").status_code == 204

    session.refresh(reply)
    assert reply.read_at is not None
    notice = session.scalars(select(Notification).where(Notification.reply_id == reply.id)).one()
    assert notice.read_at is not None
    body = world["client"].get("/api/family/notifications").json()
    assert [item["read"] for item in body] == [True]


def test_reading_twice_keeps_the_first_time(world, session):
    reply = _reply_with_notice(session, world["mine"], world["staff"])
    world["client"].post(f"/api/family/replies/{reply.id}/read")
    session.refresh(reply)
    first_time = reply.read_at

    assert world["client"].post(f"/api/family/replies/{reply.id}/read").status_code == 204

    session.refresh(reply)
    assert reply.read_at == first_time


def test_other_family_reply_is_404_and_stays_unread(world, session):
    reply = _reply_with_notice(session, world["other"], world["staff"])

    assert world["client"].post(f"/api/family/replies/{reply.id}/read").status_code == 404

    session.refresh(reply)
    assert reply.read_at is None


def test_unknown_reply_is_404(world):
    assert world["client"].post("/api/family/replies/999999999/read").status_code == 404


def test_family_without_resident_is_403(client):
    # 入居者に紐づいていない家族は、ほかの家族と混ざらないよう、どちらの API も 403
    # （ふだんはログインの時点で弾かれるので、チェックの関数を差し替えて確かめる）
    unlinked = CurrentUser(
        user_id=1,
        kind="family",
        role=None,
        staff_id=None,
        resident_id=None,
        language="ja",
        display_name="紐づいていない家族",
    )
    client.app.dependency_overrides[require_family] = lambda: unlinked
    try:
        assert client.get("/api/family/notifications").status_code == 403
        assert client.post("/api/family/replies/1/read").status_code == 403
    finally:
        client.app.dependency_overrides.pop(require_family, None)
