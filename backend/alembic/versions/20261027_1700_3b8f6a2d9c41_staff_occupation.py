"""staff.occupation：職員の職種（#263）

家族の画面の返事に「表示名（職種）」と出すため、アプリの役割とは別に職種を持つ。
職種は決まった候補のコード。空なら、家族の画面は名前だけを出す（役割では補わない）。

今ある DB の職員には、1 回だけ職種を入れる：
- 表示名の終わりに「（看護師）」などと職種を書いていた職員は、職種に移して、表示名から外す
  （初期データの「西村（看護師）」など）。それ以外の名前には触らない
- ほかの職員は、今の役割を職種として入れる（今ある職員は、初期データと申し込みの施設長だけのため）
これから作る職員は、作るときに職種を入れる（職員アカウントの作成 #68 に、職種の欄を足す）。

Revision ID: 3b8f6a2d9c41
Revises: 5d2e8c1f4b90
Create Date: 2026-10-27 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b8f6a2d9c41"
down_revision: str | Sequence[str] | None = "5d2e8c1f4b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 表示名の終わりに書いていた職種と、そのコード
SUFFIXES = {
    "（看護師）": "nurse",
    "（機能訓練指導員）": "functional_trainer",
    "（ケアマネジャー）": "care_manager",
}


def upgrade() -> None:
    op.add_column("staff", sa.Column("occupation", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_staff_occupation"),
        "staff",
        "occupation IN ('care_worker', 'leader', 'counselor', 'clerk', 'director', "
        "'nurse', 'functional_trainer', 'care_manager')",
    )
    staff = sa.table(
        "staff",
        sa.column("display_name", sa.Text()),
        sa.column("role", sa.Text()),
        sa.column("occupation", sa.Text()),
    )
    for suffix, code in SUFFIXES.items():
        # 値はこのファイルの定数だけ（利用者の入力は使わない）。パラメータで渡す
        op.execute(
            staff.update()
            .where(staff.c.display_name.like("%" + suffix), staff.c.occupation.is_(None))
            .values(
                display_name=sa.func.left(
                    staff.c.display_name, sa.func.length(staff.c.display_name) - len(suffix)
                ),
                occupation=code,
            )
        )
    # 残りの職員は、今の役割を職種として入れる（1 回だけ）
    op.execute(staff.update().where(staff.c.occupation.is_(None)).values(occupation=staff.c.role))


def downgrade() -> None:
    staff = sa.table(
        "staff", sa.column("display_name", sa.Text()), sa.column("occupation", sa.Text())
    )
    for suffix, code in SUFFIXES.items():
        op.execute(
            staff.update()
            .where(staff.c.occupation == code)
            .values(display_name=staff.c.display_name + suffix)
        )
    op.drop_constraint(op.f("ck_staff_occupation"), "staff", type_="check")
    op.drop_column("staff", "occupation")
