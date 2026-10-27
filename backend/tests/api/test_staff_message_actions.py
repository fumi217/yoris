"""「自分が対応する」とアプリでの返事の API のテスト（spec 004 の 004-T026・T027。T023 の残り）。

FR-012・FR-012b・FR-014・FR-017・FR-018・SC-008。
メールは送らない（send_email_now を記録だけにする）。2 人がほぼ同時に押す・返事をするテストは、
本当に commit する 2 本のスレッドが要るので、tests/services/test_staff_message_actions.py に置く。
"""

import pytest
from sqlalchemy import func, select

from app.models.core import User
from app.models.inquiry import (
    InquiryConversation,
    InquiryMessage,
    StaffMessage,
    StaffMessageEvent,
    StaffMessageTemplate,
)
from app.models.notifications import EmailOutbox, Notification
from app.seed.inquiry import add_staff_message_templates

FAMILY_URL = "/api/family/inquiry/messages"


@pytest.fixture
def sent_emails(monkeypatch) -> list[int]:
    """メールは送らず、送ろうとした email_outbox の id を記録する（commit のあとに呼ぶ。R-09）。"""
    sent: list[int] = []
    monkeypatch.setattr("app.api.staff.messages.send_email_now", sent.append)
    return sent


@pytest.fixture
def world(session, redis, make_family, make_staff, login_as, client, sent_emails):
    add_staff_message_templates(session)
    family = make_family()
    conversation = InquiryConversation(family_account_id=family.id, resident_id=family.resident_id)
    session.add(conversation)
    session.flush()

    def add_message(category: str = "care_request", *, assignee=None) -> StaffMessage:
        origin = InquiryMessage(
            conversation_id=conversation.id, sender="family", body="冬の上着を渡したいです"
        )
        session.add(origin)
        session.flush()
        message = StaffMessage(
            conversation_id=conversation.id,
            resident_id=family.resident_id,
            origin_message_id=origin.id,
            category=category,
            summary="上着の渡し方",
            assignee_id=assignee.id if assignee else None,
        )
        session.add(message)
        session.flush()
        return message

    def template_ids(category: str) -> list[int]:
        return list(
            session.scalars(
                select(StaffMessageTemplate.id)
                .where(StaffMessageTemplate.category == category)
                .order_by(StaffMessageTemplate.sort_order)
            )
        )

    def login(role: str = "care_worker", name: str | None = None):
        staff = make_staff(role=role, display_name=name or f"職員{role}")
        login_as(staff.user_id)
        return staff

    return {
        "family": family,
        "add_message": add_message,
        "template_ids": template_ids,
        "login": login,
        "login_as": login_as,
        "make_staff": make_staff,
    }


def _assign(client, message_id):
    return client.post(f"/api/staff/messages/{message_id}/assign")


def _reply(client, message_id, **body):
    return client.post(f"/api/staff/messages/{message_id}/reply", json=body)


def _events(session, message_id) -> list[StaffMessageEvent]:
    return list(
        session.scalars(
            select(StaffMessageEvent)
            .where(StaffMessageEvent.staff_message_id == message_id)
            .order_by(StaffMessageEvent.id)
        )
    )


# --- 自分が対応する（T026） ---


def test_assign_makes_me_the_assignee_and_keeps_a_record(client, session, world):
    staff = world["login"]("care_worker")
    message = world["add_message"]()

    assert _assign(client, message.id).status_code == 204

    session.refresh(message)
    assert message.assignee_id == staff.id
    # 担当になったことが残る（だれがいつ。FR-012b）
    [event] = _events(session, message.id)
    assert (event.type, event.staff_id, event.to_value) == ("assigned", staff.id, str(staff.id))
    detail = client.get(f"/api/staff/messages/{message.id}").json()
    assert detail["assignee"]["id"] == staff.id


def test_assign_again_is_ok_when_already_mine(client, session, world):
    world["login"]("care_worker")
    message = world["add_message"]()
    assert _assign(client, message.id).status_code == 204

    # 何度押しても同じ。履歴は 1 つのまま
    assert _assign(client, message.id).status_code == 204
    assert len(_events(session, message.id)) == 1


def test_assign_when_someone_else_is_assigned_is_409(client, session, world):
    other = world["make_staff"](role="care_worker", display_name="先の職員")
    message = world["add_message"](assignee=other)
    world["login"]("leader")

    response = _assign(client, message.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_assigned"
    session.refresh(message)
    assert message.assignee_id == other.id


def test_assign_unknown_message_is_404(client, world):
    world["login"]()

    assert _assign(client, 999_999_999).status_code == 404


def test_complaint_cannot_be_assigned_by_other_roles(client, session, world):
    message = world["add_message"]("complaint")
    for role in ("care_worker", "leader", "clerk"):
        world["login"](role)
        # 見られない苦情は 404（あるかどうかも知らせない。FR-018）
        assert _assign(client, message.id).status_code == 404
    session.refresh(message)
    assert message.assignee_id is None

    staff = world["login"]("counselor")
    assert _assign(client, message.id).status_code == 204
    session.refresh(message)
    assert message.assignee_id == staff.id


def test_clerk_can_take_a_money_message(client, session, world):
    # 事務員はお金・書類の対応をする（管理画面から入る。FR-012）
    staff = world["login"]("clerk")
    message = world["add_message"]("money")

    assert _assign(client, message.id).status_code == 204

    session.refresh(message)
    assert message.assignee_id == staff.id


def test_family_and_logged_out_cannot_assign_or_reply(client, world):
    message = world["add_message"]()

    # ログインしていない
    assert _assign(client, message.id).status_code == 401
    assert _reply(client, message.id, template_ids=[1]).status_code == 401
    # 家族は職員の API を呼べない
    world["login_as"](world["family"].user_id)
    assert _assign(client, message.id).status_code == 403
    assert _reply(client, message.id, template_ids=[1]).status_code == 403


# --- アプリで返事（T027） ---


def test_reply_answers_the_message_and_makes_the_replier_the_assignee(
    client, session, world, sent_emails
):
    staff = world["login"]("care_worker", "山本")
    message = world["add_message"]("care_request")
    ids = world["template_ids"]("care_request")

    response = _reply(client, message.id, template_ids=ids[:2], note="冬の上着をお預かりします")

    assert response.status_code == 201
    data = response.json()
    assert (data["staff_message_id"], data["status"]) == (message.id, "answered")
    session.refresh(message)
    # 対応済みになり、対応した職員・日時が残り、返した職員が担当になる（FR-014・FR-012b）
    assert message.status == "answered"
    assert message.responded_by == staff.id
    assert message.responded_at is not None
    assert message.assignee_id == staff.id
    # 家族の会話に、職員の発言が足される。定型文は code で持つ（本文は空）
    reply = session.get(InquiryMessage, data["id"])
    assert (reply.sender, reply.body, reply.staff_id) == ("staff", "", staff.id)
    assert reply.template_ids == ids[:2]
    assert (reply.note, reply.response_type, reply.staff_message_id) == (
        "冬の上着をお預かりします",
        "app",
        message.id,
    )
    # 担当が空だった → 返した人が担当になったことと、対応したことが残る
    assert [e.type for e in _events(session, message.id)] == ["assigned", "answered"]


def test_reply_makes_family_notice_and_email_without_the_content(
    client, session, world, sent_emails
):
    world["login"]("care_worker")
    message = world["add_message"]("care_request")
    ids = world["template_ids"]("care_request")

    _reply(client, message.id, template_ids=ids[:1], note="ひみつの書き足しの文")

    # アプリ内のお知らせ（家族の通知設定に関係なく）
    [notice] = session.scalars(
        select(Notification).where(Notification.staff_message_id == message.id)
    ).all()
    assert (notice.kind, notice.family_account_id) == ("staff_message_reply", world["family"].id)
    # メールの送る予定。返事の中身（書き足し・質問・要約）は入れない（SC-010）
    email = session.get(User, world["family"].user_id).email
    outbox = session.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.to_email == email, EmailOutbox.template == "staff_message_reply")
        .order_by(EmailOutbox.id.desc())
    ).first()
    assert outbox is not None
    assert "ひみつの書き足しの文" not in str(outbox.params)
    assert "上着" not in str(outbox.params)
    # commit のあとに、その場で送る（行を指定して。R-09）
    assert sent_emails == [outbox.id]


def test_reply_by_another_staff_member_takes_over_the_assignment(client, session, world):
    first = world["make_staff"](role="care_worker", display_name="担当だった職員")
    message = world["add_message"]("care_request", assignee=first)
    staff = world["login"]("leader")
    ids = world["template_ids"]("care_request")

    assert _reply(client, message.id, template_ids=ids[:1]).status_code == 201

    session.refresh(message)
    assert message.assignee_id == staff.id
    # 担当が変わったことも残す（前の担当 → 返した職員）
    events = _events(session, message.id)
    assert [e.type for e in events] == ["reassigned", "answered"]
    assert (events[0].from_value, events[0].to_value) == (str(first.id), str(staff.id))


def test_reply_by_the_assignee_keeps_the_assignment_record_short(client, session, world):
    staff = world["login"]("care_worker")
    message = world["add_message"]("care_request", assignee=staff)
    ids = world["template_ids"]("care_request")

    _reply(client, message.id, template_ids=ids[:1])

    # もう担当の人が返したときは、担当の履歴を足さず、対応したことだけ残す
    assert [e.type for e in _events(session, message.id)] == ["answered"]


def test_second_reply_is_409_and_makes_no_second_notice(client, session, world, sent_emails):
    world["login"]("care_worker")
    message = world["add_message"]("care_request")
    ids = world["template_ids"]("care_request")
    assert _reply(client, message.id, template_ids=ids[:1]).status_code == 201
    world["login"]("leader")

    response = _reply(client, message.id, template_ids=ids[1:2])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_answered"
    # 先の返事だけが有効。お知らせ・メール・会話の発言は 1 つのまま
    assert (
        session.scalar(
            select(func.count(Notification.id)).where(Notification.staff_message_id == message.id)
        )
        == 1
    )
    assert len(sent_emails) == 1
    assert (
        session.scalar(
            select(func.count(InquiryMessage.id)).where(
                InquiryMessage.staff_message_id == message.id, InquiryMessage.sender == "staff"
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    "body",
    [
        {"template_ids": []},  # 定型文は 1 つ以上
        {"template_ids": [999_999_999]},  # ない定型文
        {"note": "書き足しだけ"},  # 定型文がない
        {"template_ids": "x"},
        {"template_ids": [1], "status": "waiting"},  # 余分な項目
    ],
)
def test_invalid_reply_is_422(client, session, world, body):
    world["login"]("care_worker")
    message = world["add_message"]("care_request")

    response = _reply(client, message.id, **body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    session.refresh(message)
    assert message.status == "waiting"


def test_note_over_100_chars_is_422_and_exactly_100_is_ok(client, world):
    world["login"]("care_worker")
    ids = world["template_ids"]("care_request")

    first = world["add_message"]("care_request")
    second = world["add_message"]("care_request")

    too_long = _reply(client, first.id, template_ids=ids[:1], note="あ" * 101)
    ok = _reply(client, second.id, template_ids=ids[:1], note="あ" * 100)

    assert too_long.status_code == 422
    assert ok.status_code == 201


def test_template_of_another_category_is_422(client, session, world):
    world["login"]("care_worker")
    message = world["add_message"]("care_request")
    money = world["template_ids"]("money")

    response = _reply(client, message.id, template_ids=money[:1])

    # その種類の定型文だけ選べる（FR-014）
    assert response.status_code == 422
    session.refresh(message)
    assert message.status == "waiting"


def test_complaint_has_no_templates_so_it_is_answered_by_phone(client, session, world):
    message = world["add_message"]("complaint")
    ids = world["template_ids"]("care_request")

    # 見られない役割には 404（苦情があることも知らせない）
    world["login"]("care_worker")
    assert _reply(client, message.id, template_ids=ids[:1]).status_code == 404
    # 見られる役割でも、苦情には定型文がない（電話で対応する。FR-014）ので、アプリでは返せない
    world["login"]("counselor")
    assert _reply(client, message.id, template_ids=ids[:1]).status_code == 422
    session.refresh(message)
    assert message.status == "waiting"


def test_reply_to_unknown_message_is_404(client, world):
    world["login"]()

    assert _reply(client, 999_999_999, template_ids=[1]).status_code == 404


def test_assigning_and_replying_send_no_notification_to_staff(client, session, world):
    # 職員への通知・音は出さない（SC-008）。お知らせは家族に 1 つだけで、職員向けの行は作らない
    world["login"]("care_worker")
    message = world["add_message"]("care_request")
    before = session.scalar(select(func.count(Notification.id)))
    _assign(client, message.id)
    assert session.scalar(select(func.count(Notification.id))) == before

    _reply(client, message.id, template_ids=world["template_ids"]("care_request")[:1])

    assert session.scalar(select(func.count(Notification.id))) == before + 1


# --- 家族の会話に出る ---


def test_family_sees_the_reply_with_the_display_name(client, session, world):
    world["login"]("care_worker", "山本")
    message = world["add_message"]("care_request")
    ids = world["template_ids"]("care_request")
    _reply(client, message.id, template_ids=ids[:2], note="冬の上着をお預かりします")

    world["login_as"](world["family"].user_id)
    messages = client.get(FAMILY_URL).json()

    [staff_message] = [m for m in messages if m["sender"] == "staff"]
    # 役割ではなく表示名で出す。定型文はコード（文言は画面の辞書）。書き足しは文字のまま
    assert staff_message["staff_name"] == "山本"
    codes = dict(
        session.execute(
            select(StaffMessageTemplate.id, StaffMessageTemplate.code).where(
                StaffMessageTemplate.id.in_(ids[:2])
            )
        ).all()
    )
    assert staff_message["template_codes"] == [codes[i] for i in ids[:2]]
    assert staff_message["note"] == "冬の上着をお預かりします"
    assert staff_message["response_type"] == "app"
    assert staff_message["body"] == ""
