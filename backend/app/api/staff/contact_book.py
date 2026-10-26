"""職員の連絡帳の見返しの API（spec 001 の 001-T029）。

contracts の `GET /api/staff/residents/{id}/contact-book?date=`。

その日の記録と返事を、それぞれ時刻の順に返す（FR-024）。
職員向けなので、非開示の項目も含めて記録を直接読む
（共通の関数 get_disclosed_records は通さない。R-06）。
返事は取り消さず、開示の設定もないので、家族に出すものと同じ get_active_replies を使う。
記録の画面（001-T032）も、今付いている値を出すためにこれを使う。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.staff.records import RECORDERS
from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import Resident, Staff
from app.models.records import CareRecord
from app.services.disclosure import get_active_replies

router = APIRouter(prefix="/api/staff", tags=["staff"])


class ResidentSummary(BaseModel):
    id: int
    display_name: str
    room: str


class StaffRecord(BaseModel):
    id: int
    item: str
    slot: str
    value: str
    recorded_at: datetime
    recorded_by_name: str


class StaffReply(BaseModel):
    id: int
    request_id: int
    theme_code: str
    theme_emoji: str
    template_codes: list[str]
    # 職員が書き足した文。辞書を通さず、文字としてだけ出す
    note: str | None
    replied_by_name: str
    replied_at: datetime
    edited: bool
    read: bool


class StaffContactBook(BaseModel):
    date: date
    resident: ResidentSummary
    records: list[StaffRecord]
    replies: list[StaffReply]


@router.get("/residents/{resident_id}/contact-book")
def get_contact_book(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
    day: Annotated[date | None, Query(alias="date")] = None,
) -> StaffContactBook:
    """その日の記録（取り消したものは除く）と返事を、時刻の順に返す。日付を省くと今日（日本時間）。"""
    resident = session.get(Resident, resident_id)
    if resident is None:
        raise AppError(ErrorCode.NOT_FOUND)
    target = day or today_jst()

    rows = session.execute(
        select(CareRecord, Staff.display_name)
        .join(Staff, Staff.id == CareRecord.recorded_by)
        .where(
            CareRecord.resident_id == resident_id,
            CareRecord.date == target,
            CareRecord.deleted_at.is_(None),
        )
        .order_by(CareRecord.recorded_at, CareRecord.id)
    )
    replies = get_active_replies(session, resident_id, target, target)

    return StaffContactBook(
        date=target,
        resident=ResidentSummary(
            id=resident.id, display_name=resident.display_name, room=resident.room
        ),
        records=[
            StaffRecord(
                id=record.id,
                item=record.item,
                slot=record.slot,
                value=record.value,
                recorded_at=record.recorded_at,
                recorded_by_name=staff_name,
            )
            for record, staff_name in rows
        ],
        replies=[
            StaffReply(
                id=reply.id,
                request_id=reply.request_id,
                theme_code=reply.theme_code,
                theme_emoji=reply.theme_emoji,
                template_codes=reply.template_codes,
                note=reply.note,
                replied_by_name=reply.replied_by_name,
                replied_at=reply.replied_at,
                edited=reply.edited,
                read=reply.read,
            )
            for reply in replies
        ],
    )
