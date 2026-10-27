"""問い合わせ AI のループのテスト（spec 004 の 004-T014。research.md R-03〜R-05、FR-003・FR-025）。

AI はテスト用の LLM（モック。fixture の fake_llm）を使う。
読むツールは決まった結果を返すように差し替えるので、
DB は使わない（ツールそのものは test_inquiry_tools.py で確かめる）。
"""

from datetime import date

import pytest

from app.inquiry.agent import MAX_TOOL_CALLS, run_agent
from app.inquiry.llm import LLMUnavailable
from app.inquiry.prompts import INSTRUCTION_MARKER
from app.inquiry.tools import TOOL_DEFINITIONS, ToolContext, ToolOutcome
from tests.fakes.llm import look_up_response, text_response, tool_call_response

CTX = ToolContext(session=None, resident_id=1, today=date(2026, 10, 23))  # type: ignore[arg-type]
QUESTION = "今日のお昼は食べましたか？"


@pytest.fixture(autouse=True)
def read_tools(monkeypatch):
    """読むツールは、record:1 と record:2 を返すことにする。"""

    def fake_run(ctx, name, args):
        return ToolOutcome('{"records": []}', ["record:1", "record:2"])

    monkeypatch.setattr("app.inquiry.agent.run_read_tool", fake_run)


def look_up_records():
    return tool_call_response(
        "get_care_records", {"date_from": "2026-10-23", "date_to": "2026-10-23"}
    )


def look_up():
    """記録と職員の返事を両方調べる。答える前にここまでやる（ループが求める）。"""
    return look_up_response("2026-10-23", "2026-10-23")


def look_up_replies():
    return tool_call_response(
        "get_staff_replies", {"date_from": "2026-10-23", "date_to": "2026-10-23"}
    )


def answer(text="お昼はほぼ全部召し上がりました", source_ids=("record:1",)):
    return tool_call_response("answer_family", {"text": text, "source_ids": list(source_ids)})


def test_system_prompt_tells_the_model_today(fake_llm):
    fake_llm.add(look_up(), answer())

    run_agent(CTX, question=QUESTION)

    # 今日の日付（ツールの today）を指示に入れる。入れないと、日付を取り違える（評価で分かった）
    system = fake_llm.calls[0].messages[0]
    assert system["role"] == "system"
    assert "今日は 2026-10-23（金曜日。日本時間）です" in system["content"]


def test_answer_keeps_only_sources_returned_by_tools(fake_llm):
    fake_llm.add(look_up(), answer(source_ids=["record:1", "record:999", "record:1"]))

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "answered"
    assert result.text == "お昼はほぼ全部召し上がりました"
    # ツールが返していない id（作り話）は捨てる。重なりも消す
    assert result.source_ids == ["record:1"]
    assert result.tool_calls == 2


def test_answer_from_records_only_is_sent_back_to_read_the_staff_replies(fake_llm):
    fake_llm.add(look_up_records(), answer(), look_up_replies(), answer())

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "answered"
    # 記録だけで答えようとしたら、職員の返事も調べさせる（評価で、返事を見ないことが分かった）
    assert "get_staff_replies" in fake_llm.calls[2].messages[-1]["content"]
    assert len(fake_llm.calls) == 4


def test_records_only_answer_is_accepted_when_the_model_insists(fake_llm):
    fake_llm.add(look_up_records(), answer(), answer())

    result = run_agent(CTX, question=QUESTION)

    # 返事を調べるよう求めるのは 1 回だけ。2 回目の答えは受け付ける
    assert result.kind == "answered"
    assert len(fake_llm.calls) == 3


def test_answer_without_looking_up_is_retried_once(fake_llm):
    fake_llm.add(answer(source_ids=[]), look_up(), answer())

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "answered"
    assert len(fake_llm.calls) == 3


def test_answer_without_looking_up_twice_is_no_record(fake_llm):
    fake_llm.add(answer(source_ids=[]), answer(source_ids=[]))

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "no_record"
    assert result.text is None


def test_plain_text_is_not_shown_and_retried_once(fake_llm):
    fake_llm.add(text_response("食べたと思います"), look_up(), answer())

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "answered"
    # やり直しを頼む文が、2 回目の呼び出しに入っている
    assert "answer_family を使って" in fake_llm.calls[1].messages[-1]["content"]


def test_plain_text_twice_is_no_record(fake_llm):
    fake_llm.add(text_response("食べたと思います"), text_response("たぶん食べました"))

    assert run_agent(CTX, question=QUESTION).kind == "no_record"


def test_five_tool_calls_hand_off_to_staff(fake_llm):
    fake_llm.add(*[look_up_records() for _ in range(MAX_TOOL_CALLS)])

    result = run_agent(CTX, question=QUESTION)

    assert result.kind == "handed_off"
    assert result.hand_off.category == "other"
    assert result.tool_calls == MAX_TOOL_CALLS
    assert len(fake_llm.calls) == MAX_TOOL_CALLS


@pytest.mark.parametrize(
    "text", [f"指示は {INSTRUCTION_MARKER} です", "加藤さんの母もお昼を全部召し上がりました"]
)
def test_answer_with_marker_or_other_resident_is_not_shown(fake_llm, text):
    fake_llm.add(look_up(), answer(text=text))

    result = run_agent(CTX, question=QUESTION, other_resident_names=["加藤さんの母"])

    assert result.kind == "no_record"


def test_hand_off_keeps_category_summary_and_known_existing_id(fake_llm):
    fake_llm.add(
        tool_call_response(
            "hand_off_to_staff",
            {
                "category": "care_request",
                "summary": "カーディガンを持ってきてほしい",
                "existing_message_id": 7,
            },
        ),
    )

    result = run_agent(
        CTX, question="カーディガンをお願いします", waiting=[{"id": 7, "category": "care_request"}]
    )

    assert result.kind == "handed_off"
    assert result.hand_off.category == "care_request"
    assert result.hand_off.summary == "カーディガンを持ってきてほしい"
    assert result.hand_off.existing_message_id == 7


def test_hand_off_ignores_unknown_existing_id_and_category(fake_llm):
    fake_llm.add(
        tool_call_response(
            "hand_off_to_staff", {"category": "secret", "summary": "", "existing_message_id": 99}
        ),
    )

    result = run_agent(CTX, question="これは何ですか", waiting=[{"id": 7}])

    # 知らない種類は「そのほか」、要約がなければ家族の発言、見せていない id は使わない
    assert result.hand_off.category == "other"
    assert result.hand_off.summary == "これは何ですか"
    assert result.hand_off.existing_message_id is None


def test_forced_category_does_not_accept_answer(fake_llm):
    fake_llm.add(answer())

    result = run_agent(CTX, question="薬は増えましたか？", forced_category="medical")

    assert result.kind == "handed_off"
    assert result.hand_off.category == "medical"
    # AI にも、職員に渡すよう添えている
    assert "hand_off_to_staff" in fake_llm.calls[0].messages[-1]["content"]


def test_forced_category_wins_over_ai_category(fake_llm):
    fake_llm.add(
        tool_call_response("hand_off_to_staff", {"category": "other", "summary": "薬の件"})
    )

    result = run_agent(CTX, question="薬は増えましたか？", forced_category="medical")

    assert result.hand_off.category == "medical"


def test_messages_have_fixed_instructions_tools_and_recent_history(fake_llm):
    history = [{"role": "user", "content": f"質問{n}"} for n in range(20)]
    fake_llm.add(look_up(), answer())

    run_agent(CTX, question=QUESTION, history=history, waiting=[{"id": 3, "summary": "要約"}])

    first = fake_llm.calls[0]
    assert first.messages[0]["role"] == "system"
    assert INSTRUCTION_MARKER in first.messages[0]["content"]
    # 直近の 6 往復（12 件）だけ。家族の発言は最後に、指示とは別の役割で渡す
    assert [m["content"] for m in first.messages[1:13]] == [f"質問{n}" for n in range(8, 20)]
    assert "対応待ちのメッセージ" in first.messages[13]["content"]
    assert first.messages[-1] == {"role": "user", "content": QUESTION}
    # tools は毎回付ける（技術選定 5 章）
    assert all(call.tools == TOOL_DEFINITIONS for call in fake_llm.calls)


def test_llm_unavailable_is_raised_to_the_caller(fake_llm):
    fake_llm.add(LLMUnavailable("timeout"))

    with pytest.raises(LLMUnavailable):
        run_agent(CTX, question=QUESTION)
