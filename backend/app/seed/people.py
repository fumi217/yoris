"""施設・職員・入居者・家族アカウントの初期データ。

spec 001 の T015・spec 002 の data-model.md「初期データ」。

名前はすべて架空。毎回同じになるように、決まった並びから作る（デモのたびに変わらないように）。
パスワードは、まだ入れない（ログインできない値）。開発中は、開発用のユーザー切り替えで入る。
本物のログイン（#65）で、開発用のパスワードを決めて入れる。

DB への書き込みは、まとめて送る
（1 人ずつ送らない。人数が増えても問い合わせの回数が増えないように）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.login_ids import next_login_ids
from app.models.core import Facility, FamilyAccount, Resident, Staff, User

FACILITY_NAME = "デモ施設 みどりの家"

# どのハッシュとも一致しない値（bcrypt のハッシュは $2b$ で始まるので、この値ではログインできない）
NO_PASSWORD = "!"

# (返事に出す名前, 役割, 表示言語)。16 人（うち外国人 3 人）。施設の職種との当てはめは
# spec 001 の data-model.md「初期データの人」。名前は PRD のペルソナと、架空の名字
STAFF: list[tuple[str, str, str]] = [
    ("田中", "care_worker", "ja"),
    ("シティ", "care_worker", "id"),
    ("デウィ", "care_worker", "id"),
    ("マリア", "care_worker", "en"),
    ("鈴木", "care_worker", "ja"),
    ("高橋", "care_worker", "ja"),
    ("渡辺", "care_worker", "ja"),
    ("小松", "care_worker", "ja"),
    ("伊藤", "leader", "ja"),
    ("中村", "leader", "ja"),
    ("西村（看護師）", "care_worker", "ja"),
    ("原田（機能訓練指導員）", "care_worker", "ja"),
    ("青木（ケアマネジャー）", "care_worker", "ja"),
    ("山本", "counselor", "ja"),
    ("佐々木", "clerk", "ja"),
    ("猪熊", "director", "ja"),
]

# 入居者 30 人の名字。呼び名は「◯◯さんの母」「◯◯さんの父」（家族から見た呼び方）
SURNAMES = [
    "佐藤", "加藤", "吉田", "山田", "大野", "山口", "松本", "井上", "木村", "林",
    "斎藤", "清水", "山崎", "森", "池田", "橋本", "阿部", "石川", "山下", "中島",
    "石井", "小川", "前田", "岡田", "長谷川", "藤田", "後藤", "近藤", "村上", "遠藤",
]  # fmt: skip
RESIDENT_COUNT = len(SURNAMES)


def get_or_add_facility(session: Session) -> Facility:
    """施設を返す。まだなければ作る。

    施設は 1 つだけ。決済の申し込みで作ったあとなら、それを使う。
    """
    facility = session.scalars(select(Facility).order_by(Facility.id)).first()
    if facility is None:
        facility = Facility(name=FACILITY_NAME)
        session.add(facility)
        session.flush()
    return facility


def _family_emails(session: Session, count: int) -> list[str]:
    """家族のメールアドレス family01@example.test から順に count 個。使われているものは飛ばす。"""
    used = set(session.scalars(select(User.email).where(User.email.like("family%@example.test"))))
    emails: list[str] = []
    number = 1
    while len(emails) < count:
        email = f"family{number:02d}@example.test"
        if email not in used:
            emails.append(email)
        number += 1
    return emails


def add_people(session: Session, *, facility_id: int) -> list[Staff]:
    """職員 16 人・入居者 30 人・家族アカウント 30（入居者に 1 つ）を足す。commit は呼んだ側が行う。

    施設にもう入居者がいれば、何もしない（何度流しても同じになるように）。足した職員を返す（何もしなければ空）。
    決済の申し込みで施設長がもういれば、施設長は足さない（施設長が 2 人にならないように）。
    """
    has_residents = session.scalar(
        select(Resident.id).where(Resident.facility_id == facility_id).limit(1)
    )
    if has_residents is not None:
        return []
    has_director = session.scalar(
        select(Staff.id).where(Staff.facility_id == facility_id, Staff.role == "director").limit(1)
    )
    staff_rows = [row for row in STAFF if not (has_director and row[1] == "director")]

    # 1. ログインの情報（職員・家族）と入居者を、まとめて入れる（id が決まる）
    staff_users = [
        User(kind="staff", login_id=login_id, password_hash=NO_PASSWORD, language=language)
        for login_id, (_, _, language) in zip(
            next_login_ids(session, len(staff_rows)), staff_rows, strict=True
        )
    ]
    family_users = [
        User(kind="family", email=email, password_hash=NO_PASSWORD)
        for email in _family_emails(session, RESIDENT_COUNT)
    ]
    residents = [
        Resident(
            facility_id=facility_id,
            name=f"{surname} 架空{n}",
            display_name=f"{surname}さんの{'母' if n % 3 else '父'}",
            # 居室は 1 階 101〜115、2 階 201〜215
            room=f"{1 + (n - 1) // 15}{(n - 1) % 15 + 1:02d}",
        )
        for n, surname in enumerate(SURNAMES, start=1)
    ]
    session.add_all([*staff_users, *family_users, *residents])
    session.flush()

    # 2. 職員の役割と、家族アカウント（入居者と 1 対 1）を、まとめて入れる
    staff = [
        Staff(user_id=user.id, facility_id=facility_id, display_name=display_name, role=role)
        for user, (display_name, role, _) in zip(staff_users, staff_rows, strict=True)
    ]
    families = [
        FamilyAccount(user_id=user.id, resident_id=resident.id)
        for user, resident in zip(family_users, residents, strict=True)
    ]
    session.add_all([*staff, *families])
    session.flush()
    return staff
