"""共通の土台のテーブル。

spec 001 の data-model.md「共通の土台」と、spec 002 の data-model.md の facilities の列。

ほかのテーブルは、各自の機能のファイル（app/models/<機能>.py）に作り、ここの id を外部キーで指す。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Sequence, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, check_in

USER_KINDS = ("staff", "family")
LANGUAGES = ("ja", "id", "en")
STAFF_ROLES = ("care_worker", "leader", "counselor", "clerk", "director")
# 職種（家族の画面の返事に「表示名（職種）」と出す。#263）。役割とは別に、決まった候補から選ぶ。
# 看護師・機能訓練指導員・ケアマネジャーも役割は care_worker のため、役割から職種は決めない
STAFF_OCCUPATIONS = (
    "care_worker",
    "leader",
    "counselor",
    "clerk",
    "director",
    "nurse",
    "functional_trainer",
    "care_manager",
)

# 職員のログイン用の ID（`s` ＋ 5 桁の数字。s00001〜s99999）の番号。
# 作り方は app/auth/login_ids.py（spec 002 の T006）にまとめる。spec 002 の research.md R-06
staff_login_id_seq = Sequence(
    "staff_login_id_seq", minvalue=1, maxvalue=99999, metadata=Base.metadata
)


class Facility(Base):
    """施設（1 つだけ。2 つ目を作らないことは、作る処理で確かめる。spec 002 の R-04）。"""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str]
    # 利用料について連絡するメールアドレス。初期データの施設は空（spec 002 の R-09）
    billing_email: Mapped[str | None]
    # Stripe の顧客の ID。初期データの施設は空
    stripe_customer_id: Mapped[str | None] = mapped_column(unique=True)


class User(Base):
    """ログインの情報。職員は login_id、家族は email でログインする（spec 001 の R-01）。"""

    __tablename__ = "users"
    __table_args__ = (
        check_in("kind", USER_KINDS, name="kind"),
        check_in("language", LANGUAGES, name="language"),
        # 職員は login_id だけ、家族は email だけを持つ
        # （施設長の連絡先は facilities.billing_email に置く。spec 002 の R-09）
        CheckConstraint(
            "(kind = 'staff' AND login_id IS NOT NULL AND email IS NULL)"
            " OR (kind = 'family' AND email IS NOT NULL AND login_id IS NULL)",
            name="login_by_kind",
        ),
        # 職員のログイン用の ID は `s` ＋ 5 桁の数字だけ
        # （手で入れた値もここで弾く。spec 002 の R-06）
        CheckConstraint("login_id ~ '^s[0-9]{5}$'", name="login_id_format"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    kind: Mapped[str]
    login_id: Mapped[str | None] = mapped_column(unique=True)
    email: Mapped[str | None] = mapped_column(unique=True)
    password_hash: Mapped[str]
    language: Mapped[str] = mapped_column(server_default="ja")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Resident(Base):
    """入居者。"""

    __tablename__ = "residents"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str]
    # 表示用の呼び名（例：「佐藤さんの母」）
    display_name: Mapped[str]
    room: Mapped[str]


class FamilyAccount(Base):
    """家族アカウント（入居者に 1 つ。spec 001 の Session 2026-10-20）。"""

    __tablename__ = "family_accounts"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # ログイン中の家族から入居者を 1 人に決めるため（CurrentUser.resident_id）、
    # 1 人の家族は 1 つのアカウントだけ
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), unique=True)


class Staff(Base):
    """職員と役割。"""

    __tablename__ = "staff"
    __table_args__ = (
        check_in("role", STAFF_ROLES, name="role"),
        check_in("occupation", STAFF_OCCUPATIONS, name="occupation"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    # 返事に出す名前（spec 001 の FR-030）
    display_name: Mapped[str]
    role: Mapped[str]
    # 職種。家族の画面の返事に「表示名（職種）」と出す（#263）。空なら名前だけを出す
    # （役割で補うと、看護師が「介護職員」と出てしまうため）。
    # 役割は画面で何ができるかを決めるもので、看護師なども care_worker のため、分けて持つ
    occupation: Mapped[str | None]
