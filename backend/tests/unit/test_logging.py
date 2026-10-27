"""ログの出し方（001-T006）のテスト。DB・Redis は使わない。"""

import io
import json
import logging

import pytest
import structlog

from app.config import Settings
from app.logging import REDACTED, configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """テストごとに変えた root のログの設定を、元に戻す。"""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level
    structlog.reset_defaults()


def _configure(monkeypatch, app_env: str) -> io.StringIO:
    monkeypatch.setenv("APP_ENV", app_env)
    stream = io.StringIO()
    configure_logging(Settings(), stream=stream)
    return stream


def test_production_writes_json_lines(monkeypatch):
    stream = _configure(monkeypatch, "production")
    structlog.get_logger("app.test").info("施設を作った", facility_id=3)

    line = json.loads(stream.getvalue().strip())
    assert line["event"] == "施設を作った"
    assert line["facility_id"] == 3
    assert line["level"] == "info"
    assert line["logger"] == "app.test"
    assert "timestamp" in line


def test_production_drops_debug_but_keeps_info(monkeypatch):
    stream = _configure(monkeypatch, "production")
    logger = logging.getLogger("app.test")
    logger.debug("見せない")
    logger.info("見せる")

    assert "見せない" not in stream.getvalue()
    assert "見せる" in stream.getvalue()


def test_unset_app_env_is_treated_as_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    stream = io.StringIO()
    configure_logging(Settings(), stream=stream)
    logging.getLogger("app.test").info("確認")

    assert json.loads(stream.getvalue().strip())["event"] == "確認"


def test_development_is_readable_and_includes_debug(monkeypatch):
    stream = _configure(monkeypatch, "development")
    logging.getLogger("app.test").debug("詳しいログ")

    output = stream.getvalue()
    assert "詳しいログ" in output
    assert "debug" in output
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.strip())


def test_standard_logging_goes_through_the_same_format(monkeypatch):
    """既存の logging.getLogger(...) で書かれたログも、本番では JSON になる。"""
    stream = _configure(monkeypatch, "production")
    logging.getLogger("app.services.mail").warning("送れなかった outbox_id=%s", 12)

    line = json.loads(stream.getvalue().strip())
    assert line["event"] == "送れなかった outbox_id=12"
    assert line["level"] == "warning"
    assert line["logger"] == "app.services.mail"


def test_personal_fields_are_replaced_in_production(monkeypatch):
    stream = _configure(monkeypatch, "production")
    structlog.get_logger("app.test").info(
        "招待を送った",
        user_id=5,
        email="family@example.com",
        name="架空 太郎",
        invite_token="abc123",
        body="今日は食事を残しました",
    )

    output = stream.getvalue()
    for secret in ("family@example.com", "架空 太郎", "abc123", "今日は食事を残しました"):
        assert secret not in output
    line = json.loads(output.strip())
    assert line["user_id"] == 5
    assert line["email"] == REDACTED


def test_personal_fields_are_replaced_in_development_too(monkeypatch):
    stream = _configure(monkeypatch, "development")
    structlog.get_logger("app.test").info("返事", reply_id=2, content="お返事の本文")

    assert "お返事の本文" not in stream.getvalue()
    assert "reply_id=2" in stream.getvalue()


def test_exception_is_written_with_traceback(monkeypatch):
    stream = _configure(monkeypatch, "production")
    try:
        raise ValueError("失敗")
    except ValueError:
        logging.getLogger("app.test").exception("run_jobs() に失敗しました")

    line = json.loads(stream.getvalue().strip())
    assert line["event"] == "run_jobs() に失敗しました"
    assert "ValueError" in line["exception"]


def test_uvicorn_logs_follow_the_same_format(monkeypatch):
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger.addHandler(logging.NullHandler())
    uvicorn_logger.propagate = False
    stream = _configure(monkeypatch, "production")
    uvicorn_logger.info("Application startup complete.")

    assert uvicorn_logger.handlers == []
    assert json.loads(stream.getvalue().strip())["event"] == "Application startup complete."


def test_calling_twice_keeps_one_handler(monkeypatch):
    _configure(monkeypatch, "production")
    stream = _configure(monkeypatch, "production")
    logging.getLogger("app.test").info("1 回だけ")

    assert len(logging.getLogger().handlers) == 1
    assert stream.getvalue().count("1 回だけ") == 1


def test_personal_fields_inside_a_dict_are_replaced(monkeypatch):
    stream = _configure(monkeypatch, "production")
    structlog.get_logger("app.test").info("送った", data={"email": "family@example.com", "id": 4})

    line = json.loads(stream.getvalue().strip())
    assert line["data"] == {"email": REDACTED, "id": 4}


def test_noisy_libraries_stay_quiet_even_in_development(monkeypatch):
    stream = _configure(monkeypatch, "development")
    logging.getLogger("httpx").debug("リクエストの中身")
    logging.getLogger("httpx").warning("接続に失敗")

    assert "リクエストの中身" not in stream.getvalue()
    assert "接続に失敗" in stream.getvalue()
