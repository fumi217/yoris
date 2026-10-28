"""change_flags：変化の検知のテーブル（spec 006 の 006-T003）

change_rules・change_rule_histories・change_flags・change_flag_confirmations の 4 つ。
今の目印は入居者 × 決まりごとに 1 つ（部分インデックス）。

Revision ID: e4a7c19d3b52
Revises: 6d3b8e2f9a47
Create Date: 2026-10-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4a7c19d3b52"
down_revision: str | Sequence[str] | None = "6d3b8e2f9a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_rules",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "code IN ('meal_low', 'mood_low', 'sleep_poor')", name=op.f("ck_change_rules_code")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["staff.id"], name=op.f("fk_change_rules_updated_by_staff")
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_change_rules")),
    )
    op.create_table(
        "change_flags",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_reason", sa.Text(), nullable=True),
        sa.Column("streak", sa.BigInteger(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default="unconfirmed", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'cleared') = (cleared_at IS NOT NULL)",
            name=op.f("ck_change_flags_status_cleared"),
        ),
        sa.CheckConstraint(
            "cleared_reason IN ('not_matching', 'rule_disabled')",
            name=op.f("ck_change_flags_cleared_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('unconfirmed', 'confirmed', 'cleared')", name=op.f("ck_change_flags_status")
        ),
        sa.CheckConstraint(
            "(cleared_reason IS NOT NULL) = (cleared_at IS NOT NULL)",
            name=op.f("ck_change_flags_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_change_flags_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["rule_code"],
            ["change_rules.code"],
            name=op.f("fk_change_flags_rule_code_change_rules"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_change_flags")),
    )
    op.create_index(
        "uq_change_flags_current",
        "change_flags",
        ["resident_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("cleared_at IS NULL"),
    )
    op.create_table(
        "change_rule_histories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("enabled_before", sa.Boolean(), nullable=False),
        sa.Column("enabled_after", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["staff.id"], name=op.f("fk_change_rule_histories_changed_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["rule_code"],
            ["change_rules.code"],
            name=op.f("fk_change_rule_histories_rule_code_change_rules"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_change_rule_histories")),
    )
    op.create_table(
        "change_flag_confirmations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("change_flag_id", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("streak_at_confirmation", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "char_length(note) <= 100", name=op.f("ck_change_flag_confirmations_note_length")
        ),
        sa.ForeignKeyConstraint(
            ["change_flag_id"],
            ["change_flags.id"],
            name=op.f("fk_change_flag_confirmations_change_flag_id_change_flags"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["staff.id"],
            name=op.f("fk_change_flag_confirmations_confirmed_by_staff"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_change_flag_confirmations")),
    )


def downgrade() -> None:
    op.drop_table("change_flag_confirmations")
    op.drop_table("change_rule_histories")
    op.drop_index(
        "uq_change_flags_current",
        table_name="change_flags",
        postgresql_where=sa.text("cleared_at IS NULL"),
    )
    op.drop_table("change_flags")
    op.drop_table("change_rules")
