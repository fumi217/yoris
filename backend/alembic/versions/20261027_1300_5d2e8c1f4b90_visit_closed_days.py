"""visit_closed_days：面会がお休みの日（spec 003 の 003-T020）

施設ごとに、面会がお休みの日を持つ。一意は (facility_id, closed_date)。

Revision ID: 5d2e8c1f4b90
Revises: a9f3c25d7e14
Create Date: 2026-10-27 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d2e8c1f4b90"
down_revision: str | Sequence[str] | None = "a9f3c25d7e14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit_closed_days",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("closed_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_visit_closed_days_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["staff.id"], name=op.f("fk_visit_closed_days_created_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_closed_days")),
    )
    op.create_index(
        "uq_visit_closed_days_facility_date",
        "visit_closed_days",
        ["facility_id", "closed_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_visit_closed_days_facility_date", table_name="visit_closed_days")
    op.drop_table("visit_closed_days")
