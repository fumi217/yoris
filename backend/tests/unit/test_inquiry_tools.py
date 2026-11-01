"""問い合わせ AI のツールのテスト（spec 004 の 004-T013。FR-002・FR-006・FR-020・SC-005）。

DB と Redis は、tests/conftest.py の session と redis（テスト用の 15 番）を使う。
"""

import json
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.inquiry.tools import TOOL_DEFINITIONS, ToolContext, run_read_tool
from app.models.core import Facility, Resident, Staff, User
from app.models.disclosure import DisclosureSetting, ReplyTemplate, Theme
from app.models.records import CareRecord
from app.models.replies import Reply
from app.models.requests import Request
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache

TODAY = date(2026, 10, 23)


@pytest.fixture
def world(session: Session, redis, facility: Facility) -> Iterator[dict]:
    """架空の入居者・職員と、すべて見せる開示設定（test_disclosure.py と同じ準備）。"""
    resident = Resident(
        facility_id=facility.id,
        name="架空 花子",
        name_kana="かくう",
        name_romaji="Kaku",
        room="101",
    )
    user = User(kind="staff", login_id="s90021", password_hash="x")
    session.add_all([resident, user])
    session.flush()
    staff = Staff(user_id=user.id, facility_id=facility.id, display_name="職員A", role="leader")
    session.add(staff)
    session.flush()
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield {
        "facility": facility.id,
        "resident": resident.id,
        "staff": staff.id,
        "ctx": ToolContext(session=session, resident_id=resident.id, today=TODAY),
    }
    clear_disclosure_cache(facility.id)


def _record(session, world, item, slot, value, day=TODAY) -> CareRecord:
    record = CareRecord(
        resident_id=world["resident"],
        date=day,
        item=item,
        slot=slot,
        value=value,
        recorded_by=world["staff"],
    )
    session.add(record)
    session.flush()
    return record


def _hide(session, world, item) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world["facility"],
            DisclosureSetting.target_type == "item",
            DisclosureSetting.target_code == item,
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(world["facility"])


def _care_records(world, **args) -> tuple[dict, list[str]]:
    outcome = run_read_tool(world["ctx"], "get_care_records", args)
    return json.loads(outcome.content), outcome.source_ids


def test_records_have_source_id_and_label(session, world):
    lunch = _record(session, world, "meal", "lunch", "8")

    body, source_ids = _care_records(world, date_from="2026-10-23", date_to="2026-10-23")

    assert body["records"] == [
        {
            "source_id": f"record:{lunch.id}",
            "date": "2026-10-23",
            "item": "meal",
            "slot": "lunch",
            "value": "8",
            "label": "ほぼ全部（8割）",
        }
    ]
    assert source_ids == [f"record:{lunch.id}"]
    assert body["clamped"] is False


def test_missing_slots_without_snack(session, world):
    _record(session, world, "meal", "lunch", "8")

    body, _ = _care_records(world, date_from="2026-10-23", date_to="2026-10-23")

    # 朝・夕の食事と、機嫌・眠りが未記録。おやつは入れない
    assert {(m["item"], m["slot"]) for m in body["missing"]} == {
        ("meal", "breakfast"),
        ("meal", "dinner"),
        ("mood", "day"),
        ("sleep", "day"),
    }


def test_hidden_item_is_in_neither_records_nor_missing(session, world):
    _record(session, world, "sleep", "day", "poor")
    _hide(session, world, "sleep")

    body, source_ids = _care_records(world, date_from="2026-10-23", date_to="2026-10-23")

    assert all(r["item"] != "sleep" for r in body["records"])
    assert all(m["item"] != "sleep" for m in body["missing"])
    assert source_ids == []


def test_items_narrow_the_result(session, world):
    _record(session, world, "meal", "lunch", "8")
    _record(session, world, "mood", "day", "smile")

    body, _ = _care_records(world, date_from="2026-10-23", date_to="2026-10-23", items=["mood"])

    assert [r["item"] for r in body["records"]] == ["mood"]
    assert {m["item"] for m in body["missing"]} == set()


def test_period_is_clamped_to_seven_days_including_today(session, world):
    old = _record(session, world, "mood", "day", "low", day=TODAY - timedelta(days=7))
    inside = _record(session, world, "mood", "day", "normal", day=TODAY - timedelta(days=6))

    body, source_ids = _care_records(
        world, date_from="2026-10-01", date_to="2026-11-30", items=["mood"]
    )

    assert body["clamped"] is True
    assert source_ids == [f"record:{inside.id}"]
    assert f"record:{old.id}" not in source_ids
    # 未記録も、切り詰めた 7 日の中だけ（10/17 は記録があるので、10/18〜10/23）
    assert {m["date"] for m in body["missing"]} == {
        (TODAY - timedelta(days=n)).isoformat() for n in range(6)
    }


def test_invalid_date_returns_error(world):
    body, source_ids = _care_records(world, date_from="きのう", date_to="2026-10-23")

    assert body == {"error": "invalid_date"}
    assert source_ids == []


def test_staff_replies_have_japanese_theme_and_text(session, world):
    theme = session.scalars(select(Theme).where(Theme.code == "theme.enjoying")).one()
    template = session.scalars(
        select(ReplyTemplate).where(ReplyTemplate.code == "template.enjoying.yes")
    ).one()
    request = Request(resident_id=world["resident"], theme_id=theme.id, status="answered")
    session.add(request)
    session.flush()
    reply = Reply(
        request_id=request.id,
        template_ids=[template.id],
        note="体操の時間が好きです",
        replied_by=world["staff"],
        contact_book_date=TODAY,
    )
    session.add(reply)
    session.flush()

    outcome = run_read_tool(
        world["ctx"], "get_staff_replies", {"date_from": "2026-10-23", "date_to": "2026-10-23"}
    )

    assert json.loads(outcome.content) == {
        "replies": [
            {
                "source_id": f"reply:{reply.id}",
                "date": "2026-10-23",
                "theme": "楽しく過ごせているか",
                "text": "楽しそうに過ごしています",
                "note": "体操の時間が好きです",
            }
        ],
        "clamped": False,
    }
    assert outcome.source_ids == [f"reply:{reply.id}"]


def test_unknown_tool_returns_error(world):
    outcome = run_read_tool(world["ctx"], "delete_records", {})

    assert json.loads(outcome.content) == {"error": "unknown_tool"}


def test_no_tool_takes_a_resident_id():
    # 入居者はサーバーがログイン中の家族から決める。AI には選ばせない（FR-020）
    for tool in TOOL_DEFINITIONS:
        properties = tool["function"]["parameters"]["properties"]
        assert not any("resident" in name for name in properties), tool["function"]["name"]
