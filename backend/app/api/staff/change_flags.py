"""変化の目印の API（spec 006 の 006-T012）。

`GET /api/staff/residents/{id}/change-flags`：その入居者の今の目印と、過去の目印（新しい順）。
見られるのは、介護職員・リーダー・生活相談員・施設長（事務員と家族は 403。FR-006）。
文言は返さず、決まりのコード・記録のコード・続いた数だけを返す（research.md R-06）。
確かめた職員は表示名だけ返す。ひとこと（note）は職員が書いたまま返す（画面は文字としてだけ出す。FR-013）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.change_flags import ChangeFlag, ChangeFlagConfirmation
from app.models.core import Resident, Staff

router = APIRouter(prefix="/api/staff", tags=["staff"])

FLAG_VIEWERS = require_staff(("care_worker", "leader", "counselor", "director"))


class EvidenceItem(BaseModel):
    record_id: int
    date: date
    slot: str
    value: str


class ConfirmationItem(BaseModel):
    staff_display_name: str
    confirmed_at: datetime
    note: str | None


class ChangeFlagItem(BaseModel):
    id: int
    rule_code: str
    status: str
    started_at: datetime
    streak: int
    evidence: list[EvidenceItem]
    confirmations: list[ConfirmationItem]


class ClearedFlagItem(ChangeFlagItem):
    cleared_at: datetime
    cleared_reason: str


class ChangeFlagsResponse(BaseModel):
    current: list[ChangeFlagItem]
    history: list[ClearedFlagItem]


@router.get("/residents/{resident_id}/change-flags")
def get_change_flags(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(FLAG_VIEWERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ChangeFlagsResponse:
    """今の目印と、過去の目印。決まりがオフでも、過去の目印は出す。ない入居者は 404。"""
    if session.get(Resident, resident_id) is None:
        raise AppError(ErrorCode.NOT_FOUND)
    flags = session.scalars(
        select(ChangeFlag).where(ChangeFlag.resident_id == resident_id).order_by(ChangeFlag.id)
    ).all()
    confirmations: dict[int, list[ConfirmationItem]] = {flag.id: [] for flag in flags}
    for confirmation, display_name in session.execute(
        select(ChangeFlagConfirmation, Staff.display_name)
        .join(Staff, Staff.id == ChangeFlagConfirmation.confirmed_by)
        .where(ChangeFlagConfirmation.change_flag_id.in_([flag.id for flag in flags]))
        .order_by(ChangeFlagConfirmation.confirmed_at, ChangeFlagConfirmation.id)
    ):
        confirmations[confirmation.change_flag_id].append(
            ConfirmationItem(
                staff_display_name=display_name,
                confirmed_at=confirmation.confirmed_at,
                note=confirmation.note,
            )
        )

    def common(flag: ChangeFlag) -> dict:
        return {
            "id": flag.id,
            "rule_code": flag.rule_code,
            "status": flag.status,
            "started_at": flag.started_at,
            "streak": flag.streak,
            "evidence": flag.evidence,
            "confirmations": confirmations[flag.id],
        }

    cleared = sorted(
        (flag for flag in flags if flag.cleared_at is not None),
        key=lambda flag: (flag.cleared_at, flag.id),
        reverse=True,
    )
    return ChangeFlagsResponse(
        current=[ChangeFlagItem(**common(flag)) for flag in flags if flag.cleared_at is None],
        history=[
            ClearedFlagItem(
                **common(flag), cleared_at=flag.cleared_at, cleared_reason=flag.cleared_reason
            )
            for flag in cleared
        ],
    )
