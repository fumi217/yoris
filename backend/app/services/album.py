"""家族に出すアルバムの写真の共通の関数（spec 005 の 005-T004。research.md R-03・FR-006・FR-014）。

家族に写真を出す道は、ここの関数だけにする。一覧の API も、写真のファイルを返す
GET /api/files/{id} も、同じ条件を通る（片方だけ抜けて、URL から他の入居者の写真が
見えてしまうのを防ぐため）。

- 見えるのは、①自分の入居者の写真で、②削除されていなくて、③アルバムを「見せる」設定のとき
- 見せない設定のときは、get_visible_album_photos は空を返す（呼ぶ API が、先に 404 にする）
- 返すのは、写真の id・file_id・コメント・載せた日時だけ（削除した職員などは出さない）
- コメントは職員が自由に書いた文。そのまま返し、画面で文字としてだけ出す
- 関数の中では commit しない（読むだけ）
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.models.album import AlbumPhoto
from app.services.disclosure import is_feature_disclosed

# 一覧を 1 回で返す枚数。既定は 12（サムネイルがなく、1 枚 3〜8MB ほどなので、最初の読み込みを
# 軽くするため。#298 の相談で決定）。上限は 30
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 30


@dataclass(frozen=True)
class AlbumPhotoView:
    """家族に出す写真 1 枚。"""

    id: int
    file_id: int  # 写真のファイル（GET /api/files/{file_id}）
    comment: str | None
    posted_at: datetime


@dataclass(frozen=True)
class AlbumPage:
    """一覧の 1 ページ。next_before が空なら、続きはない。"""

    photos: list[AlbumPhotoView]
    next_before: int | None  # 続きを読むとき、before に渡す（このページの最後の写真の id）


def can_family_view_photo(session: Session, photo: AlbumPhoto, resident_id: int) -> bool:
    """この家族（resident_id の入居者の家族）が、この写真を見てよいか。"""
    return (
        photo.resident_id == resident_id
        and photo.deleted_at is None
        and photo.file_id is not None
        and is_feature_disclosed(session, "album")
    )


def get_visible_album_photos(
    session: Session,
    resident_id: int,
    before: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> AlbumPage:
    """その入居者の、削除されていない写真を、新しい順に返す。

    before は、前のページの最後の写真の id（API の next_before）。それより古いものを返す。
    limit は 1〜MAX_PAGE_SIZE に収める。アルバムを見せない設定のときは、空を返す。
    """
    if not is_feature_disclosed(session, "album"):
        return AlbumPage(photos=[], next_before=None)
    page_size = max(1, min(limit, MAX_PAGE_SIZE))

    query = select(AlbumPhoto).where(
        AlbumPhoto.resident_id == resident_id,
        AlbumPhoto.deleted_at.is_(None),
        AlbumPhoto.file_id.is_not(None),
    )
    if before is not None:
        # 載せた日時と id の組で比べる（途中で写真が増えても、ずれない）
        # ほかの入居者の写真の id は探せない（resident_id で絞る）。削除した写真でも、カーソルには
        # 使える（前のページの最後の写真が、続きを読む前に削除されても、続きを読めるように）
        cursor = select(AlbumPhoto.posted_at, AlbumPhoto.id).where(
            AlbumPhoto.id == before, AlbumPhoto.resident_id == resident_id
        )
        cursor_row = session.execute(cursor).one_or_none()
        if cursor_row is None:
            return AlbumPage(photos=[], next_before=None)
        query = query.where(
            tuple_(AlbumPhoto.posted_at, AlbumPhoto.id) < tuple_(cursor_row[0], cursor_row[1])
        )
    # 1 枚多く読んで、続きがあるかを調べる
    rows = list(
        session.scalars(
            query.order_by(AlbumPhoto.posted_at.desc(), AlbumPhoto.id.desc()).limit(page_size + 1)
        )
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    photos = [
        AlbumPhotoView(
            id=row.id,
            file_id=row.file_id,
            comment=row.comment,
            posted_at=row.posted_at,
        )
        for row in rows
        if row.file_id is not None
    ]
    return AlbumPage(photos=photos, next_before=rows[-1].id if has_more else None)


def count_new_photos(session: Session, resident_id: int, since: datetime, until: datetime) -> int:
    """since 以上 until 未満に載せた、削除されていない写真の数（まとめ用。中身は返さない）。

    アルバムを見せない設定のときは 0 を返す（まとめの側で確かめ忘れても、
    「写真が載りました」の通知が家族に届かないように。SC-006）。
    """
    if not is_feature_disclosed(session, "album"):
        return 0
    return (
        session.scalar(
            select(func.count(AlbumPhoto.id)).where(
                AlbumPhoto.resident_id == resident_id,
                AlbumPhoto.deleted_at.is_(None),
                AlbumPhoto.posted_at >= since,
                AlbumPhoto.posted_at < until,
            )
        )
        or 0
    )
