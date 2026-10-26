"""様子のメモを整える・訳し戻す（spec 007 の 007-T004・research.md R-01・R-02）。

spec 004 の LLMClient を、ツールなしで呼ぶ。モデルは OPENROUTER_REWRITE_MODEL
（未設定なら OPENROUTER_MODEL）。整えると訳し戻すは別々に呼び、訳し戻しには
**整えた日本語だけ**を渡す（原文は渡さない。R-02）。入居者の呼び名・氏名・ほかの記録は渡さない（FR-005）。

AI につながらない・30 秒を超えたときは、LLMClient が LLMUnavailable を出すので、そのまま上に出す
（呼ぶ側で 503 `ai_unavailable` にし、原文は消さない。R-09）。
保存（care_memos・care_memo_revisions）は呼ぶ側（007-T009 の service.py）で行う。
"""

import time
from dataclasses import dataclass

from app.config import get_settings
from app.inquiry.llm import ChatClient, LLMClient, LLMUnavailable
from app.memos.prompts import build_back_translation_prompt, build_rewrite_prompt
from app.models.memos import SOURCE_LANGS


@dataclass(frozen=True)
class RewriteResult:
    # 整えた日本語
    rewritten_text: str
    # 訳し戻し（職員の表示言語が日本語なら None。FR-007）
    back_translation: str | None
    model: str | None
    # 整える＋訳し戻すにかかった時間
    latency_ms: int


def get_rewrite_client() -> ChatClient:
    """整える用のモデルで呼ぶクライアント。テストでは、関数に llm を渡して差し替える。"""
    settings = get_settings()
    return LLMClient(settings, model=settings.openrouter_rewrite_model)


def _check_lang(lang: str) -> None:
    if lang not in SOURCE_LANGS:
        raise ValueError(f"扱えない言語です：{lang}")


def _ask(llm: ChatClient, instructions: str, text: str) -> tuple[str, str | None]:
    """指示（system）と文（user）だけで 1 回呼び、返ってきた文を返す。"""
    response = llm.chat(
        [{"role": "system", "content": instructions}, {"role": "user", "content": text}]
    )
    content = (response.content or "").strip()
    if not content:
        # 空の答えは保存しない（止まったときと同じに扱い、やり直せるようにする）
        raise LLMUnavailable("empty_text")
    return content, response.model


def rewrite_memo(
    original_text: str,
    source_lang: str,
    staff_lang: str,
    *,
    llm: ChatClient | None = None,
) -> RewriteResult:
    """原文を整えた日本語にし、職員の表示言語が日本語でなければ訳し戻す（FR-003・FR-007）。"""
    _check_lang(source_lang)
    _check_lang(staff_lang)
    llm = llm or get_rewrite_client()
    started = time.monotonic()
    rewritten, model = _ask(llm, build_rewrite_prompt(source_lang), original_text)
    back_translation = None
    if staff_lang != "ja":
        back_translation, model = _ask(llm, build_back_translation_prompt(staff_lang), rewritten)
    return RewriteResult(
        rewritten_text=rewritten,
        back_translation=back_translation,
        model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
