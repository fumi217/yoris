"""memo_notify：様子のメモを通知のまとめの対象にする（spec 007 の 007-T027・FR-012b）

notifications.memo_dates：まとめに入ったメモの書いた日（日本時間・重ねない・古い順）。
  家族のお知らせが、書いた日の連絡帳へのリンクを出すために使う。メモの中身は持たない。
notification_settings.notify_items：初めの設定に memo を足す。すでにある行にも足す
  （これまでは meal・mood・sleep にしか選びようがなく、「初期値で選んだ状態」にそろえるため）。

Revision ID: e7b3c1d84a29
Revises: a442f88c58e6
Create Date: 2026-11-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7b3c1d84a29"
down_revision: str | Sequence[str] | None = "a442f88c58e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "memo_dates",
            postgresql.ARRAY(sa.Date()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.alter_column(
        "notification_settings",
        "notify_items",
        server_default=sa.text("'{meal,mood,sleep,memo}'"),
    )
    op.execute(
        "UPDATE notification_settings SET notify_items = array_append(notify_items, 'memo') "
        "WHERE NOT ('memo' = ANY(notify_items))"
    )


def downgrade() -> None:
    op.execute("UPDATE notification_settings SET notify_items = array_remove(notify_items, 'memo')")
    op.alter_column(
        "notification_settings",
        "notify_items",
        server_default=sa.text("'{meal,mood,sleep}'"),
    )
    op.drop_column("notifications", "memo_dates")
