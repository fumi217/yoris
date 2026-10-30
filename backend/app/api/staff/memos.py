"""職員の様子のメモの API（spec 007 の 007-T010・T017・T018）。

contracts/api.md の「書く・整える・確かめる（本人）」。

- `POST /api/staff/residents/{id}/memos`：下書きを作る（原文を保存する。AI は呼ばない）
- `GET /api/staff/memos?resident_id=&date=`：自分のメモの一覧
- `GET /api/staff/memos/{id}`：メモ 1 つ（本人だけ。本人でなければ 404）
- `PATCH /api/staff/memos/{id}`：原文か整えた日本語を直す（下書き・戻しのときだけ）
- `POST /api/staff/memos/{id}/rewrite`：「日本語にする」（整える → 訳し戻す）。
  `{"back_translate_only": true}` なら、直した整えた日本語を訳し戻すだけ。
  AI が止まったら 503 `ai_unavailable`（原文は残り、やり直しの回数にも数えない。R-09）
- `POST /api/staff/memos/{id}/confirm`：「確かめました」（承認待ちにする）
- `POST /api/staff/memos/{id}/withdraw`：取り下げる

役割は介護職員・リーダー（事務員・生活相談員・施設長・家族は 403）。
原文・整えた日本語は、文字としてだけ返す（FR-017）。入居者は URL で決める（本文に持たない）。
"""

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.inquiry.llm import LLMUnavailable
from app.memos import service
from app.models.memos import ORIGINAL_MAX, REWRITTEN_MAX, CareMemo

router = APIRouter(prefix="/api/staff", tags=["staff"])

# 様子のメモを書ける役割（介護職員・リーダー。spec 007 の contracts）
WRITERS = require_staff(("care_worker", "leader"))


class CreateMemoBody(BaseModel):
    # 入居者・書いた職員・状態などの余分な項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    # 原文は 1〜500 文字（前後の空白は取る。FR-001）
    original_text: str = Field(max_length=ORIGINAL_MAX * 2)
    source_lang: Literal["ja", "id", "en"]

    @field_validator("original_text")
    @classmethod
    def _length(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= ORIGINAL_MAX:
            raise ValueError(f"原文は 1〜{ORIGINAL_MAX} 文字にしてください")
        return value


class UpdateMemoBody(BaseModel):
    # 状態・書いた職員・訳し戻しなどの余分な項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    original_text: str | None = Field(default=None, max_length=ORIGINAL_MAX * 2)
    rewritten_text: str | None = Field(default=None, max_length=REWRITTEN_MAX * 2)

    @field_validator("original_text")
    @classmethod
    def _original_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= ORIGINAL_MAX:
            raise ValueError(f"原文は 1〜{ORIGINAL_MAX} 文字にしてください")
        return value

    @field_validator("rewritten_text")
    @classmethod
    def _rewritten_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= REWRITTEN_MAX:
            raise ValueError(f"整えた日本語は 1〜{REWRITTEN_MAX} 文字にしてください")
        return value

    @model_validator(mode="after")
    def _something_to_change(self) -> "UpdateMemoBody":
        if self.original_text is None and self.rewritten_text is None:
            raise ValueError("直す内容を送ってください")
        return self


class RewriteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 整えた日本語を自分で直したあと、その文を訳し戻すだけにする（整え直さない）
    back_translate_only: bool = False


class MemoOut(BaseModel):
    id: int
    resident_id: int
    memo_date: date
    written_at: datetime
    source_lang: str
    # 原文・整えた日本語は、辞書を通さず、文字としてだけ出す（FR-017）
    original_text: str
    rewritten_text: str | None
    back_translation: str | None
    warnings: list[str]
    status: str
    return_reason: str | None


def _shown_reason(memo: CareMemo) -> str | None:
    """書いた職員の画面に出す、戻された理由。

    戻した理由と、公開を取り下げた理由のうち、新しい方（承認の列は消さずに残すため。
    FR-013・FR-013a・007-T022）。
    """
    unpublished_later = memo.unpublished_at is not None and (
        memo.returned_at is None or memo.unpublished_at > memo.returned_at
    )
    return memo.unpublish_reason if unpublished_later else memo.return_reason


def _out(memo: CareMemo) -> MemoOut:
    return MemoOut(
        id=memo.id,
        resident_id=memo.resident_id,
        memo_date=memo.memo_date,
        written_at=memo.written_at,
        source_lang=memo.source_lang,
        original_text=memo.original_text,
        rewritten_text=memo.rewritten_text,
        back_translation=memo.back_translation,
        warnings=list(memo.warnings or []),
        status=memo.status,
        return_reason=_shown_reason(memo),
    )


@router.post("/residents/{resident_id}/memos", status_code=201)
def create_memo(
    resident_id: int,
    body: CreateMemoBody,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
) -> MemoOut:
    """下書きを作る。原文は、AI を呼ぶ前に保存する（R-09）。ない入居者は 404。"""
    memo = service.create_memo(session, user, resident_id, body.original_text, body.source_lang)
    session.commit()
    return _out(memo)


@router.get("/memos")
def list_memos(
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
    resident_id: Annotated[int | None, Query(ge=1)] = None,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> list[MemoOut]:
    """自分のメモの一覧（新しい順）。"""
    return [
        _out(memo)
        for memo in service.list_own_memos(session, user, resident_id=resident_id, day=day)
    ]


@router.get("/memos/{memo_id}")
def get_memo(
    memo_id: int,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
) -> MemoOut:
    """メモ 1 つ。本人でないときは 404（ほかの人の下書きを探られない）。"""
    return _out(service.get_own_memo(session, user, memo_id))


@router.patch("/memos/{memo_id}")
def update_memo(
    memo_id: int,
    body: UpdateMemoBody,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
) -> MemoOut:
    """原文か整えた日本語を直す。下書き・戻しのときだけ（それ以外は 409）。"""
    memo = service.update_memo(
        session,
        user,
        memo_id,
        original_text=body.original_text,
        rewritten_text=body.rewritten_text,
    )
    session.commit()
    return _out(memo)


@router.post("/memos/{memo_id}/rewrite")
def rewrite_memo(
    memo_id: int,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
    body: RewriteBody | None = None,
) -> MemoOut:
    """「日本語にする」。AI につながらない・30 秒を超えたときは 503（何も保存しない）。"""
    try:
        memo = service.rewrite(
            session,
            user,
            memo_id,
            back_translate_only=body.back_translate_only if body else False,
        )
    except LLMUnavailable as error:
        raise AppError(ErrorCode.AI_UNAVAILABLE) from error
    session.commit()
    return _out(memo)


@router.post("/memos/{memo_id}/confirm")
def confirm_memo(
    memo_id: int,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
) -> MemoOut:
    """「確かめました」：承認待ちにする。確かめられない状態のときは 409。"""
    memo = service.confirm(session, user, memo_id)
    session.commit()
    return _out(memo)


@router.post("/memos/{memo_id}/withdraw")
def withdraw_memo(
    memo_id: int,
    user: Annotated[CurrentUser, Depends(WRITERS)],
    session: Annotated[Session, Depends(get_session)],
) -> MemoOut:
    """取り下げる。下書き・承認待ち・戻しのときだけ（承認済みは、リーダーが公開を取り下げる）。"""
    memo = service.withdraw(session, user, memo_id)
    session.commit()
    return _out(memo)
