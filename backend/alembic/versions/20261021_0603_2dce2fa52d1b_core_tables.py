"""core tables：共通の土台のテーブル（spec 001 の T009・spec 002 の T005）

自動で作ったものに、シーケンス staff_login_id_seq を手で足した
（autogenerate はシーケンスを作らないため）。

Revision ID: 2dce2fa52d1b
Revises:
Create Date: 2026-10-21 06:03:12.865886

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2dce2fa52d1b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 職員のログイン用の ID（s00001〜s99999）の番号
    op.execute("CREATE SEQUENCE staff_login_id_seq MINVALUE 1 MAXVALUE 99999")
    op.create_table(
        "facilities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("billing_email", sa.Text(), nullable=True),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facilities")),
        sa.UniqueConstraint("stripe_customer_id", name=op.f("uq_facilities_stripe_customer_id")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("login_id", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), server_default="ja", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'staff' AND login_id IS NOT NULL AND email IS NULL)"
            " OR (kind = 'family' AND email IS NOT NULL AND login_id IS NULL)",
            name=op.f("ck_users_login_by_kind"),
        ),
        sa.CheckConstraint("kind IN ('staff', 'family')", name=op.f("ck_users_kind")),
        sa.CheckConstraint("login_id ~ '^s[0-9]{5}$'", name=op.f("ck_users_login_id_format")),
        sa.CheckConstraint("language IN ('ja', 'id', 'en')", name=op.f("ck_users_language")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("login_id", name=op.f("uq_users_login_id")),
    )
    op.create_table(
        "residents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("room", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["facility_id"], ["facilities.id"], name=op.f("fk_residents_facility_id_facilities")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_residents")),
    )
    op.create_table(
        "staff",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("facility_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "role IN ('care_worker', 'leader', 'counselor', 'clerk', 'director')",
            name=op.f("ck_staff_role"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"], ["facilities.id"], name=op.f("fk_staff_facility_id_facilities")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_staff_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff")),
        sa.UniqueConstraint("user_id", name=op.f("uq_staff_user_id")),
    )
    op.create_table(
        "family_accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["resident_id"], ["residents.id"], name=op.f("fk_family_accounts_resident_id_residents")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_family_accounts_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_family_accounts")),
        sa.UniqueConstraint("resident_id", name=op.f("uq_family_accounts_resident_id")),
        sa.UniqueConstraint("user_id", name=op.f("uq_family_accounts_user_id")),
    )


def downgrade() -> None:
    op.drop_table("family_accounts")
    op.drop_table("staff")
    op.drop_table("residents")
    op.drop_table("users")
    op.drop_table("facilities")
    op.execute("DROP SEQUENCE staff_login_id_seq")
