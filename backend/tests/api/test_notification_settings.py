"""家族の通知設定の API（001-T064・FR-023）のテスト。

DB と Redis を使う（conftest.py の client・session・make_family・make_staff・login_as）。
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update

from app.models.core import User
from app.models.disclosure import DisclosureSetting
from app.models.notifications import NotificationSetting
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache

URL = "/api/family/notification-settings"
DEFAULT = {"notify_reply": True, "notify_items": ["meal", "mood", "sleep"], "frequency": "daily"}


@pytest.fixture
def world(session, redis, facility):
    """開示設定は、初期データ（記録項目はすべて見せる）。"""
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield facility
    clear_disclosure_cache(facility.id)


def _hide_item(session, facility, code: str) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == facility.id,
            DisclosureSetting.target_type == "item",
            DisclosureSetting.target_code == code,
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(facility.id)


def _hide_album(session, facility) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == facility.id,
            DisclosureSetting.target_type == "feature",
            DisclosureSetting.target_code == "album",
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(facility.id)


def _count(session) -> int:
    return session.scalar(select(func.count()).select_from(NotificationSetting))


def test_needs_a_family_login(client, make_staff, login_as):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json=DEFAULT).status_code == 401

    login_as(make_staff(role="leader").user_id)

    assert client.get(URL).status_code == 403
    assert client.put(URL, json=DEFAULT).status_code == 403


def test_get_returns_the_first_settings_and_the_email_without_making_a_row(
    client, session, world, make_family, login_as
):
    family = make_family()
    login_as(family.user_id)
    before = _count(session)

    body = client.get(URL).json()

    # 初めは「返事は通知・meal/mood/sleep・毎日」（FR-023）。送り先は、ログイン用と同じメール
    assert body == {
        **DEFAULT,
        "email": session.get(User, family.user_id).email,
        "available_items": ["meal", "mood", "sleep"],
        "notify_album": True,  # アルバムを見せる設定のときだけ返す（FR-017）
    }
    assert _count(session) == before  # 見ただけでは、行を作らない


def test_available_items_are_only_the_disclosed_ones(client, session, world, make_family, login_as):
    # 非開示の項目は、選択肢に出さない（FR-023・FR-010）。選んだ項目は、そのまま持つ
    login_as(make_family().user_id)
    _hide_item(session, world, "mood")

    got = client.get(URL).json()
    saved = client.put(
        URL, json={"notify_reply": True, "notify_items": ["meal", "mood"], "frequency": "daily"}
    ).json()

    assert got["available_items"] == ["meal", "sleep"]
    assert saved["available_items"] == ["meal", "sleep"]
    assert saved["notify_items"] == ["meal", "mood"]


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


def test_put_renews_updated_at(client, session, make_family, login_as):
    # 保存したら、最後に保存した日時（updated_at）が、いまの日時に新しくなる。
    # テストの中では now() が動かないので、昔の日時に書き換えてから保存して、新しくなったかを見る
    family = make_family()
    old = datetime(2000, 1, 1, tzinfo=UTC)
    session.add(NotificationSetting(family_account_id=family.id, frequency="daily"))
    session.flush()
    session.execute(
        update(NotificationSetting)
        .where(NotificationSetting.family_account_id == family.id)
        .values(updated_at=old)
    )
    login_as(family.user_id)

    response = client.put(
        URL, json={"notify_reply": True, "notify_items": ["meal"], "frequency": "weekly"}
    )

    assert response.status_code == 200
    session.expire_all()
    assert session.get(NotificationSetting, family.id).updated_at > old


def test_families_do_not_see_each_others_settings(client, make_family, login_as):
    mine, other = make_family(), make_family(name="べつの入居者")
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
        # 真偽ではない
        {
            "notify_reply": True,
            "notify_items": ["meal"],
            "frequency": "daily",
            "notify_album": "yes",
        },
    ],
)
def test_invalid_body_is_422_and_changes_nothing(client, session, make_family, login_as, body):
    login_as(make_family().user_id)
    before = _count(session)

    response = client.put(URL, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert _count(session) == before


# ---- アルバムの新しい写真（005-T028。FR-017・FR-014） ----


def _save(client, **extra):
    body = {"notify_reply": True, "notify_items": ["meal"], "frequency": "daily", **extra}
    return client.put(URL, json=body)


def test_notify_album_is_saved_and_kept_when_left_out(
    client, session, world, make_family, login_as
):
    login_as(make_family().user_id)

    assert _save(client, notify_album=False).json()["notify_album"] is False
    assert client.get(URL).json()["notify_album"] is False
    # 省略したら、いまの値のまま
    assert _save(client, frequency="weekly").json()["notify_album"] is False
    assert _save(client, notify_album=True).json()["notify_album"] is True


def test_a_hidden_album_has_no_notify_album(client, session, world, make_family, login_as):
    login_as(make_family().user_id)
    _hide_album(session, world)

    body = client.get(URL).json()

    # アルバムを見せない設定のときは、項目ごと返さない（FR-014）
    assert "notify_album" not in body
    assert body["frequency"] == "daily"


def test_a_hidden_album_ignores_notify_album_and_keeps_the_other_settings(
    client, session, world, make_family, login_as
):
    family = make_family()
    login_as(family.user_id)
    _save(client, notify_album=False)
    _hide_album(session, world)

    saved = _save(client, notify_reply=False, frequency="weekly", notify_album=True)

    assert saved.status_code == 200
    assert "notify_album" not in saved.json()
    assert (saved.json()["notify_reply"], saved.json()["frequency"]) == (False, "weekly")
    # 送られた notify_album は無視する。前の選択（false）が残る
    stored = session.scalar(
        select(NotificationSetting.notify_album).where(
            NotificationSetting.family_account_id == family.id
        )
    )
    assert stored is False
