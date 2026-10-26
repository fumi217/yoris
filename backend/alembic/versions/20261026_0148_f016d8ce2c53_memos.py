"""memos：様子のメモと「日本語にする」の履歴のテーブル（spec 007 の 007-T002）

Revision ID: f016d8ce2c53
Revises: a3ed548e02d5
Create Date: 2026-10-26 01:48:54.002465

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f016d8ce2c53"
down_revision: str | Sequence[str] | None = "a3ed548e02d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "care_memos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("author_staff_id", sa.BigInteger(), nullable=False),
        sa.Column("memo_date", sa.Date(), nullable=False),
        sa.Column(
            "written_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source_lang", sa.Text(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column("back_translation", sa.Text(), nullable=True),
        sa.Column("warnings", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_by", sa.BigInteger(), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("unpublished_by", sa.BigInteger(), nullable=True),
        sa.Column("unpublished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unpublish_reason", sa.Text(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_lang IN ('ja', 'id', 'en')", name=op.f("ck_care_memos_source_lang")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending', 'approved', 'returned', 'withdrawn')",
            name=op.f("ck_care_memos_status"),
        ),
        sa.CheckConstraint(
            "char_length(original_text) BETWEEN 1 AND 500",
            name=op.f("ck_care_memos_original_text_length"),
        ),
        sa.CheckConstraint(
            "return_reason IS NULL OR char_length(return_reason) <= 200",
            name=op.f("ck_care_memos_return_reason_max"),
        ),
        sa.CheckConstraint(
            "unpublish_reason IS NULL OR char_length(unpublish_reason) <= 200",
            name=op.f("ck_care_memos_unpublish_reason_max"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["staff.id"], name=op.f("fk_care_memos_approved_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["author_staff_id"], ["staff.id"], name=op.f("fk_care_memos_author_staff_id_staff")
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_care_memos_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["returned_by"], ["staff.id"], name=op.f("fk_care_memos_returned_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["unpublished_by"], ["staff.id"], name=op.f("fk_care_memos_unpublished_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_memos")),
    )
    op.create_index(
        "ix_care_memos_daily",
        "care_memos",
        ["author_staff_id", "resident_id", "memo_date"],
        unique=False,
    )
    op.create_index(
        "ix_care_memos_pending",
        "care_memos",
        ["confirmed_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "care_memo_revisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("memo_id", sa.BigInteger(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("rewritten_text", sa.Text(), nullable=False),
        sa.Column("back_translation", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["memo_id"], ["care_memos.id"], name=op.f("fk_care_memo_revisions_memo_id_care_memos")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_memo_revisions")),
    )
    op.create_index(
        "ix_care_memo_revisions_memo", "care_memo_revisions", ["memo_id", "id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_care_memo_revisions_memo", table_name="care_memo_revisions")
    op.drop_table("care_memo_revisions")
    op.drop_index(
        "ix_care_memos_pending",
        table_name="care_memos",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index("ix_care_memos_daily", table_name="care_memos")
    op.drop_table("care_memos")
