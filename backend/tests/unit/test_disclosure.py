"""家族に出す共通の関数（001-T038）のテスト（001-T035）。

DB と Redis は、tests/conftest.py の session と redis（テスト用の 15 番）を使う。
DB はテストごとに取り消し、Redis はテストの前後で空にする。
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.core import Facility, Resident, Staff, User
from app.models.disclosure import DisclosureSetting, Theme
from app.models.memos import CareMemo
from app.models.records import CareRecord
from app.seed.themes import THEMES, add_disclosure_settings, add_themes
from app.services.disclosure import (
    clear_disclosure_cache,
    get_disclosed_memos,
    get_disclosed_records,
    get_disclosed_themes,
    get_requested_themes,
    is_feature_disclosed,
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


def test_is_feature_disclosed(session, world):
    """アルバム（feature）は、初期データで「見せる」。見せない設定にすると False。

    spec 005 の 005-T003。
    """
    assert is_feature_disclosed(session, "album") is True

    _hide(session, world, "feature", "album")

    assert is_feature_disclosed(session, "album") is False
    # 行がない機能は、見せない側に倒す
    assert is_feature_disclosed(session, "unknown") is False


def test_feature_row_does_not_mix_into_items(session, world):
    """機能の行（album）は、記録項目の判断（is_item_disclosed）に混ざらない。"""
    assert is_item_disclosed(session, "album") is False


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


# --- 様子のメモ（spec 007 の 007-T024） ---


def _memo(
    session,
    world,
    *,
    status="approved",
    text="今日は、よく笑っていました。",
    day=DAY,
    written_at=None,
    approved_at=None,
    resident_id=None,
) -> CareMemo:
    memo = CareMemo(
        resident_id=resident_id or world["resident"],
        author_staff_id=world["staff"],
        memo_date=day,
        written_at=written_at or datetime(2026, 10, 23, 3, 0, tzinfo=UTC),
        # 承認したものにだけ、承認した日時が入る
        approved_at=(approved_at or datetime(2026, 10, 23, 4, 0, tzinfo=UTC))
        if status == "approved"
        else None,
        source_lang="id",
        original_text="Hari ini beliau banyak tersenyum.",
        rewritten_text=text,
        back_translation="今日は、たくさん笑っていました。",
        warnings=["length_changed"],
        status=status,
    )
    session.add(memo)
    session.flush()
    return memo


def _memos(session, world):
    return get_disclosed_memos(session, world["resident"], DAY, DAY)


def test_approved_memo_is_returned_with_only_what_the_family_may_see(session, world):
    memo = _memo(session, world)

    [shown] = _memos(session, world)

    assert (shown.id, shown.memo_date) == (memo.id, DAY)
    assert shown.text == "今日は、よく笑っていました。"
    assert shown.author_name == "職員A"
    # 原文・訳し戻し・機械の目の印は、家族に見せない（FR-012）。そもそも持っていない
    assert set(vars(shown)) == {
        "id",
        "memo_date",
        "written_at",
        "text",
        "author_name",
        "author_occupation",
        "approved_at",
    }
    assert shown.approved_at == datetime(2026, 10, 23, 4, 0, tzinfo=UTC)
    # 職種を入れていない職員は、空（名前だけを出す）
    assert shown.author_occupation is None


def test_memo_has_the_author_occupation_like_a_reply(session, world):
    session.get(Staff, world["staff"]).occupation = "nurse"
    _memo(session, world)

    [shown] = _memos(session, world)

    assert shown.author_occupation == "nurse"


@pytest.mark.parametrize("status", ["draft", "pending", "returned", "withdrawn"])
def test_memo_that_is_not_approved_is_not_returned(session, world, status):
    # 下書き・承認待ち・戻された（公開を取り下げたものも「戻された」になる）・取り下げた
    _memo(session, world, status=status)

    assert _memos(session, world) == []


def test_memo_is_not_returned_when_the_setting_hides_it(session, world):
    _memo(session, world)
    _hide(session, world, "item", "memo")

    assert _memos(session, world) == []


def test_memo_setting_is_independent_of_the_records(session, world):
    _memo(session, world)
    _hide(session, world, "item", "meal")

    assert len(_memos(session, world)) == 1


def test_memos_are_picked_by_the_day_written_in_time_order(session, world):
    late = _memo(session, world, text="夕方", written_at=datetime(2026, 10, 23, 8, 0, tzinfo=UTC))
    early = _memo(session, world, text="朝", written_at=datetime(2026, 10, 23, 0, 0, tzinfo=UTC))
    _memo(session, world, text="前の日", day=DAY - timedelta(days=1))
    _memo(session, world, text="次の日", day=DAY + timedelta(days=1))

    memos = _memos(session, world)

    assert [m.id for m in memos] == [early.id, late.id]


def test_digest_picks_memos_by_the_time_approved_not_the_day_written(session, world):
    # 昨日書いて、今日の 19 時（日本時間。UTC の 10 時）に承認したメモは、今日のまとめに入る
    # （FR-012b）
    approved_today = _memo(
        session,
        world,
        text="昨日書いた",
        day=DAY - timedelta(days=1),
        approved_at=datetime(2026, 10, 23, 10, 0, tzinfo=UTC),
    )
    # 今日書いても、前の日に承認したものは、今日のまとめに入らない
    _memo(
        session, world, text="前の日に承認", approved_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
    )
    # 期間の終わりちょうど（approved_to）は、次のまとめに回す
    _memo(session, world, text="次のまとめ", approved_at=datetime(2026, 10, 24, 0, 0, tzinfo=UTC))

    memos = get_disclosed_memos(
        session,
        world["resident"],
        approved_from=datetime(2026, 10, 23, 0, 0, tzinfo=UTC),
        approved_to=datetime(2026, 10, 24, 0, 0, tzinfo=UTC),
    )

    assert [m.id for m in memos] == [approved_today.id]


def test_digest_range_still_hides_what_the_setting_hides_and_what_is_not_approved(session, world):
    _memo(session, world, status="pending")
    _memo(session, world, text="承認済み")
    window = {
        "approved_from": datetime(2026, 10, 23, 0, 0, tzinfo=UTC),
        "approved_to": datetime(2026, 10, 24, 0, 0, tzinfo=UTC),
    }

    assert [m.text for m in get_disclosed_memos(session, world["resident"], **window)] == [
        "承認済み"
    ]
    _hide(session, world, "item", "memo")
    assert get_disclosed_memos(session, world["resident"], **window) == []


def test_a_range_is_required(session, world):
    # 範囲なしで呼ぶと、その入居者の承認済みのメモが全部返ってしまうので、断る
    with pytest.raises(ValueError):
        get_disclosed_memos(session, world["resident"])


def test_only_the_residents_own_memos_are_returned(session, world, facility):
    other = Resident(
        facility_id=facility.id, name="架空 次郎", display_name="ほかさんの父", room="102"
    )
    session.add(other)
    session.flush()
    _memo(session, world, text="よその入居者", resident_id=other.id)
    mine = _memo(session, world)

    assert [m.id for m in _memos(session, world)] == [mine.id]
