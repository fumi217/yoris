"""エラーの形とコード（spec 001 の contracts/api.md「エラーの形」）。

API は `raise AppError(ErrorCode.FORBIDDEN)` のように投げる。
返すのは次の形だけで、文言は画面が辞書から引く。

    {"error": {"code": "forbidden", "message_key": "error.forbidden"}}

コードを足すときは、ErrorCode と STATUS_CODES の両方に足す（contracts の表と合わせる）。
足し忘れは tests/unit/test_errors.py が見つける。
"""

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    NOT_LOGGED_IN = "not_logged_in"
    LOGIN_FAILED = "login_failed"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    REQUEST_LIMIT = "request_limit"
    THEME_WAITING = "theme_waiting"
    ALREADY_REPLIED = "already_replied"
    REQUEST_CANCELLED = "request_cancelled"
    NOT_TODAY = "not_today"
    INVALID_FILE = "invalid_file"
    VALIDATION_ERROR = "validation_error"
    SERVER_ERROR = "server_error"
    # 面会予約（spec 003 の contracts。003-T003）
    VISIT_OVERLAP = "visit_overlap"
    VISIT_DAY_FULL = "visit_day_full"
    VISIT_ALREADY_BOOKED_DAY = "visit_already_booked_day"
    VISIT_DEADLINE_PASSED = "visit_deadline_passed"
    VISIT_CLOSED_DAY = "visit_closed_day"
    VISIT_DAY_HAS_RESERVATIONS = "visit_day_has_reservations"
    VISIT_OUT_OF_RANGE = "visit_out_of_range"
    # 問い合わせ AI（spec 004 の contracts）
    AI_UNAVAILABLE = "ai_unavailable"
    # 決済（spec 002 の contracts。002-T017）
    EMAIL_MISMATCH = "email_mismatch"
    PAYMENT_SERVICE_UNAVAILABLE = "payment_service_unavailable"


STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.NOT_LOGGED_IN: 401,
    ErrorCode.LOGIN_FAILED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.TOO_MANY_ATTEMPTS: 429,
    ErrorCode.REQUEST_LIMIT: 409,
    ErrorCode.THEME_WAITING: 409,
    ErrorCode.ALREADY_REPLIED: 409,
    ErrorCode.REQUEST_CANCELLED: 409,
    ErrorCode.NOT_TODAY: 409,
    ErrorCode.INVALID_FILE: 422,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.SERVER_ERROR: 500,
    ErrorCode.VISIT_OVERLAP: 409,
    ErrorCode.VISIT_DAY_FULL: 409,
    ErrorCode.VISIT_ALREADY_BOOKED_DAY: 409,
    ErrorCode.VISIT_DEADLINE_PASSED: 409,
    ErrorCode.VISIT_CLOSED_DAY: 409,
    ErrorCode.VISIT_DAY_HAS_RESERVATIONS: 409,
    ErrorCode.VISIT_OUT_OF_RANGE: 422,
    ErrorCode.AI_UNAVAILABLE: 503,
    ErrorCode.EMAIL_MISMATCH: 422,
    ErrorCode.PAYMENT_SERVICE_UNAVAILABLE: 502,
}


class AppError(Exception):
    """API から投げるエラー。HTTP の番号は、コードから決まる。"""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


def error_response(
    code: ErrorCode, status_code: int | None = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = {"error": {"code": code.value, "message_key": f"error.{code.value}"}}
    return JSONResponse(
        status_code=status_code or STATUS_CODES[code], content=body, headers=headers
    )


# FastAPI が自分で返すエラー（ない URL など）も、同じ形にそろえる。
# 表にない番号（405 など）は、番号はそのままで server_error のコードにする
_HTTP_STATUS_TO_CODE = {
    401: ErrorCode.NOT_LOGGED_IN,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        # どの項目がどう違ったかは返さない（入力の値をそのまま返さないため）
        return error_response(ErrorCode.VALIDATION_ERROR)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_TO_CODE.get(exc.status_code, ErrorCode.SERVER_ERROR)
        # Allow（405）などのヘッダーは残す
        return error_response(code, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, __: Exception) -> JSONResponse:
        # 思わぬエラー。中身（スタックトレース）は返さない
        return error_response(ErrorCode.SERVER_ERROR)
