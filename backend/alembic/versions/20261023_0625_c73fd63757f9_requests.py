"""requests：家族のリクエスト（spec 001 の 001-T046）

Revision ID: c73fd63757f9
Revises: 3f9e968719c5
Create Date: 2026-10-23 06:25:40.984256

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c73fd63757f9"
down_revision: str | Sequence[str] | None = "3f9e968719c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("theme_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="waiting", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('waiting', 'answered', 'cancelled')", name=op.f("ck_requests_status")
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_requests_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], name=op.f("fk_requests_theme_id_themes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requests")),
    )
    op.create_index(
        "uq_requests_waiting_theme",
        "requests",
        ["resident_id", "theme_id"],
        unique=True,
        postgresql_where=sa.text("status = 'waiting'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_requests_waiting_theme",
        table_name="requests",
        postgresql_where=sa.text("status = 'waiting'"),
    )
    op.drop_table("requests")
