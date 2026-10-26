"""本物のログイン・ログアウト（spec 001 の T022・T023）。

本物の DB と Redis を使う（tests/conftest.py）。
"""

import pytest

from app.auth import passwords
from app.auth.passwords import hash_password
from app.auth.sessions import SESSION_COOKIE
from app.models.core import User

PASSWORD = "kumoyama-sora"


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passwords, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def with_password(session):
    """その user_id の人に PASSWORD を入れて、User を返す。"""

    def set_password(user_id: int) -> User:
        user = session.get(User, user_id)
        user.password_hash = hash_password(PASSWORD)
        session.flush()
        return user

    return set_password


def test_staff_logs_in_with_login_id(client, make_staff, with_password):
    staff = make_staff(role="leader", display_name="テストリーダー")
    user = with_password(staff.user_id)

    response = client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})

    assert response.status_code == 200
    # GET /api/me と同じ中身
    assert response.json() == {
        "kind": "staff",
        "role": "leader",
        "display_name": "テストリーダー",
        "language": "ja",
    }
    assert client.get("/api/me").json()["kind"] == "staff"


def test_family_logs_in_with_email(client, make_family, with_password):
    family = make_family(display_name="テストさんの父")
    user = with_password(family.user_id)

    response = client.post("/api/auth/login", json={"login": user.email, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["kind"] == "family"
    assert response.json()["display_name"] == "テストさんの父"


def test_login_ignores_case_and_spaces(client, make_family, with_password):
    user = with_password(make_family().user_id)

    response = client.post(
        "/api/auth/login", json={"login": f"  {user.email.upper()} ", "password": PASSWORD}
    )

    assert response.status_code == 200


@pytest.mark.parametrize("wrong", ["login", "password"])
def test_wrong_login_or_password_gets_the_same_error(client, make_staff, with_password, wrong):
    user = with_password(make_staff().user_id)
    body = {"login": user.login_id, "password": PASSWORD}
    body[wrong] = "s99999" if wrong == "login" else "kumoyama-umi"

    response = client.post("/api/auth/login", json=body)

    # どちらが違うかを教えない
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "login_failed", "message_key": "error.login_failed"}
    }
    assert SESSION_COOKIE not in client.cookies


def test_user_without_password_cannot_log_in(client, session, make_staff):
    # 初期データで SEED_PASSWORD を入れていない人（ログインできない値「!」）
    staff = make_staff()
    user = session.get(User, staff.user_id)
    user.password_hash = "!"
    session.flush()

    response = client.post("/api/auth/login", json={"login": user.login_id, "password": "!"})

    assert response.json()["error"]["code"] == "login_failed"


def test_staff_without_staff_row_cannot_log_in(client, session, make_staff, with_password):
    staff = make_staff()
    user = with_password(staff.user_id)
    session.delete(staff)
    session.flush()

    response = client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})

    assert response.json()["error"]["code"] == "login_failed"


def test_login_replaces_the_session_from_before(
    client, redis, make_staff, make_family, with_password
):
    # セッションの固定を防ぐ：ログイン前の Cookie のセッションは消え、新しい ID になる
    family = with_password(make_family().user_id)
    client.post("/api/auth/login", json={"login": family.email, "password": PASSWORD})
    old_session_id = client.cookies[SESSION_COOKIE]
    staff = with_password(make_staff().user_id)

    client.post("/api/auth/login", json={"login": staff.login_id, "password": PASSWORD})

    assert client.cookies[SESSION_COOKIE] != old_session_id
    assert redis.exists(f"session:{old_session_id}") == 0
    assert client.get("/api/me").json()["kind"] == "staff"


def test_session_cookie_attributes(client, make_staff, with_password):
    user = with_password(make_staff().user_id)

    response = client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie  # 本番の設定
    assert "SameSite=lax" in cookie


def test_login_needs_the_fetch_header(make_client, make_staff, with_password):
    # ログインも書き込みと同じく、ほかのサイトのページから送らせない（CSRF 対策）
    user = with_password(make_staff().user_id)
    client = make_client()
    del client.headers["X-Requested-With"]

    response = client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})

    assert response.status_code == 403


def test_family_cannot_call_staff_api(client, make_family, with_password):
    user = with_password(make_family().user_id)
    client.post("/api/auth/login", json={"login": user.email, "password": PASSWORD})

    response = client.get("/api/staff/residents")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_logout_deletes_the_session(client, redis, make_staff, with_password):
    user = with_password(make_staff().user_id)
    client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})
    session_id = client.cookies[SESSION_COOKIE]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert redis.exists(f"session:{session_id}") == 0
    assert SESSION_COOKIE not in client.cookies
    assert client.get("/api/me").status_code == 401


def test_old_cookie_does_not_work_after_logout(client, make_staff, with_password):
    # Cookie を取っておいて、ログアウトのあとに使っても入れない
    # （サーバーでセッションを消しているため）
    user = with_password(make_staff().user_id)
    client.post("/api/auth/login", json={"login": user.login_id, "password": PASSWORD})
    session_id = client.cookies[SESSION_COOKIE]
    client.post("/api/auth/logout")

    client.cookies.set(SESSION_COOKIE, session_id)

    assert client.get("/api/me").status_code == 401


def test_logout_without_login_is_ok(client):
    assert client.post("/api/auth/logout").status_code == 204
