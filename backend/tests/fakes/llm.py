"""テスト用の LLM（モック。spec 004 の FR-030・SC-011）。

本物の `LLMClient` と同じ `chat(messages, tools)` を持つ。
決まった応答を順に返して、呼ばれた中身を記録する。
自動テストでは本物の AI を呼ばず、学校配布のキーも使わない。
"""

import copy
import itertools
import json
from dataclasses import dataclass
from typing import Any

from app.inquiry.llm import LLMResponse, ToolCall

_ids = itertools.count(1)


def text_response(text: str) -> LLMResponse:
    """ツールを使わず、文だけで答える応答。"""
    return LLMResponse(content=text, finish_reason="stop", model="fake")


def tool_call_response(
    name: str, arguments: dict[str, Any], call_id: str | None = None
) -> LLMResponse:
    """ツールを 1 つ呼ぶ応答。"""
    call = ToolCall(
        id=call_id or f"call_{next(_ids)}",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False),
    )
    return LLMResponse(content=None, tool_calls=[call], finish_reason="tool_calls", model="fake")


@dataclass(frozen=True)
class Call:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None


class FakeLLM:
    """決まった応答（`LLMResponse` か、投げる例外）を順に返す。"""

    def __init__(self, responses: list[LLMResponse | Exception] | None = None):
        self._responses = list(responses or [])
        self.calls: list[Call] = []

    def add(self, *responses: LLMResponse | Exception) -> None:
        self._responses.extend(responses)

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        # 呼び出し側があとで履歴を書き足しても、そのときの中身を確かめられるように写しを残す
        self.calls.append(Call(messages=copy.deepcopy(messages), tools=copy.deepcopy(tools)))
        if not self._responses:
            raise AssertionError("FakeLLM に用意した応答より多く呼ばれた")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
