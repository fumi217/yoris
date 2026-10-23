"""言葉による決まり（spec 004 の 004-T009・research.md R-05）。

家族の発言に決めた言葉が入っていたら、AI の判断より先に、職員に渡す種類を決める。
引っかけすぎても「職員に渡る」だけで、安全な側に倒れる
（医療の判断をしない。Constitution 原則 III）。
言葉の一覧は、評価（R-11）で取りこぼしや引っかけすぎが見つかったら足し引きする。
"""

import unicodedata

# 種類ごとの言葉。上から順に調べ、最初に当てはまった種類にする
# （緊急を先にする：「倒れて病院に」は、医療より先に緊急として渡す）。
# カタカナはひらがなにそろえてから比べるので、かなの言葉はひらがなで書けばカタカナ書きにも当たる
KEYWORDS: dict[str, tuple[str, ...]] = {
    "urgent": (
        "倒れ",
        "たおれ",
        "救急",
        # 「けが」だけだと「お出かけが」にも当たるので、後ろまで書く
        "けがを",
        "けがし",
        "怪我",
        # 「意識」だけだと「意識して見てほしい」にも当たる（PR #176 さとこ）
        "意識が",
        "意識を",
        "骨折",
        "転倒",
        "転んだ",
        "ころん",
        "ころび",
        # 「息が」だけだと「息子が」にも当たる
        "息が苦し",
        "呼吸",
        "aed",
    ),
    "medical": (
        "薬",
        "くすり",
        "服薬",
        "病気",
        "病院",
        "診断",
        "受診",
        "熱",
        "痛い",
        "痛み",
        "症状",
        "認知症",
        "血圧",
        "体調",
        "医者",
        "医師",
        "看護",
        "検査",
        "点滴",
    ),
    "complaint": (
        "ひどい",
        "苦情",
        "くれーむ",
        "許せない",
        "訴え",
        "不満",
        "納得でき",
    ),
    "money": (
        "請求",
        "料金",
        "支払",
        "引き落とし",
        "領収書",
        "書類",
        "費用",
        "お金",
        "契約",
    ),
}


# カタカナ（ァ〜ヶ）をひらがなにそろえる表
# （「ケガを」「クスリ」も、ひらがなの言葉で見つける。PR #176 さとこ）
_KATAKANA_TO_HIRAGANA = {code: code - 0x60 for code in range(ord("ァ"), ord("ヶ") + 1)}


def _normalize(text: str) -> str:
    # 全角の英数字・半角のカタカナなどをそろえ（「ＡＥＤ」「ｸﾚｰﾑ」）、
    # 英字は小文字、カタカナはひらがなにする
    return unicodedata.normalize("NFKC", text).lower().translate(_KATAKANA_TO_HIRAGANA)


def detect_category(text: str) -> str | None:
    """家族の発言から、必ず職員に渡す種類を返す。当てはまらなければ None。"""
    normalized = _normalize(text)
    for category, words in KEYWORDS.items():
        if any(word in normalized for word in words):
            return category
    return None
