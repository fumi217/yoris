"""ログイン中の人（T010）と `GET /api/me`。本物の DB と Redis を使う（tests/conftest.py）。"""

from sqlalchemy import func, select

from app.auth.sessions import SESSION_COOKIE, SESSION_TTL_SECONDS
from app.models.core import Facility


def test_me_returns_family(client, make_family, login_as):
    family = make_family(name="テスト 花子")
    login_as(family.user_id)

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "kind": "family",
        "role": None,
        "display_name": "テスト 花子",
        "language": "ja",
    }


def test_me_returns_romaji_for_family_in_other_language(client, make_family, login_as):
    # 表示言語が id・en の家族には、入居者の名前をローマ字で返す（#389）
    family = make_family(name="佐藤 文江", name_romaji="Sato Fumie", language="en")
    login_as(family.user_id)

    assert client.get("/api/me").json()["display_name"] == "Sato Fumie"


def test_changing_language_returns_the_resident_name_in_the_new_language(
    client, make_family, login_as
):
    # 言語を変えた返事の表示名も、新しい言語の名前にする（古い言語の名前を残さない。#389）
    family = make_family(name="佐藤 文江", name_romaji="Sato Fumie")
    login_as(family.user_id)

    to_english = client.put("/api/me/language", json={"language": "en"}).json()
    back_to_japanese = client.put("/api/me/language", json={"language": "ja"}).json()

    assert (to_english["language"], to_english["display_name"]) == ("en", "Sato Fumie")
    assert (back_to_japanese["language"], back_to_japanese["display_name"]) == ("ja", "佐藤 文江")
    assert client.get("/api/me").json()["display_name"] == "佐藤 文江"


def test_me_returns_staff_with_role(client, make_staff, login_as):
    staff = make_staff(role="counselor", display_name="テスト相談員")
    login_as(staff.user_id)

    body = client.get("/api/me").json()

    assert body["kind"] == "staff"
    assert body["role"] == "counselor"
    assert body["display_name"] == "テスト相談員"


def test_staff_without_staff_row_cannot_log_in(client, session, make_staff, login_as):
    # 職員なのに staff の行がない人は、ログインさせない
    staff = make_staff()
    session.delete(staff)
    session.flush()
    login_as(staff.user_id)

    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_logged_in"


def test_unknown_session_is_not_logged_in(client):
    client.cookies.set(SESSION_COOKIE, "no-such-session")

    assert client.get("/api/me").status_code == 401


def test_session_always_has_ttl(make_staff, login_as, redis):
    # Redis のキーには必ず期限を付ける（app/redis.py の決まり）
    login_as(make_staff().user_id)

    [key] = redis.keys("session:*")
    assert 0 < redis.ttl(key) <= SESSION_TTL_SECONDS


def test_login_as_works_with_other_client(make_client, make_staff, login_as):
    dev = make_client(app_env="development")
    login_as(make_staff().user_id, dev)

    assert dev.get("/api/me").json()["kind"] == "staff"


def test_facility_is_only_one(session, facility):
    # 開発の DB（初期データの施設あり）でも CI（空の DB）でも、施設は 1 つ
    assert session.scalar(select(func.count()).select_from(Facility)) == 1
