"""家族の「質問する」の API のテスト（spec 004 の 004-T015。FR-001・FR-004・FR-008・FR-020）。

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
DB と Redis は tests/conftest.py の session・redis（テスト用の 15 番）を使う。
"""

import pytest
from sqlalchemy import select, update

from app.auth.deps import load_current_user
from app.clock import today_jst
from app.inquiry.llm import LLMUnavailable
from app.inquiry.prompts import INSTRUCTION_MARKER
from app.inquiry.service import _get_or_create_conversation
from app.models.disclosure import DisclosureSetting
from app.models.inquiry import InquiryConversation
from app.models.records import CareRecord
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache
from tests.fakes.llm import look_up_response, tool_call_response

URL = "/api/family/inquiry/messages"


@pytest.fixture
def world(session, redis, facility, make_staff, make_family, login_as):
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    staff = make_staff()
    family = make_family()
    lunch = CareRecord(
        resident_id=family.resident_id,
        date=today_jst(),
        item="meal",
        slot="lunch",
        value="8",
        recorded_by=staff.id,
    )
    session.add(lunch)
    session.flush()
    login_as(family.user_id)
    yield {"family": family, "staff": staff, "lunch": lunch, "facility": facility.id}
    clear_disclosure_cache(facility.id)


def _answer_with_lunch(fake_llm, lunch_id, text="今日のお昼は、ほぼ全部召し上がりました。"):
    today = today_jst().isoformat()
    fake_llm.add(
        look_up_response(today, today),
        tool_call_response("answer_family", {"text": text, "source_ids": [f"record:{lunch_id}"]}),
    )


def test_send_returns_family_and_ai_messages_with_sources(client, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)

    response = client.post(URL, json={"body": "今日のお昼は食べましたか？"})

    assert response.status_code == 201
    data = response.json()
    assert data["family"]["sender"] == "family"
    assert data["family"]["body"] == "今日のお昼は食べましたか？"
    assert data["ai"]["sender"] == "ai"
    assert data["ai"]["ai_result"] == "answered"
    assert data["ai"]["body"] == "今日のお昼は、ほぼ全部召し上がりました。"
    assert data["ai"]["sources"] == [
        {
            "kind": "record",
            "date": today_jst().isoformat(),
            "item": "meal",
            "slot": "lunch",
            "theme_code": None,
        }
    ]


def test_conversation_is_kept_newest_first(client, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)
    sent = client.post(URL, json={"body": "今日のお昼は食べましたか？"}).json()

    messages = client.get(URL).json()

    assert [m["id"] for m in messages] == [sent["ai"]["id"], sent["family"]["id"]]
    assert messages[0]["sources"][0]["item"] == "meal"
    # before で、それより前だけを読める
    assert [m["id"] for m in client.get(URL, params={"before": sent["ai"]["id"]}).json()] == [
        sent["family"]["id"]
    ]


def test_next_question_gets_previous_turn_as_history(client, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)
    client.post(URL, json={"body": "今日のお昼は食べましたか？"})
    _answer_with_lunch(fake_llm, world["lunch"].id, text="はい、ほぼ全部です。")

    client.post(URL, json={"body": "全部ですか？"})

    # 2 回目の質問の最初の呼び出しに、前の家族の発言と AI の答えが入っている（R-06）
    contents = [m.get("content") for m in fake_llm.calls[2].messages]
    assert "今日のお昼は食べましたか？" in contents
    assert "今日のお昼は、ほぼ全部召し上がりました。" in contents
    assert contents[-1] == "全部ですか？"


def test_response_has_no_instructions_or_tool_contents(client, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)

    text = client.post(URL, json={"body": "今日のお昼は食べましたか？"}).text

    # 指示の文・ツールの結果（値の意味・未記録の欄）は返さない（FR-021）
    assert INSTRUCTION_MARKER not in text
    assert fake_llm.calls[0].messages[0]["role"] == "system"
    assert "missing" not in text and "label" not in text


def test_guard_words_hand_off_with_empty_body(client, fake_llm, world):
    # 言葉の決まりに当たった発言は、AI が答えようとしても職員に渡す（R-05）
    fake_llm.add(tool_call_response("answer_family", {"text": "大丈夫です", "source_ids": []}))

    data = client.post(URL, json={"body": "薬はちゃんと飲んでいますか？"}).json()

    assert data["ai"]["ai_result"] == "handed_off"
    # 画面が辞書の決まった文を出すので、本文は空
    assert data["ai"]["body"] == ""
    assert data["ai"]["sources"] == []


def _hide(session, world, item):
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


def test_answer_hidden_later_shows_neither_body_nor_sources(client, session, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)
    client.post(URL, json={"body": "今日のお昼は食べましたか？"})

    _hide(session, world, "meal")

    # いま非開示になった記録をもとにした答えは、本文も根拠も出さない（原則 IV・PR #205）
    answer = client.get(URL).json()[0]
    assert answer["hidden"] is True
    assert answer["body"] == ""
    assert answer["sources"] == []
    assert "ほぼ全部" not in client.get(URL).text


def test_answer_with_one_hidden_source_is_hidden(client, session, fake_llm, world):
    mood = CareRecord(
        resident_id=world["family"].resident_id,
        date=today_jst(),
        item="mood",
        slot="day",
        value="smile",
        recorded_by=world["staff"].id,
    )
    session.add(mood)
    session.flush()
    today = today_jst().isoformat()
    fake_llm.add(
        look_up_response(today, today),
        tool_call_response(
            "answer_family",
            {
                "text": "お昼はほぼ全部召し上がり、笑顔が多かったです。",
                "source_ids": [f"record:{world['lunch'].id}", f"record:{mood.id}"],
            },
        ),
    )
    client.post(URL, json={"body": "今日はどうでしたか？"})

    _hide(session, world, "mood")

    # 根拠の 1 つ（機嫌）だけが非開示でも、本文に機嫌のことが入っているので出さない
    answer = client.get(URL).json()[0]
    assert answer["hidden"] is True
    assert answer["body"] == ""


def test_hidden_answer_is_not_passed_to_ai(client, session, fake_llm, world):
    _answer_with_lunch(fake_llm, world["lunch"].id)
    client.post(URL, json={"body": "今日のお昼は食べましたか？"})
    _hide(session, world, "meal")
    fake_llm.add(tool_call_response("answer_family", {"text": "はい", "source_ids": []}))
    fake_llm.add(tool_call_response("answer_family", {"text": "はい", "source_ids": []}))

    client.post(URL, json={"body": "ほかに何かありましたか？"})

    # 非開示になった中身は、次の質問のときも AI に渡さない（原則 IV）
    contents = [str(m.get("content")) for m in fake_llm.calls[2].messages]
    assert all("ほぼ全部召し上がりました" not in c for c in contents)
    assert "（この答えは、いまはお見せできません）" in contents


def test_conversation_is_not_created_twice(session, world):
    # 初めての質問が同時に 2 つ届いたとき、2 本目を作ろうとして 500 にならない（PR #205 ようこ）
    user = load_current_user(session, world["family"].user_id)

    first = _get_or_create_conversation(session, user)
    second = _get_or_create_conversation(session, user)

    assert first.id == second.id
    assert (
        len(
            session.scalars(
                select(InquiryConversation).where(
                    InquiryConversation.family_account_id == world["family"].id
                )
            ).all()
        )
        == 1
    )


def test_ai_unavailable_is_503_and_saves_nothing(client, session, fake_llm, world):
    fake_llm.add(LLMUnavailable("timeout"))

    response = client.post(URL, json={"body": "今日のお昼は食べましたか？"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_unavailable"
    assert client.get(URL).json() == []


def test_other_family_cannot_see_the_conversation(client, fake_llm, world, make_family, login_as):
    _answer_with_lunch(fake_llm, world["lunch"].id)
    client.post(URL, json={"body": "今日のお昼は食べましたか？"})

    other = make_family(name="ほかの方の父")
    login_as(other.user_id)

    assert client.get(URL).json() == []


def test_staff_cannot_use_family_inquiry(client, world, login_as):
    login_as(world["staff"].user_id)

    assert client.get(URL).status_code == 403
    assert client.post(URL, json={"body": "こんにちは"}).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"body": ""},
        {"body": "   "},
        {"body": "あ" * 501},
        {"body": "こんにちは", "resident_id": 1},
        {},
    ],
)
def test_invalid_body_is_422_and_ai_is_not_called(client, fake_llm, world, payload):
    response = client.post(URL, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_llm.calls == []
    assert client.get(URL).json() == []
