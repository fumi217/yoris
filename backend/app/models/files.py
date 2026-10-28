"""アップロードしたファイルのテーブル（お知らせの添付・アルバムの写真。共通）。

spec 001 の data-model.md「uploaded_files」。001-T068。
形式の確認・保存は services/uploads.py（T069）、配るのは GET /api/files/{id}（T071）が行う。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

FILE_CONTENT_TYPES = ("application/pdf", "image/jpeg", "image/png")
UPLOAD_PURPOSES = ("announcement", "album")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        check_in("content_type", FILE_CONTENT_TYPES, name="content_type"),
        check_in("purpose", UPLOAD_PURPOSES, name="purpose"),
        CheckConstraint(f"size_bytes > 0 AND size_bytes <= {MAX_UPLOAD_BYTES}", name="size_bytes"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # 保存先の中の名前。推測できないランダムな文字列にする。外には出さない（API は id で返す）。
    # 同じ名前で別のファイルを上書きしないよう、重複を許さない
    storage_key: Mapped[str] = mapped_column(unique=True)
    # 先頭のバイトで確かめた形式（送られてきた Content-Type や拡張子ではない）
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    purpose: Mapped[str]
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
