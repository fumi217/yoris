"""問い合わせ AI が読むための、テーマと定型文の日本語。

spec 004 の 004-T016・contracts/agent-tools.md。

職員の返事（get_active_replies）は、テーマと定型文を辞書のコードで返す。AI がコードのまま答えると
言い方があいまいになるので、ツールの結果には日本語を入れる。
画面の文言は辞書（frontend/src/i18n/ja.json）で引く。ここは AI に渡すためだけの表で、
中身は初期データ（app/seed/themes.py）のコメントと同じ。コードの足し忘れはテストで確かめる
（tests/unit/test_inquiry_labels.py）。
ja.json にテーマ・定型文が入ったら、その文言と同じかも確かめる。
"""

THEME_LABELS = {
    "theme.daily_life": "普段の様子",
    "theme.enjoying": "楽しく過ごせているか",
    "theme.residents": "他の入居者との関わり",
    "theme.meals": "食事の様子",
    "theme.staff": "スタッフとの関わり",
    "theme.recreation": "レクリエーションの様子",
    "theme.family_talk": "家族の話をしているか",
    "theme.supplies": "足りないものがないか",
}

TEMPLATE_LABELS = {
    "template.daily_life.usual": "いつもどおり過ごしています",
    "template.daily_life.calm": "落ち着いて過ごしています",
    "template.daily_life.smile": "笑顔が多いです",
    "template.daily_life.tired": "少し疲れている様子です",
    "template.enjoying.yes": "楽しそうに過ごしています",
    "template.enjoying.sometimes": "楽しそうなときと、静かなときがあります",
    "template.enjoying.quiet": "静かに過ごすことが多いです",
    "template.residents.friends": "仲のよい方とよく話しています",
    "template.residents.together": "みなさんと一緒に過ごしています",
    "template.residents.own_pace": "一人でゆっくり過ごすのがお好きなようです",
    "template.meals.well": "よく召し上がっています",
    "template.meals.slowly": "ゆっくり召し上がっています",
    "template.meals.favorite": "お好きなものは、よく召し上がります",
    "template.meals.less": "少なめの日があります",
    "template.staff.talks": "職員とよくお話ししています",
    "template.staff.asks": "困ったときは、職員に声をかけてくれます",
    "template.staff.reserved": "少し遠慮されているようなので、こちらから声をかけています",
    "template.recreation.joins": "よく参加しています",
    "template.recreation.watches": "見て楽しんでいます",
    "template.recreation.mood": "気分のよい日に参加しています",
    "template.family_talk.often": "ご家族のお話をよくしています",
    "template.family_talk.sometimes": "ときどきご家族のお話をしています",
    "template.family_talk.photo": "ご家族の写真をよく見ています",
    "template.supplies.none": "今は足りないものはありません",
    "template.supplies.clothes": "衣類が少なくなってきました",
    "template.supplies.daily": "日用品（歯みがき粉など）が少なくなってきました",
}
