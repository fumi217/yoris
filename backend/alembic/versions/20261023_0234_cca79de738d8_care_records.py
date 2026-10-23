"""care records：記録のテーブル（spec 001 の 001-T025）

Revision ID: cca79de738d8
Revises: 2dce2fa52d1b
Create Date: 2026-10-23 02:34:11.036396

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cca79de738d8"
down_revision: str | Sequence[str] | None = "2dce2fa52d1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "care_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("item", sa.Text(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("recorded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "(item = 'meal' AND slot IN ('breakfast', 'lunch', 'dinner', 'snack'))"
            " OR (item IN ('mood', 'sleep') AND slot = 'day')",
            name=op.f("ck_care_records_slot_by_item"),
        ),
        sa.CheckConstraint(
            "(item = 'meal' AND value IN ('10', '8', '5', '2', '0', 'none'))"
            " OR (item = 'mood' AND value IN ('smile', 'normal', 'low'))"
            " OR (item = 'sleep' AND value IN ('good', 'normal', 'poor'))",
            name=op.f("ck_care_records_value_by_item"),
        ),
        sa.CheckConstraint("item IN ('meal', 'mood', 'sleep')", name=op.f("ck_care_records_item")),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["staff.id"], name=op.f("fk_care_records_deleted_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["staff.id"], name=op.f("fk_care_records_recorded_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_care_records_resident_id_residents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_records")),
    )
    op.create_index(
        "uq_care_records_active",
        "care_records",
        ["resident_id", "date", "item", "slot"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "care_record_histories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("care_record_id", sa.BigInteger(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=False),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["care_record_id"],
            ["care_records.id"],
            name=op.f("fk_care_record_histories_care_record_id_care_records"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["staff.id"], name=op.f("fk_care_record_histories_changed_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_record_histories")),
    )


def downgrade() -> None:
    op.drop_table("care_record_histories")
    op.drop_index(
        "uq_care_records_active",
        table_name="care_records",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("care_records")
