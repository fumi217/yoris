"""家族の通知設定の API（001-T064・FR-023）のテスト。

DB と Redis を使う（conftest.py の client・session・make_family・make_staff・login_as）。
"""

import pytest
from sqlalchemy import func, select

from app.models.core import User
from app.models.notifications import NotificationSetting

URL = "/api/family/notification-settings"
DEFAULT = {"notify_reply": True, "notify_items": ["meal", "mood", "sleep"], "frequency": "daily"}


def _count(session) -> int:
    return session.scalar(select(func.count()).select_from(NotificationSetting))


def test_needs_a_family_login(client, make_staff, login_as):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json=DEFAULT).status_code == 401

    login_as(make_staff(role="leader").user_id)

    assert client.get(URL).status_code == 403
    assert client.put(URL, json=DEFAULT).status_code == 403


def test_get_returns_the_first_settings_and_the_email_without_making_a_row(
    client, session, make_family, login_as
):
    family = make_family()
    login_as(family.user_id)
    before = _count(session)

    body = client.get(URL).json()

    # 初めは「返事は通知・meal/mood/sleep・毎日」（FR-023）。送り先は、ログイン用と同じメール
    assert body == {**DEFAULT, "email": session.get(User, family.user_id).email}
    assert _count(session) == before  # 見ただけでは、行を作らない


def test_put_saves_and_get_returns_the_same(client, session, make_family, login_as):
    family = make_family()
    login_as(family.user_id)
    change = {"notify_reply": False, "notify_items": ["meal"], "frequency": "weekly"}

    saved = client.put(URL, json=change)

    assert saved.status_code == 200
    assert saved.json()["email"] == session.get(User, family.user_id).email
    assert {key: saved.json()[key] for key in change} == change
    assert {key: client.get(URL).json()[key] for key in change} == change


def test_put_again_changes_the_same_row(client, session, make_family, login_as):
    family = make_family()
    login_as(family.user_id)
    before = _count(session)

    client.put(URL, json={"notify_reply": True, "notify_items": ["mood"], "frequency": "daily"})
    client.put(URL, json={"notify_reply": True, "notify_items": ["sleep"], "frequency": "none"})

    assert _count(session) == before + 1  # 家族に 1 行
    body = client.get(URL).json()
    assert (body["notify_items"], body["frequency"]) == (["sleep"], "none")


def test_put_updates_a_row_that_was_just_made_by_another_request(
    client, session, make_family, login_as
):
    # 同じ家族から、ほぼ同時に初めて保存されたとき、先に作られた行がある（後の保存は更新する）
    family = make_family()
    session.add(NotificationSetting(family_account_id=family.id, frequency="daily"))
    session.flush()
    login_as(family.user_id)
    before = _count(session)
    change = {"notify_reply": False, "notify_items": ["mood"], "frequency": "weekly"}

    response = client.put(URL, json=change)

    assert response.status_code == 200
    assert {key: response.json()[key] for key in change} == change
    assert _count(session) == before  # 行は増えない（1 家族に 1 行）


def test_families_do_not_see_each_others_settings(client, make_family, login_as):
    mine, other = make_family(), make_family(display_name="べつの入居者")
    login_as(mine.user_id)
    client.put(URL, json={"notify_reply": False, "notify_items": [], "frequency": "none"})

    login_as(other.user_id)

    body = client.get(URL).json()
    assert {key: body[key] for key in DEFAULT} == DEFAULT  # べつの家族は、初めの設定のまま


def test_items_are_deduplicated_in_the_fixed_order_and_may_be_empty(client, make_family, login_as):
    login_as(make_family().user_id)

    messy = client.put(
        URL,
        json={
            "notify_reply": True,
            "notify_items": ["sleep", "meal", "sleep"],
            "frequency": "daily",
        },
    )
    empty = client.put(URL, json={"notify_reply": True, "notify_items": [], "frequency": "daily"})

    assert messy.json()["notify_items"] == ["meal", "sleep"]
    assert (empty.status_code, empty.json()["notify_items"]) == (200, [])


@pytest.mark.parametrize(
    "body",
    [
        {"notify_reply": True, "notify_items": ["meal"], "frequency": "hourly"},  # 知らない頻度
        {"notify_reply": True, "notify_items": ["memo"], "frequency": "daily"},  # 記録項目ではない
        {"notify_reply": True, "notify_items": ["unknown"], "frequency": "daily"},
        {"notify_reply": "yes", "notify_items": ["meal"], "frequency": "daily"},  # 真偽ではない
        {"notify_reply": True, "notify_items": "meal", "frequency": "daily"},  # 配列ではない
        {"notify_reply": True, "notify_items": ["meal"]},  # 頻度がない
    ],
)
def test_invalid_body_is_422_and_changes_nothing(client, session, make_family, login_as, body):
    login_as(make_family().user_id)
    before = _count(session)

    response = client.put(URL, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert _count(session) == before
