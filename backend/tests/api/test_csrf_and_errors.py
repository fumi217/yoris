"""書き込みの確認（T014）と、エラーの形（T012）。DB と Redis を使わずに確かめられる分。"""

from fastapi.testclient import TestClient

from app.db import get_engine
from app.main import create_app

client = TestClient(create_app())


def test_write_without_fetch_header_is_forbidden():
    response = client.post("/api/anything")

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "forbidden", "message_key": "error.forbidden"}}


def test_write_with_fetch_header_goes_through():
    # ヘッダーがあれば確認を通り、ない URL なので 404 になる
    response = client.post("/api/anything", headers={"X-Requested-With": "fetch"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_read_does_not_need_fetch_header():
    assert client.get("/api/health").status_code == 200


def test_exempt_path_skips_fetch_header_check():
    # Stripe からの知らせは、ヘッダーなしでも確認で止めない（403 でなく、署名がないので 400）
    response = client.post("/api/billing/webhook")

    assert response.status_code == 400


def test_me_without_login_is_not_logged_in(monkeypatch):
    # /api/me は DB のセッションを使うので、つなぎ先の URL だけは要る
    # （Cookie がないので、DB につなぐ前に 401 で止まる）
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    get_engine.cache_clear()
    response = client.get("/api/me")
    get_engine.cache_clear()

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "not_logged_in", "message_key": "error.not_logged_in"}
    }


def test_wrong_method_keeps_405_with_error_shape():
    response = client.post("/api/health", headers={"X-Requested-With": "fetch"})

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "server_error"
    assert "allow" in response.headers
