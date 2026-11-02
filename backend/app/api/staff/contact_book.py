"""職員の連絡帳の見返しの API（spec 001 の 001-T029）。

contracts の `GET /api/staff/residents/{id}/contact-book?date=`。

その日の記録と返事を、それぞれ時刻の順に返す（FR-024）。
職員向けなので、非開示の項目も含めて記録を直接読む
（共通の関数 get_disclosed_records は通さない。R-06）。
返事は取り消さず、開示の設定もないので、家族に出すものと同じ get_active_replies を使う。
記録の画面（001-T032）も、今付いている値を出すためにこれを使う。
返事には、直すための値（選んだ定型文の id・そのテーマの定型文・今日直せるか）も付ける（001-T063）。
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
from app.models.disclosure import ReplyTemplate
from app.models.records import CareRecord
from app.models.replies import Reply
from app.models.requests import Request
from app.services.disclosure import get_active_replies
from app.services.resident_names import name_ruby, resident_display_name

router = APIRouter(prefix="/api/staff", tags=["staff"])


class ResidentSummary(BaseModel):
    id: int
    display_name: str
    # ふりがな付きの名前（表示言語が ja のときだけ。#389）
    display_name_ruby: str
    room: str


class StaffRecord(BaseModel):
    id: int
    item: str
    slot: str
    value: str
    recorded_at: datetime
    recorded_by_name: str


class TemplateOption(BaseModel):
    id: int
    code: str  # 辞書のキー（例："template.meals.well"）


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
    # 直すための値（001-T063）：選んだ定型文の id（選んだ順）、そのテーマの定型文、今日直せるか
    template_ids: list[int]
    template_options: list[TemplateOption]
    editable: bool


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
    today = today_jst()
    # 直すための値。返事の数だけ問い合わせないよう、まとめて読む
    editing = {
        reply_id: (template_ids, theme_id)
        for reply_id, template_ids, theme_id in session.execute(
            select(Reply.id, Reply.template_ids, Request.theme_id)
            .join(Request, Request.id == Reply.request_id)
            .where(Reply.id.in_([reply.id for reply in replies]))
        )
    }
    # 定型文の候補は、今日直せる返事のテーマの分だけ読む（前の日の返事は直せないので空にする）
    editable_themes = {
        editing[reply.id][1] for reply in replies if reply.contact_book_date == today
    }
    options: dict[int, list[TemplateOption]] = {}
    for theme_id, template_id, code in session.execute(
        select(ReplyTemplate.theme_id, ReplyTemplate.id, ReplyTemplate.code)
        .where(ReplyTemplate.theme_id.in_(editable_themes))
        .order_by(ReplyTemplate.theme_id, ReplyTemplate.sort_order, ReplyTemplate.id)
    ):
        options.setdefault(theme_id, []).append(TemplateOption(id=template_id, code=code))

    return StaffContactBook(
        date=target,
        resident=ResidentSummary(
            id=resident.id,
            display_name=resident_display_name(resident, user.language),
            display_name_ruby=name_ruby(
                resident_display_name(resident, user.language), resident.name_kana, user.language
            ),
            room=resident.room,
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
                template_ids=editing[reply.id][0],
                template_options=(
                    options.get(editing[reply.id][1], [])
                    if reply.contact_book_date == today
                    else []
                ),
                editable=reply.contact_book_date == today,
            )
            for reply in replies
        ],
    )
