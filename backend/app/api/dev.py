"""開発用のユーザー切り替え（spec 001 の T013・research.md R-02）。

`APP_ENV=development` のときだけ、main.py がこのルーターを登録する。本番には存在しない（404）。
初期データの職員・家族の user_id を送ると、その人としてログインした状態になる。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.sessions import (
    SESSION_COOKIE,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import User

router = APIRouter(prefix="/api/dev", tags=["dev"])


class SwitchUserRequest(BaseModel):
    user_id: int


@router.post("/switch-user", status_code=204)
def switch_user(
    body: SwitchUserRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    if session.get(User, body.user_id) is None:
        raise AppError(ErrorCode.NOT_FOUND)
    # 前の人のセッションは消す（古い Cookie で前の人に戻れないように）
    old_session_id = request.cookies.get(SESSION_COOKIE)
    if old_session_id:
        delete_session(old_session_id)
    set_session_cookie(response, create_session(body.user_id))
