"""visit_notices：面会予約のお知らせの種類と、指す先の列（spec 003 の 003-T030）

notifications.kind と email_outbox.template に
visit_confirmed・visit_cancelled・visit_reminder を足し、
notifications に、どの予約のお知らせかを指す列 visit_reservation_id（→ visit_reservations）を足す。
前日の知らせ（visit_reminder）は、同じ予約に 2 回送らないよう、予約ごとに 1 件だけにする。

Revision ID: a9f3c25d7e14
Revises: 7c1d9e4b6a20
Create Date: 2026-10-26 20:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9f3c25d7e14"
down_revision: str | Sequence[str] | None = "7c1d9e4b6a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = "'reply', 'daily_digest', 'weekly_digest', 'announcement', 'staff_message_reply'"
TEMPLATES_BEFORE = KINDS_BEFORE + ", 'invitation', 'owner_account'"
NEW = ", 'visit_confirmed', 'visit_cancelled', 'visit_reminder'"
NEW_KINDS = ("visit_confirmed", "visit_cancelled", "visit_reminder")


def _replace_checks(kinds: str, templates: str) -> None:
    op.drop_constraint(op.f("ck_notifications_kind"), "notifications", type_="check")
    op.create_check_constraint(op.f("ck_notifications_kind"), "notifications", f"kind IN ({kinds})")
    op.drop_constraint(op.f("ck_email_outbox_template"), "email_outbox", type_="check")
    op.create_check_constraint(
        op.f("ck_email_outbox_template"), "email_outbox", f"template IN ({templates})"
    )


def upgrade() -> None:
    op.add_column(
        "notifications", sa.Column("visit_reservation_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_notifications_visit_reservation_id_visit_reservations"),
        "notifications",
        "visit_reservations",
        ["visit_reservation_id"],
        ["id"],
    )
    op.create_index(
        "uq_notifications_visit_reminder",
        "notifications",
        ["visit_reservation_id", "kind"],
        unique=True,
        postgresql_where=sa.text("kind = 'visit_reminder'"),
    )
    _replace_checks(KINDS_BEFORE + NEW, TEMPLATES_BEFORE + NEW)


def downgrade() -> None:
    # 新しい種類の行が残っていると、前の制約を付けられないので、先に消す
    names = ", ".join(f"'{k}'" for k in NEW_KINDS)
    op.execute(f"DELETE FROM notifications WHERE kind IN ({names})")
    op.execute(f"DELETE FROM email_outbox WHERE template IN ({names})")
    _replace_checks(KINDS_BEFORE, TEMPLATES_BEFORE)
    op.drop_index("uq_notifications_visit_reminder", table_name="notifications")
    op.drop_constraint(
        op.f("fk_notifications_visit_reservation_id_visit_reservations"),
        "notifications",
        type_="foreignkey",
    )
    op.drop_column("notifications", "visit_reservation_id")
