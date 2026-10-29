"""家族のアルバムの API（spec 005 の 005-T010。contracts の「家族」・FR-005・FR-006・FR-010）。

- `GET /api/family/album?before=&limit=`：自分の入居者の写真を、載せた日（日本時間）ごとに、
  新しい順に返す。続きは、返り値の `next_before` を `before` に渡して読む。
  アルバムを「見せない」設定のときは 404
- `GET /api/family/features`：開示設定の `feature` の状態（例：`{"album": true}`）。
  家族の画面の「☰ その他」に、アルバムを出すかを決めるのに使う

入居者は送らせず、ログイン中の家族から決める（ほかの入居者の写真は、頼んでも出ない）。
写真は、services/album.py の共通の関数だけを通す（一覧とファイルで判定が分かれないように。R-03）。
写真のファイルは、`url`（`GET /api/files/{id}`）で開く。
コメントは職員が自由に書いた文なので、そのまま返す（画面では、文字としてだけ表示する）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.clock import JST
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.services.album import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AlbumPhotoView,
    get_visible_album_photos,
)
from app.services.disclosure import is_feature_disclosed

router = APIRouter(prefix="/api/family", tags=["family"])


class FeaturesOut(BaseModel):
    album: bool


class AlbumPhotoOut(BaseModel):
    id: int
    posted_at: datetime
    comment: str | None
    url: str  # 写真のファイル（GET /api/files/{id}）


class AlbumDayOut(BaseModel):
    date: date  # 載せた日（日本時間）
    photos: list[AlbumPhotoOut]


class AlbumOut(BaseModel):
    days: list[AlbumDayOut]
    next_before: int | None  # 続きを読むとき、before に渡す。空なら、続きはない


def _resident_id(user: CurrentUser) -> int:
    """ログイン中の家族の入居者。紐づいていない家族は、ほかの家族と混ざらないよう 403 にする。"""
    if user.resident_id is None:
        raise AppError(ErrorCode.FORBIDDEN)
    return user.resident_id


def _group_by_day(photos: list[AlbumPhotoView]) -> list[AlbumDayOut]:
    """新しい順の写真を、載せた日（日本時間）ごとにまとめる（順番は変えない）。"""
    days: list[AlbumDayOut] = []
    for photo in photos:
        day = photo.posted_at.astimezone(JST).date()
        if not days or days[-1].date != day:
            days.append(AlbumDayOut(date=day, photos=[]))
        days[-1].photos.append(
            AlbumPhotoOut(
                id=photo.id,
                posted_at=photo.posted_at,
                comment=photo.comment,
                url=f"/api/files/{photo.file_id}",
            )
        )
    return days


@router.get("/features")
def get_features(
    _user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> FeaturesOut:
    return FeaturesOut(album=is_feature_disclosed(session, "album"))


@router.get("/album")
def get_album(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
    before: int | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> AlbumOut:
    resident_id = _resident_id(user)
    # 見せない設定のときは、空の一覧ではなく、404（アルバムがあるかも知らせない）
    if not is_feature_disclosed(session, "album"):
        raise AppError(ErrorCode.NOT_FOUND)
    page = get_visible_album_photos(session, resident_id, before=before, limit=limit)
    return AlbumOut(days=_group_by_day(page.photos), next_before=page.next_before)
