"""様子のメモの承認の API（spec 007 の 007-T022）。

contracts/api.md の「承認（リーダー・施設長）」。

- `GET /api/staff/memo-approvals?status=`：承認待ち（初期値）か、承認済みの一覧
- `GET /api/staff/memo-approvals/count`：承認待ちの件数（リーダー・施設長以外は null）
- `POST /api/staff/memo-approvals/{id}/approve`：承認する（本人以外）
- `POST /api/staff/memo-approvals/{id}/return`：理由を書いて戻す（本人以外）
- `POST /api/staff/memo-approvals/{id}/unpublish`：理由を書いて公開を取り下げる

承認・戻す・取り下げは、リーダー・施設長だけ（それ以外は 403）。同じ施設のメモだけを扱う。
原文・整えた日本語・訳し戻し・理由は、文字としてだけ返す（FR-017）。
"""

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.memos import approvals
from app.memos.approvals import APPROVER_ROLES, ApprovalRow
from app.models.memos import REASON_MAX

router = APIRouter(prefix="/api/staff/memo-approvals", tags=["staff"])

APPROVERS = require_staff(APPROVER_ROLES)
# 件数は、職員ならだれでも呼べる（リーダー・施設長以外には null を返す）
ANY_STAFF = require_staff()


class ReasonBody(BaseModel):
    # 理由以外の項目（状態・職員など）は受け付けない
    model_config = ConfigDict(extra="forbid")

    # 戻す・公開を取り下げる理由は 1〜200 文字（前後の空白は取る。FR-013・FR-013a）
    reason: str = Field(max_length=REASON_MAX * 2)

    @field_validator("reason")
    @classmethod
    def _length(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= REASON_MAX:
            raise ValueError(f"理由は 1〜{REASON_MAX} 文字にしてください")
        return value


class ApprovalOut(BaseModel):
    id: int
    resident_id: int
    # 入居者の呼び名（氏名ではない）と、書いた職員の表示名
    resident_name: str
    author_name: str
    # ログイン中の職員が書いたメモか。画面は、本人のメモに「承認する」「戻す」を出さない（FR-011a）
    is_own: bool
    memo_date: date
    written_at: datetime
    source_lang: str
    # 原文・整えた日本語・訳し戻しは、辞書を通さず、文字としてだけ出す（FR-017）
    original_text: str
    rewritten_text: str | None
    back_translation: str | None
    # 機械の目の印（承認の画面で目立たせる。FR-016）
    warnings: list[str]
    status: str
    confirmed_at: datetime | None
    approved_at: datetime | None
    # 確かめてからの経過時間（分）と、24 時間を過ぎたか。承認待ちのときだけ（FR-015）
    waiting_minutes: int | None
    overdue: bool


class CountOut(BaseModel):
    # 承認できない役割には null（件数を出さない。FR-015）
    count: int | None


def _out(row: ApprovalRow, user: CurrentUser) -> ApprovalOut:
    memo = row.memo
    return ApprovalOut(
        id=memo.id,
        resident_id=memo.resident_id,
        resident_name=row.resident_name,
        author_name=row.author_name,
        is_own=memo.author_staff_id == user.staff_id,
        memo_date=memo.memo_date,
        written_at=memo.written_at,
        source_lang=memo.source_lang,
        original_text=memo.original_text,
        rewritten_text=memo.rewritten_text,
        back_translation=memo.back_translation,
        warnings=list(memo.warnings or []),
        status=memo.status,
        confirmed_at=memo.confirmed_at,
        approved_at=memo.approved_at,
        waiting_minutes=approvals.waiting_minutes(memo),
        overdue=approvals.is_overdue(memo),
    )


@router.get("")
def list_approvals(
    user: Annotated[CurrentUser, Depends(APPROVERS)],
    session: Annotated[Session, Depends(get_session)],
    status: Literal["pending", "approved"] = "pending",
) -> list[ApprovalOut]:
    """承認待ちの一覧（長く待っている順）。status=approved は、公開を取り下げる対象を探す一覧。"""
    return [_out(row, user) for row in approvals.list_approvals(session, user, status)]


@router.get("/count")
def count_pending(
    user: Annotated[CurrentUser, Depends(ANY_STAFF)],
    session: Annotated[Session, Depends(get_session)],
) -> CountOut:
    """承認待ちの件数（施設全体）。リーダー・施設長以外は null。"""
    return CountOut(count=approvals.count_pending_memos(session, user))


@router.post("/{memo_id}/approve")
def approve_memo(
    memo_id: int,
    user: Annotated[CurrentUser, Depends(APPROVERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ApprovalOut:
    """承認する。本人は 403 `self_approval`、ほかの人が先に動かしたときは 409 `invalid_state`。"""
    row = approvals.approve(session, user, memo_id)
    session.commit()
    return _out(row, user)


@router.post("/{memo_id}/return")
def return_memo(
    memo_id: int,
    body: ReasonBody,
    user: Annotated[CurrentUser, Depends(APPROVERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ApprovalOut:
    """理由を書いて戻す。書いた職員が直して、もう一度「確かめました」を押せる（FR-013）。"""
    row = approvals.return_memo(session, user, memo_id, body.reason)
    session.commit()
    return _out(row, user)


@router.post("/{memo_id}/unpublish")
def unpublish_memo(
    memo_id: int,
    body: ReasonBody,
    user: Annotated[CurrentUser, Depends(APPROVERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ApprovalOut:
    """承認済みの公開を取り下げる。家族から見えなくなり、状態は「戻し」になる（FR-013a）。"""
    row = approvals.unpublish(session, user, memo_id, body.reason)
    session.commit()
    return _out(row, user)
