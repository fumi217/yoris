"""変化の検知のテーブルと決まりの初期データ（006-T003・006-T004）が DB で効くかのテスト。

目印を書く処理（evaluate_change_flags、006-T007）にバグがあっても、DB が受け付けないことを確かめる。
DB は tests/conftest.py の session を使う（テストごとに取り消す）。
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.change_flags import ChangeFlag, ChangeFlagConfirmation, ChangeRule
from app.models.core import Facility, Resident, Staff, User
from app.seed.change_rules import add_change_rules
from app.services.change_rules import RULE_CODES

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
EVIDENCE = [{"record_id": 1, "date": "2026-10-28", "slot": "breakfast", "value": "2"}]


@pytest.fixture
def resident_id(session: Session) -> int:
    """架空の施設と入居者を作り、決まりの初期データを入れる。"""
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    resident = Resident(
        facility_id=facility.id,
        name="架空 1",
        name_kana="かくう",
        name_romaji="Kaku",
        room="101",
    )
    session.add(resident)
    add_change_rules(session)
    session.flush()
    return resident.id


def _flag(resident_id: int, **values) -> ChangeFlag:
    fields = {
        "resident_id": resident_id,
        "rule_code": "meal_low",
        "streak": 2,
        "evidence": EVIDENCE,
        "status": "unconfirmed",
    } | values
    return ChangeFlag(**fields)


def _rejected(session: Session, *objects) -> None:
    """入れようとすると DB が受け付けない（savepoint の中で試し、テストを続けられるようにする）。"""
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add_all(objects)
        session.flush()


# --- 決まりの初期データ（006-T004） ---


def test_seed_adds_three_rules_all_enabled(session):
    add_change_rules(session)
    rules = {r.code: r.enabled for r in session.scalars(select(ChangeRule))}
    assert rules == dict.fromkeys(RULE_CODES, True)


def test_seed_twice_adds_nothing_and_keeps_the_switch(session):
    add_change_rules(session)
    # 相談員がオフにした決まりを、もう一度流しても戻さない
    session.get(ChangeRule, "sleep_poor").enabled = False
    session.flush()

    add_change_rules(session)

    assert session.scalar(select(func.count()).select_from(ChangeRule)) == 3
    assert session.get(ChangeRule, "sleep_poor").enabled is False


def test_rule_code_is_limited(session):
    _rejected(session, ChangeRule(code="unknown"))


# --- 目印の決まり（006-T003） ---


def test_current_flag_is_unique_per_resident_and_rule(session, resident_id):
    session.add(_flag(resident_id))
    session.flush()

    _rejected(session, _flag(resident_id))
    # 別の決まりなら、同じ入居者に付く
    session.add(_flag(resident_id, rule_code="mood_low"))
    session.flush()


def test_cleared_flag_stays_as_history_and_a_new_one_can_start(session, resident_id):
    session.add(_flag(resident_id, status="cleared", cleared_at=NOW, cleared_reason="not_matching"))
    session.add(_flag(resident_id))
    session.flush()

    assert session.scalar(select(func.count()).select_from(ChangeFlag)) == 2


def test_status_and_cleared_at_must_match(session, resident_id):
    # 消えたのに status が残ったまま・status が cleared なのに消えた日時がない
    _rejected(session, _flag(resident_id, cleared_at=NOW, cleared_reason="not_matching"))
    _rejected(session, _flag(resident_id, status="cleared"))


def test_cleared_reason_only_when_cleared(session, resident_id):
    _rejected(session, _flag(resident_id, cleared_reason="not_matching"))
    _rejected(session, _flag(resident_id, status="cleared", cleared_at=NOW))
    _rejected(session, _flag(resident_id, status="cleared", cleared_at=NOW, cleared_reason="other"))


def test_status_is_limited(session, resident_id):
    _rejected(session, _flag(resident_id, status="done"))


def test_confirmation_note_is_optional_and_up_to_100_chars(session, resident_id):
    flag = _flag(resident_id)
    session.add(flag)
    session.flush()

    user = User(kind="staff", login_id="s99999", password_hash="x")
    session.add(user)
    session.flush()
    staff = Staff(
        user_id=user.id,
        facility_id=session.get(Resident, resident_id).facility_id,
        display_name="架空の職員",
        role="care_worker",
    )
    session.add(staff)
    session.flush()

    def confirmation(note):
        return ChangeFlagConfirmation(
            change_flag_id=flag.id, confirmed_by=staff.id, note=note, streak_at_confirmation=2
        )

    session.add_all([confirmation(None), confirmation("あ" * 100)])
    session.flush()
    _rejected(session, confirmation("あ" * 101))
