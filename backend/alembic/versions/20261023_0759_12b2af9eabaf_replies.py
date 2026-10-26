"""replies：職員の返事のテーブル（spec 001 の 001-T047）

あわせて、notifications.reply_id に replies への外部キーを足す（PR #162 でさとこと決めたこと）。

Revision ID: 12b2af9eabaf
Revises: 4f6c0904b452
Create Date: 2026-10-23 07:59:19.340157

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "12b2af9eabaf"
down_revision: str | Sequence[str] | None = "4f6c0904b452"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("template_ids", postgresql.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("replied_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "replied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("contact_book_date", sa.Date(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "cardinality(template_ids) >= 1", name=op.f("ck_replies_template_ids_not_empty")
        ),
        sa.CheckConstraint("char_length(note) <= 100", name=op.f("ck_replies_note_length")),
        sa.ForeignKeyConstraint(
            ["replied_by"], ["staff.id"], name=op.f("fk_replies_replied_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name=op.f("fk_replies_request_id_requests")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_replies")),
        sa.UniqueConstraint("request_id", name=op.f("uq_replies_request_id")),
    )
    op.create_foreign_key(
        op.f("fk_notifications_reply_id_replies"), "notifications", "replies", ["reply_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_notifications_reply_id_replies"), "notifications", type_="foreignkey"
    )
    op.drop_table("replies")
