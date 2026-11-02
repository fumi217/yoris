"""家族のリクエストの作成・取り消し・一覧（spec 001 の 001-T049。research.md R-08・R-06）。

- 入居者は、ログイン中の家族の CurrentUser.resident_id から決める（送られた値は使わない。FR-020）
- 返事待ち（waiting）は 3 件まで、同じテーマは 1 件まで（FR-014）。
  作るときに家族アカウントの行を FOR UPDATE で押さえてから数えるので、同時に 2 回押しても
  4 件目は入らない。同じテーマは、DB の一意制約（部分インデックス）でも守る
- 選べるテーマは、開示しているものだけ（get_disclosed_themes。FR-013）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）
- 返事を保存して answered に動かすのは、ゆうの返事の保存（001-T052）
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import JST, now, today_jst
from app.models.core import FamilyAccount
from app.models.requests import MAX_WAITING_REQUESTS, Request
from app.services.disclosure import (
    get_active_replies,
    get_disclosed_themes,
    get_requested_themes,
)

# 送ってから、この時間がたっても返事がないときは、「お急ぎのときは、施設にお電話ください」を出す
OVERDUE_AFTER = timedelta(days=3)


class RequestError(Exception):
    """リクエストを作れない・取り消せない。code は spec 001 contracts のエラーのコード。"""

    code = "validation_error"


class RequestLimit(RequestError):
    """返事待ちが、すでに 3 件ある（409）。"""

    code = "request_limit"


class ThemeWaiting(RequestError):
    """同じテーマの返事待ちが、すでにある（409）。"""

    code = "theme_waiting"


class ThemeNotAvailable(RequestError):
    """知らないテーマ・開示していないテーマ（422）。"""

    code = "validation_error"


class RequestNotFound(RequestError):
    """ない・ほかの家族のリクエスト（404。存在するかどうかも知らせない）。"""

    code = "not_found"


class AlreadyReplied(RequestError):
    """返事がすでについているので、取り消せない（409）。"""

    code = "already_replied"


@dataclass(frozen=True)
class RequestView:
    id: int
    theme_id: int
    theme_code: str  # 辞書のキー（例："theme.daily_life"）
    emoji: str
    status: str  # "waiting" / "answered" / "cancelled"
    created_at: datetime
    days_ago: int  # 送ってからの日数（日本時間の日付で数える。「2 日前に送りました」）
    overdue: bool  # 返事待ちのまま 3 日たった
    # 返事が入った連絡帳の日付（返事待ち・取り消しは None。「連絡帳で見る」の行き先。#403）
    reply_date: date | None = None


def _resident_id(current_user: CurrentUser) -> int:
    if current_user.kind != "family" or current_user.resident_id is None:
        # 家族の API（require_family）からしか呼ばない
        raise RequestNotFound("家族のログインではない")
    return current_user.resident_id


def is_overdue(status: str, created_at: datetime, at: datetime | None = None) -> bool:
    """返事待ちのまま、3 日（72 時間）たったか。"""
    return status == "waiting" and (at or now()) - created_at >= OVERDUE_AFTER


def create_request(session: Session, current_user: CurrentUser, theme_id: int) -> Request:
    """リクエストを作る。返事待ちが 3 件ある・同じテーマが返事待ちなら、作らない。"""
    resident_id = _resident_id(current_user)
    # 家族アカウントの行を押さえて、同じ家族の同時の作成を、順番に処理する（R-08）
    session.execute(
        select(FamilyAccount.id).where(FamilyAccount.resident_id == resident_id).with_for_update()
    ).one()

    if theme_id not in {theme.id for theme in get_disclosed_themes(session)}:
        raise ThemeNotAvailable(f"theme_id: {theme_id}")

    waiting = session.scalars(
        select(Request).where(Request.resident_id == resident_id, Request.status == "waiting")
    ).all()
    if any(request.theme_id == theme_id for request in waiting):
        raise ThemeWaiting(f"theme_id: {theme_id}")
    if len(waiting) >= MAX_WAITING_REQUESTS:
        raise RequestLimit(f"waiting: {len(waiting)}")

    request = Request(resident_id=resident_id, theme_id=theme_id)
    try:
        with session.begin_nested():
            session.add(request)
            session.flush()
    except IntegrityError as error:
        # 処理にバグがあっても、DB の一意制約が受け付けない（R-08）
        raise ThemeWaiting(f"theme_id: {theme_id}") from error
    session.refresh(request)
    return request


def cancel_request(session: Session, current_user: CurrentUser, request_id: int) -> Request:
    """返事の前（waiting）だけ取り消す。取り消し済みなら、そのまま返す。"""
    resident_id = _resident_id(current_user)
    # ほかの家族のリクエストは、ないものと同じ扱い（FR-020・R-19）
    request = session.scalars(
        select(Request)
        .where(Request.id == request_id, Request.resident_id == resident_id)
        .with_for_update()
    ).one_or_none()
    if request is None:
        raise RequestNotFound(f"request_id: {request_id}")
    if request.status == "answered":
        raise AlreadyReplied(f"request_id: {request_id}")
    if request.status == "waiting":
        request.status = "cancelled"
        request.cancelled_at = func.now()
        session.flush()
        session.refresh(request)
    return request


def list_requests(
    session: Session, current_user: CurrentUser, at: datetime | None = None
) -> Sequence[RequestView]:
    """送ったリクエストの一覧（新しい順）。取り消したものも、status つきで返す。

    テーマ名は、いまは非開示のテーマでも出す（送ったあとに非開示になることがあるため。
    get_requested_themes を通す。issue #111）。
    """
    resident_id = _resident_id(current_user)
    requests = session.scalars(
        select(Request)
        .where(Request.resident_id == resident_id)
        .order_by(Request.created_at.desc(), Request.id.desc())
    ).all()
    themes = {
        theme.id: theme for theme in get_requested_themes(session, {r.theme_id for r in requests})
    }
    today = today_jst(at)
    reply_dates = _reply_dates(session, resident_id, requests, today)
    return [
        RequestView(
            id=request.id,
            theme_id=request.theme_id,
            theme_code=themes[request.theme_id].code,
            emoji=themes[request.theme_id].emoji,
            status=request.status,
            created_at=request.created_at,
            days_ago=(today - request.created_at.astimezone(JST).date()).days,
            overdue=is_overdue(request.status, request.created_at, at),
            reply_date=reply_dates.get(request.id),
        )
        for request in requests
    ]


def _reply_dates(
    session: Session, resident_id: int, requests: Sequence[Request], today: date
) -> dict[int, date]:
    """返事が付いたリクエストの、返事が入った連絡帳の日付（request_id → 日付）。

    家族に出す返事なので、共通の関数 get_active_replies を通す（R-06）。中身（定型文・書き足し）は
    使わず、日付だけを取る。
    """
    answered = [request for request in requests if request.status == "answered"]
    if not answered:
        return {}
    # 返事は、送った日以降に入る。いちばん古い送った日から、明日まで探す（日またぎの余裕）
    first = min(request.created_at.astimezone(JST).date() for request in answered)
    replies = get_active_replies(session, resident_id, first, today + timedelta(days=1))
    return {reply.request_id: reply.contact_book_date for reply in replies}
