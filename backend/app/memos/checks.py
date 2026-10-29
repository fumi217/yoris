"""様子のメモの「機械の目」（spec 007 の 007-T008・research.md R-03・FR-016）。

AI の判断を AI で確かめるのではなく、決まった決まりで注意の印（`warnings`）を付ける。
印が付いても止めはしない（人が判断する）ので、引っかけすぎても職員が困らないよう、
言葉の一覧は短く保つ。医療・緊急の言葉は spec 004 の `guard.py` の一覧を使い回し、
原文が日本語以外のときの言葉だけ、ここに足す（評価で取りこぼしが見つかったら足し引きする）。
"""

from app.inquiry.guard import KEYWORDS, _normalize
from app.models.memos import WARNINGS

# 整えた日本語の長さが、原文から見てこの範囲を出たら length_changed（R-03）
LENGTH_RATIO_MIN = 0.5
LENGTH_RATIO_MAX = 2.0

# 原文が日本語以外のときの言葉（小文字で書く）。原文は日本語の一覧に当たらないため
_MEDICAL_WORDS: dict[str, tuple[str, ...]] = {
    "ja": KEYWORDS["medical"],
    "id": (
        "obat",
        "sakit",
        "demam",
        "dokter",
        "rumah sakit",
        "tekanan darah",
        "diagnosis",
        "demensia",
        "gejala",
        "perawat",
        "infus",
    ),
    "en": (
        "medicine",
        "medication",
        "pain",
        "fever",
        "doctor",
        "hospital",
        "blood pressure",
        "diagnos",
        "dementia",
        "symptom",
        "nurse",
        "infusion",
    ),
}
_URGENT_WORDS: dict[str, tuple[str, ...]] = {
    "ja": KEYWORDS["urgent"],
    "id": ("pingsan", "jatuh", "darurat", "ambulans", "sesak napas", "patah", "tidak sadar"),
    "en": (
        "collapsed",
        "fell down",
        "fallen",
        "emergency",
        "ambulance",
        "fracture",
        "unconscious",
        "can't breathe",
        "cannot breathe",
    ),
}


def _found(words: tuple[str, ...], text: str) -> set[str]:
    normalized = _normalize(text)
    return {word for word in words if word in normalized}


def check_memo(
    *,
    original_text: str,
    source_lang: str,
    rewritten_text: str,
    back_translation: str | None,
    other_resident_names: list[str],
) -> list[str]:
    """原文・整えた日本語・訳し戻しから、注意の印を返す（WARNINGS の順）。

    - `medical_added`：整えた日本語に医療・服薬・体調の言葉があり、原文には対応する言葉がない。
      原文が日本語なら言葉ごとに、ほかの言語なら原文に医療の言葉が 1 つもないときに付ける
    - `medical_in_original`：原文に医療・服薬・体調の言葉がある
    - `length_changed`：原文の長さに対して、0.5 倍未満か 2 倍超。文字の種類が違うので、
      原文が日本語以外のときは訳し戻しの長さと比べる（訳し戻しがなければ比べない）
    - `other_name`：整えた日本語に、ほかの入居者の呼び名が入っている
    - `urgent_words`：原文に急変・事故の言葉がある
    """
    lang = source_lang if source_lang in _MEDICAL_WORDS else "ja"
    medical_in_original = _found(_MEDICAL_WORDS[lang], original_text)
    medical_in_rewritten = _found(_MEDICAL_WORDS["ja"], rewritten_text)
    if lang == "ja":
        medical_added = bool(medical_in_rewritten - medical_in_original)
    else:
        medical_added = bool(medical_in_rewritten) and not medical_in_original

    compared = rewritten_text if lang == "ja" else back_translation
    length_changed = False
    if compared is not None and original_text:
        ratio = len(compared) / len(original_text)
        length_changed = ratio < LENGTH_RATIO_MIN or ratio > LENGTH_RATIO_MAX

    found = {
        "medical_added": medical_added,
        "medical_in_original": bool(medical_in_original),
        "length_changed": length_changed,
        "other_name": any(name and name in rewritten_text for name in other_resident_names),
        "urgent_words": bool(_found(_URGENT_WORDS[lang], original_text)),
    }
    return [warning for warning in WARNINGS if found[warning]]
