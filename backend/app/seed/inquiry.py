"""問い合わせ AI で、職員が家族に返す定型文の初期データ（spec 004 の 004-T011・research.md R-14）。

初期データの仕組み（`python -m app.seed`）から呼ぶ。
何度流しても同じになるように、すでにあるものは足さない。
DB にはコードだけを入れ、文言は辞書（frontend/src/i18n/ja.json の staff_template.*）で引く。
苦情には定型文を用意せず、電話で対応する（FR-014）。
医療・体調の定型文には、体調の判断を書かない（看護職員・医師に回す、様子を見る、だけ。原則 III）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inquiry import StaffMessageTemplate

# (質問の種類, 定型文の code の並び)。種類ごとに 3〜5 個。右のコメントは ja.json の日本語
STAFF_TEMPLATES: list[tuple[str, list[str]]] = [
    (
        "medical",
        [
            "staff_template.medical.ask_nurse",  # 看護職員に確認して、お電話します
            "staff_template.medical.tell_doctor",  # 次の受診のときに、医師に伝えます
            "staff_template.medical.watch",  # 様子をよく見ていきます。変わったことがあれば…
        ],
    ),
    (
        "money",
        [
            "staff_template.money.check",  # 確認して、改めてお知らせします
            "staff_template.money.next_invoice",  # 次の請求書でお知らせします
            "staff_template.money.send_document",  # 書類をお送りします
            "staff_template.money.call",  # お電話でご説明します
        ],
    ),
    (
        "care_request",
        [
            "staff_template.care_request.next_visit",  # 次の面会のときにお渡しします
            "staff_template.care_request.check",  # 確認して、改めてお知らせします
            "staff_template.care_request.done",  # ご依頼のとおりにしました
            "staff_template.care_request.prepare",  # 用意しておきます
        ],
    ),
    (
        "urgent",
        [
            "staff_template.urgent.calling",  # すぐにお電話します
            "staff_template.urgent.handling",  # 施設で対応しています。あとでお電話で…
            "staff_template.urgent.call_us",  # お急ぎのときは、施設にお電話ください
        ],
    ),
    (
        "other",
        [
            "staff_template.other.check",  # 確認して、改めてお知らせします
            "staff_template.other.call",  # お電話でお答えします
            "staff_template.other.thanks",  # お知らせいただき、ありがとうございます
        ],
    ),
]


def add_staff_message_templates(session: Session) -> None:
    """職員の返事の定型文を足す。commit は呼んだ側が行う。"""
    existing = set(session.scalars(select(StaffMessageTemplate.code)))
    for category, codes in STAFF_TEMPLATES:
        for sort_order, code in enumerate(codes, start=1):
            if code not in existing:
                session.add(
                    StaffMessageTemplate(category=category, code=code, sort_order=sort_order)
                )
    session.flush()
