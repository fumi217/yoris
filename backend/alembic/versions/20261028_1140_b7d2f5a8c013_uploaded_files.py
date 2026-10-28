"""uploaded_files：アップロードしたファイル（お知らせの添付・アルバムの写真。共通）（001-T068）

形式は PDF・JPEG・PNG、大きさは 10MB まで、用途は announcement・album。
storage_key は推測できない名前で、重複を許さない。

Revision ID: b7d2f5a8c013
Revises: 8c4e1a7b2d35
Create Date: 2026-10-28 11:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2f5a8c013"
down_revision: str | Sequence[str] | None = "8c4e1a7b2d35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('application/pdf', 'image/jpeg', 'image/png')",
            name=op.f("ck_uploaded_files_content_type"),
        ),
        sa.CheckConstraint(
            "purpose IN ('announcement', 'album')", name=op.f("ck_uploaded_files_purpose")
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760", name=op.f("ck_uploaded_files_size_bytes")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["staff.id"], name=op.f("fk_uploaded_files_uploaded_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_files")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_uploaded_files_storage_key")),
    )


def downgrade() -> None:
    op.drop_table("uploaded_files")
