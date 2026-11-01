"""ログの出し方（spec 001 の 001-T006、FR-027。research.md R-18）。

開発（APP_ENV=development）は読みやすい形式で DEBUG 以上、
本番は JSON で INFO 以上を、標準出力に出す。
API（uvicorn）と worker で同じ設定を使う（`configure_logging()` を、それぞれの入口で 1 回呼ぶ）。

ログを書くときの決まり：氏名・メールアドレス・記録の値・返事の文・お知らせの本文・招待のトークンは出さず、
id だけを出す。`logger.info("...", resident_id=resident.id)` のように、値は名前つきで渡す。
万一、そういう名前の値が渡されても、`_redact_personal_fields` が「[省略]」に置き換える
（最後の守り）。
メッセージの文字列に値を埋め込んだ場合は守れないので、値は名前つきで渡すこと。
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, TextIO

import structlog

from app.config import Settings, get_settings

REDACTED = "[省略]"

# 個人情報になりうる値の名前。ここに当てはまる名前で渡された値は、ログに出さない
PERSONAL_FIELDS = frozenset(
    {
        "name",
        "name_kana",
        "name_romaji",
        "display_name",
        "facility_name",
        "director_name",
        "email",
        "to_email",
        "phone",
        "password",
        "token",
        "invite_token",
        "secret",
        "api_key",
        "body",
        "content",
        "text",
        "message",
        "note",
        "memo",
        "value",
        "values",
        "reply",
        "recipient",
        "address",
        "subject",
        "comment",
        "detail",
    }
)

# 開発で DEBUG にしても、リクエストやレスポンスの中身を出しうる外部のライブラリは、
# WARNING 以上だけにする
QUIET_LIBRARIES = ("sqlalchemy", "httpx", "httpcore", "openai", "stripe", "urllib3")

# structlog が自分で使う名前。個人情報としては扱わない
_RESERVED = frozenset({"event", "level", "logger", "timestamp", "exception", "stack"})


def _redact(value: Any) -> Any:
    """辞書の中の値も、同じ名前の決まりで置き換える。"""
    if isinstance(value, dict):
        return {
            key: REDACTED if str(key).lower() in PERSONAL_FIELDS else _redact(item)
            for key, item in value.items()
        }
    return value


def _redact_personal_fields(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in event_dict:
        if key in _RESERVED:
            continue
        event_dict[key] = REDACTED if key.lower() in PERSONAL_FIELDS else _redact(event_dict[key])
    return event_dict


def configure_logging(settings: Settings | None = None, stream: TextIO | None = None) -> None:
    """標準の logging と structlog を、同じ形式でつなぐ。何度呼んでも、ハンドラーは 1 つ。"""
    settings = settings or get_settings()
    development = settings.is_development

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_personal_fields,
    ]

    if development:
        renderer: Any = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # 標準の logging（logging.getLogger(...) で書かれたログ）にも、同じ処理をかける
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if development else logging.INFO)

    for name in QUIET_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn は自分のハンドラーを付けるので外し、同じ形式の root に流す
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
