"""OpenRouter に 1 回つながり、ツール呼び出しの応答が返ることを手で確かめる（spec 004 の T003）。

    docker compose exec backend python -m app.inquiry.check_connection

キーは .env の OPENROUTER_API_KEY から読む。キー・送った文・答えの文は出さず、
モデル名・かかった時間・呼ばれたツールの名前だけを出す。自動テストからは呼ばない。
"""

import sys
import time

from app.config import get_settings
from app.inquiry.llm import LLMClient, LLMUnavailable

# 架空の質問と、確かめ用のツール 1 つ（記録は読まない）
_MESSAGES = [
    {
        "role": "system",
        "content": (
            "あなたは確かめ用のアシスタントです。答えるときは、必ず answer ツールを使ってください。"
        ),
    },
    {"role": "user", "content": "「こんにちは」とだけ答えてください。"},
]
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "answer",
            "description": "答えの文を返す",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
]


def main() -> int:
    settings = get_settings()
    started = time.monotonic()
    try:
        response = LLMClient(settings).chat(_MESSAGES, _TOOLS)
    except LLMUnavailable as error:
        print(f"NG: つながりませんでした（{error.reason}）。model={settings.openrouter_model}")
        # OpenRouter が返したエラーの文（キーは入っていない）。原因を調べるために出す
        cause = error.__cause__
        if cause is not None:
            print(f"詳しく: {type(cause).__name__}: {str(cause)[:300]}")
        return 1
    elapsed = time.monotonic() - started
    names = [call.name for call in response.tool_calls]
    print(
        f"model={response.model or settings.openrouter_model} "
        f"finish_reason={response.finish_reason} tools={names} seconds={elapsed:.1f}"
    )
    if names != ["answer"]:
        print("NG: answer ツールが呼ばれませんでした")
        return 1
    print("OK: OpenRouter につながり、ツール呼び出しの応答が返りました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
