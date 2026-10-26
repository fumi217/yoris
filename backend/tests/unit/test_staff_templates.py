"""職員の返事の定型文の決まり（spec 004 の 004-T011・research.md R-14）。DB は使わない。"""

import json
from pathlib import Path

from app.models.inquiry import TEMPLATE_CATEGORIES
from app.seed.inquiry import STAFF_TEMPLATES

# フロントの辞書（backend/tests/unit/test_errors.py と同じ置き場所の決まり）
JA_JSON = Path(__file__).resolve().parents[3] / "frontend" / "src" / "i18n" / "ja.json"


def test_every_template_has_a_message_in_ja_json():
    messages = json.loads(JA_JSON.read_text(encoding="utf-8"))
    missing = []
    for _, codes in STAFF_TEMPLATES:
        for code in codes:
            value = messages
            for part in code.split("."):
                value = value.get(part, {}) if isinstance(value, dict) else {}
            if not (isinstance(value, str) and value.strip()):
                missing.append(code)

    assert missing == [], f"ja.json に文言がない定型文：{missing}"


def test_templates_cover_each_category_except_complaint():
    categories = [category for category, _ in STAFF_TEMPLATES]

    # 苦情には定型文を用意しない（電話で対応する。FR-014）
    assert "complaint" not in categories
    assert sorted(categories) == sorted(TEMPLATE_CATEGORIES)
    for category, codes in STAFF_TEMPLATES:
        assert 3 <= len(codes) <= 5, category
        assert all(code.startswith(f"staff_template.{category}.") for code in codes)
