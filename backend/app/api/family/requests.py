"""家族の「知りたいこと」の API（spec 001 の 001-T050。contracts の「家族」）。

入居者は送らせない（本文にも URL にも入居者の欄を持たない）。
ログイン中の家族の CurrentUser.resident_id から決める（FR-020）。
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.services.disclosure import get_disclosed_themes
from app.services.requests import RequestError, cancel_request, create_request, list_requests

router = APIRouter(prefix="/api/family", tags=["family"])


class ThemeOut(BaseModel):
    id: int
    code: str  # 辞書のキー（例："theme.daily_life"）
    emoji: str


class RequestOut(BaseModel):
    id: int
    theme_id: int
    theme_code: str
    emoji: str
    status: str  # "waiting" / "answered" / "cancelled"
    created_at: datetime
    days_ago: int
    overdue: bool  # 返事待ちのまま 3 日たった（「お急ぎのときは、施設にお電話ください」）
    reply_date: date | None  # 返事が入った連絡帳の日付（返事のないものは None。#403）


class CreateRequestBody(BaseModel):
    # 入居者などの余分な項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    theme_id: int


def _app_error(error: RequestError) -> AppError:
    return AppError(ErrorCode(error.code))


@router.get("/themes")
def themes(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ThemeOut]:
    """頼めるテーマ（開示しているものだけ。FR-013）。"""
    return [
        ThemeOut(id=theme.id, code=theme.code, emoji=theme.emoji)
        for theme in get_disclosed_themes(session)
    ]


@router.get("/requests")
def requests(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RequestOut]:
    """送ったリクエスト（新しい順。状態・送った日時・日数・3 日たったか）。"""
    try:
        views = list_requests(session, user)
    except RequestError as error:
        raise _app_error(error) from error
    return [RequestOut(**vars(view)) for view in views]


@router.post("/requests", status_code=201)
def create(
    body: CreateRequestBody,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> RequestOut:
    """テーマを選んで送る。返事待ちが 3 件ある・同じテーマが返事待ちなら 409。"""
    try:
        request = create_request(session, user, body.theme_id)
        session.flush()
        view = next(v for v in list_requests(session, user) if v.id == request.id)
    except RequestError as error:
        raise _app_error(error) from error
    session.commit()
    return RequestOut(**vars(view))


@router.delete("/requests/{request_id}", status_code=204)
def cancel(
    request_id: int,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """返事の前だけ取り消す。ほかの家族のものは 404、返事がついていれば 409。"""
    try:
        cancel_request(session, user, request_id)
    except RequestError as error:
        raise _app_error(error) from error
    session.commit()
