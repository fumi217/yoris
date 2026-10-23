"""notifications：家族のお知らせの一覧と、メールの送る予定（spec 001 の T048）

reply_id・announcement_id の外部キーは、replies（ゆう）と facility_announcements
（作り込み）のテーブルができたあとのマイグレーションで足す。

Revision ID: 5b7e3a91c2d4
Revises: 37c841313aef
Create Date: 2026-10-23 11:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5b7e3a91c2d4"
down_revision: str | Sequence[str] | None = "37c841313aef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("family_account_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("reply_id", sa.BigInteger(), nullable=True),
        sa.Column("announcement_id", sa.BigInteger(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('reply', 'daily_digest', 'weekly_digest', 'announcement')",
            name=op.f("ck_notifications_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["family_account_id"],
            ["family_accounts.id"],
            name=op.f("fk_notifications_family_account_id_family_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("to_email", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "template IN ('reply', 'daily_digest', 'weekly_digest', 'announcement',"
            " 'invitation', 'owner_account')",
            name=op.f("ck_email_outbox_template"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
    )
    op.create_index(
        "ix_email_outbox_unsent",
        "email_outbox",
        ["id"],
        unique=False,
        postgresql_where=sa.text("sent_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_outbox_unsent",
        table_name="email_outbox",
        postgresql_where=sa.text("sent_at IS NULL"),
    )
    op.drop_table("email_outbox")
    op.drop_table("notifications")
