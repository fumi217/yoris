"""OpenRouter のクライアントとテスト用の LLM（モック）のテスト（spec 004 の T003・T004）。

本物の AI は呼ばない。
"""

from types import SimpleNamespace

import httpx2
import openai
import pytest

from app.config import get_settings
from app.inquiry.llm import OPENROUTER_BASE_URL, LLMClient, LLMUnavailable, ToolCall
from tests.fakes.llm import FakeLLM, text_response, tool_call_response

TOOLS = [{"type": "function", "function": {"name": "answer_family", "parameters": {}}}]
MESSAGES = [{"role": "user", "content": "今日のお昼は食べましたか？"}]


class FakeSDK:
    """OpenAI SDK のクライアントの代わり。送った引数を残し、決まった応答か例外を返す。"""

    def __init__(self, result):
        self.kwargs = None
        self._result = result
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def completion(content=None, tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="openai/gpt-oss-120b")


def sdk_tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-openrouter-key")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    return get_settings()


def test_settings_defaults_and_key_not_in_repr(settings, monkeypatch):
    assert settings.openrouter_model == "openai/gpt-oss-120b"
    assert settings.inquiry_family_daily_limit == 10
    assert settings.inquiry_facility_daily_limit == 300
    assert "dummy-openrouter-key" not in repr(settings)

    # .env にキー名だけあって値が空でも、初期値になる
    monkeypatch.setenv("OPENROUTER_MODEL", "")
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "")
    assert get_settings().openrouter_model == "openai/gpt-oss-120b"
    assert get_settings().inquiry_family_daily_limit == 10


def test_chat_sends_tools_with_openrouter_rules(settings):
    sdk = FakeSDK(completion(content="はい"))

    LLMClient(settings, client=sdk).chat(MESSAGES, TOOLS)

    sent = sdk.kwargs
    assert sent["model"] == "openai/gpt-oss-120b"
    assert sent["messages"] == MESSAGES
    assert sent["tools"] == TOOLS
    assert sent["tool_choice"] == "auto"
    # 学校のキーの提供元が対応していないので送らない（送ると 404 になる。research.md R-01）
    assert "parallel_tool_calls" not in sent
    assert sent["stream"] is False
    assert sent["timeout"] == 30
    assert sent["extra_body"] == {"provider": {"require_parameters": True}}


def test_chat_without_tools_sends_no_tool_options(settings):
    # spec 007（様子のメモ）はツールなしで呼ぶ
    sdk = FakeSDK(completion(content="整えた日本語"))

    response = LLMClient(settings, client=sdk).chat(MESSAGES)

    assert "tools" not in sdk.kwargs
    assert "tool_choice" not in sdk.kwargs
    assert "parallel_tool_calls" not in sdk.kwargs
    assert response.content == "整えた日本語"


def test_sdk_client_points_to_openrouter_without_retry(settings):
    sdk = LLMClient(settings)._sdk()

    assert str(sdk.base_url).rstrip("/") == OPENROUTER_BASE_URL
    assert sdk.max_retries == 0
    assert sdk.timeout == 30


def test_chat_returns_tool_calls_and_history_message(settings):
    sdk = FakeSDK(
        completion(
            tool_calls=[
                sdk_tool_call("call_1", "answer_family", '{"text": "はい", "source_ids": []}')
            ],
            finish_reason="tool_calls",
        )
    )

    response = LLMClient(settings, client=sdk).chat(MESSAGES, TOOLS)

    assert response.tool_calls == [
        ToolCall(id="call_1", name="answer_family", arguments='{"text": "はい", "source_ids": []}')
    ]
    assert response.tool_calls[0].arguments_json() == {"text": "はい", "source_ids": []}
    assert response.finish_reason == "tool_calls"
    assert response.as_message()["tool_calls"][0]["function"]["name"] == "answer_family"


def test_broken_tool_arguments_become_empty_dict():
    assert ToolCall(id="c", name="answer_family", arguments="{壊れた").arguments_json() == {}
    assert ToolCall(id="c", name="answer_family", arguments="[1, 2]").arguments_json() == {}


REQUEST = httpx2.Request("POST", f"{OPENROUTER_BASE_URL}/chat/completions")


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (openai.APITimeoutError(request=REQUEST), "timeout"),
        (openai.APIConnectionError(request=REQUEST), "connection"),
        (
            openai.RateLimitError(
                "limit", response=httpx2.Response(429, request=REQUEST), body=None
            ),
            "status_429",
        ),
    ],
)
def test_service_errors_become_llm_unavailable(settings, error, reason):
    with pytest.raises(LLMUnavailable) as raised:
        LLMClient(settings, client=FakeSDK(error)).chat(MESSAGES, TOOLS)

    assert raised.value.reason == reason


def test_no_api_key_is_llm_unavailable(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(LLMUnavailable) as raised:
        LLMClient(get_settings()).chat(MESSAGES, TOOLS)

    assert raised.value.reason == "no_api_key"


def test_fake_llm_returns_in_order_and_records_calls():
    fake = FakeLLM(
        [tool_call_response("get_care_records", {"date_from": "2026-10-23"}), text_response("はい")]
    )
    history = list(MESSAGES)

    first = fake.chat(history, TOOLS)
    history.append(first.as_message())
    second = fake.chat(history, TOOLS)

    assert first.tool_calls[0].name == "get_care_records"
    assert second.content == "はい"
    assert len(fake.calls) == 2
    # 1 回目に呼ばれたときの履歴が、あとから足した分で変わっていない
    assert fake.calls[0].messages == MESSAGES
    assert fake.calls[1].tools == TOOLS


def test_fake_llm_raises_given_error_and_when_exhausted():
    fake = FakeLLM([LLMUnavailable("timeout")])

    with pytest.raises(LLMUnavailable):
        fake.chat(MESSAGES, TOOLS)
    with pytest.raises(AssertionError):
        fake.chat(MESSAGES, TOOLS)
