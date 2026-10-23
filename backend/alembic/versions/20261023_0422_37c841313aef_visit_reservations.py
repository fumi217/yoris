"""visit reservations：面会予約のテーブル（spec 003 の 003-T001）

重なりの排他制約に btree_gist 拡張を使うので、最初に入れる
（downgrade では消さない。ほかで使うことがあるため）。

Revision ID: 37c841313aef
Revises: cca79de738d8
Create Date: 2026-10-23 04:22:37.814253

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "37c841313aef"
down_revision: str | Sequence[str] | None = "cca79de738d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "visit_start_times",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_visit_start_times_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_start_times")),
    )
    op.create_index(
        "uq_visit_start_times_facility_start",
        "visit_start_times",
        ["facility_id", "start_time"],
        unique=True,
    )
    op.create_table(
        "visit_reservations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("party_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'booked'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        postgresql.ExcludeConstraint(
            (sa.column("facility_id"), "="),
            (sa.text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            where=sa.text("status = 'booked'"),
            using="gist",
            name="ex_visit_reservations_no_overlap",
        ),
        sa.CheckConstraint(
            "status <> 'cancelled_by_staff'"
            " OR (cancel_reason IS NOT NULL AND cancelled_by_staff_id IS NOT NULL)",
            name=op.f("ck_visit_reservations_staff_cancel_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled_by_family', 'cancelled_by_staff')",
            name=op.f("ck_visit_reservations_status"),
        ),
        sa.CheckConstraint(
            "party_size >= 1", name=op.f("ck_visit_reservations_party_size_positive")
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_staff_id"],
            ["staff.id"],
            name=op.f("fk_visit_reservations_cancelled_by_staff_id_staff"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_visit_reservations_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_visit_reservations_resident_id_residents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_reservations")),
    )
    op.create_index(
        "uq_visit_reservations_resident_day",
        "visit_reservations",
        ["resident_id", "visit_date"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
    )
    op.create_table(
        "visit_settings",
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("daily_limit", sa.BigInteger(), server_default=sa.text("2"), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("daily_limit >= 1", name=op.f("ck_visit_settings_daily_limit_positive")),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_visit_settings_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["staff.id"], name=op.f("fk_visit_settings_updated_by_staff")
        ),
        sa.PrimaryKeyConstraint("facility_id", name=op.f("pk_visit_settings")),
    )


def downgrade() -> None:
    op.drop_table("visit_settings")
    op.drop_index(
        "uq_visit_reservations_resident_day",
        table_name="visit_reservations",
        postgresql_where=sa.text("status = 'booked'"),
    )
    op.drop_table("visit_reservations")
    op.drop_index("uq_visit_start_times_facility_start", table_name="visit_start_times")
    op.drop_table("visit_start_times")
