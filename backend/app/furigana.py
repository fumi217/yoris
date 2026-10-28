"""自由に書かれた文に、ふりがなの読みを付ける（spec 004 の FR-028a・#266）。

職員の「家族からのメッセージ」の質問の原文と AI の要約に、表示のときだけ付ける。
返すのは、辞書の文言と同じ `{漢字|かんじ}` の書き方（frontend の `Ruby` の部品が `<ruby>` にする。
spec 001 の research.md R-11）。保存している原文・要約は変えない。

読みは pykakasi が自動で付けるので、まれに誤る（画面に「ふりがなは自動で付けています」を出す）。
pykakasi を呼ぶのは、このファイルだけ。
"""

import re
from functools import lru_cache

import pykakasi

# 書き方の { } | が、利用者の文に入っていても、ふりがなの書き方と混ざらないように全角にする
_ESCAPE = str.maketrans({"{": "｛", "}": "｝", "|": "｜"})

# 漢字（ふつうの漢字・拡張 A・互換漢字・々）
_KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々]")
# 漢字の連なりと、そのほか（仮名・数字・記号）の連なりに分ける
_RUNS = re.compile(r"[㐀-䶿一-鿿豈-﫿々]+|[^㐀-䶿一-鿿豈-﫿々]+")


def _to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def _ruby(surface: str, reading: str) -> str:
    """1 つの語（`surface`）に、読み（ひらがな）を付ける。送り仮名には付けない。

    「問い合」と「といあ」なら、「{問|と}い{合|あ}」。仮名の部分が読みと合わないときは、語全体に付ける。
    """
    if not _KANJI.search(surface) or not reading or reading == surface:
        return surface
    runs = _RUNS.findall(surface)
    pattern = "".join(
        "(.+?)" if _KANJI.match(run) else re.escape(_to_hiragana(run)) for run in runs
    )
    match = re.fullmatch(pattern, reading)
    if match is None:
        return f"{{{surface}|{reading}}}"
    readings = iter(match.groups())
    return "".join(f"{{{run}|{next(readings)}}}" if _KANJI.match(run) else run for run in runs)


@lru_cache(maxsize=1)
def _converter() -> pykakasi.kakasi:
    return pykakasi.kakasi()


@lru_cache(maxsize=512)
def add_furigana(text: str) -> str:
    """文に、ふりがなを付ける。漢字がない文や、読みを付けられないときは、文字のまま返す。"""
    safe = text.translate(_ESCAPE)
    if not _KANJI.search(safe):
        return safe
    try:
        # 改行をまたぐと、pykakasi が前の語を重ねて返すことがあるので、1 行ずつ読む
        return "".join(
            part if part in ("\n", "\r") or not part else _add_to_line(part)
            for part in re.split(r"([\r\n])", safe)
        )
    except Exception:  # 読みが付かなくても、文は読めるので、止めない
        return safe


def _add_to_line(line: str) -> str:
    if not _KANJI.search(line):
        return line
    items = _converter().convert(line)
    return "".join(_ruby(item["orig"], _to_hiragana(item["hira"])) for item in items)
