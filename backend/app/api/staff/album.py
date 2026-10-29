"""職員のアルバムの API（spec 005 の 005-T009。contracts の「職員」・FR-001・FR-003・FR-023）。

- `POST /api/staff/residents/{id}/album`：写真を 1 枚載せる（`multipart/form-data`：`file`、
  任意で `comment`（100 文字まで））。入居者は URL で指定する。画面は最大 10 枚を 1 枚ずつ順に送る
- `GET /api/staff/residents/{id}/album`：その入居者の、削除されていない写真の一覧と、
  `family_visible`（いまアルバムが家族に見えているか）
- `DELETE /api/staff/album/{id}`：写真を削除する（005-T019。FR-011）。削除済みの写真を
  もう一度削除しても、エラーにせず 204 を返す。写真は施設で絞る（ほかの施設の写真は 404）

役割は、介護職員・リーダー・生活相談員・施設長（事務員・家族は 403）。
入居者は、ログイン中の職員の施設のものだけ（ほかの施設・存在しない id は 404）。
形式（JPG・PNG だけ）と大きさ（10MB まで）は services/uploads.py の save_upload が、中身で確かめる。

既知の制限：Starlette は、ファイルを受け取ると、全体をいったん一時ファイルに受けてから、
ここの処理を呼ぶ。上限を超える大きなファイルを、入口で止める仕組みは、入れていない
（施設の職員だけが使う API で、役割で絞っているため）。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin.visits import facility_of
from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.album import COMMENT_MAX_LENGTH, AlbumPhoto
from app.models.core import Resident
from app.models.files import MAX_UPLOAD_BYTES
from app.services.album import ALBUM_FILE_TYPES, ALBUM_STAFF_ROLES, delete_album_photo
from app.services.disclosure import is_feature_disclosed
from app.services.uploads import save_upload

router = APIRouter(prefix="/api/staff", tags=["staff"])

ALBUM_STAFF = require_staff(ALBUM_STAFF_ROLES)

# 職員の画面の一覧に出す、多くても何枚か（新しい順）
STAFF_LIST_LIMIT = 100


class StaffPhotoOut(BaseModel):
    id: int
    posted_at: datetime
    comment: str | None
    url: str  # 写真のファイル（GET /api/files/{id}）


class StaffAlbumOut(BaseModel):
    family_visible: bool  # いまアルバムが家族に見えているか（見えていないときは、画面で知らせる）
    photos: list[StaffPhotoOut]


def _staff_id(user: CurrentUser) -> int:
    if user.staff_id is None:
        raise AppError(ErrorCode.FORBIDDEN)
    return user.staff_id


def _check_resident(session: Session, user: CurrentUser, resident_id: int) -> None:
    """ログイン中の職員の施設の入居者でなければ 404（あるかどうかも知らせない）。"""
    found = session.scalar(
        select(Resident.id).where(
            Resident.id == resident_id, Resident.facility_id == facility_of(session, user)
        )
    )
    if found is None:
        raise AppError(ErrorCode.NOT_FOUND)


def _photo_out(photo: AlbumPhoto) -> StaffPhotoOut:
    return StaffPhotoOut(
        id=photo.id,
        posted_at=photo.posted_at,
        comment=photo.comment,
        url=f"/api/files/{photo.file_id}",
    )


@router.post("/residents/{resident_id}/album", status_code=201)
def post_photo(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(ALBUM_STAFF)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    comment: Annotated[str | None, Form()] = None,
) -> StaffPhotoOut:
    staff_id = _staff_id(user)
    _check_resident(session, user, resident_id)
    # コメントは任意（空は「なし」）。100 文字まで
    text = comment or None
    if text is not None and len(text) > COMMENT_MAX_LENGTH:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    # 上限 + 1 バイトまでしか読まない（超えたら、save_upload が invalid_file で断る）
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    saved = save_upload(
        session,
        data=data,
        purpose="album",
        uploaded_by=staff_id,
        allowed_types=ALBUM_FILE_TYPES,
    )
    photo = AlbumPhoto(resident_id=resident_id, file_id=saved.id, comment=text, posted_by=staff_id)
    session.add(photo)
    session.flush()
    session.refresh(photo)  # 載せた日時（DB が入れる）を読む
    out = _photo_out(photo)
    session.commit()
    return out


@router.get("/residents/{resident_id}/album")
def list_photos(
    resident_id: int,
    user: Annotated[CurrentUser, Depends(ALBUM_STAFF)],
    session: Annotated[Session, Depends(get_session)],
) -> StaffAlbumOut:
    _check_resident(session, user, resident_id)
    rows = session.scalars(
        select(AlbumPhoto)
        .where(
            AlbumPhoto.resident_id == resident_id,
            AlbumPhoto.deleted_at.is_(None),
            AlbumPhoto.file_id.is_not(None),
        )
        .order_by(AlbumPhoto.posted_at.desc(), AlbumPhoto.id.desc())
        .limit(STAFF_LIST_LIMIT)
    )
    return StaffAlbumOut(
        family_visible=is_feature_disclosed(session, "album"),
        photos=[_photo_out(row) for row in rows],
    )


@router.delete("/album/{photo_id}", status_code=204)
def delete_photo(
    photo_id: int,
    user: Annotated[CurrentUser, Depends(ALBUM_STAFF)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    staff_id = _staff_id(user)
    photo = session.get(AlbumPhoto, photo_id)
    if photo is None:
        raise AppError(ErrorCode.NOT_FOUND)
    # ほかの施設の写真は、あるかどうかも知らせない
    _check_resident(session, user, photo.resident_id)
    delete_album_photo(session, photo, staff_id)
    return Response(status_code=204)
