"""家族のお知らせの API（spec 001 の 001-T056。contracts の「家族」）。

- `GET /api/family/notifications`：お知らせの一覧（新しい順）。返事の中身は入れない
  （一覧は、種類・日時・既読と、指す先の id だけ。中身は連絡帳で見る。SC-010）
- `POST /api/family/replies/{reply_id}/read`：返事を読んだ（家族で共有）。
  返事のカードが画面に出たら、フロントが自動で呼ぶ（R-15）。その返事のお知らせも、読んだことにする

id で指定するものは、ログイン中の家族のものかを必ず確かめる
（id は連番で推測できる。ほかの家族のものは 404）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.clock import now
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import FamilyAccount
from app.models.notifications import Notification
from app.models.replies import Reply
from app.models.requests import Request

router = APIRouter(prefix="/api/family", tags=["family"])

# 一覧に出す件数（新しいものから）
LIST_LIMIT = 50


class NotificationOut(BaseModel):
    id: int
    kind: str
    created_at: datetime
    read: bool
    reply_id: int | None
    announcement_id: int | None
    period_start: datetime | None
    period_end: datetime | None
    # まとめに、写真・記録が含まれるか。画面が、文言（記録だけ・写真だけ・両方）を選ぶ（FR-018）
    has_album: bool
    has_records: bool
    # まとめに入った様子のメモの書いた日（古い順）。書いた日の連絡帳へのリンクに使う。
    # 中身は返さない（FR-012b）
    memo_dates: list[date]


def _resident_id(user: CurrentUser) -> int:
    """ログイン中の家族の入居者。紐づいていない家族は、ほかの家族と混ざらないよう 403 にする。"""
    if user.resident_id is None:
        raise AppError(ErrorCode.FORBIDDEN)
    return user.resident_id


@router.get("/notifications")
def list_notifications(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> list[NotificationOut]:
    """ログイン中の家族のお知らせを、新しい順に（多くても LIST_LIMIT 件）。"""
    resident_id = _resident_id(user)
    rows = session.scalars(
        select(Notification)
        .join(FamilyAccount, FamilyAccount.id == Notification.family_account_id)
        .where(FamilyAccount.resident_id == resident_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(LIST_LIMIT)
    )
    return [
        NotificationOut(
            id=row.id,
            kind=row.kind,
            created_at=row.created_at,
            read=row.read_at is not None,
            reply_id=row.reply_id,
            announcement_id=row.announcement_id,
            period_start=row.period_start,
            period_end=row.period_end,
            has_album=row.has_album,
            has_records=row.has_records,
            memo_dates=list(row.memo_dates),
        )
        for row in rows
    ]


@router.post("/replies/{reply_id}/read", status_code=204)
def read_reply(
    reply_id: int,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """返事を読んだことにする（何度呼んでも同じ）。ほかの家族の返事の id なら 404。"""
    resident_id = _resident_id(user)
    reply = session.scalars(
        select(Reply)
        .join(Request, Request.id == Reply.request_id)
        .where(Reply.id == reply_id, Request.resident_id == resident_id)
    ).one_or_none()
    if reply is None:
        raise AppError(ErrorCode.NOT_FOUND)

    stamp = now()
    if reply.read_at is None:
        reply.read_at = stamp
    session.execute(
        update(Notification)
        .where(Notification.reply_id == reply_id, Notification.read_at.is_(None))
        .values(read_at=stamp)
    )
    session.commit()
