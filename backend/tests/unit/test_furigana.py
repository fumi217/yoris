"""自由な文へのふりがな（app/furigana.py。spec 004 の FR-028a）のテスト。"""

import pytest

from app import furigana
from app.furigana import add_furigana
from app.i18n import strip_ruby


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 漢字だけの語
        ("父が転倒しました", "{父|ちち}が{転倒|てんとう}しました"),
        # 送り仮名には付けない
        ("遅すぎます", "{遅|おそ}すぎます"),
        ("聞きました", "{聞|き}きました"),
        # 語の途中に仮名があっても、漢字ごとに付ける
        ("問い合わせ", "{問|と}い{合|あ}わせ"),
        ("召し上がり", "{召|め}し{上|あ}がり"),
        # 数字は、そのまま
        ("8割ほど", "8{割|わり}ほど"),
    ],
)
def test_readings_are_added_to_kanji_only(text, expected):
    assert add_furigana(text) == expected


def test_text_without_kanji_is_returned_as_is():
    assert add_furigana("ありがとうございます。OK 123") == "ありがとうございます。OK 123"
    assert add_furigana("") == ""


def test_line_breaks_are_kept():
    text = "父の体調\n母の様子\n\n祖父\r\n祖母"

    result = add_furigana(text)

    assert result.count("\n") == text.count("\n")
    assert strip_ruby(result) == text


@pytest.mark.parametrize(
    "text",
    [
        "{全部|ぜんぶ}と書いてあります",
        "<b>太字</b>で書いた",
        "a|b と {c} と 父",
    ],
)
def test_marks_in_the_text_never_become_furigana_marks(text):
    result = add_furigana(text)

    # 書き方の { } | は全角にして、利用者の文が、ふりがなの書き方として読まれないようにする。
    # ふりがなを外すと、もとの文（記号だけ全角）に戻る
    escaped = text.translate(furigana._ESCAPE)
    assert strip_ruby(result) == escaped
    # ふりがなを外したあとに、半角の { } | が 1 つも残らない（書かれたものは全部、全角になった）
    assert not any(mark in strip_ruby(result) for mark in "{}|")


def test_the_original_text_is_recovered_from_any_result():
    text = "父が施設内で転倒したと聞きましたが、連絡が遅すぎます。事故の経緯を説明してください。"

    assert strip_ruby(add_furigana(text)) == text


def test_text_is_returned_as_is_when_the_reader_fails(monkeypatch):
    def broken():
        raise RuntimeError("辞書が読めない")

    monkeypatch.setattr(furigana, "_converter", broken)
    furigana.add_furigana.cache_clear()

    assert furigana.add_furigana("父が転倒") == "父が転倒"
    furigana.add_furigana.cache_clear()
