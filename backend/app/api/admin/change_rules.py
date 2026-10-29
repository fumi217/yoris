"""変化の決まりのオン／オフの API（spec 006 の 006-T020。contracts の `/api/admin/change-rules`）。

決まり（食事量・機嫌・眠り）ごとに、施設全体でオン／オフを選ぶ（FR-011）。
変えられるのは生活相談員・施設長だけ（介護職員・リーダー・事務員・家族は 403）。
オフにしたら今の目印を消し、オンにしたら（変更を確定してから）全員を調べ直す。いまと同じ値なら何もしない
（履歴も増えない。research.md R-07。services/change_detection.py の `set_change_rule_enabled`）。
変更の履歴は `GET /api/admin/change-rules/history` で、新しい順に見られる。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.change_flags import ChangeRule, ChangeRuleHistory
from app.models.core import Staff
from app.services.change_detection import recheck_all_residents, set_change_rule_enabled
from app.services.change_rules import RULE_CODES

router = APIRouter(prefix="/api/admin", tags=["admin"])

RULE_EDITORS = require_staff(("counselor", "director"))

# 履歴を一度に返す件数（新しいものから）
HISTORY_LIMIT = 100


class RuleOut(BaseModel):
    code: str
    enabled: bool


class RuleUpdate(BaseModel):
    enabled: StrictBool


class RuleHistoryOut(BaseModel):
    id: int
    rule_code: str
    enabled_before: bool
    enabled_after: bool
    changed_by_name: str
    changed_at: datetime


@router.get("/change-rules")
def get_change_rules(
    user: Annotated[CurrentUser, Depends(RULE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RuleOut]:
    """決まりの一覧（食事量・機嫌・眠りの順）。"""
    enabled = dict(session.execute(select(ChangeRule.code, ChangeRule.enabled)).all())
    return [RuleOut(code=code, enabled=enabled[code]) for code in RULE_CODES if code in enabled]


# `/change-rules/{code}` より先に登録する（"history" を決まりのコードと取り違えない）
@router.get("/change-rules/history")
def get_change_rule_history(
    user: Annotated[CurrentUser, Depends(RULE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RuleHistoryOut]:
    """決まりの変更履歴（いつ・誰が・どの決まりを・どう変えたか）を、新しい順に返す。"""
    rows = session.execute(
        select(ChangeRuleHistory, Staff.display_name)
        .join(Staff, Staff.id == ChangeRuleHistory.changed_by)
        .order_by(ChangeRuleHistory.changed_at.desc(), ChangeRuleHistory.id.desc())
        .limit(HISTORY_LIMIT)
    )
    return [
        RuleHistoryOut(
            id=history.id,
            rule_code=history.rule_code,
            enabled_before=history.enabled_before,
            enabled_after=history.enabled_after,
            changed_by_name=name,
            changed_at=history.changed_at,
        )
        for history, name in rows
    ]


@router.put("/change-rules/{code}")
def put_change_rule(
    code: str,
    body: RuleUpdate,
    user: Annotated[CurrentUser, Depends(RULE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> RuleOut:
    """決まりをオン／オフする。ない決まりのコードは 404。同じ値なら何もせず、いまの値を返す。"""
    result = set_change_rule_enabled(session, code, body.enabled, staff_id=user.staff_id)
    if result is None:
        raise AppError(ErrorCode.NOT_FOUND)
    rule, changed = result
    out = RuleOut(code=rule.code, enabled=rule.enabled)
    session.commit()
    # オンにしたら、決まりの変更を確定してから全員を調べ直す（入居者ごとに commit。R-07）
    if changed and rule.enabled:
        recheck_all_residents(session)
    return out
