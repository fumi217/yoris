"""アルバムの写真のテーブル（spec 005 の 005-T001。data-model.md「album_photos」）。

写真の中身は spec 001 の uploaded_files（purpose = 'album'）に置き、ここは「どの入居者の、
どの写真か」「誰がいつ載せたか」「コメント」「削除したか」の記録を持つ。
サムネイルは作らない（Session 2026-10-28）ので、写真は file_id の 1 つだけ。

削除したときは、行を「誰がいつ削除したか」の記録として残し、file_id・comment を空にして、
uploaded_files の行と保存先のファイルを消す（research.md R-05）。
家族に出すときは、必ず services/album.py（005-T004）の関数を通す。
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

COMMENT_MAX_LENGTH = 100


class AlbumPhoto(Base):
    __tablename__ = "album_photos"
    __table_args__ = (
        # 家族の一覧（新しい順）と、まとめで使う
        Index(
            "ix_album_photos_resident_posted",
            "resident_id",
            text("posted_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    # 削除したら空にする（uploaded_files の行を消すため）
    file_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_files.id"))
    # 職員が自由に書いた文。辞書を通さず、文字としてだけ出す。任意。削除したら空にする
    comment: Mapped[str | None] = mapped_column(String(COMMENT_MAX_LENGTH))
    posted_by: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    posted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # 入っていれば削除済み（元に戻せない）
    deleted_at: Mapped[datetime | None]
