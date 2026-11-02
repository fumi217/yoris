"""入居者の名前の出し方と、ほかの入居者の名前の照らし合わせ（#389。app/services/resident_names.py）。"""

import pytest
from sqlalchemy import select

from app.models.core import Resident
from app.services.resident_names import (
    mentions_any_name,
    name_ruby,
    other_resident_names,
    resident_display_name,
    resident_name,
)


def _resident(name_romaji: str = "Sato Fumie") -> Resident:
    return Resident(name="佐藤 文江", name_kana="さとう ふみえ", name_romaji=name_romaji)


@pytest.mark.parametrize(
    ("language", "expected"), [("ja", "佐藤 文江"), ("id", "Sato Fumie"), ("en", "Sato Fumie")]
)
def test_display_name_follows_language(language, expected):
    assert resident_display_name(_resident(), language) == expected


def test_display_name_falls_back_to_full_name_without_romaji():
    # ローマ字が空でも、名前が空にならない
    assert resident_display_name(_resident(name_romaji=""), "en") == "佐藤 文江"


@pytest.mark.parametrize("language", ["ja", "en"])
def test_name_column_matches_display_name(session, make_family, language):
    # SQL で選ぶ名前も、読み込んでから決める名前と同じ決まり
    family = make_family(name="佐藤 文江", name_romaji="Sato Fumie")
    resident = session.get_one(Resident, family.resident_id)

    selected = session.scalar(
        select(resident_name(language)).where(Resident.id == family.resident_id)
    )

    assert selected == resident_display_name(resident, language)


def test_name_column_falls_back_to_full_name_without_romaji(session, make_family):
    family = make_family(name="佐藤 文江", name_romaji="")

    selected = session.scalar(select(resident_name("id")).where(Resident.id == family.resident_id))

    assert selected == "佐藤 文江"


def test_other_resident_names_has_full_name_kana_and_romaji(session, make_family):
    # 開発の DB には seed の入居者がいるので、名前は seed と重ならない架空のものにする
    mine = make_family(name="試験 一郎", name_romaji="Shiken Ichiro")
    other = make_family(name="試験 二郎", name_romaji="Shiken Jiro")
    other_resident = session.get_one(Resident, other.resident_id)

    names = other_resident_names(session, mine.resident_id)

    assert {"試験 二郎", other_resident.name_kana, "Shiken Jiro"} <= set(names)
    # 自分の入居者の名前は入れない（家族の答えに出てよいので）
    assert "試験 一郎" not in names
    assert "Shiken Ichiro" not in names


@pytest.mark.parametrize(
    "text",
    [
        "山下 咲子さんは元気です",
        # AI が空白を取って書いても見つける
        "山下咲子さんは元気です",
        # 全角の空白
        "山下　咲子さんは元気です",
        # 大文字・小文字の違い
        "YAMASHITA SAKIKO is fine",
        "yamashita sakiko is fine",
        # 全角の英字
        "Ｙａｍａｓｈｉｔａ Ｓａｋｉｋｏ",
        # 読み
        "やました さきこさん",
    ],
)
def test_mentions_any_name_finds_variants(text):
    names = ["山下 咲子", "やました さきこ", "Yamashita Sakiko"]

    assert mentions_any_name(text, names)


def test_mentions_any_name_ignores_other_text_and_empty_names():
    assert not mentions_any_name("今日はお昼を全部召し上がりました", ["山下 咲子", ""])


@pytest.mark.parametrize(
    ("display_name", "kana", "language", "expected"),
    [
        # 日本語：漢字を含む方だけに読みを付ける
        ("佐藤 文江", "さとう ふみえ", "ja", "{佐藤|さとう} {文江|ふみえ}"),
        ("山田 トミ", "やまだ とみ", "ja", "{山田|やまだ} トミ"),
        # 姓と名の数が合わないときは、全体に付ける
        ("佐藤 文江", "さとうふみえ", "ja", "{佐藤 文江|さとうふみえ}"),
        # 読みが空なら、名前のまま
        ("佐藤 文江", "", "ja", "佐藤 文江"),
        # ふりがなの書き方の記号を含む名前は、書き方が崩れるので、読みを付けない
        ("田中{花子|はなこ}", "たなか はなこ", "ja", "田中{花子|はなこ}"),
        # ローマ字（ja 以外）は、ふりがなを付けない
        ("Sato Fumie", "さとう ふみえ", "en", "Sato Fumie"),
        ("Sato Fumie", "さとう ふみえ", "id", "Sato Fumie"),
    ],
)
def test_name_ruby(display_name, kana, language, expected):
    assert name_ruby(display_name, kana, language) == expected
