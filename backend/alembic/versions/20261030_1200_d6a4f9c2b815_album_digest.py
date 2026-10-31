"""album_digest：まとめにアルバムを足す列（spec 005 の 005-T026・FR-017・FR-018）

notifications.has_album：まとめに、載せた写真が含まれるか。
notifications.has_records：まとめに、記録が含まれるか（写真だけのまとめは false。
すでにあるまとめはすべて記録のまとめなので、初期値は true）。
notification_settings.notify_album：「アルバムの新しい写真」を通知するか（初期値は true）。

Revision ID: d6a4f9c2b815
Revises: c5d8e2a91f64
Create Date: 2026-10-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6a4f9c2b815"
down_revision: str | Sequence[str] | None = "c5d8e2a91f64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("has_album", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "notifications",
        sa.Column("has_records", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "notification_settings",
        sa.Column("notify_album", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "notify_album")
    op.drop_column("notifications", "has_records")
    op.drop_column("notifications", "has_album")
