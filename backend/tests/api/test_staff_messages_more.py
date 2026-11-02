"""「電話で対応した」・担当を外す／変える・種類の付け替えのテスト（spec 004 の 004-T036 の一部）。

FR-012b・FR-014・FR-015・SC-008。家族の続きの書き込み（T034）と、24 時間・3 日の判定（T035）の
テストは、その実装と一緒に足す。メールは送らない（send_email_now を記録だけにする）。
"""

import pytest
from sqlalchemy import func, select

from app.auth.deps import CurrentUser
from app.auth.login_ids import next_login_ids
from app.inquiry.staff_actions import InvalidCategory, change_category
from app.models.core import Facility, Staff, User
from app.models.inquiry import (
    InquiryConversation,
    InquiryMessage,
    StaffMessage,
    StaffMessageEvent,
)
from app.models.notifications import EmailOutbox, Notification
from app.seed.inquiry import add_staff_message_templates


@pytest.fixture
def sent_emails(monkeypatch) -> list[int]:
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

    def add_message(category: str = "care_request", *, assignee=None, status="waiting"):
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
            status=status,
            assignee_id=assignee.id if assignee else None,
        )
        session.add(message)
        session.flush()
        return message

    def login(role: str = "care_worker", name: str | None = None):
        staff = make_staff(role=role, display_name=name or f"職員{role}")
        login_as(staff.user_id)
        return staff

    return {
        "family": family,
        "conversation": conversation,
        "add_message": add_message,
        "login": login,
        "login_as": login_as,
        "make_staff": make_staff,
    }


def _events(session, message_id) -> list[StaffMessageEvent]:
    return list(
        session.scalars(
            select(StaffMessageEvent)
            .where(StaffMessageEvent.staff_message_id == message_id)
            .order_by(StaffMessageEvent.id)
        )
    )


def _types(session, message_id) -> list[str]:
    return [event.type for event in _events(session, message_id)]


def _phone(client, message_id):
    return client.post(f"/api/staff/messages/{message_id}/phone")


def _unassign(client, message_id):
    return client.delete(f"/api/staff/messages/{message_id}/assign")


def _change_assignee(client, message_id, staff_id):
    return client.put(f"/api/staff/messages/{message_id}/assignee", json={"staff_id": staff_id})


def _change_category(client, message_id, category):
    return client.patch(f"/api/staff/messages/{message_id}/category", json={"category": category})


# --- 電話で対応した（T032。FR-014） ---


def test_phone_answers_the_message_and_makes_me_the_assignee(client, session, world):
    staff = world["login"]("care_worker")
    message = world["add_message"]()

    response = _phone(client, message.id)

    assert response.status_code == 201
    assert response.json()["status"] == "answered"
    session.refresh(message)
    assert (message.status, message.assignee_id, message.responded_by) == (
        "answered",
        staff.id,
        staff.id,
    )
    assert message.responded_at is not None
    # 担当が空だったので assigned、そのあと answered（担当が空のまま対応済みにならない）
    assert _types(session, message.id) == ["assigned", "answered"]


def test_phone_adds_a_staff_line_to_the_family_conversation(client, session, world):
    staff = world["login"]("care_worker")
    message = world["add_message"]()

    saved_id = _phone(client, message.id).json()["id"]

    saved = session.get(InquiryMessage, saved_id)
    assert (saved.sender, saved.response_type, saved.body) == ("staff", "phone", "")
    assert saved.staff_id == staff.id
    assert saved.staff_message_id == message.id
    assert saved.template_ids is None and saved.note is None


def test_phone_sends_no_notice_and_no_email(client, session, world, sent_emails):
    world["login"]("care_worker")
    message = world["add_message"]()
    before = (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    )

    _phone(client, message.id)

    after = (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    )
    # 電話で伝わっているので、家族へのお知らせもメールも作らない（職員にも通知しない。SC-008）
    assert after == before
    assert sent_emails == []


def test_phone_takes_over_from_another_assignee(client, session, world):
    other = world["make_staff"](role="care_worker", display_name="先の担当")
    message = world["add_message"](assignee=other)
    staff = world["login"]("leader")

    assert _phone(client, message.id).status_code == 201

    session.refresh(message)
    assert message.assignee_id == staff.id
    reassigned = _events(session, message.id)[0]
    assert (reassigned.type, reassigned.from_value, reassigned.to_value) == (
        "reassigned",
        str(other.id),
        str(staff.id),
    )


def test_second_phone_is_409_already_answered(client, session, world):
    world["login"]("care_worker", "先の職員")
    message = world["add_message"]()
    assert _phone(client, message.id).status_code == 201
    world["login"]("care_worker", "後の職員")

    response = _phone(client, message.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_answered"
    assert (
        session.scalar(
            select(func.count())
            .select_from(InquiryMessage)
            .where(InquiryMessage.staff_message_id == message.id, InquiryMessage.sender == "staff")
        )
        == 1
    )


def test_complaint_is_answered_by_phone_only_by_counselor_or_director(client, session, world):
    message = world["add_message"]("complaint")
    world["login"]("care_worker")
    assert _phone(client, message.id).status_code == 404

    world["login"]("counselor")
    assert _phone(client, message.id).status_code == 201
    session.refresh(message)
    assert message.status == "answered"


def test_phone_for_unknown_message_is_404_and_family_is_403(client, world, make_family, login_as):
    world["login"]("care_worker")
    assert _phone(client, 999999999).status_code == 404

    login_as(make_family().user_id)
    assert _phone(client, 999999999).status_code == 403


# --- 担当を外す（T033。FR-012b） ---


def test_unassign_clears_the_assignee_and_keeps_a_record(client, session, world):
    staff = world["login"]("care_worker")
    message = world["add_message"](assignee=staff)

    assert _unassign(client, message.id).status_code == 204

    session.refresh(message)
    assert message.assignee_id is None
    [event] = _events(session, message.id)
    assert (event.type, event.staff_id, event.from_value) == ("unassigned", staff.id, str(staff.id))


def test_anyone_who_can_see_the_message_can_unassign_it(client, session, world):
    other = world["make_staff"](role="care_worker", display_name="休みの職員")
    message = world["add_message"](assignee=other)
    me = world["login"]("clerk")

    assert _unassign(client, message.id).status_code == 204

    [event] = _events(session, message.id)
    # 外した人（私）と、前の担当が残る
    assert (event.staff_id, event.from_value) == (me.id, str(other.id))


def test_unassign_when_already_empty_is_ok_and_adds_no_record(client, session, world):
    world["login"]("care_worker")
    message = world["add_message"]()

    assert _unassign(client, message.id).status_code == 204
    assert _events(session, message.id) == []


def test_unassign_after_answered_is_409_so_an_answered_message_never_has_no_assignee(
    client, session, world
):
    staff = world["login"]("care_worker")
    message = world["add_message"](assignee=staff, status="answered")

    response = _unassign(client, message.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_answered"
    session.refresh(message)
    assert message.assignee_id == staff.id


def test_unassign_a_complaint_is_404_for_other_roles(client, session, world):
    counselor = world["make_staff"](role="counselor")
    message = world["add_message"]("complaint", assignee=counselor)
    world["login"]("care_worker")

    assert _unassign(client, message.id).status_code == 404

    session.refresh(message)
    assert message.assignee_id == counselor.id


# --- 担当を変える（T033。FR-012b） ---


def test_change_assignee_records_who_changed_it(client, session, world):
    old = world["make_staff"](role="care_worker", display_name="休みの職員")
    new = world["make_staff"](role="care_worker", display_name="代わりの職員")
    message = world["add_message"](assignee=old)
    me = world["login"]("leader")

    assert _change_assignee(client, message.id, new.id).status_code == 204

    session.refresh(message)
    assert message.assignee_id == new.id
    [event] = _events(session, message.id)
    assert (event.type, event.staff_id, event.from_value, event.to_value) == (
        "reassigned",
        me.id,
        str(old.id),
        str(new.id),
    )


def test_change_assignee_from_empty_is_recorded_as_assigned(client, session, world):
    new = world["make_staff"](role="care_worker")
    message = world["add_message"]()
    world["login"]("leader")

    _change_assignee(client, message.id, new.id)

    [event] = _events(session, message.id)
    assert (event.type, event.from_value) == ("assigned", None)


def test_change_assignee_to_the_same_person_adds_no_record(client, session, world):
    staff = world["make_staff"](role="care_worker")
    message = world["add_message"](assignee=staff)
    world["login"]("leader")

    assert _change_assignee(client, message.id, staff.id).status_code == 204
    assert _events(session, message.id) == []


def test_change_assignee_after_answered_is_409(client, session, world):
    staff = world["login"]("care_worker")
    other = world["make_staff"](role="care_worker")
    message = world["add_message"](assignee=staff, status="answered")

    response = _change_assignee(client, message.id, other.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_answered"


def test_change_assignee_to_unknown_or_other_facility_staff_is_422(client, session, world):
    message = world["add_message"]()
    world["login"]("leader")
    assert _change_assignee(client, message.id, 999999999).status_code == 422

    facility = Facility(name="ほかの施設")
    session.add(facility)
    session.flush()
    [login_id] = next_login_ids(session, 1)
    user = User(kind="staff", login_id=login_id, password_hash="x", language="ja")
    session.add(user)
    session.flush()
    outsider = Staff(
        user_id=user.id, facility_id=facility.id, display_name="ほかの施設の職員", role="leader"
    )
    session.add(outsider)
    session.flush()

    response = _change_assignee(client, message.id, outsider.id)

    assert response.status_code == 422
    session.refresh(message)
    assert message.assignee_id is None


def test_a_complaint_can_only_be_given_to_counselor_or_director(client, session, world):
    care_worker = world["make_staff"](role="care_worker")
    director = world["make_staff"](role="director")
    message = world["add_message"]("complaint")
    world["login"]("counselor")

    # 苦情を読めない役割が担当になると、自分の担当のメッセージを開けなくなる
    assert _change_assignee(client, message.id, care_worker.id).status_code == 422
    assert _change_assignee(client, message.id, director.id).status_code == 204
    session.refresh(message)
    assert message.assignee_id == director.id


def test_change_assignee_needs_a_body_with_only_staff_id(client, session, world):
    message = world["add_message"]()
    world["login"]("leader")

    assert client.put(f"/api/staff/messages/{message.id}/assignee", json={}).status_code == 422
    extra = client.put(
        f"/api/staff/messages/{message.id}/assignee", json={"staff_id": 1, "status": "answered"}
    )
    assert extra.status_code == 422


# --- 種類を付け替える（T033。FR-015） ---


def test_change_category_records_who_and_from_to(client, session, world):
    message = world["add_message"]("care_request")
    me = world["login"]("care_worker")

    assert _change_category(client, message.id, "medical").status_code == 204

    session.refresh(message)
    assert message.category == "medical"
    [event] = _events(session, message.id)
    assert (event.type, event.staff_id, event.from_value, event.to_value) == (
        "category_changed",
        me.id,
        "care_request",
        "medical",
    )


def test_change_category_to_the_same_one_adds_no_record(client, session, world):
    message = world["add_message"]("money")
    world["login"]("care_worker")

    assert _change_category(client, message.id, "money").status_code == 204
    assert _events(session, message.id) == []


def test_unknown_category_is_422(client, session, world):
    message = world["add_message"]()
    world["login"]("care_worker")

    assert _change_category(client, message.id, "gossip").status_code == 422
    session.refresh(message)
    assert message.category == "care_request"


def test_unknown_category_is_rejected_by_the_service_too(session, world):
    """API の入口を通らない呼び出し（管理コマンドなど）でも、ない種類は DB に入れない。"""
    message = world["add_message"]()
    me = world["login"]("care_worker")
    user = CurrentUser(
        user_id=me.user_id,
        kind="staff",
        role=me.role,
        staff_id=me.id,
        resident_id=None,
        language="ja",
        display_name="田中",
    )

    with pytest.raises(InvalidCategory):
        change_category(session, user, message.id, "gossip")
    session.refresh(message)
    assert message.category == "care_request"
    assert _events(session, message.id) == []


def test_after_moving_to_complaint_only_counselor_and_director_can_see_it(client, session, world):
    message = world["add_message"]("medical")
    world["login"]("care_worker")

    assert _change_category(client, message.id, "complaint").status_code == 204

    # 付け替えた本人にも、その時点から見えない（FR-015・FR-012）
    assert client.get(f"/api/staff/messages/{message.id}").status_code == 404
    world["login"]("counselor")
    assert client.get(f"/api/staff/messages/{message.id}").status_code == 200


def test_moving_to_complaint_removes_an_assignee_who_cannot_read_it(client, session, world):
    care_worker = world["make_staff"](role="care_worker")
    message = world["add_message"]("medical", assignee=care_worker)
    me = world["login"]("leader")

    _change_category(client, message.id, "complaint")

    session.refresh(message)
    assert message.assignee_id is None
    events = _events(session, message.id)
    assert [event.type for event in events] == ["category_changed", "unassigned"]
    assert (events[1].staff_id, events[1].from_value) == (me.id, str(care_worker.id))


def test_moving_to_complaint_keeps_an_assignee_who_can_read_it(client, session, world):
    counselor = world["make_staff"](role="counselor")
    message = world["add_message"]("medical", assignee=counselor)
    world["login"]("leader")

    _change_category(client, message.id, "complaint")

    session.refresh(message)
    assert message.assignee_id == counselor.id


def test_only_counselor_and_director_can_move_a_message_out_of_complaint(client, session, world):
    message = world["add_message"]("complaint")
    world["login"]("care_worker")
    # 苦情は、ほかの役割には最初から見えない
    assert _change_category(client, message.id, "other").status_code == 404
    session.refresh(message)
    assert message.category == "complaint"

    world["login"]("counselor")
    assert _change_category(client, message.id, "other").status_code == 204
    session.refresh(message)
    assert message.category == "other"
    # 付け替えたあとは、ほかの役割にも見える
    world["login"]("care_worker")
    assert client.get(f"/api/staff/messages/{message.id}").status_code == 200


def test_family_cannot_use_the_new_apis(client, world, make_family, login_as):
    message = world["add_message"]()
    login_as(make_family().user_id)

    assert _unassign(client, message.id).status_code == 403
    assert _change_assignee(client, message.id, 1).status_code == 403
    assert _change_category(client, message.id, "other").status_code == 403
