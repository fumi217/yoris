"""返事のお知らせとメールの送る予定（001-T051）のテスト。

ふつうのテストは tests/conftest.py の session を使う（テストごとに取り消す）。
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disclosure import ReplyTemplate, Theme
from app.models.notifications import EmailOutbox, Notification
from app.models.requests import Request
from app.seed.themes import add_themes
from app.services.notifications import create_reply_notice
from app.services.replies import save_reply

NOTE = "ひみつの書き足しの文"


@pytest.fixture
def world(session: Session, make_staff, make_family):
    add_themes(session)
    theme = session.scalars(select(Theme).where(Theme.code == "theme.daily_life")).one()
    template_ids = list(
        session.scalars(select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id))
    )
    staff = make_staff(display_name="ひみつの職員名")
    family = make_family(display_name="ひみつの入居者名")
    other_family = make_family(display_name="べつの入居者")
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    reply = save_reply(
        session,
        request_id=request.id,
        staff_id=staff.id,
        template_ids=template_ids[:2],
        note=NOTE,
    )
    return {"family": family, "other_family": other_family, "reply": reply}


def test_creates_notification_and_outbox_for_the_family(session, world):
    outbox_id = create_reply_notice(session, world["reply"].id)

    notification = session.scalars(select(Notification)).one()
    assert notification.kind == "reply"
    assert notification.reply_id == world["reply"].id
    assert notification.family_account_id == world["family"].id
    assert notification.read_at is None

    outbox = session.get(EmailOutbox, outbox_id)
    assert outbox is not None
    assert outbox.template == "reply"
    assert outbox.sent_at is None
    assert outbox.to_email.endswith("@example.test")


def test_returns_the_outbox_id(session, world):
    outbox_id = create_reply_notice(session, world["reply"].id)

    assert isinstance(outbox_id, int)
    assert session.scalars(select(EmailOutbox.id)).one() == outbox_id


def _app_url(monkeypatch: pytest.MonkeyPatch, url: str | None) -> None:
    """アプリの URL（APP_BASE_URL）を、このテストの中だけ決める。"""
    monkeypatch.setattr(
        "app.services.notifications.get_settings", lambda: SimpleNamespace(app_base_url=url)
    )


def test_outbox_params_have_only_the_link(session, world, monkeypatch):
    _app_url(monkeypatch, "http://app.test")
    outbox_id = create_reply_notice(session, world["reply"].id)

    params = session.get(EmailOutbox, outbox_id).params
    assert params == {"link": "http://app.test/family"}
    # 返事の中身・職員の名前・入居者の名前は、メールの材料に入らない（SC-010）
    text = json.dumps(params, ensure_ascii=False)
    for secret in (NOTE, "ひみつの職員名", "ひみつの入居者名"):
        assert secret not in text


def test_no_link_when_the_app_url_is_not_set(session, world, monkeypatch):
    # リンクを入れないと、メールの文面の側が、アプリの URL に戻る（開けないリンクにならない）
    _app_url(monkeypatch, None)
    outbox_id = create_reply_notice(session, world["reply"].id)

    assert session.get(EmailOutbox, outbox_id).params == {}


def test_other_family_gets_nothing(session, world):
    create_reply_notice(session, world["reply"].id)

    families = set(session.scalars(select(Notification.family_account_id)))
    assert families == {world["family"].id}
    assert world["other_family"].id not in families


def test_does_not_commit(session, world):
    # 呼んだ API が最後に 1 回だけ commit する。ここでは、まだ確定していない（flush だけ）
    create_reply_notice(session, world["reply"].id)

    assert session.in_transaction()
    session.rollback()
    assert session.scalars(select(Notification)).first() is None
    assert session.scalars(select(EmailOutbox)).first() is None
