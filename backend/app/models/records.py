"""記録（食事量・機嫌・様子・眠り）のテーブル。

spec 001 の data-model.md「care_records」「care_record_histories」と research.md R-04・R-05。
食事量・機嫌・眠りを 1 つのテーブルにまとめ、item と slot で区別する。
"""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

ITEMS = ("meal", "mood", "sleep")
# 食事は区分ごと、機嫌・眠りは 1 日 1 つ（slot は空にしない。空どうしは一意制約で別物になるため）
MEAL_SLOTS = ("breakfast", "lunch", "dinner", "snack")
DAY_SLOT = "day"
# value のコード。画面の文言は辞書で引く（research.md R-11）
VALUES = {
    # 全部・ほぼ全部・半分・少し・食べていない・食事なし（外泊・入院など）
    "meal": ("10", "8", "5", "2", "0", "none"),
    # 笑顔が多い・いつもどおり・元気がない
    "mood": ("smile", "normal", "low"),
    # よく眠れた・いつもどおり・あまり眠れなかった
    "sleep": ("good", "normal", "poor"),
}


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class CareRecord(Base):
    """1 つの記録。入居者×日付×項目×区分で、取り消していないものは 1 つだけ。"""

    __tablename__ = "care_records"
    __table_args__ = (
        check_in("item", ITEMS, name="item"),
        # 項目と区分の組み合わせ
        CheckConstraint(
            f"(item = 'meal' AND slot IN ({_in(MEAL_SLOTS)}))"
            f" OR (item IN ('mood', 'sleep') AND slot = '{DAY_SLOT}')",
            name="slot_by_item",
        ),
        # 項目ごとの値
        CheckConstraint(
            " OR ".join(
                f"(item = '{item}' AND value IN ({_in(values)}))" for item, values in VALUES.items()
            ),
            name="value_by_item",
        ),
        # 取り消していない記録だけを一意にする
        # （取り消したあとに記録し直せるように。research.md R-04）
        Index(
            "uq_care_records_active",
            "resident_id",
            "date",
            "item",
            "slot",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    # 連絡帳の日付（日本時間）。眠りは記録した朝の日付（research.md R-05）
    date: Mapped[date]
    item: Mapped[str]
    slot: Mapped[str]
    value: Mapped[str]
    recorded_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 当日中に取り消したら入れる（001-T034）
    deleted_at: Mapped[datetime | None]
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))


class CareRecordHistory(Base):
    """押し直し・取り消しの前の値（FR-005）。取り消しは new_value を空にする。"""

    __tablename__ = "care_record_histories"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    care_record_id: Mapped[int] = mapped_column(ForeignKey("care_records.id"))
    old_value: Mapped[str]
    new_value: Mapped[str | None]
    changed_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
