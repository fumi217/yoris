"""家族の会話に出す、職員の返事の中身（spec 004 の 004-T027・FR-014・FR-005）。

職員の発言は、返事をした職員の表示名と、選んだ定型文のコード（文言は画面の辞書で引く）と、
書き足した短い文を持つ。職員の発言は職種（役割）ではなく表示名で出す（spec 004 の Clarifications。
看護職員・機能訓練指導員・ケアマネジャーが同じ役割 care_worker のため）。
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Staff
from app.models.inquiry import InquiryMessage, StaffMessageTemplate


@dataclass(frozen=True)
class StaffReplyDetail:
    staff_name: str
    # 選んだ定型文のコード（選んだ順。電話で対応したときは空）
    template_codes: list[str]
    # 書き足した短い文。辞書を通さず、文字としてだけ出す
    note: str | None
    # app（アプリで返事）／phone（電話で対応した）
    response_type: str | None


def load_staff_reply_details(
    session: Session, messages: Iterable[InquiryMessage]
) -> dict[int, StaffReplyDetail]:
    """職員の発言（sender = staff）の中身を、発言の id から引ける形で返す。"""
    staff_messages = [m for m in messages if m.sender == "staff"]
    if not staff_messages:
        return {}
    names = dict(
        session.execute(
            select(Staff.id, Staff.display_name).where(
                Staff.id.in_({m.staff_id for m in staff_messages if m.staff_id is not None})
            )
        ).all()
    )
    template_ids = {i for m in staff_messages for i in (m.template_ids or [])}
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
    return {
        m.id: StaffReplyDetail(
            staff_name=names.get(m.staff_id, ""),
            template_codes=[codes[i] for i in (m.template_ids or []) if i in codes],
            note=m.note,
            response_type=m.response_type,
        )
        for m in staff_messages
    }
