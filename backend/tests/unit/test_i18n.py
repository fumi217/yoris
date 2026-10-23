"""メール用にふりがなを外す関数のテスト（spec 001 の T017）。"""

from app.i18n import strip_ruby


def test_strip_ruby_keeps_only_kanji():
    assert strip_ruby("{全部|ぜんぶ}（8{割|わり}）") == "全部（8割）"


def test_text_without_ruby_stays_the_same():
    assert strip_ruby("Makan siang habis") == "Makan siang habis"


def test_braces_that_are_not_ruby_stay_the_same():
    assert strip_ruby("{だけ} と {|よみ}") == "{だけ} と {|よみ}"
