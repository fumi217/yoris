"""開発用のユーザー切り替えが、本番の設定では存在しないこと。

spec 001 の T021・research.md R-02。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FETCH = {"X-Requested-With": "fetch"}


@pytest.mark.parametrize("app_env", [None, "production"])
def test_switch_user_is_not_found_outside_development(monkeypatch, app_env):
    # APP_ENV を付け忘れたとき（None）も、本番として扱う
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    client = TestClient(create_app())

    response = client.post("/api/dev/switch-user", json={"user_id": 1}, headers=FETCH)

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message_key": "error.not_found"}}


def test_switch_user_exists_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    # 登録した API の一覧（OpenAPI）に入っているかで確かめる（DB を使わずに済む）
    paths = create_app().openapi()["paths"]

    assert "/api/dev/switch-user" in paths
