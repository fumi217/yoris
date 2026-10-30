"""家族の「質問する」の API（spec 004 の 004-T019。contracts/api.md の「家族の『質問する』」）。

入居者は送らせない（本文にも URL にも入居者の欄を持たない）。
ログイン中の家族の CurrentUser.resident_id から決める（FR-020）。
返す値に、AI への指示の文・ツールの中身は入れない（FR-021）。
"""

import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.inquiry.llm import LLMUnavailable
from app.inquiry.ratelimit import InquiryLimit, consume, release
from app.inquiry.service import (
    MessageView,
    get_family_account_id,
    list_messages,
    mark_staff_reply_read,
    send_message,
    to_views,
)
from app.models.inquiry import FAMILY_BODY_MAX

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/family/inquiry", tags=["family"])


class SourceOut(BaseModel):
    """もとにした記録（日付・項目／テーマ。画面は辞書で引く）。"""

    kind: str  # "record" / "reply"
    date: date
    item: str | None
    slot: str | None
    theme_code: str | None


class HandoffOut(BaseModel):
    """職員に渡した AI の発言の状態（contracts/api.md。質問の種類そのものは返さない）。"""

    status: str  # "waiting" / "answered"
    urgent: bool  # 画面は「お急ぎのときは、施設にお電話ください」も出す
    already: bool  # 画面は「すでに施設の職員にお伝えしています」を出す


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
    # 職員の発言だけ：返事をした職員の表示名（役割ではなく表示名）・
    # 選んだ定型文のコード（辞書で引く）・書き足した文（辞書を通さず文字としてだけ出す）・
    # 返し方（app／phone）
    staff_name: str | None
    # 職種のコード（画面が辞書の occupation.* で引く。空なら名前だけを出す。#263）
    staff_occupation: str | None
    template_codes: list[str] | None
    note: str | None
    response_type: str | None
    # 職員に渡した AI の発言だけ（ほかは null）
    handoff: HandoffOut | None


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
        staff_name=view.staff_name,
        staff_occupation=view.staff_occupation,
        template_codes=view.template_codes,
        note=view.note,
        response_type=view.response_type,
        handoff=HandoffOut(
            status=view.handoff.status, urgent=view.handoff.urgent, already=view.handoff.already
        )
        if view.handoff
        else None,
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
    # AI を呼ぶ前に回数を数える。上限なら AI は呼ばない（家族 1 日 10 回・施設全体 1 日 300 回。
    # FR-024・FR-027・SC-009）
    try:
        ticket = consume(get_family_account_id(session, user))
    except InquiryLimit as error:
        raise AppError(ErrorCode.INQUIRY_LIMIT) from error
    try:
        family_message, ai_message = send_message(session, user, text)
        family_view, ai_view = to_views(session, user, [family_message, ai_message])
        session.commit()
    except Exception as error:
        # 答えが出なかった発言は、回数に数えない（AI が止まったときなど。FR-026）。
        # AI を呼ぶ前には何も書いていないので、取り消すデータはない
        release(ticket)
        if isinstance(error, LLMUnavailable):
            # 出すのは、つながらなかった理由の種類だけ（timeout・status_429 など。本文は出さない）
            logger.warning("問い合わせの AI につながらなかった reason=%s", error.reason)
            raise AppError(ErrorCode.AI_UNAVAILABLE) from error
        raise
    return SendOut(family=_out(family_view), ai=_out(ai_view))


@router.post("/messages/{message_id}/read", status_code=204)
def read_staff_reply(
    message_id: int,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """職員の返事の発言が画面に出たとき、その発言のお知らせを読んだことにする（Issue #244）。

    get_session は commit しないので、書き込んだら、ここで 1 回だけ commit する（app/db.py）。
    """
    mark_staff_reply_read(session, user, message_id)
    session.commit()
