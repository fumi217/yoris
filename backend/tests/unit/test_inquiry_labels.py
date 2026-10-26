"""AI が読むテーマ・定型文の日本語の表に、足し忘れがないこと。

spec 004 の 004-T016。DB は使わない。
"""

from app.inquiry.labels import TEMPLATE_LABELS, THEME_LABELS
from app.seed.themes import THEMES


def test_labels_cover_every_theme_and_template_in_seed():
    theme_codes = {code for code, _, _ in THEMES}
    template_codes = {template for _, _, templates in THEMES for template in templates}

    # 初期データにテーマや定型文が増えたら、ここの表にも足す（ないと AI にコードのまま渡る）
    assert set(THEME_LABELS) == theme_codes
    assert set(TEMPLATE_LABELS) == template_codes
    assert all(label.strip() for label in [*THEME_LABELS.values(), *TEMPLATE_LABELS.values()])
