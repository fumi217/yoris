"""職員の返事の API（001-T053）のテスト（001-T044）。

tests/conftest.py の client・session・make_staff・make_family・login_as を使う。
2 人がほぼ同時に返事をする場面は、tests/services/test_replies_service.py で
2 本のスレッドで確かめる。
"""

import pytest
from sqlalchemy import func, select

from app.api.staff import requests as requests_api
from app.models.disclosure import ReplyTemplate, Theme
from app.models.notifications import EmailOutbox, Notification
from app.models.replies import Reply
from app.models.requests import Request
from app.seed.themes import add_themes


@pytest.fixture(autouse=True)
def sent(monkeypatch) -> list[int]:
    """メールを送る関数を差し替える（本物のメールは送らない）。

    呼ばれた email_outbox の id が入る。
    """
    calls: list[int] = []
    monkeypatch.setattr(requests_api, "send_email_now", calls.append)
    return calls


@pytest.fixture
def world(session, make_staff, make_family, login_as):
    add_themes(session)
    theme = session.scalars(select(Theme).where(Theme.code == "theme.daily_life")).one()
    other = session.scalars(select(Theme).where(Theme.code == "theme.meals")).one()
    family = make_family()
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    staff = make_staff(display_name="職員A")
    login_as(staff.user_id)
    templates = session.scalars(
        select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id)
    ).all()
    other_templates = session.scalars(
        select(ReplyTemplate.id).where(ReplyTemplate.theme_id == other.id)
    ).all()
    return {
        "family": family,
        "request": request,
        "staff": staff,
        "templates": list(templates),
        "other_templates": list(other_templates),
    }


def _reply(client, request_id, **body):
    return client.post(f"/api/staff/requests/{request_id}/reply", json=body)


def test_reply_is_saved_and_request_is_answered(client, session, world):
    response = _reply(client, world["request"].id, template_ids=world["templates"][:2])

    assert response.status_code == 201
    data = response.json()
    assert data["template_ids"] == world["templates"][:2]
    session.refresh(world["request"])
    assert world["request"].status == "answered"
    reply = session.get(Reply, data["id"])
    assert reply.replied_by == world["staff"].id


def test_second_reply_is_409_already_replied(client, world):
    assert (
        _reply(client, world["request"].id, template_ids=world["templates"][:1]).status_code == 201
    )

    response = _reply(client, world["request"].id, template_ids=world["templates"][1:2])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_replied"


def test_cancelled_request_is_409_request_cancelled(client, session, world):
    world["request"].status = "cancelled"
    session.flush()

    response = _reply(client, world["request"].id, template_ids=world["templates"][:1])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "request_cancelled"


def test_script_in_note_is_returned_as_text(client, world):
    note = "<script>alert(1)</script>"

    response = _reply(client, world["request"].id, template_ids=world["templates"][:1], note=note)

    # 文字として、そのまま返る（画面でも文字としてだけ出す。SC-009）
    assert response.status_code == 201
    assert response.json()["note"] == note


@pytest.mark.parametrize(
    "body",
    [
        {"template_ids": []},  # 定型文は 1 つ以上
        {"template_ids": [1], "note": "あ" * 101},  # 書き足しは 100 文字まで
        {"template_ids": [1], "staff_id": 1},  # 余分な項目
    ],
)
def test_invalid_body_is_422(client, world, body):
    if body.get("template_ids"):
        body["template_ids"] = world["templates"][:1]

    assert _reply(client, world["request"].id, **body).status_code == 422


def test_template_of_another_theme_is_422(client, world):
    response = _reply(client, world["request"].id, template_ids=world["other_templates"][:1])

    assert response.status_code == 422


def test_unknown_request_is_404(client, world):
    assert _reply(client, 999_999_999, template_ids=world["templates"][:1]).status_code == 404


def test_waiting_requests_list(client, session, world):
    answered = Request(
        resident_id=world["family"].resident_id,
        theme_id=session.scalars(select(Theme.id).where(Theme.code == "theme.meals")).one(),
        status="answered",
    )
    session.add(answered)
    session.flush()

    response = client.get(f"/api/staff/residents/{world['family'].resident_id}/requests")

    assert response.status_code == 200
    data = response.json()
    # 返事待ちだけ。テーマと、そのテーマの定型文が付く
    assert [r["id"] for r in data["requests"]] == [world["request"].id]
    request = data["requests"][0]
    assert request["theme_code"] == "theme.daily_life"
    assert [t["id"] for t in request["templates"]] == world["templates"]
    assert request["days"] == 0
    assert data["waiting_messages"] == 0


def test_clerk_and_family_cannot_reply(client, world, make_staff, login_as):
    login_as(make_staff(role="clerk").user_id)
    assert (
        _reply(client, world["request"].id, template_ids=world["templates"][:1]).status_code == 403
    )

    login_as(world["family"].user_id)
    assert (
        _reply(client, world["request"].id, template_ids=world["templates"][:1]).status_code == 403
    )


def test_reply_creates_notice_and_mail(client, session, world, sent):
    # 返事を保存すると、同じトランザクションで家族へのお知らせとメールの送る予定ができ、
    # commit のあとにその場で送る（001-T045 の一部・R-09）
    response = _reply(client, world["request"].id, template_ids=world["templates"][:1], note="秘密")

    assert response.status_code == 201
    reply_id = response.json()["id"]
    [notice] = session.scalars(select(Notification).where(Notification.reply_id == reply_id)).all()
    assert notice.kind == "reply"
    assert notice.family_account_id == world["family"].id
    [outbox] = session.scalars(select(EmailOutbox).where(EmailOutbox.id.in_(sent))).all()
    assert outbox.template == "reply"
    # メールには返事の中身を渡さない（SC-010）。APP_BASE_URL がないときは link も入らない（#198）
    assert set(outbox.params) <= {"link"}
    assert "秘密" not in str(outbox.params)


def test_second_reply_adds_no_notice(client, session, world, sent):
    _reply(client, world["request"].id, template_ids=world["templates"][:1])

    assert (
        _reply(client, world["request"].id, template_ids=world["templates"][1:2]).status_code == 409
    )

    notices = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.family_account_id == world["family"].id)
    )
    assert notices == 1
    assert len(sent) == 1
