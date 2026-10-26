"""職員の返事のテーブル（spec 001 の data-model.md「replies」、001-T047）。

1 つのリクエストへの返事は 1 つだけ（返事は取り消さない。FR-030）。
保存は、requests の条件つきの更新と同じトランザクションで行う
（research.md R-07。services/replies.py）。
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 書き足す短い文の上限（FR-030）
MAX_NOTE_LENGTH = 100


class Reply(Base):
    """リクエストへの職員の返事。"""

    __tablename__ = "replies"
    __table_args__ = (
        # 定型文は 1 つ以上（FR-030）
        CheckConstraint("cardinality(template_ids) >= 1", name="template_ids_not_empty"),
        CheckConstraint(f"char_length(note) <= {MAX_NOTE_LENGTH}", name="note_length"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # 1 つのリクエストへの返事は 1 つだけ
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), unique=True)
    # 選んだ定型文（reply_templates.id。1 つ以上）
    template_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    # 書き足した短い文（任意）。辞書を通さず、文字としてだけ出す
    note: Mapped[str | None]
    replied_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    replied_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 返事が入る連絡帳の日付（返事をした日、日本時間）
    contact_book_date: Mapped[date]
    # 当日中に直したら入れる（未読には戻さない。再通知しない。001-T063）
    edited_at: Mapped[datetime | None]
    # 家族が読んだ時刻（家族で共有。FR-015）
    read_at: Mapped[datetime | None]
