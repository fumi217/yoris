"""ログイン中の人の API（spec 001 の contracts「ログイン・アカウント」）。

本物のログイン・ログアウト（T022）も、あとでこのファイルに足す。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


class MeResponse(BaseModel):
    kind: Literal["staff", "family"]
    role: str | None
    display_name: str
    language: str


@router.get("/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    """自分の種類・役割・表示名・表示言語。表示名は、職員は返事に出す名前、家族は入居者の呼び名。"""
    return MeResponse(
        kind=user.kind, role=user.role, display_name=user.display_name, language=user.language
    )
