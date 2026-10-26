"""テーマと定型文のすべてに、画面の文言（ja.json）があること（001-T037）。

DB にはコードだけを入れ、文言は辞書で引く（research.md R-11）。
文言がないと、家族の画面や職員の返事の画面に theme.<code> のようなキーがそのまま出る。
辞書の場所は tests/unit/test_errors.py と同じ（CI と手元の Docker のどちらでも届く）。
"""

import json
from pathlib import Path

from app.seed.themes import THEMES

JA_JSON = Path(__file__).resolve().parents[3] / "frontend" / "src" / "i18n" / "ja.json"


def _has_text(messages: dict, code: str) -> bool:
    # "template.daily_life.usual" → messages["template"]["daily_life"]["usual"]
    node: object = messages
    for key in code.split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return isinstance(node, str) and bool(node.strip())


def test_every_theme_and_template_has_a_message_in_ja_json():
    assert JA_JSON.exists(), f"{JA_JSON} がありません"
    messages = json.loads(JA_JSON.read_text(encoding="utf-8"))
    codes = [code for theme, _, templates in THEMES for code in (theme, *templates)]

    missing = [code for code in codes if not _has_text(messages, code)]

    assert missing == [], f"ja.json に文言がないコード：{missing}"
