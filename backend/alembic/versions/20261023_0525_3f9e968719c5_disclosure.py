"""disclosure：開示設定・テーマ・定型文のテーブル（spec 001 の 001-T036）

Revision ID: 3f9e968719c5
Revises: 5b7e3a91c2d4
Create Date: 2026-10-23 05:25:50.951301

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f9e968719c5"
down_revision: str | Sequence[str] | None = "5b7e3a91c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "themes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("emoji", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_themes")),
        sa.UniqueConstraint("code", name=op.f("uq_themes_code")),
    )
    op.create_table(
        "reply_templates",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("theme_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], name=op.f("fk_reply_templates_theme_id_themes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reply_templates")),
        sa.UniqueConstraint("code", name=op.f("uq_reply_templates_code")),
    )
    op.create_table(
        "disclosure_setting_histories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_code", sa.Text(), nullable=False),
        sa.Column("old_visible", sa.Boolean(), nullable=False),
        sa.Column("new_visible", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_type IN ('item', 'theme')",
            name=op.f("ck_disclosure_setting_histories_target_type"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            ["staff.id"],
            name=op.f("fk_disclosure_setting_histories_changed_by_staff"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_disclosure_setting_histories_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_disclosure_setting_histories")),
    )
    op.create_table(
        "disclosure_settings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_code", sa.Text(), nullable=False),
        sa.Column("visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_type IN ('item', 'theme')", name=op.f("ck_disclosure_settings_target_type")
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_disclosure_settings_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["staff.id"], name=op.f("fk_disclosure_settings_updated_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_disclosure_settings")),
    )
    op.create_index(
        "uq_disclosure_settings_target",
        "disclosure_settings",
        ["facility_id", "target_type", "target_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_disclosure_settings_target", table_name="disclosure_settings")
    op.drop_table("disclosure_settings")
    op.drop_table("disclosure_setting_histories")
    op.drop_table("reply_templates")
    op.drop_table("themes")
