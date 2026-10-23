"""職員の入居者一覧の API（spec 001 の 001-T028、spec 004 の 004-T030）。

`GET /api/staff/residents?date=`：入居者ごとに、その日の食事区分ごとの記録済み／未記録と、
家族からのメッセージの対応待ちの件数を返す（FR-008・spec 004 の FR-013）。
並びは入居の順（residents.id の小さい順。docs/画面設計.md の「4」）。
職員向けなので、非開示の項目も含めて記録を直接読んでよい（spec 001 の research.md R-06）。
返事待ちのリクエストの件数は、#114（001-T053）で足す。
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.staff.records import RECORDERS
from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.db import get_session
from app.inquiry.visibility import count_waiting_staff_messages_by_resident
from app.models.core import Resident
from app.models.records import MEAL_SLOTS, CareRecord

router = APIRouter(prefix="/api/staff", tags=["staff"])


class MealsRecorded(BaseModel):
    breakfast: bool
    lunch: bool
    dinner: bool
    snack: bool


class ResidentRow(BaseModel):
    id: int
    display_name: str
    room: str
    # その日に記録済みか（食事は区分ごと）。未記録が分かるように（FR-008）
    meals: MealsRecorded
    mood: bool
    sleep: bool
    # 家族からのメッセージの対応待ちの件数（苦情は生活相談員・施設長にだけ数える。spec 004）
    waiting_messages: int


class ResidentListResponse(BaseModel):
    date: date
    residents: list[ResidentRow]


@router.get("/residents")
def list_residents(
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
    day: Annotated[date | None, Query(alias="date")] = None,
) -> ResidentListResponse:
    """入居者一覧。date を省くと、日本時間の今日。事務員と家族は 403。"""
    day = day or today_jst()
    residents = session.scalars(select(Resident).order_by(Resident.id)).all()
    recorded = set(
        session.execute(
            select(CareRecord.resident_id, CareRecord.item, CareRecord.slot).where(
                CareRecord.date == day, CareRecord.deleted_at.is_(None)
            )
        ).all()
    )
    # 全員の件数を 1 回の問い合わせで数える（1 人ずつ数えない。PR #42）
    waiting = count_waiting_staff_messages_by_resident(session, user)

    rows = []
    for resident in residents:
        meals = {slot: (resident.id, "meal", slot) in recorded for slot in MEAL_SLOTS}
        rows.append(
            ResidentRow(
                id=resident.id,
                display_name=resident.display_name,
                room=resident.room,
                meals=MealsRecorded(**meals),
                mood=(resident.id, "mood", "day") in recorded,
                sleep=(resident.id, "sleep", "day") in recorded,
                waiting_messages=waiting.get(resident.id, 0),
            )
        )
    return ResidentListResponse(date=day, residents=rows)
