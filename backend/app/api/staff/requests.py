"""職員の「知りたいこと」の API（spec 001 の 001-T053。contracts の「職員」）。

- `GET /api/staff/residents/{id}/requests`：その入居者の返事待ちのリクエストと、選べる定型文
  （あわせて、家族からのメッセージの対応待ちの件数。spec 004 の 004-T030）
- `POST /api/staff/requests/{id}/reply`：返事をする（409：already_replied・request_cancelled）
- 職員への通知・音は出さない（FR-029・SC-013）。職員が画面を開いたときに見せる
- 返事のメール（さとこの create_reply_notice・send_email_now）は、001-T051 ができたらつなぐ
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.staff.records import RECORDERS
from app.auth.deps import CurrentUser
from app.clock import JST, today_jst
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.inquiry.visibility import count_waiting_staff_messages
from app.models.core import Resident
from app.models.disclosure import ReplyTemplate, Theme
from app.models.replies import MAX_NOTE_LENGTH
from app.models.requests import Request
from app.services.replies import ReplyError, save_reply

router = APIRouter(prefix="/api/staff", tags=["staff"])


class TemplateOut(BaseModel):
    id: int
    code: str  # 辞書のキー（例："template.daily_life.smile"）


class WaitingRequestOut(BaseModel):
    id: int
    theme_code: str
    theme_emoji: str
    created_at: datetime  # 送られた日時
    days: int  # 送られてからの日数（日本時間の日付で数える）
    templates: list[TemplateOut]


class WaitingRequestsResponse(BaseModel):
    requests: list[WaitingRequestOut]
    # 家族からのメッセージの対応待ちの件数（苦情は生活相談員・施設長にだけ数える。spec 004）
    waiting_messages: int


class ReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_ids: list[int] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class ReplyResponse(BaseModel):
    id: int
    request_id: int
    template_ids: list[int]
    note: str | None
    replied_at: datetime


@router.get("/residents/{resident_id}/requests")
def waiting_requests(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
) -> WaitingRequestsResponse:
    """返事待ちのリクエストを、古い順に返す。"""
    if session.get(Resident, resident_id) is None:
        raise AppError(ErrorCode.NOT_FOUND)
    rows = session.execute(
        select(Request, Theme)
        .join(Theme, Theme.id == Request.theme_id)
        .where(Request.resident_id == resident_id, Request.status == "waiting")
        .order_by(Request.created_at, Request.id)
    ).all()
    theme_ids = {theme.id for _, theme in rows}
    templates: dict[int, list[TemplateOut]] = {}
    if theme_ids:
        for template in session.scalars(
            select(ReplyTemplate)
            .where(ReplyTemplate.theme_id.in_(theme_ids))
            .order_by(ReplyTemplate.sort_order, ReplyTemplate.id)
        ):
            templates.setdefault(template.theme_id, []).append(
                TemplateOut(id=template.id, code=template.code)
            )
    today = today_jst()
    return WaitingRequestsResponse(
        requests=[
            WaitingRequestOut(
                id=request.id,
                theme_code=theme.code,
                theme_emoji=theme.emoji,
                created_at=request.created_at,
                days=(today - request.created_at.astimezone(JST).date()).days,
                templates=templates.get(theme.id, []),
            )
            for request, theme in rows
        ],
        waiting_messages=count_waiting_staff_messages(session, user, resident_id),
    )


@router.post("/requests/{request_id}/reply", status_code=201)
def reply(
    request_id: int,
    body: ReplyRequest,
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ReplyResponse:
    """返事をする。同時に保存したときは、先の 1 つだけが保存される（R-07）。"""
    try:
        saved = save_reply(
            session,
            request_id=request_id,
            staff_id=user.staff_id,
            template_ids=body.template_ids,
            note=body.note,
        )
    except ReplyError as error:
        raise AppError(ErrorCode(error.code)) from error
    session.commit()
    return ReplyResponse(
        id=saved.id,
        request_id=saved.request_id,
        template_ids=saved.template_ids,
        note=saved.note,
        replied_at=saved.replied_at,
    )
