"""苦情の見え方と件数のテスト（spec 004 の 004-T007。FR-012・FR-013・SC-013）。

手元の DB には開発の初期データがあるので、件数はテストで作った行だけで確かめる。
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.deps import CurrentUser
from app.inquiry.visibility import (
    count_waiting_staff_messages,
    count_waiting_staff_messages_by_resident,
    visible_staff_messages,
)
from app.models.inquiry import InquiryConversation, InquiryMessage, StaffMessage


def as_staff(staff) -> CurrentUser:
    return CurrentUser(staff.user_id, "staff", staff.role, staff.id, None, "ja", staff.display_name)


@pytest.fixture
def add_message(session):
    """入居者（家族）の会話に、職員へのメッセージを 1 つ足す。"""

    def add(family, category: str, status: str = "waiting") -> StaffMessage:
        conversation = session.scalar(
            select(InquiryConversation).where(InquiryConversation.family_account_id == family.id)
        )
        if conversation is None:
            conversation = InquiryConversation(
                family_account_id=family.id, resident_id=family.resident_id
            )
            session.add(conversation)
            session.flush()
        origin = InquiryMessage(conversation_id=conversation.id, sender="family", body="質問")
        session.add(origin)
        session.flush()
        message = StaffMessage(
            conversation_id=conversation.id,
            resident_id=family.resident_id,
            origin_message_id=origin.id,
            category=category,
            summary="要約",
            status=status,
        )
        session.add(message)
        session.flush()
        return message

    return add


@pytest.fixture
def messages(make_family, add_message):
    """入居者 A に医療と苦情、入居者 B にお金（対応待ち）と医療（対応済み）。"""
    family_a = make_family()
    family_b = make_family()
    return {
        "a": family_a.resident_id,
        "b": family_b.resident_id,
        "a_medical": add_message(family_a, "medical"),
        "a_complaint": add_message(family_a, "complaint"),
        "b_money": add_message(family_b, "money"),
        "b_answered": add_message(family_b, "medical", status="answered"),
    }


def visible_ids(session, user, messages) -> set[int]:
    ours = {m.id for m in messages.values() if isinstance(m, StaffMessage)}
    return {m.id for m in session.scalars(visible_staff_messages(user))} & ours


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_complaints_are_hidden_from_other_roles(session, make_staff, messages, role):
    user = as_staff(make_staff(role=role))

    assert visible_ids(session, user, messages) == {
        messages["a_medical"].id,
        messages["b_money"].id,
        messages["b_answered"].id,
    }
    assert count_waiting_staff_messages(session, user, messages["a"]) == 1
    assert count_waiting_staff_messages_by_resident(session, user)[messages["a"]] == 1


@pytest.mark.parametrize("role", ["counselor", "director"])
def test_complaints_are_visible_to_counselor_and_director(session, make_staff, messages, role):
    user = as_staff(make_staff(role=role))

    assert messages["a_complaint"].id in visible_ids(session, user, messages)
    assert count_waiting_staff_messages(session, user, messages["a"]) == 2
    assert count_waiting_staff_messages_by_resident(session, user)[messages["a"]] == 2


def test_counts_only_waiting_messages(session, make_staff, messages):
    user = as_staff(make_staff(role="counselor"))
    by_resident = count_waiting_staff_messages_by_resident(session, user)

    # B は対応待ちのお金だけ（対応済みの医療は数えない）
    assert count_waiting_staff_messages(session, user, messages["b"]) == 1
    assert by_resident[messages["b"]] == 1


def test_facility_count_includes_only_visible_waiting(
    session, make_staff, make_family, add_message
):
    care_worker = as_staff(make_staff(role="care_worker"))
    counselor = as_staff(make_staff(role="counselor"))
    # 手元の DB の初期データの分を引いて、テストで足した分だけを確かめる
    before_worker = count_waiting_staff_messages(session, care_worker)
    before_counselor = count_waiting_staff_messages(session, counselor)

    family = make_family()
    add_message(family, "medical")
    add_message(family, "complaint")
    add_message(family, "other", status="answered")

    assert count_waiting_staff_messages(session, care_worker) - before_worker == 1
    assert count_waiting_staff_messages(session, counselor) - before_counselor == 2


def test_residents_without_waiting_messages_are_not_in_the_dict(
    session, make_staff, make_family, add_message
):
    user = as_staff(make_staff(role="care_worker"))
    family = make_family()
    add_message(family, "complaint")  # 介護職員には見えない
    add_message(family, "money", status="answered")  # 対応済み

    assert family.resident_id not in count_waiting_staff_messages_by_resident(session, user)


def test_family_sees_no_staff_messages(session, make_family, messages):
    family = make_family()
    user = CurrentUser(family.user_id, "family", None, None, family.resident_id, "ja", "家族")

    assert visible_ids(session, user, messages) == set()
    assert count_waiting_staff_messages(session, user, messages["a"]) == 0
    assert count_waiting_staff_messages_by_resident(session, user) == {}


def test_family_message_is_at_most_500_characters(session, make_family):
    family = make_family()
    conversation = InquiryConversation(family_account_id=family.id, resident_id=family.resident_id)
    session.add(conversation)
    session.flush()
    session.add(InquiryMessage(conversation_id=conversation.id, sender="family", body="あ" * 500))
    session.flush()

    session.add(InquiryMessage(conversation_id=conversation.id, sender="family", body="あ" * 501))
    with pytest.raises(IntegrityError):
        session.flush()


def test_one_conversation_per_family(session, make_family):
    family = make_family()
    session.add(InquiryConversation(family_account_id=family.id, resident_id=family.resident_id))
    session.flush()

    session.add(InquiryConversation(family_account_id=family.id, resident_id=family.resident_id))
    with pytest.raises(IntegrityError):
        session.flush()
