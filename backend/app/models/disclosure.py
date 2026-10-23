"""開示設定のテーブル（spec 001 の data-model.md「開示設定」、001-T036）。

「知りたいこと」のテーマと定型文、施設が家族に見せる記録項目・テーマの設定、その変更の履歴。
家族に出すものは、必ず services/disclosure.py の共通の関数を通す（research.md R-06）。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

# 記録項目（item）と「知りたいこと」のテーマ（theme）。
# アルバム（feature、spec 005 の 005-T003）は、そのタスクで足す
TARGET_TYPES = ("item", "theme")


class Theme(Base):
    """「知りたいこと」のテーマ。文言は辞書で引く（code が辞書のキー）。"""

    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # 例："theme.daily_life"
    code: Mapped[str] = mapped_column(unique=True)
    emoji: Mapped[str]
    sort_order: Mapped[int]


class ReplyTemplate(Base):
    """テーマごとの返事の定型文（3〜5 個。FR-030）。文言は辞書で引く。"""

    __tablename__ = "reply_templates"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"))
    # 例："template.daily_life.smile"
    code: Mapped[str] = mapped_column(unique=True)
    sort_order: Mapped[int]


class DisclosureSetting(Base):
    """施設が家族に見せるかどうか（施設全体で一括。FR-009）。"""

    __tablename__ = "disclosure_settings"
    __table_args__ = (
        check_in("target_type", TARGET_TYPES, name="target_type"),
        Index(
            "uq_disclosure_settings_target",
            "facility_id",
            "target_type",
            "target_code",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    target_type: Mapped[str]
    # item なら "meal"・"mood"・"sleep"、theme ならテーマの code
    target_code: Mapped[str]
    visible: Mapped[bool] = mapped_column(server_default=text("true"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DisclosureSettingHistory(Base):
    """開示設定の変更の履歴（いつ・誰が・何を。FR-011）。"""

    __tablename__ = "disclosure_setting_histories"
    __table_args__ = (check_in("target_type", TARGET_TYPES, name="target_type"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    target_type: Mapped[str]
    target_code: Mapped[str]
    old_visible: Mapped[bool]
    new_visible: Mapped[bool]
    changed_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
