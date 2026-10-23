"""ふりがなの書き方 `{漢字|かんじ}` の扱い（spec 001 の T017・research.md R-11）。

画面では frontend の `Ruby` の部品がふりがなを付ける。メールの文面ではふりがなを付けられないので、
辞書の文言から書き方を外して漢字だけにする（FR-021）。
"""

import re

# { と } の間に「漢字|読み」が 1 組。どちらも空でなく、{ } | を含まない
# （frontend の rubyText.ts と同じ）
_RUBY_PATTERN = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}")


def strip_ruby(text: str) -> str:
    """ふりがなを外して漢字だけにする。書き方に合わない { } はそのまま残す。"""
    return _RUBY_PATTERN.sub(r"\1", text)
