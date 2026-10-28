"""家族の会話に出す、職員の返事の中身（spec 004 の 004-T027・FR-014・FR-005）。

職員の発言は、返事をした職員の表示名と、選んだ定型文のコード（文言は画面の辞書で引く）と、
書き足した短い文を持つ。職員の発言は「表示名（職種）」で出す（spec 004 の Clarifications の
Session 2026-10-27・#263）。職種は役割ではなく職員の occupation（空なら名前だけ）。看護職員・
機能訓練指導員・ケアマネジャーは役割が同じ care_worker のため。
職員の名前と職種は、家族の画面に出すだけで、AI には渡さない（_history には入れない）。
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
    # 職種のコード（辞書の occupation.*）。空なら、画面は名前だけを出す
    staff_occupation: str | None
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
    people = {
        staff_id: (name, occupation)
        for staff_id, name, occupation in session.execute(
            select(Staff.id, Staff.display_name, Staff.occupation).where(
                Staff.id.in_({m.staff_id for m in staff_messages if m.staff_id is not None})
            )
        )
    }
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
            staff_name=people.get(m.staff_id, ("", None))[0],
            staff_occupation=people.get(m.staff_id, ("", None))[1],
            template_codes=[codes[i] for i in (m.template_ids or []) if i in codes],
            note=m.note,
            response_type=m.response_type,
        )
        for m in staff_messages
    }
