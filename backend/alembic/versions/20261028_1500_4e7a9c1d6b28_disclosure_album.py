"""disclosure_settings に、機能（feature）の「アルバム」（album）の行を足す（spec 005 の 005-T003）

開示設定で、アルバムを家族に見せる・見せないを選べるようにする。初期値は「見せる」。
- target_type の CHECK に feature を足す（disclosure_settings・disclosure_setting_histories の両方）
- 今ある DB では、開示設定の行がもうある施設（初期データの施設）にだけ、album の行を足す

Revision ID: 4e7a9c1d6b28
Revises: b7d2f5a8c013
Create Date: 2026-10-28 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e7a9c1d6b28"
down_revision: str | Sequence[str] | None = "b7d2f5a8c013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("disclosure_settings", "disclosure_setting_histories")


def _replace_target_type_check(types: str) -> None:
    for table in TABLES:
        op.drop_constraint(op.f(f"ck_{table}_target_type"), table, type_="check")
        op.create_check_constraint(
            op.f(f"ck_{table}_target_type"), table, f"target_type IN ({types})"
        )


def upgrade() -> None:
    _replace_target_type_check("'item', 'theme', 'feature'")
    # 値はこのファイルの定数だけ（利用者の入力は使わない）
    op.execute(
        """
        INSERT INTO disclosure_settings (facility_id, target_type, target_code, visible)
        SELECT DISTINCT facility_id, 'feature', 'album', true
        FROM disclosure_settings
        WHERE NOT EXISTS (
            SELECT 1 FROM disclosure_settings AS album
            WHERE album.facility_id = disclosure_settings.facility_id
              AND album.target_type = 'feature'
              AND album.target_code = 'album'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM disclosure_setting_histories WHERE target_type = 'feature'")
    op.execute("DELETE FROM disclosure_settings WHERE target_type = 'feature'")
    _replace_target_type_check("'item', 'theme'")
