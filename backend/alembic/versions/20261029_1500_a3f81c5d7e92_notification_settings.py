"""notification_settings：家族の通知設定（spec 001 の 001-T064・FR-023）

家族アカウントに 1 行。知りたいことへの返事を通知するか（notify_reply）、まとめに入れる記録項目
（notify_items）、まとめの頻度（frequency：daily／weekly／none）。
行がない家族は、初めの設定（返事は通知・meal/mood/sleep・毎日）として扱う。

Revision ID: a3f81c5d7e92
Revises: e4a7c19d3b52
Create Date: 2026-10-29 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f81c5d7e92"
down_revision: str | Sequence[str] | None = "e4a7c19d3b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column("family_account_id", sa.BigInteger(), nullable=False),
        sa.Column("notify_reply", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "notify_items",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{meal,mood,sleep}'"),
            nullable=False,
        ),
        sa.Column("frequency", sa.Text(), server_default="daily", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'none')",
            name=op.f("ck_notification_settings_frequency"),
        ),
        sa.ForeignKeyConstraint(
            ["family_account_id"],
            ["family_accounts.id"],
            name=op.f("fk_notification_settings_family_account_id_family_accounts"),
        ),
        sa.PrimaryKeyConstraint("family_account_id", name=op.f("pk_notification_settings")),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
