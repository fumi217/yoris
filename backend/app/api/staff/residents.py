"""職員の入居者一覧の API（spec 001 の 001-T028、spec 004 の 004-T030）。

`GET /api/staff/residents?date=`：入居者ごとに、その日の食事区分ごとの記録済み／未記録と、
家族からのメッセージの対応待ちの件数を返す（FR-008・spec 004 の FR-013）。
並びは入居の順（residents.id の小さい順。docs/画面設計.md の「4」）。
職員向けなので、非開示の項目も含めて記録を直接読んでよい（spec 001 の research.md R-06）。
返事待ちのリクエストの件数（001-T053）も返す。
変化の目印（spec 006 の 006-T011）：入居者ごとの目印と、まだ確かめていない目印がある
入居者の人数を返す。
並べ替え（目印のある入居者を先に）と絞り込みは、画面の側で行う（API は入居の順のまま）。
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.staff.records import RECORDERS
from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.db import get_session
from app.inquiry.visibility import count_waiting_staff_messages_by_resident
from app.models.core import Resident
from app.models.records import MEAL_SLOTS, CareRecord
from app.models.requests import Request
from app.services.change_detection import get_flag_summary
from app.services.resident_names import name_ruby, resident_display_name

router = APIRouter(prefix="/api/staff", tags=["staff"])


class MealsRecorded(BaseModel):
    breakfast: bool
    lunch: bool
    dinner: bool
    snack: bool


class ChangeFlagMark(BaseModel):
    # 今の目印がある（確かめ済みも含む）
    has_flag: bool
    # まだ確かめていない目印がある
    has_unconfirmed: bool


class ResidentRow(BaseModel):
    id: int
    display_name: str
    # ふりがな付きの名前（表示言語が ja のときだけ。#389）
    display_name_ruby: str
    room: str
    # その日に記録済みか（食事は区分ごと）。未記録が分かるように（FR-008）
    meals: MealsRecorded
    mood: bool
    sleep: bool
    # 返事待ちの「知りたいこと」のリクエストの件数（FR-029）
    waiting_requests: int
    # 家族からのメッセージの対応待ちの件数（苦情は生活相談員・施設長にだけ数える。spec 004）
    waiting_messages: int
    # 変化の目印（spec 006 の FR-003）。今の目印がなければ null
    change_flag: ChangeFlagMark | None


class ResidentListResponse(BaseModel):
    date: date
    residents: list[ResidentRow]
    # まだ確かめていない目印がある入居者の人数（spec 006 の FR-003・research.md R-04）
    unconfirmed_flag_count: int


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
    waiting_requests = dict(
        session.execute(
            select(Request.resident_id, func.count())
            .where(Request.status == "waiting")
            .group_by(Request.resident_id)
        ).all()
    )

    # 目印も、全員の分を 1 回で読む（spec 006 の 006-T011）
    flags = get_flag_summary(session)

    rows = []
    for resident in residents:
        flag = flags.residents.get(resident.id)
        display_name = resident_display_name(resident, user.language)
        meals = {slot: (resident.id, "meal", slot) in recorded for slot in MEAL_SLOTS}
        rows.append(
            ResidentRow(
                id=resident.id,
                display_name=display_name,
                display_name_ruby=name_ruby(display_name, resident.name_kana, user.language),
                room=resident.room,
                meals=MealsRecorded(**meals),
                mood=(resident.id, "mood", "day") in recorded,
                sleep=(resident.id, "sleep", "day") in recorded,
                waiting_requests=waiting_requests.get(resident.id, 0),
                waiting_messages=waiting.get(resident.id, 0),
                change_flag=(
                    ChangeFlagMark(has_flag=flag.has_flag, has_unconfirmed=flag.has_unconfirmed)
                    if flag
                    else None
                ),
            )
        )
    return ResidentListResponse(
        date=day, residents=rows, unconfirmed_flag_count=flags.unconfirmed_resident_count
    )
