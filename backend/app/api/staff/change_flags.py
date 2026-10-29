"""変化の目印の API（spec 006 の 006-T012）。

`GET /api/staff/residents/{id}/change-flags`：その入居者の今の目印と、過去の目印（新しい順）。
見られるのは、介護職員・リーダー・生活相談員・施設長（事務員と家族は 403。FR-006）。
`POST /api/staff/residents/{id}/change-flags/confirm`（006-T017）：まだ確かめていない目印を、
まとめて確かめ済みにする。同じ役割が押せる。ない入居者・ほかの施設の入居者は 404、
確かめていない目印がなければ 409 `already_confirmed`。
文言は返さず、決まりのコード・記録のコード・続いた数だけを返す（research.md R-06）。
確かめた職員は表示名だけ返す。ひとこと（note）は職員が書いたまま返す（画面は文字としてだけ出す。FR-013）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.change_flags import NOTE_MAX_LENGTH, ChangeFlag, ChangeFlagConfirmation
from app.models.core import Resident, Staff
from app.services.change_detection import confirm_change_flags

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


def _check_resident(session: Session, user: CurrentUser, resident_id: int) -> None:
    """入居者は、見る・確かめる職員と同じ施設のときだけ。ない入居者・ほかの施設の入居者は 404。

    様子のメモの API と同じ作り（#326・#327）。今は施設が 1 つだけなので、防御の層。
    """
    assert user.staff_id is not None
    resident = session.get(Resident, resident_id)
    facility_id = session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()
    if resident is None or resident.facility_id != facility_id:
        raise AppError(ErrorCode.NOT_FOUND)


@router.get("/residents/{resident_id}/change-flags")
def get_change_flags(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(FLAG_VIEWERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ChangeFlagsResponse:
    """今の目印と、過去の目印。決まりがオフでも、過去の目印は出す。ない入居者・ほかの施設は 404。"""
    _check_resident(session, user, resident_id)
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


class ConfirmRequest(BaseModel):
    # ひとこと（任意）。100 文字を超えたら 422（FR-009）。文字としてだけ扱う（FR-013）
    note: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)

    @field_validator("note", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        # 前後の空白を取ってから、100 文字の検査をする（空白だけは、あとで「なし」になる）
        return value.strip() if isinstance(value, str) else value


class ConfirmResponse(BaseModel):
    confirmed: int


@router.post("/residents/{resident_id}/change-flags/confirm")
def confirm_flags(
    resident_id: int,
    body: ConfirmRequest,
    user: Annotated[CurrentUser, Depends(FLAG_VIEWERS)],
    session: Annotated[Session, Depends(get_session)],
) -> ConfirmResponse:
    """まだ確かめていない目印を、まとめて確かめ済みにする。確かめた職員は、ログイン中の職員から決める。"""
    _check_resident(session, user, resident_id)
    assert user.staff_id is not None
    confirmed = confirm_change_flags(session, resident_id, user.staff_id, body.note)
    session.commit()
    return ConfirmResponse(confirmed=confirmed)
