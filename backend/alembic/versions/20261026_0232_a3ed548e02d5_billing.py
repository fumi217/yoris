"""billing：決済（J）の契約・状態の履歴・申し込み・知らせのテーブル（spec 002 の 002-T009）

Revision ID: a3ed548e02d5
Revises: 12b2af9eabaf
Create Date: 2026-10-26 02:32:39.575029

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3ed548e02d5"
down_revision: str | Sequence[str] | None = "12b2af9eabaf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("stripe_event_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_events")),
        sa.UniqueConstraint("stripe_event_id", name=op.f("uq_billing_events_stripe_event_id")),
    )
    op.create_table(
        "billing_applications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("facility_name", sa.Text(), nullable=True),
        sa.Column("director_name", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.Text(), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_facility_id", sa.BigInteger(), nullable=True),
        sa.Column("created_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'rejected')",
            name=op.f("ck_billing_applications_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_facility_id"],
            ["facilities.id"],
            name=op.f("fk_billing_applications_created_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["created_user_id"],
            ["users.id"],
            name=op.f("fk_billing_applications_created_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_applications")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_billing_applications_idempotency_key")
        ),
        sa.UniqueConstraint(
            "stripe_checkout_session_id",
            name=op.f("uq_billing_applications_stripe_checkout_session_id"),
        ),
    )
    op.create_table(
        "facility_subscriptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_checkout_session_id", sa.Text(), nullable=True),
        sa.Column("open_checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'payment_failed', 'cancel_scheduled', 'canceled')",
            name=op.f("ck_facility_subscriptions_status"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_facility_subscriptions_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facility_subscriptions")),
        sa.UniqueConstraint("facility_id", name=op.f("uq_facility_subscriptions_facility_id")),
    )
    op.create_table(
        "subscription_status_histories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("stripe_event_id", sa.Text(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IN ('active', 'payment_failed', 'cancel_scheduled', 'canceled')",
            name=op.f("ck_subscription_status_histories_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IN ('active', 'payment_failed', 'cancel_scheduled', 'canceled')",
            name=op.f("ck_subscription_status_histories_to_status"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_subscription_status_histories_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_status_histories")),
    )


def downgrade() -> None:
    op.drop_table("subscription_status_histories")
    op.drop_table("facility_subscriptions")
    op.drop_table("billing_applications")
    op.drop_table("billing_events")
