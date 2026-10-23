"""inquiry：問い合わせ AI の会話と、職員へのメッセージのテーブル（spec 004 の 004-T005）

inquiry_messages.staff_message_id と staff_messages.origin_message_id がお互いを指すので、
inquiry_messages の外部キーは、staff_messages を作ったあとに足す。

Revision ID: 4f6c0904b452
Revises: c73fd63757f9
Create Date: 2026-10-23 06:28:03.305533

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4f6c0904b452"
down_revision: str | Sequence[str] | None = "c73fd63757f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_message_templates",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "category IN ('medical', 'money', 'care_request', 'urgent', 'other')",
            name=op.f("ck_staff_message_templates_category"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_message_templates")),
        sa.UniqueConstraint("code", name=op.f("uq_staff_message_templates_code")),
    )
    op.create_table(
        "inquiry_conversations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("family_account_id", sa.BigInteger(), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["family_account_id"],
            ["family_accounts.id"],
            name=op.f("fk_inquiry_conversations_family_account_id_family_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_inquiry_conversations_resident_id_residents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiry_conversations")),
        sa.UniqueConstraint(
            "family_account_id", name=op.f("uq_inquiry_conversations_family_account_id")
        ),
    )
    op.create_table(
        "inquiry_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ai_result", sa.Text(), nullable=True),
        sa.Column("source_ids", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.BigInteger(), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("staff_message_id", sa.BigInteger(), nullable=True),
        sa.Column("staff_id", sa.BigInteger(), nullable=True),
        sa.Column("template_ids", postgresql.ARRAY(sa.BigInteger()), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("response_type", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "ai_result IN ('answered', 'handed_off', 'no_record')",
            name=op.f("ck_inquiry_messages_ai_result"),
        ),
        sa.CheckConstraint(
            "response_type IN ('app', 'phone')", name=op.f("ck_inquiry_messages_response_type")
        ),
        sa.CheckConstraint(
            "sender <> 'family' OR char_length(body) <= 500",
            name=op.f("ck_inquiry_messages_family_body_max"),
        ),
        sa.CheckConstraint(
            "sender IN ('family', 'ai', 'staff')", name=op.f("ck_inquiry_messages_sender")
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 100", name=op.f("ck_inquiry_messages_note_max")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["inquiry_conversations.id"],
            name=op.f("fk_inquiry_messages_conversation_id_inquiry_conversations"),
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff.id"], name=op.f("fk_inquiry_messages_staff_id_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiry_messages")),
    )
    op.create_index(
        "ix_inquiry_messages_conversation",
        "inquiry_messages",
        ["conversation_id", "id"],
        unique=False,
    )
    op.create_table(
        "staff_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("origin_message_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="waiting", nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "handed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by", sa.BigInteger(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('medical', 'complaint', 'money', 'care_request', 'urgent', 'other')",
            name=op.f("ck_staff_messages_category"),
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'answered')", name=op.f("ck_staff_messages_status")
        ),
        sa.CheckConstraint(
            "char_length(summary) <= 500", name=op.f("ck_staff_messages_summary_max")
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["staff.id"], name=op.f("fk_staff_messages_assignee_id_staff")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["inquiry_conversations.id"],
            name=op.f("fk_staff_messages_conversation_id_inquiry_conversations"),
        ),
        sa.ForeignKeyConstraint(
            ["origin_message_id"],
            ["inquiry_messages.id"],
            name=op.f("fk_staff_messages_origin_message_id_inquiry_messages"),
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_staff_messages_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["responded_by"], ["staff.id"], name=op.f("fk_staff_messages_responded_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_messages")),
    )
    op.create_index(
        "ix_staff_messages_waiting",
        "staff_messages",
        ["resident_id"],
        unique=False,
        postgresql_where=sa.text("status = 'waiting'"),
    )
    op.create_foreign_key(
        op.f("fk_inquiry_messages_staff_message_id_staff_messages"),
        "inquiry_messages",
        "staff_messages",
        ["staff_message_id"],
        ["id"],
    )
    op.create_table(
        "staff_message_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("staff_message_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("staff_id", sa.BigInteger(), nullable=True),
        sa.Column("from_value", sa.Text(), nullable=True),
        sa.Column("to_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('assigned', 'unassigned', 'reassigned', "
            "'category_changed', 'reopened', 'answered')",
            name=op.f("ck_staff_message_events_type"),
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff.id"], name=op.f("fk_staff_message_events_staff_id_staff")
        ),
        sa.ForeignKeyConstraint(
            ["staff_message_id"],
            ["staff_messages.id"],
            name=op.f("fk_staff_message_events_staff_message_id_staff_messages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_message_events")),
    )


def downgrade() -> None:
    op.drop_table("staff_message_events")
    op.drop_constraint(
        op.f("fk_inquiry_messages_staff_message_id_staff_messages"),
        "inquiry_messages",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_staff_messages_waiting",
        table_name="staff_messages",
        postgresql_where=sa.text("status = 'waiting'"),
    )
    op.drop_table("staff_messages")
    op.drop_index("ix_inquiry_messages_conversation", table_name="inquiry_messages")
    op.drop_table("inquiry_messages")
    op.drop_table("inquiry_conversations")
    op.drop_table("staff_message_templates")
