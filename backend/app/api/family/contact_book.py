"""家族の連絡帳の API（spec 001 の 001-T055。contracts の「家族」）。

`GET /api/family/contact-book?date=`（日付を省くと日本時間の今日）。
入居者は、ログイン中の家族の CurrentUser.resident_id から決める（送られた値は使わない。FR-020）。

- unread_replies：まだ読んでいない返事。日付に関わらず、すべて（FR-015）
- day_replies：その日の、もう読んだ返事（未読は上の unread_replies に出すので、重ねない）
- sections：開示している項目だけ、食事（朝・昼・夜・おやつ）→ 機嫌・様子 → 眠りの順。
  まだ記録がない欄は、record を null にして、message_key（辞書のキー）を返す（FR-017）。
  ただし、おやつは、記録があるときだけ欄を出す（毎日付けるとは限らないため）

記録は get_disclosed_records、返事は get_active_replies を通す（直接読まない。R-06）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.clock import today_jst
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.records import DAY_SLOT, ITEMS, MEAL_SLOTS
from app.services.disclosure import (
    DisclosedRecord,
    DisclosedReply,
    get_active_replies,
    get_disclosed_records,
    is_item_disclosed,
)

router = APIRouter(prefix="/api/family", tags=["family"])

# 「まだ記録されていません」の辞書のキー
NOT_RECORDED_KEY = "contact_book.not_recorded"
# 記録があるときだけ出す欄（毎日付けるとは限らないもの）
OPTIONAL_SLOTS = ("snack",)


class RecordOut(BaseModel):
    id: int
    value: str
    recorded_at: datetime
    recorded_by_name: str


class SlotOut(BaseModel):
    slot: str
    record: RecordOut | None
    # 記録がないときだけ入る
    message_key: str | None


class SectionOut(BaseModel):
    item: str
    slots: list[SlotOut]


class ReplyOut(BaseModel):
    id: int
    contact_book_date: date
    theme_code: str
    theme_emoji: str
    template_codes: list[str]
    # 職員が書き足した文。辞書を通さず、文字としてだけ出す
    note: str | None
    replied_by_name: str
    # 職種のコード（画面が辞書の occupation.* で引き、「表示名（職種）からの返事」と出す。#263）。
    # 空なら、画面は名前だけを出す
    replied_by_occupation: str | None
    replied_at: datetime
    edited: bool
    read: bool


class ContactBookResponse(BaseModel):
    date: date
    unread_replies: list[ReplyOut]
    day_replies: list[ReplyOut]
    sections: list[SectionOut]


def _reply_out(reply: DisclosedReply) -> ReplyOut:
    return ReplyOut(
        id=reply.id,
        contact_book_date=reply.contact_book_date,
        theme_code=reply.theme_code,
        theme_emoji=reply.theme_emoji,
        template_codes=reply.template_codes,
        note=reply.note,
        replied_by_name=reply.replied_by_name,
        replied_by_occupation=reply.replied_by_occupation,
        replied_at=reply.replied_at,
        edited=reply.edited,
        read=reply.read,
    )


def _slot_out(slot: str, record: DisclosedRecord | None) -> SlotOut:
    if record is None:
        return SlotOut(slot=slot, record=None, message_key=NOT_RECORDED_KEY)
    return SlotOut(
        slot=slot,
        record=RecordOut(
            id=record.id,
            value=record.value,
            recorded_at=record.recorded_at,
            recorded_by_name=record.recorded_by_name,
        ),
        message_key=None,
    )


@router.get("/contact-book")
def get_contact_book(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
    day: Annotated[date | None, Query(alias="date")] = None,
) -> ContactBookResponse:
    """その日の連絡帳。まだ読んでいない返事を先頭に、開示している項目の記録、未記録の欄。"""
    if user.resident_id is None:
        raise AppError(ErrorCode.FORBIDDEN)
    target = day or today_jst()

    records = {
        (record.item, record.slot): record
        for record in get_disclosed_records(session, user.resident_id, target, target)
    }
    sections = [
        SectionOut(
            item=item,
            slots=[
                _slot_out(slot, records.get((item, slot)))
                for slot in (MEAL_SLOTS if item == "meal" else (DAY_SLOT,))
                # おやつは、毎日付けるとは限らない。付けない日に「まだ記録されていません」と
                # 出ると、記録し忘れに見えるので、記録があるときだけ出す（FR-017 の例外）
                if slot not in OPTIONAL_SLOTS or (item, slot) in records
            ],
        )
        for item in ITEMS
        if is_item_disclosed(session, item)
    ]

    replies = get_active_replies(session, user.resident_id, date.min, date.max)
    return ContactBookResponse(
        date=target,
        unread_replies=[_reply_out(reply) for reply in replies if not reply.read],
        day_replies=[
            _reply_out(reply)
            for reply in replies
            if reply.read and reply.contact_book_date == target
        ],
        sections=sections,
    )
