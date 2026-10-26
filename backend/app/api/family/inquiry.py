"""家族の「質問する」の API（spec 004 の 004-T019。contracts/api.md の「家族の『質問する』」）。

入居者は送らせない（本文にも URL にも入居者の欄を持たない）。
ログイン中の家族の CurrentUser.resident_id から決める（FR-020）。
返す値に、AI への指示の文・ツールの中身は入れない（FR-021）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.inquiry.llm import LLMUnavailable
from app.inquiry.service import MessageView, list_messages, send_message, to_views
from app.models.inquiry import FAMILY_BODY_MAX

router = APIRouter(prefix="/api/family/inquiry", tags=["family"])


class SourceOut(BaseModel):
    """もとにした記録（日付・項目／テーマ。画面は辞書で引く）。"""

    kind: str  # "record" / "reply"
    date: date
    item: str | None
    slot: str | None
    theme_code: str | None


class MessageOut(BaseModel):
    id: int
    sender: str  # "family" / "ai" / "staff"
    # 文。AI が答えなかったとき（handed_off・no_record）は空で、画面が辞書の文を出す
    body: str
    created_at: datetime
    ai_result: str | None
    sources: list[SourceOut]
    # 根拠のうち 1 つでも非開示になった答え（body・sources は空。画面は inquiry.answer_hidden）
    hidden: bool


class SendBody(BaseModel):
    # 入居者などの余分な項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=FAMILY_BODY_MAX)


class SendOut(BaseModel):
    family: MessageOut
    ai: MessageOut


def _out(view: MessageView) -> MessageOut:
    return MessageOut(
        id=view.id,
        sender=view.sender,
        body=view.body,
        created_at=view.created_at,
        ai_result=view.ai_result,
        sources=[
            SourceOut(kind=s.kind, date=s.date, item=s.item, slot=s.slot, theme_code=s.theme_code)
            for s in view.sources
        ],
        hidden=view.hidden,
    )


@router.get("/messages")
def messages(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[MessageOut]:
    """会話の発言を新しい順に返す（FR-008）。before を渡すと、その id より前を返す。"""
    return [_out(view) for view in list_messages(session, user, before=before, limit=limit)]


@router.post("/messages", status_code=201)
def send(
    body: SendBody,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> SendOut:
    """質問を送る。AI の答え（または職員に渡したこと）が決まってから、家族の発言と AI の発言を返す。

    本文の前後の空白だけのときは 422。AI につながらなければ 503 `ai_unavailable`（何も保存しない）。
    """
    text = body.body.strip()
    if not text:
        raise AppError(ErrorCode.VALIDATION_ERROR)
    try:
        family_message, ai_message = send_message(session, user, text)
    except LLMUnavailable as error:
        # AI を呼ぶ前には何も書いていないので、取り消すものはない（FR-026）
        raise AppError(ErrorCode.AI_UNAVAILABLE) from error
    family_view, ai_view = to_views(session, user, [family_message, ai_message])
    session.commit()
    return SendOut(family=_out(family_view), ai=_out(ai_view))
