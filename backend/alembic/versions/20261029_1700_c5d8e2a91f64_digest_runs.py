"""digest_runs：どの家族のどのまとめを作ったかの記録（spec 001 の 001-T065・R-13）

同じまとめを 2 回送らないための表。(family_account_id, kind, period_end) が一意。
kind は daily／weekly、period_end はまとめの終わりの時刻（その日の 20:00）。

Revision ID: c5d8e2a91f64
Revises: a3f81c5d7e92
Create Date: 2026-10-29 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d8e2a91f64"
down_revision: str | Sequence[str] | None = "a3f81c5d7e92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "digest_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("family_account_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('daily', 'weekly')", name=op.f("ck_digest_runs_kind")),
        sa.ForeignKeyConstraint(
            ["family_account_id"],
            ["family_accounts.id"],
            name=op.f("fk_digest_runs_family_account_id_family_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digest_runs")),
    )
    op.create_index(
        "uq_digest_runs_family_kind_period",
        "digest_runs",
        ["family_account_id", "kind", "period_end"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_digest_runs_family_kind_period", table_name="digest_runs")
    op.drop_table("digest_runs")
