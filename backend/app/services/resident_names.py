"""入居者の名前の出し方と、ほかの入居者の名前の照らし合わせ（#389）。

spec 001 の data-model.md「入居者の名前の出し方」：表示言語が `ja` ならフルネーム（`name`）、
`id`・`en` ならローマ字（`name_romaji`）。ローマ字が空なら、フルネームを出す。
職員の画面でも家族の画面でも、名前はここで決める（画面ごとに決め方を書かない）。

ほかの入居者の名前が、AI の答え（spec 004 の research.md R-04 の 6）や、整えた日本語
（spec 007 の other_name）に入っていないかも、ここで照らす。フルネーム・読み・ローマ字を、
空白を取り、全角・半角と大文字・小文字をそろえて照らす（「佐藤文江」「SATO FUMIE」も見つける）。
"""

import re
import unicodedata
from collections.abc import Iterable

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.orm import Session

from app.furigana import add_reading
from app.models.core import Resident

_SPACES = re.compile(r"\s+")


def _romaji_or_name() -> ColumnElement[str]:
    return func.coalesce(func.nullif(Resident.name_romaji, ""), Resident.name)


def resident_name(language: str | ColumnElement[str]) -> ColumnElement[str]:
    """表示言語に合わせた入居者の名前の列（select に入れて使う）。

    language は、ログイン中の人の言語（文字）か、行ごとに違うときは言語の列（User.language）。
    """
    if isinstance(language, str):
        return Resident.name if language == "ja" else _romaji_or_name()
    return case((language == "ja", Resident.name), else_=_romaji_or_name())


def resident_display_name(resident: Resident, language: str) -> str:
    """読み込み済みの入居者から、表示言語に合わせた名前を返す（resident_name と同じ決まり）。"""
    if language == "ja":
        return resident.name
    return resident.name_romaji or resident.name


def other_resident_names(session: Session, resident_id: int) -> list[str]:
    """同じ施設の、ほかの入居者の名前（フルネーム・読み・ローマ字）。照らし合わせに使う。"""
    facility_id = select(Resident.facility_id).where(Resident.id == resident_id).scalar_subquery()
    rows = session.execute(
        select(Resident.name, Resident.name_kana, Resident.name_romaji).where(
            Resident.facility_id == facility_id, Resident.id != resident_id
        )
    )
    return [name for row in rows for name in row if name]


def _normalized(text: str) -> str:
    return _SPACES.sub("", unicodedata.normalize("NFKC", text)).casefold()


def mentions_any_name(text: str, names: Iterable[str]) -> bool:
    """text に、names のどれかが入っているか（空白・全角半角・大文字小文字の違いは無視する）。

    文の一部が一致するかで調べるので、とても短い名前（2 文字など）は、たまたま入った文字でも
    当たることがある（誤検知。seed の名前は 3 文字以上）。短い名前の入居者を入れるときは、
    最小の長さを決めることも考える。
    """
    target = _normalized(text)
    return any(key and key in target for key in map(_normalized, names))


def name_ruby(display_name: str, kana: str, language: str) -> str:
    """ふりがな付きの名前。職員の画面で、日本語のときだけ付ける（家族の画面は、画面の側で外す）。

    display_name は resident_name・resident_display_name で決めた名前、kana は name_kana。
    ja なら、姓と名に分けて、漢字を含む方だけに読みを付ける（「{佐藤|さとう} {文江|ふみえ}」）。
    ja 以外（ローマ字）や、読みが空のときは、名前のまま返す。
    """
    if language != "ja" or not kana or set("{}|") & set(display_name + kana):
        # ふりがなの書き方の記号（{ } |）を含む名前は、書き方が崩れるので、読みを付けない
        return display_name
    names, readings = display_name.split(" "), kana.split(" ")
    if len(names) != len(readings):
        return add_reading(display_name, kana)
    return " ".join(
        add_reading(name, reading) for name, reading in zip(names, readings, strict=True)
    )
