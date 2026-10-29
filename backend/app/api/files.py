"""ファイルを返す API（spec 001 の 001-T071。contracts の「ファイル」・research.md R-10・FR-034）。

- `GET /api/files/{id}`：ログイン中の家族・職員に、保存したファイルを返す。
  ファイルは公開の URL を持たない（URL を知っていても、ログインしていなければ開けない）

返すときは、保存した形式の Content-Type に固定し、nosniff を付ける
（形式を偽ったファイルを、画面の一部として実行させない。FR-025）。

アルバムの写真（spec 005 の 005-T011）は、services/album.py の can_open_album_file の条件を通す
（職員の役割・自分の入居者の写真・削除されていない・見せる設定。一覧と同じ判定）。
条件に合わないときは、あるかどうかも知らせず、404 にする。
取り消したお知らせの添付を 404 にする条件は、お知らせの表（#144）ができてから足す。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_current_user
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.files import UploadedFile
from app.services.album import can_open_album_file
from app.services.uploads import read_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{file_id}")
def get_file(
    file_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    uploaded = session.get(UploadedFile, file_id)
    # 開けない理由は区別しない（あるかどうかも知らせない）
    if uploaded is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if uploaded.purpose == "album":
        if not can_open_album_file(session, uploaded.id, user):
            raise AppError(ErrorCode.NOT_FOUND)
    elif uploaded.purpose != "announcement":
        raise AppError(ErrorCode.NOT_FOUND)
    try:
        data = read_upload(uploaded.storage_key)
    except OSError:
        # 保存先から消えている。パスなどの中身は、ログにも画面にも出さない
        logger.error("保存したファイルを読めません file_id=%s", uploaded.id)
        raise AppError(ErrorCode.NOT_FOUND) from None
    headers = {"X-Content-Type-Options": "nosniff"}
    if uploaded.purpose == "album":
        # 12 枚ぶんの元の写真を見るたびに読み直さないため。5 分は、削除してから見えなくなるまでの
        # 長さ（FR-012）と同じ。長くすると、削除のあとも端末に残る
        headers["Cache-Control"] = "private, max-age=300"
    return Response(content=data, media_type=uploaded.content_type, headers=headers)
