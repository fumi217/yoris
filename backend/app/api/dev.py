"""開発用のユーザー切り替え（spec 001 の T013・research.md R-02）。

`APP_ENV=development` のときだけ、main.py がこのルーターを登録する。本番には存在しない（404）。
初期データの職員・家族の user_id を送ると、その人としてログインした状態になる。
選べる人の一覧は GET /api/dev/users（画面の切り替えの部品が使う）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.auth.sessions import (
    SESSION_COOKIE,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import FamilyAccount, Resident, Staff, User
from app.services.resident_names import resident_name

router = APIRouter(prefix="/api/dev", tags=["dev"])


class SwitchUserRequest(BaseModel):
    user_id: int


class DevUser(BaseModel):
    user_id: int
    kind: str
    role: str | None
    # 職員は返事に出す名前、家族は入居者の名前（その家族の表示言語に合わせる）
    display_name: str
    # 表示言語（外国人の職員を選んで試すときの目印）
    language: str


@router.get("/users")
def list_users(session: Annotated[Session, Depends(get_session)]) -> list[DevUser]:
    """切り替えで選べる人の一覧（職員が先、それぞれ id の順）。"""
    rows = session.execute(
        select(
            User.id,
            User.kind,
            User.language,
            User.login_id,
            User.email,
            Staff.role,
            Staff.display_name.label("staff_name"),
            resident_name(User.language).label("resident_name"),
        )
        .outerjoin(Staff, Staff.user_id == User.id)
        .outerjoin(FamilyAccount, FamilyAccount.user_id == User.id)
        .outerjoin(Resident, Resident.id == FamilyAccount.resident_id)
        # 職員が先、それぞれ id の順
        .order_by(case((User.kind == "staff", 0), else_=1), User.id)
    )
    return [
        DevUser(
            user_id=row.id,
            kind=row.kind,
            role=row.role,
            language=row.language,
            # 職員・家族の行がまだない人（手で入れた途中の人など）は、
            # ログイン用の ID かメールアドレスを出す
            display_name=row.staff_name or row.resident_name or row.login_id or row.email or "",
        )
        for row in rows
    ]


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
