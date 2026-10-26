"""職員の「家族からのメッセージ」の一覧・件数・詳細の API（spec 004 の 004-T025）。

- `GET /api/staff/messages?status=&resident_id=`：一覧。
  対応待ち → 担当が自分か空 → 古い順（FR-012・FR-016b）
- `GET /api/staff/messages/count?resident_id=`：対応待ちの件数（FR-013）
- `GET /api/staff/messages/{id}`：詳細。原文・直前の 3 往復・追加された家族の書き込み・
  その種類の定型文（FR-011・FR-012）

どれも visible_staff_messages(user) を通す。苦情は生活相談員・施設長だけに出し、
ほかの役割が id で開いたら 404（research.md R-12）。家族が呼んだら 403。
詳細の直前の 3 往復も、ほかの役割には苦情の発言を除く（visible_conversation_messages）。
職員への通知・音は出さない（SC-008）。職員が画面を開いたときに見せる。
「担当が空なら 24 時間でいちばん上に」の並び（004-T035）は、作り込みで足す。
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.orm import Session

from app import clock
from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.inquiry.visibility import (
    count_waiting_staff_messages,
    visible_conversation_messages,
    visible_staff_messages,
)
from app.models.core import Resident, Staff
from app.models.inquiry import (
    InquiryMessage,
    StaffMessage,
    StaffMessageTemplate,
)

router = APIRouter(prefix="/api/staff", tags=["staff"])

# 役割の略号 S（事務員も含む職員全員）。苦情の絞り込みは visible_staff_messages が行う
STAFF = require_staff()

# 直前の 3 往復（家族 3・AI／職員 3）。それより前は職員に見せない（FR-012・data-model.md）
PREVIOUS_TURNS = 3
# 「1 日以上待っています」（そのままの時間で数える。research.md R-13）
WAITING_LONG = timedelta(hours=24)


class AssigneeOut(BaseModel):
    id: int
    display_name: str


class StaffMessageRow(BaseModel):
    id: int
    resident_id: int
    resident_display_name: str
    category: str
    assignee: AssigneeOut | None
    summary: str
    status: str
    # 受け付けた日時（最初に渡した日時）
    handed_at: datetime
    # 経過日数と「1 日以上待っています」は、対応待ちに戻った日時があればそこから数える
    elapsed_days: int
    waiting_over_a_day: bool


class StaffMessageListResponse(BaseModel):
    messages: list[StaffMessageRow]


class CountResponse(BaseModel):
    count: int


class ConversationMessageOut(BaseModel):
    id: int
    sender: str  # family／ai／staff
    body: str
    created_at: datetime
    # 職員の発言だけ：選んだ定型文のコードと、書き足した文
    template_codes: list[str] | None = None
    note: str | None = None


class TemplateOut(BaseModel):
    id: int
    code: str  # 辞書のキー（例："staff_template.care_request.next_visit"）


class StaffMessageDetail(StaffMessageRow):
    # 質問の原文（渡すきっかけになった家族の発言）
    origin: ConversationMessageOut
    # 原文の直前の 3 往復（古い順）
    previous: list[ConversationMessageOut]
    # 渡したあとに、このメッセージに続けて家族が書いたもの（古い順）
    follow_ups: list[ConversationMessageOut]
    # その種類の定型文（苦情には用意しないので空）
    templates: list[TemplateOut]


def _waiting_since() -> ColumnElement[datetime]:
    return func.coalesce(StaffMessage.reopened_at, StaffMessage.handed_at)


def _row(
    message: StaffMessage, resident_name: str, assignee: Staff | None, now: datetime
) -> StaffMessageRow:
    elapsed = now - (message.reopened_at or message.handed_at)
    return StaffMessageRow(
        id=message.id,
        resident_id=message.resident_id,
        resident_display_name=resident_name,
        category=message.category,
        assignee=AssigneeOut(id=assignee.id, display_name=assignee.display_name)
        if assignee
        else None,
        summary=message.summary,
        status=message.status,
        handed_at=message.handed_at,
        elapsed_days=max(elapsed // timedelta(days=1), 0),
        waiting_over_a_day=message.status == "waiting" and elapsed >= WAITING_LONG,
    )


def _with_names(user: CurrentUser):
    """見られるメッセージに、入居者の呼び名と担当の職員を付けて選ぶ問い合わせ。"""
    return (
        visible_staff_messages(user)
        .join(Resident, Resident.id == StaffMessage.resident_id)
        .outerjoin(Staff, Staff.id == StaffMessage.assignee_id)
        .add_columns(Resident.display_name, Staff)
    )


@router.get("/messages")
def list_messages(
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
    status: Literal["waiting", "answered"] | None = None,
    resident_id: Annotated[int | None, Query()] = None,
) -> StaffMessageListResponse:
    """一覧。status・resident_id を省くと、見られるものすべて。"""
    query = _with_names(user).order_by(
        # 対応待ちを先に
        case((StaffMessage.status == "waiting", 0), else_=1),
        # 担当が自分か空のものを先に
        case(
            (StaffMessage.assignee_id.is_(None), 0),
            (StaffMessage.assignee_id == user.staff_id, 0),
            else_=1,
        ),
        # 古い順
        _waiting_since(),
        StaffMessage.id,
    )
    if status is not None:
        query = query.where(StaffMessage.status == status)
    if resident_id is not None:
        query = query.where(StaffMessage.resident_id == resident_id)
    now = clock.now()
    return StaffMessageListResponse(
        messages=[
            _row(message, resident_name, assignee, now)
            for message, resident_name, assignee in session.execute(query)
        ]
    )


@router.get("/messages/count")
def count_messages(
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
    resident_id: Annotated[int | None, Query()] = None,
) -> CountResponse:
    """対応待ちの件数。resident_id を省くと施設全体。苦情は生活相談員・施設長にだけ数える。"""
    return CountResponse(count=count_waiting_staff_messages(session, user, resident_id))


def _message_out(message: InquiryMessage, codes: dict[int, str]) -> ConversationMessageOut:
    return ConversationMessageOut(
        id=message.id,
        sender=message.sender,
        body=message.body,
        created_at=message.created_at,
        template_codes=[codes[i] for i in message.template_ids if i in codes]
        if message.template_ids
        else None,
        note=message.note,
    )


@router.get("/messages/{message_id}")
def get_message(
    message_id: int,
    user: Annotated[CurrentUser, Depends(STAFF)],
    session: Annotated[Session, Depends(get_session)],
) -> StaffMessageDetail:
    """詳細。見られないメッセージ（ほかの役割の苦情・ないもの）は 404。"""
    found = session.execute(_with_names(user).where(StaffMessage.id == message_id)).one_or_none()
    if found is None:
        raise AppError(ErrorCode.NOT_FOUND)
    message, resident_name, assignee = found

    origin = session.get_one(InquiryMessage, message.origin_message_id)
    # 原文の直前の 6 件（家族 3・AI／職員 3）を取り出し、その中から見せられないもの
    # （生活相談員・施設長以外には苦情の発言）を除く。除いた分、さらに前は取りに行かない
    last_six = (
        select(InquiryMessage.id)
        .where(
            InquiryMessage.conversation_id == message.conversation_id,
            InquiryMessage.id < origin.id,
        )
        .order_by(InquiryMessage.id.desc())
        .limit(PREVIOUS_TURNS * 2)
    )
    previous = session.scalars(
        select(InquiryMessage)
        .where(InquiryMessage.id.in_(last_six), visible_conversation_messages(user))
        .order_by(InquiryMessage.id)
    ).all()
    follow_ups = session.scalars(
        select(InquiryMessage)
        .where(
            InquiryMessage.staff_message_id == message.id,
            InquiryMessage.sender == "family",
            InquiryMessage.id > origin.id,
        )
        .order_by(InquiryMessage.id)
    ).all()
    templates = session.scalars(
        select(StaffMessageTemplate)
        .where(StaffMessageTemplate.category == message.category)
        .order_by(StaffMessageTemplate.sort_order, StaffMessageTemplate.id)
    ).all()

    # 直前のやりとりにある職員の返事の定型文を、コードに直す
    template_ids = {i for m in previous for i in (m.template_ids or [])}
    codes = (
        dict(
            session.execute(
                select(StaffMessageTemplate.id, StaffMessageTemplate.code).where(
                    StaffMessageTemplate.id.in_(template_ids)
                )
            ).all()
        )
        if template_ids
        else {}
    )

    row = _row(message, resident_name, assignee, clock.now())
    return StaffMessageDetail(
        **row.model_dump(),
        origin=_message_out(origin, codes),
        previous=[_message_out(m, codes) for m in previous],
        follow_ups=[_message_out(m, codes) for m in follow_ups],
        templates=[TemplateOut(id=t.id, code=t.code) for t in templates],
    )
