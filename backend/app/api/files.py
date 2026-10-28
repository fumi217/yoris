"""ファイルを返す API（spec 001 の 001-T071。contracts の「ファイル」・research.md R-10・FR-034）。

- `GET /api/files/{id}`：ログイン中の家族・職員に、保存したファイルを返す。
  ファイルは公開の URL を持たない（URL を知っていても、ログインしていなければ開けない）

返すときは、保存した形式の Content-Type に固定し、nosniff を付ける
（形式を偽ったファイルを、画面の一部として実行させない。FR-025）。

アルバムの写真は、入居者ごとの条件（開示設定など）を 005-T011 で足すまで、開けない
（条件がないまま、ログインしていれば誰でも見える状態にしないため）。
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
from app.services.uploads import read_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{file_id}")
def get_file(
    file_id: int,
    _user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    uploaded = session.get(UploadedFile, file_id)
    # 開けない理由は区別しない（あるかどうかも知らせない）
    if uploaded is None or uploaded.purpose != "announcement":
        raise AppError(ErrorCode.NOT_FOUND)
    try:
        data = read_upload(uploaded.storage_key)
    except OSError:
        # 保存先から消えている。パスなどの中身は、ログにも画面にも出さない
        logger.error("保存したファイルを読めません file_id=%s", uploaded.id)
        raise AppError(ErrorCode.NOT_FOUND) from None
    return Response(
        content=data,
        media_type=uploaded.content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
