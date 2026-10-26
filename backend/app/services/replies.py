"""職員の返事の保存（spec 001 の 001-T052。research.md R-07）。

- 最初に保存された返事だけを有効にする：`UPDATE requests SET status='answered'
  WHERE id=:id AND status='waiting'` が 0 件なら保存しない（answered なら already_replied、
  cancelled なら request_cancelled）。返事の追加と、この更新は 1 つのトランザクションで行う
- 定型文は 1 つ以上で、そのリクエストのテーマのものだけ。書き足しは 100 文字まで（FR-030）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）
- 返事のお知らせ（さとこの create_reply_notice、001-T051）は、できたらここで呼ぶ（R-09）
"""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clock import today_jst
from app.models.disclosure import ReplyTemplate
from app.models.replies import MAX_NOTE_LENGTH, Reply
from app.models.requests import Request


class ReplyError(Exception):
    """返事を保存できない。code は spec 001 contracts のエラーのコード。"""

    code = "validation_error"


class InvalidReply(ReplyError):
    """定型文がない・ほかのテーマの定型文・書き足しが長すぎる（422）。"""

    code = "validation_error"


class ReplyRequestNotFound(ReplyError):
    """ないリクエスト（404）。"""

    code = "not_found"


class AlreadyReplied(ReplyError):
    """ほかの職員が先に返事をした（409）。"""

    code = "already_replied"


class RequestCancelled(ReplyError):
    """家族がリクエストを取り消した（409）。"""

    code = "request_cancelled"


def save_reply(
    session: Session,
    *,
    request_id: int,
    staff_id: int,
    template_ids: Sequence[int],
    note: str | None = None,
) -> Reply:
    """リクエストに返事をする。同時に保存したときは、先の 1 つだけが保存される（R-07）。"""
    ids = list(dict.fromkeys(template_ids))  # 同じ定型文を 2 回選んでも 1 つにする
    if not ids:
        raise InvalidReply("template_ids: empty")
    note = (note or "").strip() or None
    if note is not None and len(note) > MAX_NOTE_LENGTH:
        raise InvalidReply(f"note: {len(note)} chars")

    request = session.get(Request, request_id)
    if request is None:
        raise ReplyRequestNotFound(f"request_id: {request_id}")
    valid = set(
        session.scalars(
            select(ReplyTemplate.id).where(
                ReplyTemplate.theme_id == request.theme_id, ReplyTemplate.id.in_(ids)
            )
        )
    )
    if valid != set(ids):
        raise InvalidReply("template_ids: not for this theme")

    # 返事待ちのときだけ answered にする。ほかの職員が同時に返事をしていたら、
    # 先の人の commit を待ってから 0 件になる（ロックを自分で取らずに済む）
    result = session.execute(
        update(Request)
        .where(Request.id == request_id, Request.status == "waiting")
        .values(status="answered")
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        status = session.scalar(select(Request.status).where(Request.id == request_id))
        if status == "cancelled":
            raise RequestCancelled(f"request_id: {request_id}")
        raise AlreadyReplied(f"request_id: {request_id}")

    reply = Reply(
        request_id=request_id,
        template_ids=ids,
        note=note,
        replied_by=staff_id,
        contact_book_date=today_jst(),
    )
    session.add(reply)
    session.flush()
    return reply
