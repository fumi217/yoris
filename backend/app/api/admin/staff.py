"""職員のアカウントを作る API（spec 001 の 001-T088。contracts の `POST /api/admin/staff`）。

作れるのは生活相談員・施設長（どの役割も作れる）。施設は、ログイン中の職員の施設から決める。
ログイン用の ID は決まりの形（`s` ＋ 5 桁。auth/login_ids.py）、初期パスワードはサーバーが作り、
この返事で 1 回だけ返す（`Cache-Control: no-store`。DB にはハッシュだけを入れ、ログに出さない）。
`users` と `staff` は同じ commit で入れる（どちらかだけが残らない）。
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.auth.login_ids import next_login_ids
from app.auth.passwords import generate_initial_password, hash_password
from app.db import get_session
from app.models.core import Staff, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

STAFF_CREATORS = require_staff(("counselor", "director"))

# models/core.py の STAFF_ROLES・STAFF_OCCUPATIONS と同じ。足すときは両方に足す（tests が見つける）
Role = Literal["care_worker", "leader", "counselor", "clerk", "director"]
Occupation = Literal[
    "care_worker",
    "leader",
    "counselor",
    "clerk",
    "director",
    "nurse",
    "functional_trainer",
    "care_manager",
]
DISPLAY_NAME_MAX = 20


class StaffCreate(BaseModel):
    # 決まりの外の項目（施設の id など）は受け付けない
    model_config = ConfigDict(extra="forbid")

    # 前後の空白は除く。同じ名前の人がいてもよい
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DISPLAY_NAME_MAX)
    ]
    role: Role
    # 空（null・省略）なら、家族の画面には名前だけが出る
    occupation: Occupation | None = None


class StaffCreated(BaseModel):
    id: int
    login_id: str
    display_name: str
    role: str
    occupation: str | None
    # この返事でだけ返す。あとからは見られない
    initial_password: str


@router.post("/staff", status_code=201)
def create_staff(
    body: StaffCreate,
    response: Response,
    user: Annotated[CurrentUser, Depends(STAFF_CREATORS)],
    session: Annotated[Session, Depends(get_session)],
) -> StaffCreated:
    # 重い計算（bcrypt）は、DB の処理を始める前に済ませる（DB の接続を、計算の間つかまない）
    password = generate_initial_password()
    password_hash = hash_password(password)
    facility_id = session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()
    (login_id,) = next_login_ids(session)
    account = User(kind="staff", login_id=login_id, password_hash=password_hash, language="ja")
    session.add(account)
    session.flush()
    staff = Staff(
        user_id=account.id,
        facility_id=facility_id,
        display_name=body.display_name,
        role=body.role,
        occupation=body.occupation,
    )
    session.add(staff)
    session.commit()
    # だれが・どの ID を作ったかだけ残す（氏名・パスワードは出さない）
    logger.info(
        "職員のアカウントを作りました（作った人 staff_id=%s、作られた ID=%s、役割=%s）",
        user.staff_id,
        login_id,
        staff.role,
    )
    # パスワードを、ブラウザや途中の中継に残さない
    response.headers["Cache-Control"] = "no-store"
    return StaffCreated(
        id=staff.id,
        login_id=login_id,
        display_name=staff.display_name,
        role=staff.role,
        occupation=staff.occupation,
        initial_password=password,
    )
