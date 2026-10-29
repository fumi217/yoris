"""表示言語の切り替え PUT /api/me/language（spec 001 の T084・FR-021）。"""

import pytest

from app.models.core import User


@pytest.mark.parametrize("language", ["ja", "id", "en"])
def test_staff_changes_language(client, session, make_staff, login_as, language):
    staff = make_staff(language="ja")
    login_as(staff.user_id)

    response = client.put("/api/me/language", json={"language": language})

    assert response.status_code == 200
    # GET /api/me と同じ中身を返す
    assert response.json()["language"] == language
    assert client.get("/api/me").json()["language"] == language
    assert session.get(User, staff.user_id).language == language


def test_family_changes_language(client, make_family, login_as):
    family = make_family()
    login_as(family.user_id)

    response = client.put("/api/me/language", json={"language": "id"})

    assert response.status_code == 200
    assert response.json()["kind"] == "family"
    assert response.json()["language"] == "id"


def test_changes_only_own_language(client, session, make_staff, login_as):
    me = make_staff(language="ja")
    other = make_staff(language="ja")
    login_as(me.user_id)

    client.put("/api/me/language", json={"language": "en"})

    assert session.get(User, other.user_id).language == "ja"


@pytest.mark.parametrize("language", ["fr", "", "JA"])
def test_unknown_language_is_rejected(client, session, make_staff, login_as, language):
    staff = make_staff(language="ja")
    login_as(staff.user_id)

    response = client.put("/api/me/language", json={"language": language})

    assert response.status_code == 422
    assert session.get(User, staff.user_id).language == "ja"


def test_requires_login(client):
    response = client.put("/api/me/language", json={"language": "en"})

    assert response.status_code == 401
