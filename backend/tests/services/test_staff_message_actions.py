"""2 人の職員がほぼ同時に「自分が対応する」を押す・返事をする（spec 004 の 004-T023）。

FR-012b・FR-017。

ふつうのテストは tests/conftest.py の session を使う（テストごとに取り消す）。
このテストだけは、2 本のスレッドが本当に commit するので、最後に作った行をすべて消す
（tests/services/test_replies_service.py と同じ作り）。
"""

import threading
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.inquiry.staff_actions import (
    AlreadyAnswered,
    AlreadyAssigned,
    StaffMessageError,
    assign_to_me,
    reply_in_app,
)
from app.models.core import Facility, FamilyAccount, Resident, Staff, User
from app.models.inquiry import (
    InquiryConversation,
    InquiryMessage,
    StaffMessage,
    StaffMessageEvent,
    StaffMessageTemplate,
)
from app.models.notifications import EmailOutbox, Notification
from app.seed.inquiry import add_staff_message_templates

FAMILY_EMAIL = "concurrent-staff-message@example.test"


@pytest.fixture
def committed(engine) -> Iterator[dict]:
    with Session(engine) as db:
        created_templates = not db.scalars(select(StaffMessageTemplate).limit(1)).first()
        add_staff_message_templates(db)
        facility = Facility(name="テスト施設（同時の対応）")
        db.add(facility)
        db.flush()
        resident = Resident(
            facility_id=facility.id,
            name="架空 同時の対応",
            name_kana="かくう",
            name_romaji="Kaku",
            room="901",
        )
        staff_users = [User(kind="staff", login_id=f"s9{n}001", password_hash="x") for n in (6, 7)]
        family_user = User(kind="family", email=FAMILY_EMAIL, password_hash="x")
        db.add_all([resident, *staff_users, family_user])
        db.flush()
        staff = [
            Staff(
                user_id=u.id, facility_id=facility.id, display_name=f"職員{n}", role="care_worker"
            )
            for n, u in enumerate(staff_users)
        ]
        family = FamilyAccount(user_id=family_user.id, resident_id=resident.id)
        db.add_all([*staff, family])
        db.flush()
        conversation = InquiryConversation(family_account_id=family.id, resident_id=resident.id)
        db.add(conversation)
        db.flush()
        origin = InquiryMessage(conversation_id=conversation.id, sender="family", body="質問")
        db.add(origin)
        db.flush()
        message = StaffMessage(
            conversation_id=conversation.id,
            resident_id=resident.id,
            origin_message_id=origin.id,
            category="care_request",
            summary="要約",
        )
        db.add(message)
        db.flush()
        templates = list(
            db.scalars(
                select(StaffMessageTemplate.id)
                .where(StaffMessageTemplate.category == "care_request")
                .order_by(StaffMessageTemplate.sort_order)
            )
        )
        db.commit()
        data = {
            "facility": facility.id,
            "resident": resident.id,
            "users": [*(u.id for u in staff_users), family_user.id],
            "staff": [s.id for s in staff],
            "family": family.id,
            "conversation": conversation.id,
            "message": message.id,
            "templates": templates,
            "login_users": [
                (u.id, s.id, s.display_name) for u, s in zip(staff_users, staff, strict=True)
            ],
        }
    try:
        yield data
    finally:
        with Session(engine) as db:
            db.execute(delete(Notification).where(Notification.family_account_id == data["family"]))
            db.execute(delete(EmailOutbox).where(EmailOutbox.to_email == FAMILY_EMAIL))
            db.execute(
                delete(StaffMessageEvent).where(
                    StaffMessageEvent.staff_message_id == data["message"]
                )
            )
            # 発言と職員へのメッセージは、お互いを指すので、先に外す
            db.execute(
                update(InquiryMessage)
                .where(InquiryMessage.conversation_id == data["conversation"])
                .values(staff_message_id=None)
            )
            db.execute(delete(StaffMessage).where(StaffMessage.id == data["message"]))
            db.execute(
                delete(InquiryMessage).where(InquiryMessage.conversation_id == data["conversation"])
            )
            db.execute(
                delete(InquiryConversation).where(InquiryConversation.id == data["conversation"])
            )
            db.execute(delete(FamilyAccount).where(FamilyAccount.id == data["family"]))
            db.execute(delete(Staff).where(Staff.id.in_(data["staff"])))
            db.execute(delete(User).where(User.id.in_(data["users"])))
            db.execute(delete(Resident).where(Resident.id == data["resident"]))
            db.execute(delete(Facility).where(Facility.id == data["facility"]))
            if created_templates:
                db.execute(delete(StaffMessageTemplate))
            db.commit()


def _user(committed, index: int) -> CurrentUser:
    user_id, staff_id, name = committed["login_users"][index]
    return CurrentUser(user_id, "staff", "care_worker", staff_id, None, "ja", name)


def _run_together(engine, committed, action) -> list[object]:
    """2 人が同時に action を行い、成功は None（または値）、失敗は例外を返す。"""
    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def run(index: int) -> None:
        with Session(engine) as db:
            barrier.wait()
            try:
                value = action(db, _user(committed, index))
                db.commit()
                results[index] = value if value is not None else "ok"
            except StaffMessageError as error:
                db.rollback()
                results[index] = error

    threads = [threading.Thread(target=run, args=(n,)) for n in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_simultaneous_assign_makes_only_the_first_the_assignee(engine, committed):
    results = _run_together(
        engine, committed, lambda db, user: assign_to_me(db, user, committed["message"])
    )

    # 先の 1 人だけが担当になり、後の人は already_assigned（FR-012b）
    assert [r for r in results if not isinstance(r, StaffMessageError)] == ["ok"]
    assert [type(r) for r in results if isinstance(r, StaffMessageError)] == [AlreadyAssigned]
    with Session(engine) as db:
        assignee = db.scalar(
            select(StaffMessage.assignee_id).where(StaffMessage.id == committed["message"])
        )
        events = db.scalar(
            select(func.count(StaffMessageEvent.id)).where(
                StaffMessageEvent.staff_message_id == committed["message"]
            )
        )
    assert assignee in committed["staff"]
    # 担当になった履歴も 1 つだけ
    assert events == 1


def test_simultaneous_replies_save_only_the_first(engine, committed):
    results = _run_together(
        engine,
        committed,
        lambda db, user: (
            reply_in_app(db, user, committed["message"], template_ids=committed["templates"][:1])[
                0
            ].id
        ),
    )

    # 先の返事だけが有効で、後の人は already_answered（FR-017）
    assert sum(isinstance(r, int) for r in results) == 1
    assert [type(r) for r in results if isinstance(r, StaffMessageError)] == [AlreadyAnswered]
    with Session(engine) as db:
        message = db.get(StaffMessage, committed["message"])
        replies = db.scalar(
            select(func.count(InquiryMessage.id)).where(
                InquiryMessage.staff_message_id == committed["message"],
                InquiryMessage.sender == "staff",
            )
        )
        notices = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.staff_message_id == committed["message"]
            )
        )
    assert message.status == "answered"
    # 会話の発言も、家族へのお知らせも 1 つだけ
    assert (replies, notices) == (1, 1)
    # 返した職員が担当になり、対応した職員とそろう
    assert message.assignee_id == message.responded_by
    assert message.responded_by in committed["staff"]
