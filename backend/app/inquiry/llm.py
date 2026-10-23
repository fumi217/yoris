"""OpenRouter のクライアント（spec 004 の research.md R-01）。

OpenAI Python SDK の接続先を OpenRouter に向けて使う。AI を呼ぶところはここ 1 か所にまとめ、
`LLMClient.chat(messages, tools)` だけを持つ。
テストでは同じ形のモック（tests/fakes/llm.py）に差し替える。
spec 007（様子のメモ）も、ツールなしでこのクライアントを使う。
"""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import openai

from app.config import Settings, get_settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# 1 回の呼び出しの上限（秒）。超えたら止まったものとして扱う（spec 004 FR-026）
TIMEOUT_SECONDS = 30


class LLMUnavailable(Exception):
    """AI のサービスにつながらない・30 秒を超えた・キーがない。

    呼び出し側は 503 `ai_unavailable` にする。

    `reason` にはエラーの種類だけを入れる。キーや送った文は入れない（ログに出してよい形にする）。
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    # AI が返した引数の JSON 文字列（そのまま）。読むときは `arguments_json()` を使う
    arguments: str

    def arguments_json(self) -> dict[str, Any]:
        """引数を dict にする。JSON として読めないときは空の dict（AI の間違いで止めない）。"""
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class LLMResponse:
    """AI の応答のうち、ループで使うところだけ。"""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    model: str | None = None

    def as_message(self) -> dict[str, Any]:
        """会話の履歴に足す形。

        `tool_calls` を含む応答は、ツールの結果より先に履歴に足す（技術選定 5 章）。
        """
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in self.tool_calls
            ]
        return message


class ChatClient(Protocol):
    """`LLMClient` と、テスト用のモックが持つ形。"""

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse: ...


class LLMClient:
    """OpenRouter を呼ぶ本物のクライアント。"""

    def __init__(self, settings: Settings | None = None, client: Any | None = None):
        self._settings = settings or get_settings()
        # テストで SDK のクライアントを差し替えられるようにする（本物の通信はしない）
        self._client = client

    def _sdk(self) -> Any:
        if self._client is None:
            settings = self._settings
            if not settings.openrouter_api_key:
                raise LLMUnavailable("no_api_key")
            self._client = openai.OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=settings.openrouter_api_key,
                timeout=TIMEOUT_SECONDS,
                # SDK の自動の再試行はしない（待ち時間が延びるため）
                max_retries=0,
            )
        return self._client

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        """AI を 1 回呼ぶ。

        問い合わせ AI は `tools` を毎回付ける。様子のメモ（spec 007）は付けない。
        """
        params: dict[str, Any] = {
            "model": self._settings.openrouter_model,
            "messages": messages,
            # 最初はストリーミングなし（tool_calls が分かれて届くため。技術選定 5 章）
            "stream": False,
            "timeout": TIMEOUT_SECONDS,
            # 指定した機能（ツール呼び出し）に対応した提供元にだけ送る（技術選定 4・5 章）
            "extra_body": {"provider": {"require_parameters": True}},
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
            # parallel_tool_calls は送らない。学校のキーの提供元が対応しておらず、
            # require_parameters と一緒に送ると 404 になるため（research.md R-01）。
            # まとめて呼ばれたツールは、ループで 1 つずつ順に処理する
        try:
            completion = self._sdk().chat.completions.create(**params)
        except openai.APIConnectionError as error:
            # APITimeoutError（30 秒を超えた）もここに入る
            reason = "timeout" if isinstance(error, openai.APITimeoutError) else "connection"
            raise LLMUnavailable(reason) from error
        except openai.APIStatusError as error:
            # 回数の上限・サービス側の不具合・キーの誤りなど。家族には「いまお答えできません」を出す
            raise LLMUnavailable(f"status_{error.status_code}") from error
        return _to_response(completion)


def _to_response(completion: Any) -> LLMResponse:
    if not completion.choices:
        raise LLMUnavailable("empty_response")
    choice = completion.choices[0]
    message = choice.message
    calls = [
        ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments or "")
        for call in (message.tool_calls or [])
        if getattr(call, "function", None) is not None
    ]
    return LLMResponse(
        content=message.content,
        tool_calls=calls,
        finish_reason=choice.finish_reason,
        model=getattr(completion, "model", None),
    )
