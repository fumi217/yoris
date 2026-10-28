"""職員のアカウントを作る API（001-T088）のテスト。

tests/conftest.py の client・session・redis・facility・make_staff・make_family・login_as を使う。
"""

import logging
import re
from typing import get_args

import pytest
from sqlalchemy import select

from app.api.admin.staff import Occupation, Role
from app.auth import passwords
from app.auth.passwords import verify_password
from app.models.core import STAFF_OCCUPATIONS, STAFF_ROLES, Staff, User

URL = "/api/admin/staff"


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passwords, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def counselor(make_staff, login_as):
    staff = make_staff(role="counselor", display_name="相談員")
    login_as(staff.user_id)
    return staff


def _saved(session, response):
    staff = session.get(Staff, response.json()["id"])
    return staff, session.get(User, staff.user_id)


def test_counselor_creates_a_staff_with_login_id_and_initial_password(
    client, session, facility, counselor
):
    response = client.post(
        URL, json={"display_name": "新人", "role": "care_worker", "occupation": "nurse"}
    )

    assert response.status_code == 201
    data = response.json()
    assert re.fullmatch(r"s\d{5}", data["login_id"])
    assert len(data["initial_password"]) == 8
    assert data["display_name"] == "新人"
    assert data["role"] == "care_worker"
    assert data["occupation"] == "nurse"
    staff, user = _saved(session, response)
    # 施設は、作った人の施設。ログイン用の情報は、職員用（家族用の項目は空）
    assert staff.facility_id == facility.id
    assert (user.kind, user.login_id, user.email, user.language) == (
        "staff",
        data["login_id"],
        None,
        "ja",
    )
    # DB にはハッシュだけを入れ、返したパスワードでログインできる
    assert user.password_hash != data["initial_password"]
    assert verify_password(data["initial_password"], user.password_hash)


def test_response_is_not_cached(client, counselor):
    response = client.post(URL, json={"display_name": "新人", "role": "leader"})

    assert response.headers["Cache-Control"] == "no-store"


def test_new_staff_can_log_in_with_the_initial_password(client, make_client, counselor):
    created = client.post(URL, json={"display_name": "新人", "role": "clerk"}).json()

    other = make_client()
    response = other.post(
        "/api/auth/login",
        json={"login": created["login_id"], "password": created["initial_password"]},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "clerk"
    assert response.json()["display_name"] == "新人"


def test_director_can_create_any_role_including_a_director(
    client, session, make_staff, login_as, counselor
):
    login_as(make_staff(role="director").user_id)

    for role in STAFF_ROLES:
        response = client.post(URL, json={"display_name": "新人", "role": role})
        assert response.status_code == 201, role
        assert _saved(session, response)[0].role == role


def test_counselor_can_create_a_director(client, counselor):
    # 追加の権限は、生活相談員・施設長で同じ（contracts）。役割ごとの制限はしない
    response = client.post(URL, json={"display_name": "新しい施設長", "role": "director"})

    assert response.status_code == 201


def test_occupation_is_optional_and_empty_means_none(client, session, counselor):
    omitted = client.post(URL, json={"display_name": "A", "role": "care_worker"})
    explicit = client.post(
        URL, json={"display_name": "B", "role": "care_worker", "occupation": None}
    )

    assert omitted.status_code == explicit.status_code == 201
    assert omitted.json()["occupation"] is None
    assert _saved(session, explicit)[0].occupation is None


def test_every_occupation_code_is_accepted(client, counselor):
    for code in STAFF_OCCUPATIONS:
        response = client.post(
            URL, json={"display_name": "新人", "role": "care_worker", "occupation": code}
        )
        assert response.status_code == 201, code


def test_display_name_is_trimmed_and_may_repeat(client, session, make_staff, counselor):
    make_staff(display_name="田中")

    response = client.post(URL, json={"display_name": "  田中  ", "role": "care_worker"})

    assert response.status_code == 201
    assert _saved(session, response)[0].display_name == "田中"


def test_each_account_gets_a_different_login_id_and_password(client, counselor):
    first = client.post(URL, json={"display_name": "A", "role": "care_worker"}).json()
    second = client.post(URL, json={"display_name": "B", "role": "care_worker"}).json()

    assert first["login_id"] != second["login_id"]
    assert first["initial_password"] != second["initial_password"]


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": "", "role": "care_worker"},
        {"display_name": "   ", "role": "care_worker"},
        {"display_name": "あ" * 21, "role": "care_worker"},
        {"display_name": "新人", "role": "nurse"},  # 職種のコードは、役割には使えない
        {"display_name": "新人", "role": "care_worker", "occupation": "doctor"},
        {"display_name": "新人"},
        {"display_name": "新人", "role": "care_worker", "facility_id": 1},
        {"display_name": 123, "role": "care_worker"},
    ],
)
def test_invalid_body_is_422_and_nothing_is_saved(client, session, counselor, body):
    before = session.scalar(select(User.id).order_by(User.id.desc()).limit(1))

    response = client.post(URL, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert session.scalar(select(User.id).order_by(User.id.desc()).limit(1)) == before


def test_twenty_characters_is_ok(client, counselor):
    assert (
        client.post(URL, json={"display_name": "あ" * 20, "role": "care_worker"}).status_code == 201
    )


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_other_staff_roles_are_forbidden(client, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    response = client.post(URL, json={"display_name": "新人", "role": "care_worker"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_family_is_forbidden(client, make_family, login_as):
    login_as(make_family().user_id)

    assert client.post(URL, json={"display_name": "新人", "role": "care_worker"}).status_code == 403


def test_not_logged_in_is_401(client):
    assert client.post(URL, json={"display_name": "新人", "role": "care_worker"}).status_code == 401


def test_initial_password_is_not_written_to_the_log(client, counselor, caplog):
    with caplog.at_level(logging.DEBUG):
        password = client.post(URL, json={"display_name": "新人", "role": "care_worker"}).json()[
            "initial_password"
        ]

    assert password not in caplog.text


def test_role_and_occupation_choices_match_the_models():
    # 足すときは、models/core.py と api/admin/staff.py の両方に足す
    assert get_args(Role) == STAFF_ROLES
    assert get_args(Occupation) == STAFF_OCCUPATIONS


def test_creation_is_logged_with_ids_but_not_name_or_password(client, counselor, caplog):
    with caplog.at_level(logging.INFO):
        body = client.post(URL, json={"display_name": "新人", "role": "care_worker"}).json()

    assert body["login_id"] in caplog.text
    assert "新人" not in caplog.text
    assert body["initial_password"] not in caplog.text
