"""通知のテーブル（家族のお知らせの一覧、メールの送る予定）。

spec 001 の data-model.md「通知（さとこ）」。001-T048。
返事のお知らせとメール（ミニマム版）と、まとめ・施設からのお知らせ（作り込み）が使う。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

NOTIFICATION_KINDS = ("reply", "daily_digest", "weekly_digest", "announcement")
EMAIL_TEMPLATES = (
    "reply",
    "daily_digest",
    "weekly_digest",
    "announcement",
    "invitation",
    "owner_account",
)


class Notification(Base):
    """家族のお知らせの一覧（アプリ内）。"""

    __tablename__ = "notifications"
    __table_args__ = (check_in("kind", NOTIFICATION_KINDS, name="kind"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    family_account_id: Mapped[int] = mapped_column(ForeignKey("family_accounts.id"))
    kind: Mapped[str]
    # replies の外部キーは、replies を作ったマイグレーション（#114 ゆう）で足した。
    # facility_announcements は作り込みなので、announcement_id の外部キーはそのときに足す
    reply_id: Mapped[int | None] = mapped_column(ForeignKey("replies.id"))
    announcement_id: Mapped[int | None]
    # まとめ（daily_digest・weekly_digest）の対象の期間
    period_start: Mapped[datetime | None]
    period_end: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    read_at: Mapped[datetime | None]


class EmailOutbox(Base):
    """メールの送る予定。run_jobs() と、保存のあとにその場で送る処理が、ここから取り出して送る。"""

    __tablename__ = "email_outbox"
    __table_args__ = (
        check_in("template", EMAIL_TEMPLATES, name="template"),
        # 未送信の行だけを、古い順に取り出すため（FOR UPDATE SKIP LOCKED で 2 回送らない。R-09）
        Index("ix_email_outbox_unsent", "id", postgresql_where=text("sent_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    to_email: Mapped[str]
    template: Mapped[str]
    # 種類・お知らせのタイトル・リンクだけ。記録・返事・本文は入れない（SC-010）。
    # 例外：owner_account だけは login_id を入れる（spec 002 の research.md R-08）
    params: Mapped[dict[str, str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 送れたら入れる
    sent_at: Mapped[datetime | None]
    # 失敗した回数（5 回まで送り直す）
    attempts: Mapped[int] = mapped_column(server_default="0")
    last_error: Mapped[str | None]
