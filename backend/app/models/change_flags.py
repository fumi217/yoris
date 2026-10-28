"""変化の検知のテーブル（spec 006 の data-model.md、006-T003）。

決まりの条件（何食・何日続けて）はコード（services/change_rules.py）に持ち、ここには持たない。
目印を書くのは、調べ直す処理（evaluate_change_flags）と、確かめる処理・決まりのオン／オフだけ。
家族に出す道（共通の関数・家族の API・問い合わせ AI）からは読まない（FR-007）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in
from app.services.change_rules import RULE_CODES

# まだ確かめていない・確かめ済み・消えた（履歴）
FLAG_STATUSES = ("unconfirmed", "confirmed", "cleared")
# 当てはまらなくなった・決まりをオフにした（消えたときだけ入る）
CLEARED_REASONS = ("not_matching", "rule_disabled")
NOTE_MAX_LENGTH = 100


class ChangeRule(Base):
    """変化の決まり（3 つ）とオン／オフ。初期データ（seed/change_rules.py）で入れる。"""

    __tablename__ = "change_rules"
    __table_args__ = (check_in("code", RULE_CODES, name="code"),)

    code: Mapped[str] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 初期データは空
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))


class ChangeRuleHistory(Base):
    """決まりのオン／オフの変更履歴（FR-011）。"""

    __tablename__ = "change_rule_histories"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    rule_code: Mapped[str] = mapped_column(ForeignKey("change_rules.code"))
    enabled_before: Mapped[bool]
    enabled_after: Mapped[bool]
    changed_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChangeFlag(Base):
    """変化の目印。入居者 × 決まりごとの、当てはまった期間。"""

    __tablename__ = "change_flags"
    __table_args__ = (
        check_in("status", FLAG_STATUSES, name="status"),
        check_in("cleared_reason", CLEARED_REASONS, name="cleared_reason"),
        # 状態と消えた日時をそろえる（消えた目印が unconfirmed・confirmed のまま残らないように）
        CheckConstraint("(status = 'cleared') = (cleared_at IS NOT NULL)", name="status_cleared"),
        # 消えた理由は、消えたときだけ入れる
        CheckConstraint("(cleared_reason IS NOT NULL) = (cleared_at IS NOT NULL)", name="reason"),
        # 今の目印（消えていないもの）は、入居者 × 決まりごとに 1 つ
        Index(
            "uq_change_flags_current",
            "resident_id",
            "rule_code",
            unique=True,
            postgresql_where=text("cleared_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    rule_code: Mapped[str] = mapped_column(ForeignKey("change_rules.code"))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 空なら今の目印
    cleared_at: Mapped[datetime | None]
    cleared_reason: Mapped[str | None]
    # 続いた数（例：2 食）
    streak: Mapped[int]
    # もとになった記録の写し [{record_id, date, slot, value}]（古い順）。
    # 押し直しで記録の値が変わっても、そのときの値が残るように持つ。ログには出さない（FR-014）
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(server_default="unconfirmed")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChangeFlagConfirmation(Base):
    """目印を確かめた記録。確かめ直したら行が増え、前の記録も残る。"""

    __tablename__ = "change_flag_confirmations"
    __table_args__ = (
        # ひとこと（任意）は 100 文字まで（FR-009）。文字としてだけ表示する（FR-013）
        CheckConstraint(f"char_length(note) <= {NOTE_MAX_LENGTH}", name="note_length"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    change_flag_id: Mapped[int] = mapped_column(ForeignKey("change_flags.id"))
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    confirmed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    note: Mapped[str | None]
    # 確かめたときの続いた数。これより増えたら、まだ確かめていないに戻す（FR-010）
    streak_at_confirmation: Mapped[int]
