"""album_photos：アルバムの写真の記録（spec 005 の 005-T001）

どの入居者の、どの写真か・誰がいつ載せたか・コメント（100 文字まで）・削除したか。
サムネイルは作らないので、写真は file_id（→ uploaded_files）の 1 つだけ。
索引は (resident_id, posted_at DESC, id DESC)（家族の一覧と、まとめで使う）。

Revision ID: 6d3b8e2f9a47
Revises: 4e7a9c1d6b28
Create Date: 2026-10-28 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d3b8e2f9a47"
down_revision: str | Sequence[str] | None = "4e7a9c1d6b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "album_photos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=True),
        sa.Column("comment", sa.String(length=100), nullable=True),
        sa.Column("posted_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_album_photos_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["uploaded_files.id"], name=op.f("fk_album_photos_file_id_uploaded_files")
        ),
        sa.ForeignKeyConstraint(
            ["posted_by"], ["staff.id"], name=op.f("fk_album_photos_posted_by_staff")
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["staff.id"], name=op.f("fk_album_photos_deleted_by_staff")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_album_photos")),
    )
    op.create_index(
        "ix_album_photos_resident_posted",
        "album_photos",
        ["resident_id", sa.text("posted_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_album_photos_resident_posted", table_name="album_photos")
    op.drop_table("album_photos")
