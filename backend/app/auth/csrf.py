"""書き込みの確認（spec 001 の T014・research.md R-03。CSRF 対策）。

書き込み（POST・PUT・PATCH・DELETE）は、`X-Requested-With: fetch` ヘッダーがなければ
403 `forbidden`。
ほかのサイトのページからは、このヘッダーを付けたリクエストを送れない（ブラウザが止める）ので、
ログイン中の人のブラウザを使って勝手に書き込まれるのを防げる。
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.errors import ErrorCode, error_response

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# ブラウザから呼ばない API は対象から外す（代わりにそれぞれのやり方で確かめる）
EXEMPT_PATHS = {
    "/api/internal/jobs/run",  # 決まった時刻の処理。合言葉で確かめる（spec 001 の contracts）
    "/api/billing/webhook",  # Stripe からの知らせ。署名で確かめる（spec 002 の contracts）
}


class RequireFetchHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.method in WRITE_METHODS
            and request.url.path not in EXEMPT_PATHS
            and request.headers.get("X-Requested-With") != "fetch"
        ):
            return error_response(ErrorCode.FORBIDDEN)
        return await call_next(request)
