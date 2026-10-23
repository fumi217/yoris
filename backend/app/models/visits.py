"""面会予約のテーブル（spec 003 の data-model.md、003-T001）。

予約を作る道は `services/visits.py` の `book_visit` 1 つだけにし、
重なりと「1 家族 1 日 1 回」は DB の決まりでも守る（research.md R-01）。
「1 日 2 組まで」は件数なので DB の決まりでは表せず、book_visit の中の順番待ちで守る。
"""

from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

RESERVATION_STATUSES = ("booked", "cancelled_by_family", "cancelled_by_staff")


class VisitSetting(Base):
    """施設ごとの面会の設定（施設に 1 行）。"""

    __tablename__ = "visit_settings"
    __table_args__ = (CheckConstraint("daily_limit >= 1", name="daily_limit_positive"),)

    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), primary_key=True)
    # 1 日に受け付ける組数（FR-009）
    daily_limit: Mapped[int] = mapped_column(server_default=text("2"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class VisitStartTime(Base):
    """開始時刻の候補（日本時間）。終わりは開始の 1 時間 30 分後で、列には持たない。"""

    __tablename__ = "visit_start_times"
    __table_args__ = (
        Index("uq_visit_start_times_facility_start", "facility_id", "start_time", unique=True),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    start_time: Mapped[time]
    # 候補から外したら false（すでに入っている予約はそのまま残す。FR-009）
    active: Mapped[bool] = mapped_column(server_default=text("true"))


class VisitReservation(Base):
    """面会予約。"""

    __tablename__ = "visit_reservations"
    __table_args__ = (
        check_in("status", RESERVATION_STATUSES, name="status"),
        CheckConstraint("party_size >= 1", name="party_size_positive"),
        # 職員が取り消したときは、理由と取り消した職員が必ずある（FR-012）
        CheckConstraint(
            "status <> 'cancelled_by_staff'"
            " OR (cancel_reason IS NOT NULL AND cancelled_by_staff_id IS NOT NULL)",
            name="staff_cancel_has_reason",
        ),
        # 1 家族（入居者）1 日 1 回（予約済みだけを数える）
        Index(
            "uq_visit_reservations_resident_day",
            "resident_id",
            "visit_date",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        # 面会の時間が重ならない（予約済みだけ。btree_gist 拡張を使う）
        ExcludeConstraint(
            ("facility_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            using="gist",
            where=text("status = 'booked'"),
            name="ex_visit_reservations_no_overlap",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    # ログイン中の家族の CurrentUser.resident_id から決める（送られた値は使わない。R-05）
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    # 面会の日と開始時刻（日本時間）
    visit_date: Mapped[date]
    start_time: Mapped[time]
    # 面会の時間（UTC）。ends_at = starts_at + 1 時間 30 分（R-02）
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    # 来る人数（1 以上、上限なし）
    party_size: Mapped[int]
    status: Mapped[str] = mapped_column(server_default=text("'booked'"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    cancelled_at: Mapped[datetime | None]
    cancelled_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # 職員が取り消したときの理由（画面では文字としてだけ出す。FR-016）
    cancel_reason: Mapped[str | None]
