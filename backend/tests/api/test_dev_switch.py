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


def test_switch_user_logs_in_and_drops_old_session(make_client, make_staff, make_family, redis):
    client = make_client(app_env="development")
    staff = make_staff(role="counselor")
    family = make_family()

    assert client.post("/api/dev/switch-user", json={"user_id": staff.user_id}).status_code == 204
    assert client.get("/api/me").json()["kind"] == "staff"

    assert client.post("/api/dev/switch-user", json={"user_id": family.user_id}).status_code == 204
    assert client.get("/api/me").json()["kind"] == "family"
    # 前の人のセッションは消え、残るのは 1 つだけ（古い Cookie で前の人に戻れない）
    assert len(redis.keys("session:*")) == 1


def test_switch_user_to_unknown_user_is_not_found(make_client):
    client = make_client(app_env="development")

    assert client.post("/api/dev/switch-user", json={"user_id": 0}).status_code == 404


def test_dev_users_lists_staff_first(make_client, make_staff, make_family):
    client = make_client(app_env="development")
    staff = make_staff(role="counselor", display_name="テスト相談員")
    family = make_family(display_name="テストさんの母")

    users = client.get("/api/dev/users").json()

    assert {
        "user_id": staff.user_id,
        "kind": "staff",
        "role": "counselor",
        "display_name": "テスト相談員",
    } in users
    assert {
        "user_id": family.user_id,
        "kind": "family",
        "role": None,
        "display_name": "テストさんの母",
    } in users
    # 職員がすべて家族より先、それぞれ id の順
    staff_ids = [user["user_id"] for user in users if user["kind"] == "staff"]
    family_ids = [user["user_id"] for user in users if user["kind"] == "family"]
    assert users == sorted(users, key=lambda user: user["kind"] != "staff")
    assert staff_ids == sorted(staff_ids)
    assert family_ids == sorted(family_ids)


def test_dev_users_is_not_found_in_production(client):
    assert client.get("/api/dev/users").status_code == 404
