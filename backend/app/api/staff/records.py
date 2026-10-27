"""記録の API（spec 001 の 001-T027・T034）。

contracts の `PUT /api/staff/residents/{id}/records`・`DELETE /api/staff/records/{id}`。

記録できるのは、介護職員・リーダー・生活相談員・施設長（事務員と家族は 403）。
保存の決まり（押し直し・3 日前まで・今日だけ直せる）は services/records.py の save_record、
取り消し（今日の記録だけ）は delete_record にある。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import Resident
from app.services.records import RecordError, delete_record, save_record

router = APIRouter(prefix="/api/staff", tags=["staff"])

RECORDERS = require_staff(("care_worker", "leader", "counselor", "director"))


class RecordRequest(BaseModel):
    # 決まりの外の項目（resident_id など）は受け付けない
    model_config = ConfigDict(extra="forbid")

    date: date
    item: str  # "meal" / "mood" / "sleep"
    slot: str  # 食事は "breakfast" / "lunch" / "dinner" / "snack"、機嫌・眠りは "day"
    value: str  # app.models.records.VALUES のコード


class RecordResponse(BaseModel):
    id: int
    date: date
    item: str
    slot: str
    value: str
    recorded_at: datetime


@router.put("/residents/{resident_id}/records")
def put_record(
    resident_id: int,
    body: RecordRequest,
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
) -> RecordResponse:
    """記録を付ける。同じ日・項目・区分の記録があれば押し直す（上書きし、前の値を履歴に残す）。"""
    if session.get(Resident, resident_id) is None:
        raise AppError(ErrorCode.NOT_FOUND)
    try:
        record = save_record(
            session,
            resident_id=resident_id,
            staff_id=user.staff_id,
            record_date=body.date,
            item=body.item,
            slot=body.slot,
            value=body.value,
        )
    except RecordError as error:
        raise AppError(ErrorCode(error.code)) from error
    session.commit()
    return RecordResponse(
        id=record.id,
        date=record.date,
        item=record.item,
        slot=record.slot,
        value=record.value,
        recorded_at=record.recorded_at,
    )


@router.delete("/records/{record_id}", status_code=204)
def cancel_record(
    record_id: int,
    user: Annotated[CurrentUser, Depends(RECORDERS)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """今日の記録を取り消す（001-T034）。ない・もう取り消した記録は 404、今日でなければ 409。"""
    try:
        delete_record(session, record_id=record_id, staff_id=user.staff_id)
    except RecordError as error:
        raise AppError(ErrorCode(error.code)) from error
    session.commit()
