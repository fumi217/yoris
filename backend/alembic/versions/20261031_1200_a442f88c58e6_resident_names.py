"""resident_names：入居者の名前をフルネームにし、続柄・かな・ローマ字を別に持つ（#389）

residents.name_kana・name_romaji：名前の読みとローマ字。すでにある入居者は、いったん name を写す
（DB を作り直すまで、id・en の画面で名前が空にならないように）。正しい値（フルネーム・かな・
ローマ字・続柄）は、DB を作り直して seed を流すと入る。seed は入居者がいると何もしないので、
この移行だけでは入らない（続柄も other のまま）。
residents.display_name：なくす（「佐藤さんの母」。取り違え・誤送のもとになるため）。
family_accounts.relationship：入居者から見た家族の続柄（初期値は other）。

spec 001 の data-model.md の residents・family_accounts。

Revision ID: a442f88c58e6
Revises: d6a4f9c2b815
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a442f88c58e6"
down_revision: str | Sequence[str] | None = "d6a4f9c2b815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("residents", sa.Column("name_kana", sa.Text(), nullable=True))
    op.add_column("residents", sa.Column("name_romaji", sa.Text(), nullable=True))
    op.execute("UPDATE residents SET name_kana = name, name_romaji = name")
    op.alter_column("residents", "name_kana", nullable=False)
    op.alter_column("residents", "name_romaji", nullable=False)
    op.drop_column("residents", "display_name")
    op.add_column(
        "family_accounts",
        sa.Column("relationship", sa.Text(), server_default="other", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_family_accounts_relationship"),
        "family_accounts",
        "relationship IN ('daughter', 'son', 'spouse', 'grandchild', 'sibling', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_family_accounts_relationship"), "family_accounts", type_="check")
    op.drop_column("family_accounts", "relationship")
    op.add_column("residents", sa.Column("display_name", sa.Text(), nullable=True))
    op.execute("UPDATE residents SET display_name = name")
    op.alter_column("residents", "display_name", nullable=False)
    op.drop_column("residents", "name_romaji")
    op.drop_column("residents", "name_kana")
