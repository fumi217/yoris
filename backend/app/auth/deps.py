"""ログイン中の人と、役割のチェック（spec 001 の T010・data-model.md「ログイン中の人」）。

各担当の API は、次のように受け取る（本物のログインでも、開発用の切り替えでも、ここの形は同じ）。

    @router.get("/api/family/...")
    def handler(user: Annotated[CurrentUser, Depends(require_family)]): ...

    COUNSELOR_OR_DIRECTOR = require_staff(("counselor", "director"))

    @router.post("/api/staff/...")
    def handler(user: Annotated[CurrentUser, Depends(COUNSELOR_OR_DIRECTOR)]): ...
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import SESSION_COOKIE, read_session
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import STAFF_ROLES, FamilyAccount, Resident, Staff, User
from app.services.resident_names import resident_name


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    kind: str  # "staff"／"family"
    role: str | None  # 職員の役割（家族は None）
    staff_id: int | None  # 職員なら staff.id（記録・返事などの職員の参照に使う。家族は None）
    resident_id: int | None  # 家族なら、紐づいた入居者（職員は None）
    language: str
    # 職員は返事に出す名前、家族は入居者の名前（表示言語に合わせる。/api/me で使う。#389）
    display_name: str


def get_current_user(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> CurrentUser:
    """Cookie のセッションから、ログイン中の人を組み立てる。ログインしていなければ 401。

    全部の API がここを通るので、ログインの情報・職員・家族アカウント・入居者を 1 回でつなげて読む。
    """
    session_id = request.cookies.get(SESSION_COOKIE)
    user_id = read_session(session_id) if session_id else None
    user = load_current_user(session, user_id) if user_id is not None else None
    if user is None:
        raise AppError(ErrorCode.NOT_LOGGED_IN)
    return user


def load_current_user(session: Session, user_id: int) -> CurrentUser | None:
    """user_id から、ログイン中の人を組み立てる。ログインさせない人なら None。

    ログイン（app/auth/routes.py）でも、セッションを作る前にここで確かめる。
    """
    row = session.execute(
        select(
            User.kind,
            User.language,
            Staff.id.label("staff_id"),
            Staff.role,
            Staff.display_name.label("staff_name"),
            FamilyAccount.resident_id,
            resident_name(User.language).label("resident_name"),
        )
        .outerjoin(Staff, Staff.user_id == User.id)
        .outerjoin(FamilyAccount, FamilyAccount.user_id == User.id)
        .outerjoin(Resident, Resident.id == FamilyAccount.resident_id)
        .where(User.id == user_id)
    ).one_or_none()
    if row is None:
        return None

    # 職員なのに職員の行がない・家族なのに家族アカウントがない人は、ログインさせない
    if row.kind == "staff" and row.role is not None:
        return CurrentUser(
            user_id, row.kind, row.role, row.staff_id, None, row.language, row.staff_name
        )
    if row.kind == "family" and row.resident_id is not None:
        return CurrentUser(
            user_id, row.kind, None, None, row.resident_id, row.language, row.resident_name
        )
    return None


# 役割のチェック（テスト：backend/tests/unit/test_auth_deps.py）


def require_family(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """家族だけを通す。家族でなければ 403 `forbidden`。通すときは user をそのまま返す。"""
    if user.kind != "family":
        raise AppError(ErrorCode.FORBIDDEN)
    return user


def require_staff(roles: tuple[str, ...] | None = None) -> Callable[..., CurrentUser]:
    """職員だけを通す「チェックの関数」を作って返す。

    - roles を渡さないとき：職員なら、役割を問わず通す
    - roles を渡したとき：その役割の職員だけを通す
    - 通さないときは 403 `forbidden`
    - 役割の名前を書き間違えたら・空の役割を渡したら、起動したときにすぐエラーにする
      （その API に誰も入れなくなるのを防ぐ）
    """
    if roles is not None and not roles:
        raise ValueError("require_staff に空の役割が渡されました（職員ならだれでも、なら引数なし）")
    unknown = set(roles or ()) - set(STAFF_ROLES)
    if unknown:
        raise ValueError(f"require_staff に知らない役割があります：{sorted(unknown)}")

    def check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.kind != "staff":
            raise AppError(ErrorCode.FORBIDDEN)
        if roles is not None and user.role not in roles:
            raise AppError(ErrorCode.FORBIDDEN)
        return user

    return check
