"""ログイン・ログアウトと、ログイン中の人の API。

spec 001 の T022・contracts「ログイン・アカウント」。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_current_user, load_current_user
from app.auth.passwords import verify_password
from app.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import User

router = APIRouter(prefix="/api", tags=["auth"])


class MeResponse(BaseModel):
    kind: Literal["staff", "family"]
    role: str | None
    display_name: str
    language: str


def _me_response(user: CurrentUser) -> MeResponse:
    return MeResponse(
        kind=user.kind, role=user.role, display_name=user.display_name, language=user.language
    )


class LoginRequest(BaseModel):
    # 職員はログイン用の ID（s00001）、家族はメールアドレス
    login: str = Field(min_length=1, max_length=254)
    # 決まり（8〜64 文字）はパスワードを決めるときに確かめる。ここでは大きすぎる入力だけを弾く
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> MeResponse:
    """ログインして、`GET /api/me` と同じ中身を返す（画面が続けて /api/me を呼ばずに済むように）。

    ID（メールアドレス）とパスワードのどちらが違っても、同じ 401 `login_failed`
    （どちらが違うかを教えない）。
    """
    # 大文字・前後の空白の違いではじかない
    # （ID は s＋数字、メールアドレスは大文字・小文字を区別しない）
    login_value = body.login.strip().lower()
    user = session.scalars(
        select(User)
        .where(or_(User.login_id == login_value, func.lower(User.email) == login_value))
        .order_by(User.id)
    ).first()
    if not verify_password(body.password, user.password_hash if user else None):
        raise AppError(ErrorCode.LOGIN_FAILED)
    # 職員の行・家族アカウントがない人はログインさせない（/api/me と同じ決まり）
    current = load_current_user(session, user.id)
    if current is None:
        raise AppError(ErrorCode.LOGIN_FAILED)

    # ログインのたびに新しいセッションを作り、ログイン前のセッションは消す（セッションの固定を防ぐ）
    old_session_id = request.cookies.get(SESSION_COOKIE)
    if old_session_id:
        delete_session(old_session_id)
    set_session_cookie(response, create_session(user.id))
    return _me_response(current)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    """ログアウト。セッションをすぐ消し、Cookie も消す。ログインしていなくても 204。"""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        delete_session(session_id)
    clear_session_cookie(response)


@router.get("/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    """自分の種類・役割・表示名・表示言語。表示名は、職員は返事に出す名前、家族は入居者の呼び名。"""
    return _me_response(user)
