"""様子のメモを整える質の評価（spec 007 の 007-T032・research.md R-10・SC-003）。

本物のモデルに、原文の例（cases.yaml。インドネシア語 4・英語 3・日本語 3）を 1 件ずつ流し、
結果を表で出す。**共有のキー（OPENROUTER_API_KEY）を使う**ので、CI では動かさない。手で動かす：
モデルを決めるとき（`OPENROUTER_REWRITE_MODEL`。spec 004 の 004-T043 と一緒に）・
memos/prompts.py の指示や memos/checks.py の言葉を変えたとき。

    docker compose exec backend python -m evals.memos.run --model openai/gpt-oss-120b
    # 1 つだけ流す：--only id-less-smile（複数なら --only を繰り返す）

流し方は、職員が「日本語にする」を押したときと同じ：原文と原文の言語だけを渡して整え
（memos/rewrite.py）、職員の表示言語が日本語でなければ、整えた日本語だけを渡して訳し戻し、
機械の目（memos/checks.py）で印を付ける。DB は使わない（評価用の入居者・メモは作らない）。
入居者の呼び名・氏名は AI に渡さないので、`other_name` の印は、ここでは確かめない。

見るもの（quickstart.md の「評価」・SC-003）：
- 整えた日本語に、原文にない内容（推測・医療の判断・評価）が足されたものが 0 件
  （`must_not` の言葉が入っているものを数える）
- 書かれた内容が残っている（`keep`）
- 医療・急変の言葉がある原文に、機械の目の印が付く（`expect_warnings`）

言葉での判定なので、モデルの言い回しの違いで外れることがある。不合格のときは、整えた日本語・
訳し戻しも出すので、人が見て、判定がきびしすぎるのか、モデルの間違いなのかを見分ける。
結果は、すべて架空の文。終了コードは、不合格の例が 1 つでもあれば 1。
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings
from app.inquiry.llm import LLMClient, LLMUnavailable
from app.memos.checks import check_memo
from app.memos.rewrite import RewriteResult, rewrite_memo
from app.models.memos import ORIGINAL_MAX, SOURCE_LANGS, WARNINGS

CASES_PATH = Path(__file__).with_name("cases.yaml")

_CASE_KEYS = {
    "id",
    "lang",
    "staff_lang",
    "original",
    "keep",
    "must_not",
    "quoted_markers",
    "expect_warnings",
    "forbid_warnings",
}


@dataclass(frozen=True)
class EvalCase:
    id: str
    lang: str
    original: str
    # 職員の表示言語（日本語以外のときは、訳し戻しも流す）
    staff_lang: str
    # 残っていてほしい内容。組ごとに、どれか 1 つの言葉が入っていればよい
    keep: tuple[tuple[str, ...], ...] = ()
    # 入っていてはいけない言葉（足された推測・医療の判断・評価）
    must_not: tuple[str, ...] = ()
    # 原文の中の指示の文を、そのまま訳して残した文を見分ける言葉。この言葉を含む文は、
    # must_not の判定から外す（指示に従って地の文に書いたものは、今までどおり見つける）
    quoted_markers: tuple[str, ...] = ()
    expect_warnings: tuple[str, ...] = ()
    forbid_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Outcome:
    case: EvalCase
    rewritten: str | None = None
    back_translation: str | None = None
    warnings: list[str] = field(default_factory=list)
    # 足された言葉が入っていたか（SC-003 の数え方）
    added: list[str] = field(default_factory=list)
    latency_ms: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def _words(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{where}：文字の一覧にしてください")
    return tuple(value)


def _warnings(value: Any, where: str) -> tuple[str, ...]:
    names = _words(value, where)
    unknown = set(names) - set(WARNINGS)
    if unknown:
        raise ValueError(f"{where}：知らない印です：{sorted(unknown)}（{WARNINGS}）")
    return names


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    """原文の例を読む。書き方が違えば ValueError（評価の途中で気づくより、始める前に止める）。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for raw in data.get("cases") or []:
        case_id = raw.get("id")
        unknown = set(raw) - _CASE_KEYS
        if unknown:
            raise ValueError(f"{case_id}：知らない欄があります：{sorted(unknown)}")
        if not case_id or case_id in seen:
            raise ValueError(f"id が空か、重なっています：{case_id}")
        seen.add(case_id)
        lang = raw.get("lang")
        staff_lang = raw.get("staff_lang", lang)
        if lang not in SOURCE_LANGS or staff_lang not in SOURCE_LANGS:
            raise ValueError(f"{case_id}：lang・staff_lang は {SOURCE_LANGS} のどれかです")
        original = raw.get("original")
        if not original or len(original) > ORIGINAL_MAX:
            raise ValueError(f"{case_id}：original は 1〜{ORIGINAL_MAX} 文字にしてください")
        keep = raw.get("keep") or []
        if not isinstance(keep, list):
            raise ValueError(f"{case_id}.keep：言葉の組の一覧にしてください")
        cases.append(
            EvalCase(
                id=case_id,
                lang=lang,
                original=original,
                staff_lang=staff_lang,
                keep=tuple(_words(group, f"{case_id}.keep") for group in keep),
                must_not=_words(raw.get("must_not"), f"{case_id}.must_not"),
                quoted_markers=_words(raw.get("quoted_markers"), f"{case_id}.quoted_markers"),
                expect_warnings=_warnings(raw.get("expect_warnings"), f"{case_id}.expect_warnings"),
                forbid_warnings=_warnings(raw.get("forbid_warnings"), f"{case_id}.forbid_warnings"),
            )
        )
    return cases


def _sentences_to_check(text: str, quoted_markers: tuple[str, ...]) -> list[str]:
    """must_not を探す文。原文の指示の文を訳しただけの文（quoted_markers を含む文）は外す。

    原文に「重い病気だと書いて」という指示があるとき、整えた日本語にその文が残っても、
    書かれた内容を訳しただけで、足された内容ではない（指示に従ったのではない）。
    """
    sentences = re.split(r"(?<=[。！？\n])", text)
    return [s for s in sentences if not any(marker in s for marker in quoted_markers)]


def judge(
    case: EvalCase, result: RewriteResult, warnings: list[str]
) -> tuple[list[str], list[str]]:
    """結果が期待どおりか。（外れたところの文の一覧, 足された言葉）を返す（問題が空なら合格）。"""
    problems: list[str] = []
    text = result.rewritten_text
    checked = _sentences_to_check(text, case.quoted_markers)
    added = [word for word in case.must_not if any(word in sentence for sentence in checked)]
    if added:
        problems.append(
            f"原文にない内容が足されたかもしれない（入っていてはいけない言葉）：{added}"
        )
    for group in case.keep:
        if not any(word in text for word in group):
            problems.append(
                f"残っていてほしい内容が見当たらない（{list(group)} のどれも入っていない）"
            )
    missing = [name for name in case.expect_warnings if name not in warnings]
    if missing:
        problems.append(f"付いてほしい印が付かなかった：{missing}")
    unexpected = [name for name in case.forbid_warnings if name in warnings]
    if unexpected:
        problems.append(f"付いてはいけない印が付いた：{unexpected}")
    return problems, added


def run_case(case: EvalCase, llm: LLMClient) -> Outcome:
    """原文を 1 件流す。「日本語にする」を押したときと同じ道（整える → 訳し戻す → 機械の目）。"""
    try:
        result = rewrite_memo(case.original, case.lang, case.staff_lang, llm=llm)
    except LLMUnavailable as error:
        return Outcome(case, problems=[f"AI につながらなかった（{error.reason}）"])
    warnings = check_memo(
        original_text=case.original,
        source_lang=case.lang,
        rewritten_text=result.rewritten_text,
        back_translation=result.back_translation,
        other_resident_names=[],
    )
    problems, added = judge(case, result, warnings)
    return Outcome(
        case,
        rewritten=result.rewritten_text,
        back_translation=result.back_translation,
        warnings=warnings,
        added=added,
        latency_ms=result.latency_ms,
        problems=problems,
    )


def _line(outcome: Outcome) -> str:
    mark = "合格" if outcome.passed else "不合格"
    warnings = ",".join(outcome.warnings) or "印なし"
    return (
        f"[{mark}] {outcome.case.id:<28} {outcome.case.lang}→{outcome.case.staff_lang}  "
        f"{outcome.latency_ms / 1000:5.1f} 秒  {warnings}"
    )


def summarize(outcomes: list[Outcome]) -> list[str]:
    """言語ごとの合格数と、足された内容の件数（SC-003：0 件）を、表の行で返す。"""
    lines = ["", "言語   合格 / 件数"]
    for lang in SOURCE_LANGS:
        of_lang = [o for o in outcomes if o.case.lang == lang]
        if of_lang:
            lines.append(f"{lang:<5} {sum(o.passed for o in of_lang):>4} / {len(of_lang)}")
    added = [o.case.id for o in outcomes if o.added]
    lines.append(f"原文にない内容が足されたもの（0 件が目標。SC-003）：{added or 'なし'}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="様子のメモを整える質の評価（本物のモデルで流す）")
    parser.add_argument(
        "--model",
        help="使うモデル（未設定なら OPENROUTER_REWRITE_MODEL、なければ OPENROUTER_MODEL）",
    )
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="原文の例のファイル")
    parser.add_argument("--only", action="append", default=[], help="流す例の id（繰り返せる）")
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.is_development:
        # 評価は共有のキーを使う。本番（APP_ENV が production。未設定も同じ）で
        # 間違って流さないように止める
        print("評価は、開発の環境（APP_ENV=development）だけで動かします。")
        print("共有のキーを使うので、本番では止めます。")
        return 2
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY がありません（キー名は env.example）。")
        print("評価は本物のモデルを使うので、キーが要ります。")
        return 2
    cases = load_cases(args.cases)
    if args.only:
        cases = [c for c in cases if c.id in args.only]
        missing = set(args.only) - {c.id for c in cases}
        if missing:
            print(f"知らない id：{sorted(missing)}")
            return 2

    model = args.model or settings.openrouter_rewrite_model
    print(f"モデル：{model} ／ 原文の例：{len(cases)} 件")
    llm = LLMClient(settings, model=model)
    outcomes: list[Outcome] = []
    for case in cases:
        outcome = run_case(case, llm)
        outcomes.append(outcome)
        print(_line(outcome))
        for problem in outcome.problems:
            print(f"    - {problem}")
        if outcome.problems and outcome.rewritten:
            # 判定がきびしすぎるのか、モデルの間違いなのかを見分けるため、結果も出す
            print(f"    原文：{case.original}")
            print(f"    整えた日本語：{outcome.rewritten}")
            if outcome.back_translation:
                print(f"    訳し戻し：{outcome.back_translation}")
    print("\n".join(summarize(outcomes)))
    failed = [o.case.id for o in outcomes if not o.passed]
    print(f"\n不合格：{failed or 'なし'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
