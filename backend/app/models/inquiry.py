"""問い合わせ AI のテーブル（家族の会話・職員へのメッセージ）。

spec 004 の data-model.md。004-T005。
苦情（category = 'complaint'）は生活相談員・施設長だけが読める。読むところはすべて
app/inquiry/visibility.py の visible_staff_messages(user) を通す（research.md R-12）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

SENDERS = ("family", "ai", "staff")
AI_RESULTS = ("answered", "handed_off", "no_record")
RESPONSE_TYPES = ("app", "phone")
CATEGORIES = ("medical", "complaint", "money", "care_request", "urgent", "other")
# 苦情には定型文を用意しない（spec 004 の data-model.md）
TEMPLATE_CATEGORIES = tuple(c for c in CATEGORIES if c != "complaint")
STATUSES = ("waiting", "answered")
EVENT_TYPES = ("assigned", "unassigned", "reassigned", "category_changed", "reopened", "answered")

# 家族の発言・職員の書き足し・要約の文字数の上限（FR-001・FR-014・data-model.md）
FAMILY_BODY_MAX = 500
NOTE_MAX = 100
SUMMARY_MAX = 500


class InquiryConversation(Base):
    """家族の会話（家族アカウントに 1 本。初めて送ったときに作る）。"""

    __tablename__ = "inquiry_conversations"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    family_account_id: Mapped[int] = mapped_column(ForeignKey("family_accounts.id"), unique=True)
    # 家族アカウントの入居者（探しやすくするため）
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class InquiryMessage(Base):
    """会話の発言（家族・AI・職員）。家族の画面には時刻の順にすべて出す（FR-008）。

    AI への指示の文は保存しない（家族の画面に出すものだけを保存する）。
    """

    __tablename__ = "inquiry_messages"
    __table_args__ = (
        check_in("sender", SENDERS, name="sender"),
        check_in("ai_result", AI_RESULTS, name="ai_result"),
        check_in("response_type", RESPONSE_TYPES, name="response_type"),
        CheckConstraint(
            f"sender <> 'family' OR char_length(body) <= {FAMILY_BODY_MAX}", name="family_body_max"
        ),
        CheckConstraint(f"note IS NULL OR char_length(note) <= {NOTE_MAX}", name="note_max"),
        # 会話を時刻の順に読むため
        Index("ix_inquiry_messages_conversation", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("inquiry_conversations.id"))
    sender: Mapped[str]
    # 発言の文。辞書を通さずそのまま出す（職員の定型文は template_ids から引く）
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # ここから AI の発言だけ
    ai_result: Mapped[str | None]
    # 確かめたあとの根拠（record:<id>・reply:<id>。research.md R-03）
    source_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    model: Mapped[str | None]
    # ツールを呼んだ回数（上限 5）
    tool_calls: Mapped[int | None]
    latency_ms: Mapped[int | None]
    # 職員に渡したもの・職員の返事・家族の続きの書き込みのとき、どのメッセージか。
    # staff_messages も inquiry_messages を指すので、外部キーはテーブルを作ったあとに足す
    staff_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff_messages.id", use_alter=True)
    )
    # ここから職員の発言だけ
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # 選んだ定型文（1 つ以上）
    template_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    # 書き足した短い文（任意）
    note: Mapped[str | None]
    response_type: Mapped[str | None]


class StaffMessage(Base):
    """AI から職員に渡したメッセージ（質問の種類が付く。担当は職員が決める）。"""

    __tablename__ = "staff_messages"
    __table_args__ = (
        check_in("category", CATEGORIES, name="category"),
        check_in("status", STATUSES, name="status"),
        CheckConstraint(f"char_length(summary) <= {SUMMARY_MAX}", name="summary_max"),
        # 対応待ちを入居者ごとに数えるため（件数の関数。data-model.md）
        Index(
            "ix_staff_messages_waiting", "resident_id", postgresql_where=text("status = 'waiting'")
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("inquiry_conversations.id"))
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    # 渡すきっかけになった家族の発言
    origin_message_id: Mapped[int] = mapped_column(ForeignKey("inquiry_messages.id"))
    category: Mapped[str]
    # AI がまとめた要約（日本語）。開示されていない記録の内容は入れない
    summary: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="waiting")
    # 担当（1 人）。渡した時点では空
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # 最初に渡した日時（経過日数・24 時間・3 日はここから。対応待ちに戻ったら reopened_at）
    handed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reopened_at: Mapped[datetime | None]
    # 最後に対応した職員・日時
    responded_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    responded_at: Mapped[datetime | None]


class StaffMessageEvent(Base):
    """職員へのメッセージの履歴（担当・種類・対応）。"""

    __tablename__ = "staff_message_events"
    __table_args__ = (check_in("type", EVENT_TYPES, name="type"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    staff_message_id: Mapped[int] = mapped_column(ForeignKey("staff_messages.id"))
    type: Mapped[str]
    # 操作した職員（家族の続きの書き込みのときは空）
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # 変わる前と後（担当の id・種類のコードなど）
    from_value: Mapped[str | None]
    to_value: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class StaffMessageTemplate(Base):
    """職員の返事の定型文（質問の種類ごとに 3〜5 個。文言は辞書の code で引く）。"""

    __tablename__ = "staff_message_templates"
    __table_args__ = (check_in("category", TEMPLATE_CATEGORIES, name="category"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    category: Mapped[str]
    # 辞書のキー（例：staff_template.care_request.next_visit）
    code: Mapped[str] = mapped_column(unique=True)
    sort_order: Mapped[int]
