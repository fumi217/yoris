"""変化の決まりのオン／オフの API（006-T019。FR-011・research.md R-07）のテスト。

DB を使う（conftest.py の session・client・engine・make_staff・make_family・login_as。
なければ手元では飛ばす）。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.login_ids import next_login_ids
from app.clock import today_jst
from app.models.change_flags import ChangeFlag, ChangeRule, ChangeRuleHistory
from app.models.core import Facility, Resident, Staff, User
from app.models.records import CareRecord
from app.seed.change_rules import add_change_rules
from app.services import change_detection
from app.services.change_detection import evaluate_change_flags, set_change_rule_enabled

TODAY = today_jst()
URL = "/api/admin/change-rules"
CODES = ["meal_low", "mood_low", "sleep_poor"]


@pytest.fixture
def world(session, make_staff, make_family, login_as):
    add_change_rules(session)
    director = make_staff(role="director", display_name="架空 施設長")
    login_as(director.user_id)
    return {"director": director, "resident_id": make_family().resident_id}


def _add_low_meals(session, resident_id, staff_id) -> None:
    """前の日の夜「少し」・今日の朝「食べていない」（食事量の目印が付く並び）。"""
    for days_ago, slot, value in [(1, "dinner", "2"), (0, "breakfast", "0")]:
        session.add(
            CareRecord(
                resident_id=resident_id,
                date=TODAY - timedelta(days=days_ago),
                item="meal",
                slot=slot,
                value=value,
                recorded_by=staff_id,
            )
        )
    session.flush()


def _add_poor_sleep(session, resident_id, staff_id) -> None:
    for days_ago in (1, 0):
        session.add(
            CareRecord(
                resident_id=resident_id,
                date=TODAY - timedelta(days=days_ago),
                item="sleep",
                slot="day",
                value="poor",
                recorded_by=staff_id,
            )
        )
    session.flush()


def _current_flags(session, resident_id) -> dict[str, ChangeFlag]:
    return {
        flag.rule_code: flag
        for flag in session.scalars(
            select(ChangeFlag).where(
                ChangeFlag.resident_id == resident_id, ChangeFlag.cleared_at.is_(None)
            )
        )
    }


def _history_count(session) -> int:
    return session.scalar(select(func.count()).select_from(ChangeRuleHistory))


# --- 一覧と役割（FR-011） ---


def test_get_lists_three_rules_all_on(client, world):
    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == [{"code": code, "enabled": True} for code in CODES]


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_only_counselor_and_director(client, world, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.get(URL).status_code == 403
    assert client.put(f"{URL}/meal_low", json={"enabled": False}).status_code == 403
    assert client.get(f"{URL}/history").status_code == 403


@pytest.mark.parametrize("role", ["counselor", "director"])
def test_counselor_and_director_can_change(client, world, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    response = client.put(f"{URL}/mood_low", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == {"code": "mood_low", "enabled": False}


def test_family_cannot_open(client, world, make_family, login_as):
    login_as(make_family().user_id)

    assert client.get(URL).status_code == 403
    assert client.put(f"{URL}/meal_low", json={"enabled": False}).status_code == 403
    assert client.get(f"{URL}/history").status_code == 403


def test_unknown_code_is_404(client, world):
    response = client.put(f"{URL}/no_such_rule", json={"enabled": False})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("body", [{}, {"enabled": "false"}, {"enabled": None}])
def test_enabled_must_be_a_boolean(client, world, body):
    assert client.put(f"{URL}/meal_low", json=body).status_code == 422


# --- オフにする（R-07） ---


def test_turning_off_clears_the_current_flags_of_that_rule(client, session, world):
    resident_id, staff_id = world["resident_id"], world["director"].id
    _add_low_meals(session, resident_id, staff_id)
    _add_poor_sleep(session, resident_id, staff_id)
    evaluate_change_flags(session, resident_id)
    assert set(_current_flags(session, resident_id)) == {"meal_low", "sleep_poor"}

    assert client.put(f"{URL}/meal_low", json={"enabled": False}).status_code == 200

    session.expire_all()
    # 食事量の目印だけが、消えた理由「決まりをオフにした」で消える。ほかの決まりの目印はそのまま
    assert set(_current_flags(session, resident_id)) == {"sleep_poor"}
    cleared = session.scalars(
        select(ChangeFlag).where(
            ChangeFlag.resident_id == resident_id, ChangeFlag.rule_code == "meal_low"
        )
    ).one()
    assert cleared.status == "cleared"
    assert cleared.cleared_at is not None
    assert cleared.cleared_reason == "rule_disabled"


def test_confirmed_flag_is_cleared_too(client, session, world):
    resident_id, staff_id = world["resident_id"], world["director"].id
    _add_low_meals(session, resident_id, staff_id)
    evaluate_change_flags(session, resident_id)
    _current_flags(session, resident_id)["meal_low"].status = "confirmed"
    session.flush()

    client.put(f"{URL}/meal_low", json={"enabled": False})

    session.expire_all()
    assert _current_flags(session, resident_id) == {}


def test_records_do_not_make_a_flag_while_off(client, session, world):
    resident_id, staff_id = world["resident_id"], world["director"].id
    client.put(f"{URL}/meal_low", json={"enabled": False})

    _add_low_meals(session, resident_id, staff_id)
    evaluate_change_flags(session, resident_id)

    assert "meal_low" not in _current_flags(session, resident_id)


# --- オンに戻す（R-07） ---


def test_turning_on_checks_every_resident_again(client, session, world, make_family):
    staff_id = world["director"].id
    other_id = make_family().resident_id
    client.put(f"{URL}/meal_low", json={"enabled": False})
    # オフのあいだに、2 人の記録が入った（調べ直しは、決まりがオフなので目印を付けない）
    for resident_id in (world["resident_id"], other_id):
        _add_low_meals(session, resident_id, staff_id)
        evaluate_change_flags(session, resident_id)
        assert _current_flags(session, resident_id) == {}

    assert client.put(f"{URL}/meal_low", json={"enabled": True}).status_code == 200

    for resident_id in (world["resident_id"], other_id):
        flag = _current_flags(session, resident_id)["meal_low"]
        assert (flag.status, flag.streak) == ("unconfirmed", 2)


def test_one_resident_failing_does_not_stop_the_others(
    client, session, world, make_family, monkeypatch
):
    staff_id = world["director"].id
    failing_id, other_id = world["resident_id"], make_family().resident_id
    client.put(f"{URL}/meal_low", json={"enabled": False})
    for resident_id in (failing_id, other_id):
        _add_low_meals(session, resident_id, staff_id)

    real = change_detection.evaluate_change_flags

    def fail_for_one(session, resident_id):
        if resident_id == failing_id:
            raise RuntimeError("テスト用の失敗")
        real(session, resident_id)

    monkeypatch.setattr(change_detection, "evaluate_change_flags", fail_for_one)

    # オンにする変更は確定していて、応答も成功。失敗した 1 人のほかは付け直される
    assert client.put(f"{URL}/meal_low", json={"enabled": True}).json() == {
        "code": "meal_low",
        "enabled": True,
    }
    assert _current_flags(session, failing_id) == {}
    assert "meal_low" in _current_flags(session, other_id)
    assert session.get(ChangeRule, "meal_low").enabled is True


def test_turning_off_and_on_again_makes_a_new_flag_and_keeps_the_old_one(client, session, world):
    resident_id, staff_id = world["resident_id"], world["director"].id
    _add_low_meals(session, resident_id, staff_id)
    evaluate_change_flags(session, resident_id)
    first_id = _current_flags(session, resident_id)["meal_low"].id

    client.put(f"{URL}/meal_low", json={"enabled": False})
    client.put(f"{URL}/meal_low", json={"enabled": True})

    session.expire_all()
    assert _current_flags(session, resident_id)["meal_low"].id != first_id
    old = session.get(ChangeFlag, first_id)
    assert (old.status, old.cleared_reason) == ("cleared", "rule_disabled")


# --- 履歴（FR-011） ---


def test_each_change_is_kept_in_history_newest_first(client, session, world):
    client.put(f"{URL}/meal_low", json={"enabled": False})
    client.put(f"{URL}/sleep_poor", json={"enabled": False})
    client.put(f"{URL}/meal_low", json={"enabled": True})

    rows = client.get(f"{URL}/history").json()

    assert [(r["rule_code"], r["enabled_before"], r["enabled_after"]) for r in rows] == [
        ("meal_low", False, True),
        ("sleep_poor", True, False),
        ("meal_low", True, False),
    ]
    assert {r["changed_by_name"] for r in rows} == {"架空 施設長"}
    assert all(r["changed_at"] for r in rows)
    # 決まりの行にも、最後に変えた人が入る
    session.expire_all()
    assert session.get(ChangeRule, "meal_low").updated_by == world["director"].id


def test_history_is_empty_at_first(client, world):
    assert client.get(f"{URL}/history").json() == []


# --- 同じ値を送っても、何も変わらない（R-07） ---


def test_same_value_adds_no_history(client, session, world):
    assert client.put(f"{URL}/meal_low", json={"enabled": True}).status_code == 200
    client.put(f"{URL}/meal_low", json={"enabled": False})
    client.put(f"{URL}/meal_low", json={"enabled": False})

    assert client.put(f"{URL}/meal_low", json={"enabled": False}).json() == {
        "code": "meal_low",
        "enabled": False,
    }
    rows = client.get(f"{URL}/history").json()
    assert [(r["enabled_before"], r["enabled_after"]) for r in rows] == [(True, False)]


def test_same_value_does_not_check_residents_again(client, session, world):
    # すでにオンの決まりをオンにしても、全員の調べ直しはしない（調べ直していれば目印が付く）
    _add_low_meals(session, world["resident_id"], world["director"].id)

    assert client.put(f"{URL}/meal_low", json={"enabled": True}).status_code == 200

    assert _current_flags(session, world["resident_id"]) == {}
    assert _history_count(session) == 0


# --- オフにする処理と、記録の保存から呼ばれる調べ直しが同時に走る（R-07） ---


@contextmanager
def _committed_world(engine) -> Iterator[dict[str, int]]:
    """本当に commit する世界（施設・入居者・職員・決まり）を作り、終わったら自分で消す。

    ロックの待ち合いは、commit したデータと別々の接続でしか確かめられない。
    テストの外の DB を汚さないよう、作ったものだけを消す。
    """
    with Session(engine) as setup_session:
        rules_before = set(setup_session.scalars(select(ChangeRule.code)))
        add_change_rules(setup_session)
        facility = Facility(name="決まりの変更のテスト施設")
        setup_session.add(facility)
        setup_session.flush()
        [login_id] = next_login_ids(setup_session, 1)
        user = User(kind="staff", login_id=login_id, password_hash="x")
        resident = Resident(
            facility_id=facility.id,
            name="架空 変更",
            name_kana="かくう",
            name_romaji="Kaku",
            room="998",
        )
        setup_session.add_all([user, resident])
        setup_session.flush()
        staff = Staff(
            user_id=user.id, facility_id=facility.id, display_name="架空", role="care_worker"
        )
        setup_session.add(staff)
        setup_session.flush()
        ids = {
            "facility": facility.id,
            "user": user.id,
            "resident": resident.id,
            "staff": staff.id,
        }
        setup_session.commit()
    try:
        yield ids
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(
                delete(ChangeRuleHistory).where(ChangeRuleHistory.changed_by == ids["staff"])
            )
            cleanup.execute(delete(ChangeFlag).where(ChangeFlag.resident_id == ids["resident"]))
            cleanup.execute(
                ChangeRule.__table__.update()
                .where(ChangeRule.updated_by == ids["staff"])
                .values(updated_by=None)
            )
            cleanup.execute(delete(Staff).where(Staff.id == ids["staff"]))
            cleanup.execute(delete(Resident).where(Resident.id == ids["resident"]))
            cleanup.execute(delete(User).where(User.id == ids["user"]))
            cleanup.execute(delete(Facility).where(Facility.id == ids["facility"]))
            # 空の DB（CI）で入れた決まりは、残さない（開発の DB にあった決まりは消さない）
            if not rules_before:
                cleanup.execute(delete(ChangeRule))
            cleanup.commit()


def test_evaluation_waits_while_a_rule_is_being_changed(engine):
    """オフにする処理が決まりの行を押さえているあいだ、調べ直しは待つ。

    待たずに決まりを読むと、オフになる前の値で目印を付けてしまう。
    """
    with _committed_world(engine) as ids:
        changer = Session(engine)
        waiter = Session(engine)
        try:
            # オフにする処理が、決まりの行を押さえたまま（まだ commit していない）
            changer.execute(
                ChangeRule.__table__.update()
                .where(ChangeRule.code == "meal_low")
                .values(enabled=False)
            )
            waiter.connection().exec_driver_sql("SET LOCAL lock_timeout = '500ms'")

            with pytest.raises(OperationalError):
                evaluate_change_flags(waiter, ids["resident"])
        finally:
            waiter.rollback()
            waiter.close()
            changer.rollback()
            changer.close()


def test_changing_a_rule_does_not_wait_for_a_resident_row(engine):
    """オン／オフの保存は、決まりの行を持ったまま入居者の行を待たない。

    記録の保存は、外部キーで入居者の行を先に押さえてから決まりの行を待つ。保存が
    入居者の行を持っているあいだに、オンにする処理も入居者の行を待つと、待ち合って止まる。
    """
    with _committed_world(engine) as ids:
        with Session(engine) as prepare:
            prepare.execute(
                ChangeRule.__table__.update()
                .where(ChangeRule.code == "meal_low")
                .values(enabled=False)
            )
            prepare.commit()

        saver = Session(engine)
        changer = Session(engine)
        try:
            # 記録の保存が、外部キーで入居者の行を押さえている
            saver.execute(
                select(Resident.id)
                .where(Resident.id == ids["resident"])
                .with_for_update(key_share=True)
            ).all()
            changer.connection().exec_driver_sql("SET LOCAL lock_timeout = '500ms'")

            result = set_change_rule_enabled(changer, "meal_low", True, staff_id=ids["staff"])
            changer.commit()

            assert result is not None and result[1] is True
        finally:
            saver.rollback()
            saver.close()
            changer.rollback()
            changer.close()
