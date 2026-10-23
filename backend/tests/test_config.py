from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_app_env_defaults_to_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    assert get_settings().app_env == "production"
    assert get_settings().is_development is False


def test_settings_read_env_when_called(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert get_settings().is_development is True

    monkeypatch.setenv("APP_ENV", "production")
    assert get_settings().is_development is False


def test_secrets_are_not_in_repr(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "dummy-resend-key")
    monkeypatch.setenv("JOBS_TOKEN", "dummy-jobs-token")

    text = repr(get_settings())

    assert "dummy-resend-key" not in text
    assert "dummy-jobs-token" not in text


def test_docs_only_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert TestClient(create_app()).get("/docs").status_code == 404

    monkeypatch.setenv("APP_ENV", "development")
    assert TestClient(create_app()).get("/docs").status_code == 200


def test_tests_never_see_ai_key():
    # tests/conftest.py が、どのテストでも OPENROUTER_API_KEY を空にしている
    assert get_settings().openrouter_api_key is None
