"""変化の目印を付け直す処理と API（006-T005）のテスト。

DB を使う（conftest.py の session・client・make_staff・make_family・login_as。
なければ手元では飛ばす）。
記録の保存・取り消しの処理から呼ぶのはゆうの 006-T008 なので、ここでは `evaluate_change_flags` を
直接呼んで確かめる（記録の保存から目印が付くことは、T008 のテストで確かめる）。
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.login_ids import next_login_ids
from app.clock import today_jst
from app.models.change_flags import ChangeFlag, ChangeFlagConfirmation, ChangeRule
from app.models.core import Facility, Resident, Staff, User
from app.models.notifications import EmailOutbox, Notification
from app.models.records import CareRecord
from app.seed.change_rules import add_change_rules
from app.services.change_detection import evaluate_change_flags, get_flag_summary

TODAY = today_jst()
URL = "/api/staff/residents/{}/change-flags"


@pytest.fixture
def rules(session: Session) -> None:
    """決まり 3 つ（すべてオン）。空の DB（CI）でも動くように。

    同時実行のテストでは使わない（commit していない行を、別のセッションが待ってしまうため）。
    """
    add_change_rules(session)


def _record(session, resident_id, staff_id, days_ago, item, slot, value) -> CareRecord:
    record = CareRecord(
        resident_id=resident_id,
        date=TODAY - timedelta(days=days_ago),
        item=item,
        slot=slot,
        value=value,
        recorded_by=staff_id,
    )
    session.add(record)
    session.flush()
    return record


def _two_low_meals(session, resident_id, staff_id) -> list[CareRecord]:
    """前の日の夜「少し」・今日の朝「食べていない」（US1 シナリオ 1）。"""
    return [
        _record(session, resident_id, staff_id, 1, "meal", "dinner", "2"),
        _record(session, resident_id, staff_id, 0, "meal", "breakfast", "0"),
    ]


def _flags(session, resident_id) -> list[ChangeFlag]:
    return list(
        session.scalars(
            select(ChangeFlag).where(ChangeFlag.resident_id == resident_id).order_by(ChangeFlag.id)
        )
    )


@pytest.fixture
def setup(rules, session, make_staff, make_family):
    staff = make_staff()
    family = make_family()
    return staff, family.resident_id


# --- 付ける・直す・消す（T007） ---


def test_matching_records_make_an_unconfirmed_flag(session, setup):
    staff, resident_id = setup
    records = _two_low_meals(session, resident_id, staff.id)

    evaluate_change_flags(session, resident_id)

    [flag] = _flags(session, resident_id)
    assert (flag.rule_code, flag.status, flag.streak, flag.cleared_at) == (
        "meal_low",
        "unconfirmed",
        2,
        None,
    )
    assert flag.evidence == [
        {
            "record_id": records[0].id,
            "date": (TODAY - timedelta(days=1)).isoformat(),
            "slot": "dinner",
            "value": "2",
        },
        {"record_id": records[1].id, "date": TODAY.isoformat(), "slot": "breakfast", "value": "0"},
    ]


def test_not_matching_records_make_no_flag(session, setup):
    staff, resident_id = setup
    _record(session, resident_id, staff.id, 1, "meal", "dinner", "2")
    _record(session, resident_id, staff.id, 0, "meal", "breakfast", "8")

    evaluate_change_flags(session, resident_id)

    assert _flags(session, resident_id) == []


def test_evaluating_again_keeps_one_flag_and_does_not_touch_it(session, setup):
    staff, resident_id = setup
    _two_low_meals(session, resident_id, staff.id)
    evaluate_change_flags(session, resident_id)
    [first] = _flags(session, resident_id)
    first_updated_at = first.updated_at

    evaluate_change_flags(session, resident_id)
    evaluate_change_flags(session, resident_id)

    [again] = _flags(session, resident_id)
    assert again.id == first.id
    assert again.updated_at == first_updated_at


def test_flag_is_cleared_when_a_record_is_overwritten(session, setup):
    staff, resident_id = setup
    breakfast = _two_low_meals(session, resident_id, staff.id)[1]
    evaluate_change_flags(session, resident_id)

    breakfast.value = "8"  # 押し直し
    session.flush()
    evaluate_change_flags(session, resident_id)

    [flag] = _flags(session, resident_id)
    assert (flag.status, flag.cleared_reason) == ("cleared", "not_matching")
    assert flag.cleared_at is not None

    # また当てはまったら、新しい行ができ、消えた行は履歴に残る
    breakfast.value = "2"
    session.flush()
    evaluate_change_flags(session, resident_id)
    old, new = _flags(session, resident_id)
    assert (old.status, new.status, new.cleared_at) == ("cleared", "unconfirmed", None)


def test_flag_is_cleared_when_a_record_is_cancelled(session, setup):
    staff, resident_id = setup
    breakfast = _two_low_meals(session, resident_id, staff.id)[1]
    evaluate_change_flags(session, resident_id)

    breakfast.deleted_at = datetime.now(UTC)  # 取り消し
    session.flush()
    evaluate_change_flags(session, resident_id)

    [flag] = _flags(session, resident_id)
    assert (flag.status, flag.cleared_reason) == ("cleared", "not_matching")


def test_cancelled_record_is_not_counted(session, setup):
    staff, resident_id = setup
    dinner, _ = _two_low_meals(session, resident_id, staff.id)
    dinner.deleted_at = datetime.now(UTC)
    session.flush()

    evaluate_change_flags(session, resident_id)

    assert _flags(session, resident_id) == []


def test_only_seven_days_from_the_newest_record_are_counted(session, setup):
    staff, resident_id = setup
    # 10 日続けて元気がなくても、数えるのは最新の記録の日から 7 日分（古い 3 日分は入らない）
    for days_ago in range(10):
        _record(session, resident_id, staff.id, days_ago, "mood", "day", "low")

    evaluate_change_flags(session, resident_id)

    [flag] = _flags(session, resident_id)
    assert flag.streak == 7
    assert [e["date"] for e in flag.evidence] == [
        (TODAY - timedelta(days=days_ago)).isoformat() for days_ago in range(6, -1, -1)
    ]


def test_disabled_rule_is_not_evaluated(session, setup):
    staff, resident_id = setup
    _two_low_meals(session, resident_id, staff.id)
    session.get(ChangeRule, "meal_low").enabled = False
    session.flush()

    evaluate_change_flags(session, resident_id)

    assert _flags(session, resident_id) == []


def test_other_residents_records_are_not_mixed_in(session, setup, make_family):
    staff, resident_id = setup
    other_id = make_family().resident_id
    _record(session, resident_id, staff.id, 1, "meal", "dinner", "2")
    _record(session, other_id, staff.id, 0, "meal", "breakfast", "0")

    evaluate_change_flags(session, resident_id)
    evaluate_change_flags(session, other_id)

    assert _flags(session, resident_id) == []
    assert _flags(session, other_id) == []


def _confirm(session, flag, staff_id, note=None):
    flag.status = "confirmed"
    session.add(
        ChangeFlagConfirmation(
            change_flag_id=flag.id,
            confirmed_by=staff_id,
            note=note,
            streak_at_confirmation=flag.streak,
        )
    )
    session.flush()


def test_confirmed_flag_goes_back_when_the_streak_grows(session, setup):
    staff, resident_id = setup
    _two_low_meals(session, resident_id, staff.id)
    evaluate_change_flags(session, resident_id)
    [flag] = _flags(session, resident_id)
    _confirm(session, flag, staff.id)

    # 続いた数が同じなら、確かめ済みのまま
    evaluate_change_flags(session, resident_id)
    assert flag.status == "confirmed"

    # 3 食続けたら、まだ確かめていないに戻る。前の確かめた記録は残る（FR-010）
    _record(session, resident_id, staff.id, 0, "meal", "lunch", "2")
    evaluate_change_flags(session, resident_id)
    assert (flag.status, flag.streak) == ("unconfirmed", 3)
    assert session.scalar(select(func.count()).select_from(ChangeFlagConfirmation)) >= 1


def test_streak_stops_growing_at_seven_days(session, setup):
    staff, resident_id = setup
    # 機嫌が 7 日続いて確かめた（昨日の時点）。翌日も続いても、7 日分までしか数えないので戻らない
    for days_ago in range(1, 8):
        _record(session, resident_id, staff.id, days_ago, "mood", "day", "low")
    evaluate_change_flags(session, resident_id)
    [flag] = _flags(session, resident_id)
    assert flag.streak == 7
    _confirm(session, flag, staff.id)

    _record(session, resident_id, staff.id, 0, "mood", "day", "low")
    evaluate_change_flags(session, resident_id)

    assert (flag.streak, flag.status) == (7, "confirmed")


def test_window_counts_from_the_newest_record_not_from_today(session, setup):
    staff, resident_id = setup
    # 最新の記録が 8 日前でも、その日から 7 日分を読んで目印が付く（今日から数えると何も読まない）
    for days_ago in (12, 11, 10, 9, 8):
        _record(session, resident_id, staff.id, days_ago, "mood", "day", "low")

    evaluate_change_flags(session, resident_id)

    [flag] = _flags(session, resident_id)
    assert (flag.rule_code, flag.streak, flag.status) == ("mood_low", 5, "unconfirmed")


def test_old_flag_stays_while_no_new_record_comes(session, setup):
    staff, resident_id = setup
    for days_ago in (9, 8):
        _record(session, resident_id, staff.id, days_ago, "mood", "day", "low")
    evaluate_change_flags(session, resident_id)
    [flag] = _flags(session, resident_id)

    # 記録が来ないあいだは、調べ直しても消えない（消えるのは、新しい記録で当てはまらなくなったとき）
    evaluate_change_flags(session, resident_id)

    assert _flags(session, resident_id) == [flag]
    assert flag.cleared_at is None


def test_each_item_has_its_own_window(session, setup):
    staff, resident_id = setup
    # 機嫌は 20 日前で止まり、食事は今日まである。食事の決まりは今日から数える
    for days_ago in (21, 20):
        _record(session, resident_id, staff.id, days_ago, "mood", "day", "low")
    _two_low_meals(session, resident_id, staff.id)

    evaluate_change_flags(session, resident_id)

    assert sorted(f.rule_code for f in _flags(session, resident_id)) == ["meal_low", "mood_low"]


def test_two_rules_make_two_rows_and_one_resident_in_the_count(session, setup):
    staff, resident_id = setup
    _two_low_meals(session, resident_id, staff.id)
    _record(session, resident_id, staff.id, 1, "sleep", "day", "poor")
    _record(session, resident_id, staff.id, 0, "sleep", "day", "poor")
    before = get_flag_summary(session).unconfirmed_resident_count

    evaluate_change_flags(session, resident_id)

    assert {f.rule_code for f in _flags(session, resident_id)} == {"meal_low", "sleep_poor"}
    summary = get_flag_summary(session)
    assert summary.unconfirmed_resident_count == before + 1
    assert summary.residents[resident_id].has_flag
    assert summary.residents[resident_id].has_unconfirmed


def test_summary_tells_confirmed_from_unconfirmed(session, setup):
    staff, resident_id = setup
    _two_low_meals(session, resident_id, staff.id)
    evaluate_change_flags(session, resident_id)
    before = get_flag_summary(session).unconfirmed_resident_count
    [flag] = _flags(session, resident_id)
    _confirm(session, flag, staff.id)

    summary = get_flag_summary(session)

    assert summary.residents[resident_id].has_flag
    assert not summary.residents[resident_id].has_unconfirmed
    assert summary.unconfirmed_resident_count == before - 1


def test_resident_without_flag_is_not_in_the_summary(session, setup):
    _, resident_id = setup
    evaluate_change_flags(session, resident_id)

    assert resident_id not in get_flag_summary(session).residents


# --- 同時に調べ直しても、目印は 1 つ（R-03） ---


@contextmanager
def _committed_resident(engine, *, with_low_meals: bool) -> Iterator[dict[str, int]]:
    """本当に commit する入居者（と職員・決まり）を作り、終わったら自分で消す。

    ロックの待ち合いは、commit したデータと別々の接続でしか確かめられない。
    テストの外の DB を汚さないよう、作ったものだけを消す。
    """
    today = date.today()
    with Session(engine) as setup_session:
        rules_before = set(setup_session.scalars(select(ChangeRule.code)))
        add_change_rules(setup_session)
        facility = Facility(name="同時実行のテスト施設")
        setup_session.add(facility)
        setup_session.flush()
        [login_id] = next_login_ids(setup_session, 1)
        user = User(kind="staff", login_id=login_id, password_hash="x")
        resident = Resident(
            facility_id=facility.id, name="架空 同時", display_name="同時さんの母", room="999"
        )
        setup_session.add_all([user, resident])
        setup_session.flush()
        staff = Staff(
            user_id=user.id, facility_id=facility.id, display_name="架空", role="care_worker"
        )
        setup_session.add(staff)
        setup_session.flush()
        if with_low_meals:
            for slot, value, days_ago in [("dinner", "2", 1), ("breakfast", "0", 0)]:
                setup_session.add(
                    CareRecord(
                        resident_id=resident.id,
                        date=today - timedelta(days=days_ago),
                        item="meal",
                        slot=slot,
                        value=value,
                        recorded_by=staff.id,
                    )
                )
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
            cleanup.execute(delete(ChangeFlag).where(ChangeFlag.resident_id == ids["resident"]))
            cleanup.execute(delete(CareRecord).where(CareRecord.resident_id == ids["resident"]))
            cleanup.execute(delete(Staff).where(Staff.id == ids["staff"]))
            cleanup.execute(delete(Resident).where(Resident.id == ids["resident"]))
            cleanup.execute(delete(User).where(User.id == ids["user"]))
            cleanup.execute(delete(Facility).where(Facility.id == ids["facility"]))
            # 空の DB（CI）で入れた決まりは、残さない（開発の DB にあった決まりは消さない）
            if not rules_before:
                cleanup.execute(delete(ChangeRule))
            cleanup.commit()


def _run_in_two_threads(work) -> list[BaseException]:
    """work(worker_number) を 2 つのスレッドで、同時に始めて走らせる。起きた例外を返す。"""
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def run(number: int) -> None:
        try:
            work(number, barrier)
        except BaseException as error:
            # 失敗はあとでまとめて確かめる
            errors.append(error)

    threads = [threading.Thread(target=run, args=(number,)) for number in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def test_concurrent_evaluations_make_one_flag(engine):
    """目印がまだない入居者を、2 つのセッションで同時に調べ直しても、一意制約に当たらない。"""
    with _committed_resident(engine, with_low_meals=True) as ids:

        def work(number: int, barrier: threading.Barrier) -> None:
            with Session(engine) as worker:
                barrier.wait()
                evaluate_change_flags(worker, ids["resident"])
                worker.commit()

        errors = _run_in_two_threads(work)
        with Session(engine) as check:
            count = check.scalar(
                select(func.count())
                .select_from(ChangeFlag)
                .where(ChangeFlag.resident_id == ids["resident"])
            )

    assert errors == []
    assert count == 1


def test_concurrent_new_records_do_not_deadlock(engine):
    """同じ入居者に、2 人が同時に別の食事区分を新しく記録しても、止まらない。

    記録を新しく足すと、外部キーの確認で入居者の行に FOR KEY SHARE が付く。そのあとの
    調べ直しが入居者の行を FOR UPDATE で押さえると、2 人がお互いの KEY SHARE の終わりを待ち、
    片方が deadlock detected で失敗する（FOR NO KEY UPDATE なら KEY SHARE と両立する）。
    """
    today = date.today()
    with _committed_resident(engine, with_low_meals=False) as ids:

        def work(number: int, barrier: threading.Barrier) -> None:
            with Session(engine) as worker:
                worker.add(
                    CareRecord(
                        resident_id=ids["resident"],
                        date=today,
                        item="meal",
                        slot=("lunch", "dinner")[number],
                        value="0",
                        recorded_by=ids["staff"],
                    )
                )
                worker.flush()
                # 2 人とも記録を足し終えて（入居者の行に KEY SHARE が付いて）から、調べ直す
                barrier.wait()
                evaluate_change_flags(worker, ids["resident"])
                worker.commit()

        errors = _run_in_two_threads(work)

    assert errors == []


# --- 通知は出ない・ログに値を出さない（SC-004・FR-014） ---


def test_flag_makes_no_notification_or_email(session, setup):
    staff, resident_id = setup
    counts = (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    )
    _two_low_meals(session, resident_id, staff.id)

    evaluate_change_flags(session, resident_id)

    assert _flags(session, resident_id)
    assert (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    ) == counts


def test_log_has_ids_only(rules, session, make_staff, make_family, caplog):
    staff = make_staff(display_name="ログ確認の職員")
    family = make_family(display_name="ログ確認さんの母")
    _two_low_meals(session, family.resident_id, staff.id)

    with caplog.at_level(logging.INFO):
        evaluate_change_flags(session, family.resident_id)

    text = caplog.text
    assert "meal_low" in text
    assert "ログ確認さんの母" not in text
    assert "ログ確認の職員" not in text
    assert "breakfast" not in text
    assert "evidence" not in text


# --- API（T012） ---


def _login(login_as, staff):
    login_as(staff.user_id)


@pytest.mark.parametrize("role", ["care_worker", "leader", "counselor", "director"])
def test_recording_staff_can_open(client, session, make_staff, login_as, setup, role):
    _, resident_id = setup
    login_as(make_staff(role=role).user_id)

    response = client.get(URL.format(resident_id))

    assert response.status_code == 200
    assert response.json() == {"current": [], "history": []}


def test_clerk_and_family_cannot_open(client, make_staff, make_family, login_as, setup):
    _, resident_id = setup
    login_as(make_staff(role="clerk").user_id)
    assert client.get(URL.format(resident_id)).status_code == 403

    family = make_family()
    login_as(family.user_id)
    assert client.get(URL.format(family.resident_id)).status_code == 403


def test_not_logged_in_is_401(client, setup):
    _, resident_id = setup
    assert client.get(URL.format(resident_id)).status_code == 401


def test_unknown_resident_is_404(client, make_staff, login_as):
    login_as(make_staff().user_id)
    assert client.get(URL.format(2**40)).status_code == 404


def test_current_and_history_shape(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    records = _two_low_meals(session, resident_id, staff.id)
    evaluate_change_flags(session, resident_id)
    [flag] = _flags(session, resident_id)
    _confirm(session, flag, staff.id, note="<script>alert(1)</script>")
    # 過去の目印：消えた機嫌の目印
    old = ChangeFlag(
        resident_id=resident_id,
        rule_code="mood_low",
        streak=2,
        evidence=[],
        status="cleared",
        cleared_at=datetime.now(UTC),
        cleared_reason="not_matching",
    )
    session.add(old)
    session.flush()
    login_as(make_staff(display_name="見る人").user_id)

    data = client.get(URL.format(resident_id)).json()

    [current] = data["current"]
    assert current["rule_code"] == "meal_low"
    assert current["status"] == "confirmed"
    assert current["streak"] == 2
    assert [e["record_id"] for e in current["evidence"]] == [r.id for r in records]
    assert current["evidence"][0] == {
        "record_id": records[0].id,
        "date": (TODAY - timedelta(days=1)).isoformat(),
        "slot": "dinner",
        "value": "2",
    }
    # 確かめた職員は表示名だけ。ひとこと（タグを含む）はそのまま文字として返る（FR-013）
    [confirmation] = current["confirmations"]
    assert set(confirmation) == {"staff_display_name", "confirmed_at", "note"}
    assert confirmation["staff_display_name"] == staff.display_name
    assert confirmation["note"] == "<script>alert(1)</script>"
    [history] = data["history"]
    assert (history["id"], history["rule_code"], history["cleared_reason"]) == (
        old.id,
        "mood_low",
        "not_matching",
    )
    assert history["confirmations"] == []


def test_history_is_newest_first(client, session, make_staff, login_as, setup):
    _, resident_id = setup
    now = datetime.now(UTC)
    for minutes_ago, code in [(30, "meal_low"), (10, "mood_low"), (20, "sleep_poor")]:
        session.add(
            ChangeFlag(
                resident_id=resident_id,
                rule_code=code,
                streak=2,
                evidence=[],
                status="cleared",
                cleared_at=now - timedelta(minutes=minutes_ago),
                cleared_reason="not_matching",
            )
        )
    session.flush()
    login_as(make_staff().user_id)

    history = client.get(URL.format(resident_id)).json()["history"]

    assert [h["rule_code"] for h in history] == ["mood_low", "sleep_poor", "meal_low"]


def test_family_screens_do_not_show_flags(
    rules, client, session, make_staff, make_family, login_as
):
    """家族の連絡帳に、目印が入らない（FR-007・SC-005）。"""
    staff = make_staff()
    family = make_family()
    _two_low_meals(session, family.resident_id, staff.id)
    evaluate_change_flags(session, family.resident_id)
    assert _flags(session, family.resident_id)
    login_as(family.user_id)

    response = client.get("/api/family/contact-book")

    assert response.status_code == 200
    assert "change" not in response.text
    assert "flag" not in response.text
