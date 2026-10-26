"""「知りたいこと」のテーマと定型文、開示設定の初期データ（spec 001 の 001-T037）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。施設を入れたあとに呼ぶこと。
何度流しても同じになるように、すでにあるものは足さない。
DB にはコードだけを入れ、文言は辞書（frontend/src/i18n/ja.json の theme.*・template.*）で引く。
右のコメントは、辞書の日本語（ふりがなを外したもの）。
文言を変えるときは ja.json を直し、ここも合わせる。
コードを足したら ja.json にも足す（tests/unit/test_theme_texts.py が足し忘れを知らせる）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disclosure import DisclosureSetting, ReplyTemplate, Theme
from app.models.records import ITEMS

# (テーマの code, 絵文字, 定型文の code の並び)。テーマは spec 001 の FR-013 の 8 個
THEMES: list[tuple[str, str, list[str]]] = [
    (
        "theme.daily_life",  # 普段の様子
        "👀",
        [
            "template.daily_life.usual",  # いつもどおり過ごしています
            "template.daily_life.calm",  # 落ち着いて過ごしています
            "template.daily_life.smile",  # 笑顔が多いです
            "template.daily_life.tired",  # 少し疲れている様子です
        ],
    ),
    (
        "theme.enjoying",  # 楽しく過ごせているか
        "😊",
        [
            "template.enjoying.yes",  # 楽しそうに過ごしています
            "template.enjoying.sometimes",  # 楽しそうなときと、静かなときがあります
            "template.enjoying.quiet",  # 静かに過ごすことが多いです
        ],
    ),
    (
        "theme.residents",  # 他の入居者との関わり
        "👫",
        [
            "template.residents.friends",  # 仲のよい方とよく話しています
            "template.residents.together",  # みなさんと一緒に過ごしています
            "template.residents.own_pace",  # 一人でゆっくり過ごすのがお好きなようです
        ],
    ),
    (
        "theme.meals",  # 食事の様子
        "🍚",
        [
            "template.meals.well",  # よく召し上がっています
            "template.meals.slowly",  # ゆっくり召し上がっています
            "template.meals.favorite",  # お好きなものは、よく召し上がります
            "template.meals.less",  # 少なめの日があります
        ],
    ),
    (
        "theme.staff",  # スタッフとの関わり
        "🤝",
        [
            "template.staff.talks",  # 職員とよくお話ししています
            "template.staff.asks",  # 困ったときは、職員に声をかけてくれます
            "template.staff.reserved",  # 少し遠慮されているようなので、こちらから声をかけています
        ],
    ),
    (
        "theme.recreation",  # レクリエーションの様子
        "🎨",
        [
            "template.recreation.joins",  # よく参加しています
            "template.recreation.watches",  # 見て楽しんでいます
            "template.recreation.mood",  # 気分のよい日に参加しています
        ],
    ),
    (
        "theme.family_talk",  # 家族の話をしているか
        "👨‍👩‍👧",
        [
            "template.family_talk.often",  # ご家族のお話をよくしています
            "template.family_talk.sometimes",  # ときどきご家族のお話をしています
            "template.family_talk.photo",  # ご家族の写真をよく見ています
        ],
    ),
    (
        "theme.supplies",  # 足りないものがないか
        "🧺",
        [
            "template.supplies.none",  # 今は足りないものはありません
            "template.supplies.clothes",  # 衣類が少なくなってきました
            "template.supplies.daily",  # 日用品（歯みがき粉など）が少なくなってきました
        ],
    ),
]


def add_themes(session: Session) -> None:
    """テーマ 8 個と定型文を足す。commit は呼んだ側が行う。"""
    existing_themes = {theme.code: theme for theme in session.scalars(select(Theme))}
    existing_templates = set(session.scalars(select(ReplyTemplate.code)))
    for theme_order, (code, emoji, templates) in enumerate(THEMES, start=1):
        theme = existing_themes.get(code)
        if theme is None:
            theme = Theme(code=code, emoji=emoji, sort_order=theme_order)
            session.add(theme)
            session.flush()
        for template_order, template_code in enumerate(templates, start=1):
            if template_code not in existing_templates:
                session.add(
                    ReplyTemplate(theme_id=theme.id, code=template_code, sort_order=template_order)
                )
    session.flush()


def add_disclosure_settings(session: Session, *, facility_id: int) -> None:
    """記録項目とテーマを、すべて「見せる」で入れる（FR-009）。commit は呼んだ側が行う。"""
    existing = set(
        session.execute(
            select(DisclosureSetting.target_type, DisclosureSetting.target_code).where(
                DisclosureSetting.facility_id == facility_id
            )
        ).all()
    )
    targets = [("item", item) for item in ITEMS] + [("theme", code) for code, _, _ in THEMES]
    for target_type, target_code in targets:
        if (target_type, target_code) not in existing:
            session.add(
                DisclosureSetting(
                    facility_id=facility_id,
                    target_type=target_type,
                    target_code=target_code,
                    visible=True,
                )
            )
    session.flush()
