"""変化の決まりの初期データ（spec 006 の 006-T004）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。
3 つの決まりを、すべてオンで入れる。すでにある決まりは足さない（オン／オフを変えていても戻さない）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.change_flags import ChangeRule
from app.services.change_rules import RULE_CODES


def add_change_rules(session: Session) -> None:
    """足りない決まりをオンで足す。commit は呼んだ側が行う。"""
    existing = set(session.scalars(select(ChangeRule.code)))
    for code in RULE_CODES:
        if code not in existing:
            session.add(ChangeRule(code=code, enabled=True))
    session.flush()
