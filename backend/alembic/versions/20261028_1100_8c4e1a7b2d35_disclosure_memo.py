"""disclosure_settings に、様子のメモ（memo）の行を足す（spec 007 の 007-T025）

開示設定で、様子のメモを家族に見せる・見せないを選べるようにする。初期値は「見せる」。
今ある DB では、開示設定の行がもうある施設（初期データの施設）にだけ足す
（行がないと「見せない」扱いになり、様子のメモが家族に出ないため）。表の形は変えない。

Revision ID: 8c4e1a7b2d35
Revises: 3b8f6a2d9c41
Create Date: 2026-10-28 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c4e1a7b2d35"
down_revision: str | Sequence[str] | None = "3b8f6a2d9c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 値はこのファイルの定数だけ（利用者の入力は使わない）
    op.execute(
        """
        INSERT INTO disclosure_settings (facility_id, target_type, target_code, visible)
        SELECT DISTINCT facility_id, 'item', 'memo', true
        FROM disclosure_settings
        WHERE NOT EXISTS (
            SELECT 1 FROM disclosure_settings AS memo
            WHERE memo.facility_id = disclosure_settings.facility_id
              AND memo.target_type = 'item'
              AND memo.target_code = 'memo'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM disclosure_setting_histories "
        "WHERE target_type = 'item' AND target_code = 'memo'"
    )
    op.execute(
        "DELETE FROM disclosure_settings WHERE target_type = 'item' AND target_code = 'memo'"
    )
