"""職員の「自分が対応する」・アプリでの返事・電話で対応した・担当と種類の変更
（spec 004 の 004-T026・T027・T032・T033。R-08・R-09）。

- 見られるメッセージだけ（visible_staff_messages）。ほかの役割の苦情・ないものは 404（R-12）
- 「自分が対応する」：`UPDATE ... WHERE assignee_id IS NULL` が 0 件なら、
  もう自分が担当ならそのまま、ほかの職員なら 409 `already_assigned`（FR-012b）。
  担当を決めたことを staff_message_events に残す
- アプリで返事：`UPDATE ... WHERE status='waiting'` が 0 件なら 409 `already_answered`（FR-017）。
  返した職員を担当にし（担当が変わったら履歴に残す）、家族の会話に職員の発言を足し、
  同じトランザクションで、家族へのお知らせとメールの送る予定を作る
  （さとこの create_staff_message_reply_notice）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit し、
  そのあとに send_email_now を呼ぶ）
"""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import clock
from app.auth.deps import CurrentUser
from app.inquiry.visibility import COMPLAINT_ROLES, visible_staff_messages
from app.models.core import Resident, Staff
from app.models.inquiry import (
    CATEGORIES,
    NOTE_MAX,
    InquiryMessage,
    StaffMessage,
    StaffMessageEvent,
    StaffMessageTemplate,
)
from app.services.notifications import create_staff_message_reply_notice


class StaffMessageError(Exception):
    """職員へのメッセージを操作できない。code は spec 004 contracts のエラーのコード。"""

    code = "validation_error"


class InvalidReply(StaffMessageError):
    """定型文がない・この種類にない定型文・書き足しが長すぎる（422）。"""

    code = "validation_error"


class InvalidAssignee(StaffMessageError):
    """担当にできない職員（いない・ほかの施設・苦情を読めない役割に苦情を渡す。422）。"""

    code = "validation_error"


class InvalidCategory(StaffMessageError):
    """質問の種類にない値（422）。API の入口でも確かめるが、ほかの呼び出しでも DB に入れない。"""

    code = "validation_error"


class MessageNotFound(StaffMessageError):
    """ないメッセージ・その人には見られないメッセージ（404。苦情は生活相談員・施設長以外に隠す）。"""

    code = "not_found"


class AlreadyAssigned(StaffMessageError):
    """ほかの職員が先に「自分が対応する」を押した（409）。"""

    code = "already_assigned"


class AlreadyAnswered(StaffMessageError):
    """ほかの職員が先に返事をした（409）。"""

    code = "already_answered"


def _visible(session: Session, user: CurrentUser, message_id: int, *, lock: bool = False):
    """その人が見られるメッセージ。見られなければ MessageNotFound。"""
    query = visible_staff_messages(user).where(StaffMessage.id == message_id)
    if lock:
        # 返した人の前の担当を正しく残すため、行を押さえて順番に処理する
        query = query.with_for_update()
    message = session.scalars(query).one_or_none()
    if message is None:
        raise MessageNotFound(f"staff_message_id: {message_id}")
    return message


def _mark_answered(
    session: Session, user: CurrentUser, message_id: int, *, previous_assignee: int | None
) -> None:
    """対応待ちを対応済みにして、対応した職員を担当にする（アプリの返事・電話で対応した、の共通）。

    `UPDATE ... WHERE status='waiting'` が 0 件なら、ほかの職員が先に対応している（409）。
    担当でない職員が対応したら、その職員を担当にする（FR-012b）。担当が空のまま対応済みになる
    ことはない（担当を外す・変えるは、対応待ちのときだけ。unassign・change_assignee）。

    UPDATE は、読み込み済みの message に反映しない（synchronize_session=False）。呼んだ側が、
    このあとも使うのは conversation_id・category など、ここで変えない列だけ。status・assignee_id
    などは、API が最後に commit したときに読み直される。
    """
    assert user.staff_id is not None
    result = session.execute(
        update(StaffMessage)
        .where(StaffMessage.id == message_id, StaffMessage.status == "waiting")
        .values(
            status="answered",
            responded_by=user.staff_id,
            responded_at=clock.now(),
            assignee_id=user.staff_id,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        raise AlreadyAnswered(f"staff_message_id: {message_id}")

    if previous_assignee != user.staff_id:
        session.add(
            StaffMessageEvent(
                staff_message_id=message_id,
                type="assigned" if previous_assignee is None else "reassigned",
                staff_id=user.staff_id,
                from_value=None if previous_assignee is None else str(previous_assignee),
                to_value=str(user.staff_id),
            )
        )
    session.add(
        StaffMessageEvent(staff_message_id=message_id, type="answered", staff_id=user.staff_id)
    )


def assign_to_me(session: Session, user: CurrentUser, message_id: int) -> None:
    """「自分が対応する」。最初の 1 人だけが担当になる（FR-012b・R-08）。"""
    assert user.staff_id is not None
    _visible(session, user, message_id)
    result = session.execute(
        update(StaffMessage)
        .where(StaffMessage.id == message_id, StaffMessage.assignee_id.is_(None))
        .values(assignee_id=user.staff_id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        # ほぼ同時に押されたときは、先の人の commit を待ってから 0 件になる。
        # 担当がもう自分なら、何度押しても同じ（エラーにしない）
        assignee_id = session.scalar(
            select(StaffMessage.assignee_id).where(StaffMessage.id == message_id)
        )
        if assignee_id == user.staff_id:
            return
        raise AlreadyAssigned(f"staff_message_id: {message_id}")
    session.add(
        StaffMessageEvent(
            staff_message_id=message_id,
            type="assigned",
            staff_id=user.staff_id,
            to_value=str(user.staff_id),
        )
    )
    session.flush()


def reply_in_app(
    session: Session,
    user: CurrentUser,
    message_id: int,
    *,
    template_ids: Sequence[int],
    note: str | None = None,
) -> tuple[InquiryMessage, int]:
    """アプリで返事をする。家族の会話に足した職員の発言と、email_outbox の id を返す。

    commit は呼んだ側が行い、そのあとに send_email_now(outbox_id) でその場でも送る（R-09）。
    """
    assert user.staff_id is not None
    ids = list(dict.fromkeys(template_ids))  # 同じ定型文を 2 回選んでも 1 つにする
    if not ids:
        raise InvalidReply("template_ids: empty")
    note = (note or "").strip() or None
    if note is not None and len(note) > NOTE_MAX:
        raise InvalidReply(f"note: {len(note)} chars")

    message = _visible(session, user, message_id, lock=True)
    # 苦情には定型文を用意しない（電話で対応する。FR-014）ので、ここで 422 になる
    valid = set(
        session.scalars(
            select(StaffMessageTemplate.id).where(
                StaffMessageTemplate.category == message.category,
                StaffMessageTemplate.id.in_(ids),
            )
        )
    )
    if valid != set(ids):
        raise InvalidReply("template_ids: not for this category")

    _mark_answered(session, user, message_id, previous_assignee=message.assignee_id)

    # 家族の会話に、職員の発言を足す。定型文は code で引く（文言は画面の辞書）ので、本文は空
    reply = InquiryMessage(
        conversation_id=message.conversation_id,
        sender="staff",
        body="",
        staff_id=user.staff_id,
        template_ids=ids,
        note=note,
        response_type="app",
        staff_message_id=message_id,
    )
    session.add(reply)
    session.flush()
    # 保存と同じトランザクションでお知らせとメールの送る予定を作る。先に返事をした人がいれば、
    # ここまで来ないので、お知らせが 2 回できることはない
    outbox_id = create_staff_message_reply_notice(session, message_id)
    return reply, outbox_id


def phone_in_app(session: Session, user: CurrentUser, message_id: int) -> InquiryMessage:
    """「電話で対応した」：対応済みにして、家族の会話に電話で対応したことを足す（FR-014）。

    定型文は選ばない（苦情にも使える）。アプリでの返事ではないので、家族へのお知らせとメールは
    作らない（電話で伝わっている）。同じ担当・履歴の決まりは、アプリの返事と同じ。
    """
    message = _visible(session, user, message_id, lock=True)
    _mark_answered(session, user, message_id, previous_assignee=message.assignee_id)
    reply = InquiryMessage(
        conversation_id=message.conversation_id,
        sender="staff",
        body="",
        staff_id=user.staff_id,
        response_type="phone",
        staff_message_id=message_id,
    )
    session.add(reply)
    session.flush()
    return reply


def _waiting(message: StaffMessage) -> None:
    """担当を外す・変えるのは、対応待ちのときだけ（対応済みは、対応した職員が担当のまま残る）。"""
    if message.status != "waiting":
        raise AlreadyAnswered(f"staff_message_id: {message.id}")


def unassign(session: Session, user: CurrentUser, message_id: int) -> None:
    """担当を外す（FR-012b）。もう空なら、何もしない。"""
    assert user.staff_id is not None
    message = _visible(session, user, message_id, lock=True)
    _waiting(message)
    previous = message.assignee_id
    if previous is None:
        return
    message.assignee_id = None
    session.add(
        StaffMessageEvent(
            staff_message_id=message_id,
            type="unassigned",
            staff_id=user.staff_id,
            from_value=str(previous),
        )
    )
    session.flush()


def change_assignee(session: Session, user: CurrentUser, message_id: int, staff_id: int) -> None:
    """担当をほかの職員に変える（FR-012b）。だれが変えたかを残す。

    変えられるのは、同じ施設の職員。苦情は、苦情を読める生活相談員・施設長にだけ（ほかの役割が
    担当になると、自分が担当のメッセージを開けなくなる。R-12）。もう同じ担当なら、何もしない。
    """
    assert user.staff_id is not None
    message = _visible(session, user, message_id, lock=True)
    _waiting(message)
    target = session.get(Staff, staff_id)
    facility_id = session.scalar(
        select(Resident.facility_id).where(Resident.id == message.resident_id)
    )
    if target is None or target.facility_id != facility_id:
        raise InvalidAssignee(f"staff_id: {staff_id}")
    if message.category == "complaint" and target.role not in COMPLAINT_ROLES:
        raise InvalidAssignee("staff_id: cannot read complaints")
    previous = message.assignee_id
    if previous == staff_id:
        return
    message.assignee_id = staff_id
    session.add(
        StaffMessageEvent(
            staff_message_id=message_id,
            type="assigned" if previous is None else "reassigned",
            staff_id=user.staff_id,
            from_value=None if previous is None else str(previous),
            to_value=str(staff_id),
        )
    )
    session.flush()


def change_category(session: Session, user: CurrentUser, message_id: int, category: str) -> None:
    """質問の種類を付け替える（FR-015）。だれがいつ付け替えたかを残す。

    「苦情」から別の種類に付け替えられるのは、生活相談員・施設長だけ（苦情は、この 2 つの役割
    にしか見えないので、ほかの役割はここまで来られない。念のためここでも確かめる）。
    「苦情」に付け替えたとき、担当が苦情を読めない役割なら、対応待ちのときは担当を外す
    （自分が担当のメッセージを開けなくなるため）。もう同じ種類なら、何もしない。
    """
    assert user.staff_id is not None
    if category not in CATEGORIES:
        raise InvalidCategory(f"category: {category}")
    message = _visible(session, user, message_id, lock=True)
    previous = message.category
    if previous == category:
        return
    if previous == "complaint" and user.role not in COMPLAINT_ROLES:
        raise MessageNotFound(f"staff_message_id: {message_id}")
    message.category = category
    session.add(
        StaffMessageEvent(
            staff_message_id=message_id,
            type="category_changed",
            staff_id=user.staff_id,
            from_value=previous,
            to_value=category,
        )
    )
    if category == "complaint" and message.status == "waiting" and message.assignee_id is not None:
        assignee_role = session.scalar(select(Staff.role).where(Staff.id == message.assignee_id))
        if assignee_role not in COMPLAINT_ROLES:
            session.add(
                StaffMessageEvent(
                    staff_message_id=message_id,
                    type="unassigned",
                    staff_id=user.staff_id,
                    from_value=str(message.assignee_id),
                )
            )
            message.assignee_id = None
    session.flush()
