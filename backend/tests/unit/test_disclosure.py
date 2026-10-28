"""家族に出す共通の関数（001-T038）のテスト（001-T035）。

DB と Redis は、tests/conftest.py の session と redis（テスト用の 15 番）を使う。
DB はテストごとに取り消し、Redis はテストの前後で空にする。
"""

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.core import Facility, Resident, Staff, User
from app.models.disclosure import DisclosureSetting, Theme
from app.models.records import CareRecord
from app.seed.themes import THEMES, add_disclosure_settings, add_themes
from app.services.disclosure import (
    clear_disclosure_cache,
    get_disclosed_records,
    get_disclosed_themes,
    get_requested_themes,
    is_item_disclosed,
)

DAY = date(2026, 10, 23)


@pytest.fixture
def world(session: Session, redis, facility: Facility) -> Iterator[dict]:
    """conftest の施設（1 つだけ）に、架空の入居者・職員と、
    初期データ（テーマ・すべて見せる開示設定）を作る。
    """
    resident = Resident(
        facility_id=facility.id, name="架空 花子", display_name="テストさんの母", room="101"
    )
    user = User(kind="staff", login_id="s90011", password_hash="x")
    session.add_all([resident, user])
    session.flush()
    staff = Staff(user_id=user.id, facility_id=facility.id, display_name="職員A", role="leader")
    session.add(staff)
    session.flush()
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield {"facility": facility.id, "resident": resident.id, "staff": staff.id}
    clear_disclosure_cache(facility.id)


def _record(session, world, item, slot, value, day=DAY, deleted=False) -> CareRecord:
    record = CareRecord(
        resident_id=world["resident"],
        date=day,
        item=item,
        slot=slot,
        value=value,
        recorded_by=world["staff"],
        deleted_at=None,
    )
    session.add(record)
    session.flush()
    if deleted:
        record.deleted_at = record.recorded_at
        session.flush()
    return record


def _hide(session, world, target_type, target_code) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world["facility"],
            DisclosureSetting.target_type == target_type,
            DisclosureSetting.target_code == target_code,
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(world["facility"])


def _records(session, world, **kwargs):
    return get_disclosed_records(session, world["resident"], DAY, DAY, **kwargs)


# --- 記録 ---


def test_records_in_order_with_staff_name(session, world):
    _record(session, world, "sleep", "day", "good")
    _record(session, world, "meal", "dinner", "5")
    _record(session, world, "meal", "breakfast", "10")
    _record(session, world, "mood", "day", "smile")

    records = _records(session, world)

    # 項目（食事 → 機嫌 → 眠り）→ 区分（朝 → 夜）の順
    assert [(r.item, r.slot) for r in records] == [
        ("meal", "breakfast"),
        ("meal", "dinner"),
        ("mood", "day"),
        ("sleep", "day"),
    ]
    assert {r.recorded_by_name for r in records} == {"職員A"}


def test_hidden_item_is_not_returned(session, world):
    _record(session, world, "meal", "lunch", "8")
    _record(session, world, "sleep", "day", "poor")
    _hide(session, world, "item", "sleep")

    assert [r.item for r in _records(session, world)] == ["meal"]
    # 非開示の項目を指定しても返らない
    assert _records(session, world, items=["sleep"]) == []


def test_items_filter_and_date_range_and_cancelled(session, world):
    _record(session, world, "meal", "lunch", "8")
    _record(session, world, "mood", "day", "low")
    _record(session, world, "meal", "breakfast", "2", deleted=True)
    _record(session, world, "meal", "lunch", "10", day=DAY - timedelta(days=1))

    records = _records(session, world, items=["meal"])

    # 取り消した記録と、期間の外の記録は返らない
    assert [(r.item, r.slot, r.value) for r in records] == [("meal", "lunch", "8")]


# --- 記録項目・テーマ ---


def test_is_item_disclosed(session, world):
    assert is_item_disclosed(session, "meal") is True

    _hide(session, world, "item", "meal")

    assert is_item_disclosed(session, "meal") is False
    # 様子のメモは、初期データで「見せる」の行がある（spec 007 の 007-T025）
    assert is_item_disclosed(session, "memo") is True
    # 開示設定に行がない項目は、見せない側に倒す
    assert is_item_disclosed(session, "unknown") is False


def test_hidden_theme_is_not_returned(session, world):
    themes = get_disclosed_themes(session)
    assert [t.code for t in themes] == [code for code, _, _ in THEMES]

    _hide(session, world, "theme", "theme.supplies")

    codes = [t.code for t in get_disclosed_themes(session)]
    assert "theme.supplies" not in codes
    assert len(codes) == len(THEMES) - 1


def test_requested_themes_are_returned_even_if_hidden(session, world):
    supplies = session.query(Theme).filter_by(code="theme.supplies").one()
    _hide(session, world, "theme", "theme.supplies")

    # 送ったリクエストのテーマ名は、非開示になっても出せる（issue #111 さとこ）
    assert [t.code for t in get_requested_themes(session, [supplies.id])] == ["theme.supplies"]


# --- キャッシュ（R-12） ---


def test_cache_is_used_until_cleared(session, world):
    _record(session, world, "sleep", "day", "good")
    assert [r.item for r in _records(session, world)] == ["sleep"]  # ここでキャッシュに入る

    # キャッシュを消さずに設定だけ変えると、期限（5 分）まで古い設定のまま
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world["facility"],
            DisclosureSetting.target_code == "sleep",
        )
        .values(visible=False)
    )
    session.flush()
    assert [r.item for r in _records(session, world)] == ["sleep"]

    # 保存したらキャッシュを消す決まり。消せば、すぐ反映される（FR-012・SC-006）
    clear_disclosure_cache(world["facility"])
    assert _records(session, world) == []


def test_cache_has_ttl(session, world, redis):
    is_item_disclosed(session, "meal")

    ttl = redis.ttl(f"cache:disclosure:{world['facility']}")

    assert 0 < ttl <= 5 * 60


def test_works_without_redis(session, world, monkeypatch):
    # Redis だけが止まっても、DB から読んで家族の画面が開ける（PR #166 みさき）
    def broken_redis():
        raise ConnectionError("Redis が止まっている")

    monkeypatch.setattr("app.services.disclosure.get_redis", broken_redis)
    _record(session, world, "meal", "lunch", "8")
    _hide(session, world, "item", "sleep")

    assert [r.item for r in _records(session, world)] == ["meal"]
    assert is_item_disclosed(session, "sleep") is False
