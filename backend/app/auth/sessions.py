"""ログインのセッション（spec 001 の research.md R-03・R-12）。

ブラウザには推測できないランダムな値（セッションの ID）だけを Cookie で渡し、
誰なのか（user_id）は Redis の `session:<セッションの ID>` に置く。
開発用のユーザー切り替え（app/api/dev.py）と、本物のログイン（T022）の両方がこれを使う。
"""

import secrets

from fastapi import Response

from app.config import get_settings
from app.redis import get_redis

SESSION_COOKIE = "session_id"
# セッションの期限（仮）。
# 操作がないまま 30 分で自動ログアウトする決まりは、#66（T086）で役割ごとに足す
SESSION_TTL_SECONDS = 60 * 60 * 12


def _key(session_id: str) -> str:
    return f"session:{session_id}"


def create_session(user_id: int) -> str:
    """セッションを作り、その ID を返す。

    ログイン・切り替えのたびに必ず新しく作り、前の ID は delete_session で消す
    （ログイン前の Cookie を使い続けない。セッションの固定を防ぐ。#65 の本物のログインも同じ）。
    """
    session_id = secrets.token_urlsafe(32)
    get_redis().set(_key(session_id), str(user_id), ex=SESSION_TTL_SECONDS)
    return session_id


def read_session(session_id: str) -> int | None:
    """セッションの user_id を返す。ない・期限切れなら None。"""
    value = get_redis().get(_key(session_id))
    return int(value) if value is not None else None


def delete_session(session_id: str) -> None:
    get_redis().delete(_key(session_id))


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,  # 画面の JavaScript から読めないようにする
        secure=not get_settings().is_development,  # 本番は https だけで送る
        samesite="lax",
        path="/",
    )
