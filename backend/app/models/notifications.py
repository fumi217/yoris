"""通知のテーブル（家族のお知らせの一覧、メールの送る予定）。

spec 001 の data-model.md「通知（さとこ）」。001-T048。
返事のお知らせとメール（ミニマム版）と、まとめ・施設からのお知らせ（作り込み）が使う。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in
from app.models.records import ITEMS

# まとめを送る頻度（spec 001 の FR-023）。daily は毎日、weekly は日曜に 1 回、none は送らない
NOTIFICATION_FREQUENCIES = ("daily", "weekly", "none")
# まとめの種類（digest_runs の kind。通知設定の頻度のうち、送るもの）
DIGEST_KINDS = ("daily", "weekly")
# 初めの設定（設定の行がない家族は、この値で扱う。FR-023：選ばなかった場合は「1 日 1 回まとめて」）
DEFAULT_FREQUENCY = "daily"
DEFAULT_NOTIFY_ITEMS = ITEMS

NOTIFICATION_KINDS = (
    "reply",
    "daily_digest",
    "weekly_digest",
    "announcement",
    "staff_message_reply",
    "visit_confirmed",
    "visit_cancelled",
    "visit_reminder",
)
EMAIL_TEMPLATES = (
    "reply",
    "daily_digest",
    "weekly_digest",
    "announcement",
    "invitation",
    "owner_account",
    "staff_message_reply",
    "visit_confirmed",
    "visit_cancelled",
    "visit_reminder",
)


class Notification(Base):
    """家族のお知らせの一覧（アプリ内）。"""

    __tablename__ = "notifications"
    __table_args__ = (
        check_in("kind", NOTIFICATION_KINDS, name="kind"),
        # 前日の知らせ（visit_reminder）は同じ予約に 1 件だけ（何度呼ばれても増えない。R-07）
        Index(
            "uq_notifications_visit_reminder",
            "visit_reservation_id",
            "kind",
            unique=True,
            postgresql_where=text("kind = 'visit_reminder'"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    family_account_id: Mapped[int] = mapped_column(ForeignKey("family_accounts.id"))
    kind: Mapped[str]
    # replies の外部キーは、replies を作ったマイグレーション（#114 ゆう）で足した。
    # facility_announcements は作り込みなので、announcement_id の外部キーはそのときに足す
    reply_id: Mapped[int | None] = mapped_column(ForeignKey("replies.id"))
    # 職員の返事（問い合わせ AI。kind = 'staff_message_reply'）が、どのメッセージのものか
    staff_message_id: Mapped[int | None] = mapped_column(ForeignKey("staff_messages.id"))
    # 面会予約のお知らせ（kind が visit_*）が、どの予約のものか
    visit_reservation_id: Mapped[int | None] = mapped_column(ForeignKey("visit_reservations.id"))
    announcement_id: Mapped[int | None]
    # まとめ（daily_digest・weekly_digest）の対象の期間
    period_start: Mapped[datetime | None]
    period_end: Mapped[datetime | None]
    # まとめに、載せた写真・記録が含まれるか（spec 005 の FR-018）。写真だけのまとめは
    # has_records が false。まとめ以外の種類では使わない
    has_album: Mapped[bool] = mapped_column(server_default=text("false"))
    has_records: Mapped[bool] = mapped_column(server_default=text("true"))
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
    params: Mapped[dict[str, str | bool]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 送れたら入れる
    sent_at: Mapped[datetime | None]
    # 失敗した回数（5 回まで送り直す）
    attempts: Mapped[int] = mapped_column(server_default="0")
    last_error: Mapped[str | None]


class NotificationSetting(Base):
    """家族の通知設定（家族アカウントに 1 行。spec 001 の FR-023・001-T064）。

    行がない家族は、初めの設定（DEFAULT_*）として扱う。初めて保存したときに行を作る。
    notify_items は、まとめに入れる記録項目（ITEMS のどれか）。開示されていない項目は、
    まとめを作るときに除く（ここでは、選んだ項目をそのまま持つ）。
    """

    __tablename__ = "notification_settings"
    __table_args__ = (check_in("frequency", NOTIFICATION_FREQUENCIES, name="frequency"),)

    family_account_id: Mapped[int] = mapped_column(
        ForeignKey("family_accounts.id"), primary_key=True
    )
    # 知りたいことへの返事を、すぐ通知するか（頻度の設定に関係なく。FR-023）
    notify_reply: Mapped[bool] = mapped_column(server_default=text("true"))
    notify_items: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{meal,mood,sleep}'")
    )
    # 「アルバムの新しい写真」を通知するか（spec 005 の FR-017）
    notify_album: Mapped[bool] = mapped_column(server_default=text("true"))
    frequency: Mapped[str] = mapped_column(server_default=DEFAULT_FREQUENCY)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class DigestRun(Base):
    """どの家族のどのまとめを作ったかの記録（spec 001 の 001-T065。research.md R-13）。

    同じまとめを 2 回送らないための表。(家族, 種類, まとめの終わりの時刻) が一意で、
    呼び出しが重なったり、遅れたりしても、DB が 2 つ目を断る（SC-010）。
    送る記録がなかった日も残す（その日の分は確かめ済みにして、毎分探し直さない）。
    """

    __tablename__ = "digest_runs"
    __table_args__ = (
        check_in("kind", DIGEST_KINDS, name="kind"),
        Index(
            "uq_digest_runs_family_kind_period",
            "family_account_id",
            "kind",
            "period_end",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    family_account_id: Mapped[int] = mapped_column(ForeignKey("family_accounts.id"))
    kind: Mapped[str]
    # まとめの終わりの時刻（その日の 20:00）
    period_end: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
