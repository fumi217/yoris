"""様子のメモのテーブル（spec 007 の data-model.md。007-T002）。

職員が書いた原文・AI が整えた日本語・訳し戻しを、どれも残す（FR-004）。
家族に出すのは承認済み（status = 'approved'）だけで、必ず services/disclosure.py の
get_disclosed_memos を通す（research.md R-07。007-T024 で作る）。
"""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

# 原文の言語（職員の表示言語と同じ選択肢。research.md R-12）
SOURCE_LANGS = ("ja", "id", "en")
STATUSES = ("draft", "pending", "approved", "returned", "withdrawn")
# 機械の目の印（research.md R-03。付けるのは 007-T008）
WARNINGS = ("medical_added", "medical_in_original", "length_changed", "other_name", "urgent_words")

# 原文の文字数の上限（FR-001）と、戻す・公開を取り下げる理由の上限（FR-013・FR-013a）
ORIGINAL_MAX = 500
REASON_MAX = 200


def _max_length(column: str, limit: int) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IS NULL OR char_length({column}) <= {limit}", name=f"{column}_max"
    )


class CareMemo(Base):
    """様子のメモ（入居者 × 書いた日。職員ごと・入居者ごとに 1 日 3 件まで）。"""

    __tablename__ = "care_memos"
    __table_args__ = (
        check_in("source_lang", SOURCE_LANGS, name="source_lang"),
        check_in("status", STATUSES, name="status"),
        CheckConstraint(
            f"char_length(original_text) BETWEEN 1 AND {ORIGINAL_MAX}", name="original_text_length"
        ),
        _max_length("return_reason", REASON_MAX),
        _max_length("unpublish_reason", REASON_MAX),
        # 1 日 3 件を数えるため（取り下げたものは数えない。research.md R-06）
        Index("ix_care_memos_daily", "author_staff_id", "resident_id", "memo_date"),
        # 承認待ちの一覧と件数のため
        Index("ix_care_memos_pending", "confirmed_at", postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    # 書いた職員（直す・整える・確かめる・取り下げるのは本人だけ。承認はできない。FR-011a）
    author_staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    # 書いた日（日本時間）。承認が日付をまたいでも、家族の連絡帳はこの日に出す
    memo_date: Mapped[date]
    # 書いた時刻（家族の連絡帳の並び順）
    written_at: Mapped[datetime] = mapped_column(server_default=func.now())
    source_lang: Mapped[str]
    # 原文（500 文字まで）。辞書を通さず、文字としてだけ出す（FR-017）
    original_text: Mapped[str]
    # 整えた日本語（職員が直したものを含む）。「日本語にする」の前は空
    rewritten_text: Mapped[str | None]
    # 訳し戻し（職員の表示言語が日本語なら空。FR-007）
    back_translation: Mapped[str | None]
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    status: Mapped[str] = mapped_column(server_default="draft")
    # 本人が「確かめました」を押した日時（承認待ちの経過時間はここから。FR-015）
    confirmed_at: Mapped[datetime | None]
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    approved_at: Mapped[datetime | None]
    # 戻したときも承認の列は消さずに残す（最新の状態は status で見る）
    returned_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    returned_at: Mapped[datetime | None]
    return_reason: Mapped[str | None]
    unpublished_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    unpublished_at: Mapped[datetime | None]
    unpublish_reason: Mapped[str | None]
    withdrawn_at: Mapped[datetime | None]


class CareMemoRevision(Base):
    """「日本語にする」の履歴（どの原文からどの日本語ができたかを追跡する。FR-004）。

    1 つのメモでやり直せるのは 5 回まで（この行の数で数える。research.md R-08）。
    """

    __tablename__ = "care_memo_revisions"
    __table_args__ = (Index("ix_care_memo_revisions_memo", "memo_id", "id"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("care_memos.id"))
    # このときの原文
    original_text: Mapped[str]
    # AI が整えた日本語（職員が直したあとに訳し戻しだけを作ったときは、直したあとの文）
    rewritten_text: Mapped[str]
    back_translation: Mapped[str | None]
    model: Mapped[str | None]
    # 整える＋訳し戻すにかかった時間
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
