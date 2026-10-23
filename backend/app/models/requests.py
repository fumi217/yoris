"""家族のリクエスト（「知りたいこと」）のテーブル（spec 001 の 001-T046）。

家族が、テーマのボタンを 1 つ選んで送る。返事待ちは 3 件まで、同じテーマは 1 件まで（FR-014）。
状態の動き：waiting →（職員が返事）→ answered、waiting →（家族が取り消す）→ cancelled。
返事を保存する処理（ゆう。001-T052）が、waiting を answered に動かす。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

REQUEST_STATUSES = ("waiting", "answered", "cancelled")
# 返事待ちの上限（FR-014）
MAX_WAITING_REQUESTS = 3


class Request(Base):
    """家族が送った 1 つのリクエスト。"""

    __tablename__ = "requests"
    __table_args__ = (
        check_in("status", REQUEST_STATUSES, name="status"),
        # 同じテーマの返事待ちは 1 件まで。返事がついた・取り消したあとは、また送れる
        # （research.md R-08。3 件の上限は、作るときに家族アカウントの行を押さえて数える）
        Index(
            "uq_requests_waiting_theme",
            "resident_id",
            "theme_id",
            unique=True,
            postgresql_where=text("status = 'waiting'"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # 家族アカウントは入居者に 1 つなので、家族はここから分かる
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"))
    status: Mapped[str] = mapped_column(server_default="waiting")
    # 送った日時（送ってからの日数も、ここから出す）
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # 家族が取り消したら入れる
    cancelled_at: Mapped[datetime | None]
