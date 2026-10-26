"""開示設定の API（001-T039）のテスト。

tests/conftest.py の client・session・redis・facility・make_staff・make_family・login_as を使う。
"""

import pytest
from sqlalchemy import delete, select

from app.clock import today_jst
from app.models.disclosure import DisclosureSetting
from app.models.records import CareRecord
from app.seed.themes import THEMES, add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache, get_disclosed_records

URL = "/api/admin/disclosure"


@pytest.fixture
def world(session, redis, facility, make_staff, make_family, login_as):
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    director = make_staff(role="director")
    login_as(director.user_id)
    yield {"facility": facility, "director": director, "family": make_family()}
    clear_disclosure_cache(facility.id)


def _visible(data, kind, code):
    return next(row["visible"] for row in data[kind] if row["code"] == code)


def test_get_lists_items_and_themes_in_order(client, world):
    response = client.get(URL)

    assert response.status_code == 200
    data = response.json()
    assert [row["code"] for row in data["items"]] == ["meal", "mood", "sleep"]
    assert [row["code"] for row in data["themes"]] == [code for code, _, _ in THEMES]
    # 初期データはすべて見せる（FR-009）
    assert all(row["visible"] for row in [*data["items"], *data["themes"]])


def test_missing_setting_is_hidden(client, session, world):
    # 設定の行がないものは「見せない」（家族に出す共通の関数と同じ）
    session.execute(
        delete(DisclosureSetting).where(
            DisclosureSetting.facility_id == world["facility"].id,
            DisclosureSetting.target_code == "sleep",
        )
    )

    assert _visible(client.get(URL).json(), "items", "sleep") is False


def test_put_changes_only_what_was_sent(client, session, world):
    response = client.put(URL, json={"items": {"mood": False}, "themes": {"theme.meals": False}})

    assert response.status_code == 200
    data = response.json()
    assert _visible(data, "items", "mood") is False
    assert _visible(data, "themes", "theme.meals") is False
    # 送らなかったものはそのまま
    assert _visible(data, "items", "meal") is True
    setting = session.scalars(
        select(DisclosureSetting).where(
            DisclosureSetting.facility_id == world["facility"].id,
            DisclosureSetting.target_code == "mood",
        )
    ).one()
    assert setting.updated_by == world["director"].id


def test_saving_is_seen_by_family_at_once(client, session, world):
    # 家族の連絡帳を一度開いて、開示設定がキャッシュに入った状態
    resident = world["family"].resident_id
    session.add(
        CareRecord(
            resident_id=resident,
            date=today_jst(),
            item="meal",
            slot="lunch",
            value="8",
            recorded_by=world["director"].id,
        )
    )
    session.flush()
    assert len(get_disclosed_records(session, resident, today_jst(), today_jst())) == 1

    assert client.put(URL, json={"items": {"meal": False}}).status_code == 200

    # 保存したらキャッシュが消えるので、次に開いたときにはもう出ない（FR-012）
    assert get_disclosed_records(session, resident, today_jst(), today_jst()) == []


def test_missing_row_is_created_on_save(client, session, world):
    session.execute(
        delete(DisclosureSetting).where(DisclosureSetting.facility_id == world["facility"].id)
    )

    data = client.put(URL, json={"items": {"meal": True}}).json()

    assert _visible(data, "items", "meal") is True
    assert _visible(data, "items", "mood") is False


@pytest.mark.parametrize(
    "body",
    [
        {"items": {"memo": True}},  # 知らない項目
        {"themes": {"theme.unknown": True}},  # 知らないテーマ
        {"items": {"meal": "yes"}},  # 真偽でない
        {"facility_id": 1},  # 余分な項目
    ],
)
def test_invalid_body_is_422(client, world, body):
    assert client.put(URL, json=body).status_code == 422


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_only_counselor_and_director(client, world, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.get(URL).status_code == 403
    assert client.put(URL, json={"items": {"meal": False}}).status_code == 403


def test_counselor_can_change(client, world, make_staff, login_as):
    login_as(make_staff(role="counselor").user_id)

    assert client.put(URL, json={"items": {"sleep": False}}).status_code == 200


def test_family_cannot_open(client, world, login_as):
    login_as(world["family"].user_id)

    assert client.get(URL).status_code == 403


# --- 変更履歴（001-T041・FR-011） ---


def test_changes_are_kept_in_history(client, session, world):
    client.put(URL, json={"items": {"mood": False}, "themes": {"theme.meals": False}})
    client.put(URL, json={"items": {"mood": True}})

    rows = client.get(f"{URL}/history").json()

    # 新しい順（同じ時刻なら、あとで変えたものが先）。いつ・誰が・何を（前と後）
    changes = [
        (r["target_type"], r["target_code"], r["old_visible"], r["new_visible"]) for r in rows
    ]
    assert changes == [
        ("item", "mood", False, True),
        ("theme", "theme.meals", True, False),
        ("item", "mood", True, False),
    ]
    assert rows[0]["changed_by_name"] == "テスト職員"
    assert rows[0]["changed_at"]


def test_unchanged_values_are_not_in_history(client, session, world):
    # 見せるものを「見せる」にしても、変わっていないので残さない
    client.put(URL, json={"items": {"meal": True}})

    assert client.get(f"{URL}/history").json() == []


def test_missing_row_history_starts_from_hidden(client, session, world):
    session.execute(
        delete(DisclosureSetting).where(
            DisclosureSetting.facility_id == world["facility"].id,
            DisclosureSetting.target_code == "sleep",
        )
    )

    client.put(URL, json={"items": {"sleep": True}})

    [row] = client.get(f"{URL}/history").json()
    # 行がないものは「見せない」として扱うので、前の値は「見せない」
    assert (row["target_code"], row["old_visible"], row["new_visible"]) == ("sleep", False, True)


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_history_only_counselor_and_director(client, world, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.get(f"{URL}/history").status_code == 403


# --- 関係しそうな組み合わせの注意書き（001-T042・FR-009） ---


def test_related_pairs_are_returned(client, world):
    data = client.get(URL).json()

    assert {(p["item"], p["theme"]) for p in data["related"]} == {
        ("meal", "theme.meals"),
        ("mood", "theme.enjoying"),
        ("mood", "theme.daily_life"),
        ("sleep", "theme.daily_life"),
    }
    # すべて見せる初期値では、当てはまる組はない
    assert data["warnings"] == []


def test_warning_when_item_hidden_but_theme_visible(client, world):
    # 機嫌・様子を見せないのに、「楽しく過ごせているか」「普段の様子」は見せるまま（FR-009 の例）
    data = client.put(URL, json={"items": {"mood": False}}).json()

    assert {(p["item"], p["theme"]) for p in data["warnings"]} == {
        ("mood", "theme.enjoying"),
        ("mood", "theme.daily_life"),
    }

    # テーマも見せないにすれば、その組の注意書きは消える（止めはしないので、どちらでも保存できる）
    data = client.put(URL, json={"themes": {"theme.enjoying": False}}).json()
    assert [(p["item"], p["theme"]) for p in data["warnings"]] == [("mood", "theme.daily_life")]
