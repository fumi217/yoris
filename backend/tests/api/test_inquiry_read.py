"""職員の返事の発言を見たときの既読の API のテスト（Issue #244・spec 004 contracts/api.md）。

`POST /api/family/inquiry/messages/{id}/read`：その発言のお知らせ（kind = staff_message_reply）を
読んだことにする。読んだことにするのは、その発言と同じ staff_message_id で、その発言の日時までに
作られた、同じ家族の未読のお知らせ。
テストは 1 本が 1 つのトランザクションなので、now() は全部同じ時刻になる。時刻の前後を見る
テストは、created_at を自分で決めて行を作る。
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.inquiry import (
    InquiryConversation,
    InquiryMessage,
    StaffMessage,
    StaffMessageTemplate,
)
from app.models.notifications import Notification
from app.seed.inquiry import add_staff_message_templates

T0 = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)


def read_url(message_id: int) -> str:
    return f"/api/family/inquiry/messages/{message_id}/read"


@pytest.fixture
def world(session, redis, make_family, make_staff, login_as, client):
    add_staff_message_templates(session)
    family = make_family()
    conversation = InquiryConversation(family_account_id=family.id, resident_id=family.resident_id)
    session.add(conversation)
    session.flush()

    def add_staff_message() -> StaffMessage:
        origin = InquiryMessage(conversation_id=conversation.id, sender="family", body="質問です")
        session.add(origin)
        session.flush()
        message = StaffMessage(
            conversation_id=conversation.id,
            resident_id=family.resident_id,
            origin_message_id=origin.id,
            category="care_request",
            summary="要約",
        )
        session.add(message)
        session.flush()
        return message

    def add_reply(
        message: StaffMessage, at: datetime, *, response_type: str = "app", notice: bool = True
    ) -> tuple[InquiryMessage, Notification | None]:
        """職員の返事の発言と、そのお知らせを、同じ時刻で作る（reply_in_app と同じ）。"""
        reply = InquiryMessage(
            conversation_id=conversation.id,
            sender="staff",
            body="",
            response_type=response_type,
            staff_message_id=message.id,
            created_at=at,
        )
        session.add(reply)
        notification = None
        if notice:
            notification = Notification(
                family_account_id=family.id,
                kind="staff_message_reply",
                staff_message_id=message.id,
                created_at=at,
            )
            session.add(notification)
        session.flush()
        return reply, notification

    return {
        "family": family,
        "conversation": conversation,
        "add_staff_message": add_staff_message,
        "add_reply": add_reply,
        "login_family": lambda: login_as(family.user_id),
        "make_staff": make_staff,
        "make_family": make_family,
        "login_as": login_as,
    }


def test_reading_a_staff_reply_marks_its_notice_read(client, session, world):
    message = world["add_staff_message"]()
    reply, notice = world["add_reply"](message, T0)
    world["login_family"]()

    response = client.post(read_url(reply.id))

    assert response.status_code == 204
    session.refresh(notice)
    assert notice.read_at is not None


def test_reading_commits_once(client, session, world, monkeypatch):
    """テストの session は commit しなくても変更が見えるので、commit を数えて確かめる。

    get_session は commit しない（app/db.py）。呼ばないと、本番では応答のあとに取り消される。
    """
    message = world["add_staff_message"]()
    reply, _ = world["add_reply"](message, T0)
    world["login_family"]()
    commits: list[str] = []
    real_commit = session.commit
    monkeypatch.setattr(session, "commit", lambda: (commits.append("commit"), real_commit())[1])

    assert client.post(read_url(reply.id)).status_code == 204
    assert commits == ["commit"]

    # 見つからなかったとき（404）は、何も書かないので、commit まで進まない
    commits.clear()
    assert client.post(read_url(999999)).status_code == 404
    assert commits == []


def test_reading_again_changes_nothing(client, session, world):
    message = world["add_staff_message"]()
    reply, notice = world["add_reply"](message, T0)
    world["login_family"]()
    client.post(read_url(reply.id))
    session.refresh(notice)
    first = notice.read_at

    assert client.post(read_url(reply.id)).status_code == 204

    session.refresh(notice)
    assert notice.read_at == first


def test_two_replies_to_one_message_are_read_one_by_one(client, session, world):
    message = world["add_staff_message"]()
    first_reply, first_notice = world["add_reply"](message, T0)
    second_reply, second_notice = world["add_reply"](message, T0 + timedelta(hours=2))
    world["login_family"]()

    # 前の返事だけ見たときは、前の分だけが読んだことになる
    assert client.post(read_url(first_reply.id)).status_code == 204
    session.refresh(first_notice)
    session.refresh(second_notice)
    assert first_notice.read_at is not None
    assert second_notice.read_at is None

    # 後の返事を見れば、後の分も（前の分は、すでに読んだまま）
    assert client.post(read_url(second_reply.id)).status_code == 204
    session.refresh(second_notice)
    assert second_notice.read_at is not None


def test_seeing_the_later_reply_also_reads_the_earlier_notice(client, session, world):
    message = world["add_staff_message"]()
    _, first_notice = world["add_reply"](message, T0)
    second_reply, second_notice = world["add_reply"](message, T0 + timedelta(hours=2))
    world["login_family"]()

    assert client.post(read_url(second_reply.id)).status_code == 204

    session.refresh(first_notice)
    session.refresh(second_notice)
    assert first_notice.read_at is not None
    assert second_notice.read_at is not None


def test_other_messages_notices_stay_unread(client, session, world):
    first = world["add_staff_message"]()
    second = world["add_staff_message"]()
    reply, notice = world["add_reply"](first, T0)
    _, other_notice = world["add_reply"](second, T0)
    world["login_family"]()

    client.post(read_url(reply.id))

    session.refresh(notice)
    session.refresh(other_notice)
    assert notice.read_at is not None
    assert other_notice.read_at is None


def test_notices_of_other_kinds_stay_unread(client, session, world):
    message = world["add_staff_message"]()
    reply, _ = world["add_reply"](message, T0)
    other_kind = Notification(
        family_account_id=world["family"].id,
        kind="announcement",
        staff_message_id=message.id,
        created_at=T0,
    )
    session.add(other_kind)
    session.flush()
    world["login_family"]()

    client.post(read_url(reply.id))

    session.refresh(other_kind)
    assert other_kind.read_at is None


def test_another_familys_message_is_404_and_changes_nothing(client, session, world):
    message = world["add_staff_message"]()
    reply, notice = world["add_reply"](message, T0)
    other_family = world["make_family"]()
    world["login_as"](other_family.user_id)

    response = client.post(read_url(reply.id))

    assert response.status_code == 404
    session.refresh(notice)
    assert notice.read_at is None


def test_family_and_ai_messages_are_404(client, session, world):
    message = world["add_staff_message"]()
    world["add_reply"](message, T0)
    ai = InquiryMessage(
        conversation_id=world["conversation"].id, sender="ai", body="答え", ai_result="answered"
    )
    session.add(ai)
    session.flush()
    family_message = session.scalars(
        select(InquiryMessage).where(InquiryMessage.sender == "family")
    ).first()
    world["login_family"]()

    assert client.post(read_url(ai.id)).status_code == 404
    assert client.post(read_url(family_message.id)).status_code == 404


def test_a_phone_reply_is_404(client, session, world):
    message = world["add_staff_message"]()
    reply, _ = world["add_reply"](message, T0, response_type="phone", notice=False)
    world["login_family"]()

    assert client.post(read_url(reply.id)).status_code == 404


def test_missing_message_is_404(client, world):
    world["login_family"]()

    assert client.post(read_url(999999)).status_code == 404


def test_login_is_required_and_staff_cannot_use_it(client, session, world):
    message = world["add_staff_message"]()
    reply, _ = world["add_reply"](message, T0)

    assert client.post(read_url(reply.id)).status_code == 401

    staff = world["make_staff"](role="care_worker")
    world["login_as"](staff.user_id)
    assert client.post(read_url(reply.id)).status_code == 403


def test_reply_message_and_notice_are_created_together(client, session, world, monkeypatch):
    """本物の返事の API で作ると、発言とお知らせの created_at が同じになる（対応の前提）。"""
    monkeypatch.setattr("app.api.staff.messages.send_email_now", lambda _outbox_id: None)
    message = world["add_staff_message"]()
    template_id = session.scalars(
        select(StaffMessageTemplate.id)
        .where(StaffMessageTemplate.category == "care_request")
        .order_by(StaffMessageTemplate.sort_order)
    ).first()
    staff = world["make_staff"](role="care_worker")
    world["login_as"](staff.user_id)

    response = client.post(
        f"/api/staff/messages/{message.id}/reply", json={"template_ids": [template_id]}
    )
    assert response.status_code == 201
    reply = session.get(InquiryMessage, response.json()["id"])
    notice = session.scalars(
        select(Notification).where(Notification.staff_message_id == message.id)
    ).one()
    assert notice.created_at == reply.created_at

    # その発言を家族が見ると、そのお知らせが読んだことになる
    world["login_family"]()
    assert client.post(read_url(reply.id)).status_code == 204
    session.refresh(notice)
    assert notice.read_at is not None
