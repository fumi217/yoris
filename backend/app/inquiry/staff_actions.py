"""職員の「自分が対応する」とアプリでの返事（spec 004 の 004-T026・T027。R-08・R-09）。

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
from app.inquiry.visibility import visible_staff_messages
from app.models.inquiry import (
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

    previous_assignee = message.assignee_id
    result = session.execute(
        update(StaffMessage)
        .where(StaffMessage.id == message_id, StaffMessage.status == "waiting")
        .values(
            status="answered",
            responded_by=user.staff_id,
            responded_at=clock.now(),
            # 担当でない職員が返事をしたら、その職員を担当にする（FR-012b）
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
