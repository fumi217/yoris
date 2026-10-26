"""staff_message_reply：職員の返事（問い合わせ AI）のお知らせの種類と列（spec 004 の 004-T028）

notifications.kind と email_outbox.template に staff_message_reply を足し、
notifications に、どのメッセージの返事かを指す列 staff_message_id（→ staff_messages）を足す。

Revision ID: 7c1d9e4b6a20
Revises: f016d8ce2c53
Create Date: 2026-10-26 14:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1d9e4b6a20"
down_revision: str | Sequence[str] | None = "f016d8ce2c53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = "'reply', 'daily_digest', 'weekly_digest', 'announcement'"
TEMPLATES_BEFORE = KINDS_BEFORE + ", 'invitation', 'owner_account'"
NEW = ", 'staff_message_reply'"


def _replace_checks(kinds: str, templates: str) -> None:
    op.drop_constraint(op.f("ck_notifications_kind"), "notifications", type_="check")
    op.create_check_constraint(op.f("ck_notifications_kind"), "notifications", f"kind IN ({kinds})")
    op.drop_constraint(op.f("ck_email_outbox_template"), "email_outbox", type_="check")
    op.create_check_constraint(
        op.f("ck_email_outbox_template"), "email_outbox", f"template IN ({templates})"
    )


def upgrade() -> None:
    op.add_column("notifications", sa.Column("staff_message_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notifications_staff_message_id_staff_messages"),
        "notifications",
        "staff_messages",
        ["staff_message_id"],
        ["id"],
    )
    _replace_checks(KINDS_BEFORE + NEW, TEMPLATES_BEFORE + NEW)


def downgrade() -> None:
    # 新しい種類の行が残っていると、前の制約を付けられないので、先に消す
    op.execute("DELETE FROM notifications WHERE kind = 'staff_message_reply'")
    op.execute("DELETE FROM email_outbox WHERE template = 'staff_message_reply'")
    _replace_checks(KINDS_BEFORE, TEMPLATES_BEFORE)
    op.drop_constraint(
        op.f("fk_notifications_staff_message_id_staff_messages"),
        "notifications",
        type_="foreignkey",
    )
    op.drop_column("notifications", "staff_message_id")
