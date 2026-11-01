"""変化の目印を付け直す処理と API（006-T005）のテスト。

DB を使う（conftest.py の session・client・make_staff・make_family・login_as。
なければ手元では飛ばす）。
前半は `evaluate_change_flags` を直接呼んで確かめる。記録の保存・押し直し・取り消しの API から
実際に呼ばれること（006-T008）と、入居者一覧に返すこと（006-T011）は、後半（006-T005b）で確かめる。
"""

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.auth.login_ids import next_login_ids
from app.clock import today_jst
from app.errors import AppError, ErrorCode
from app.models.change_flags import ChangeFlag, ChangeFlagConfirmation, ChangeRule
from app.models.core import Facility, Resident, Staff, User
from app.models.notifications import EmailOutbox, Notification
from app.models.records import CareRecord
from app.seed.change_rules import add_change_rules
from app.services.change_detection import (
    confirm_change_flags,
    evaluate_change_flags,
    get_flag_summary,
)
from app.services.records import save_record

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
            facility_id=facility.id, name="架空 同時", display_name="同時 花子", room="999"
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
            cleanup.execute(
                delete(ChangeFlagConfirmation).where(
                    ChangeFlagConfirmation.change_flag_id.in_(
                        select(ChangeFlag.id).where(ChangeFlag.resident_id == ids["resident"])
                    )
                )
            )
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
    family = make_family(name="ログ確認 花子")
    _two_low_meals(session, family.resident_id, staff.id)

    with caplog.at_level(logging.INFO):
        evaluate_change_flags(session, family.resident_id)

    text = caplog.text
    assert "meal_low" in text
    assert "ログ確認 花子" not in text
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


# --- 確かめる（T016。FR-009・FR-010。POST …/change-flags/confirm） ---

CONFIRM_URL = "/api/staff/residents/{}/change-flags/confirm"


def _two_flags(session, resident_id, staff_id) -> list[ChangeFlag]:
    """食事量と眠り、2 つの決まりに当てはまる記録を入れて、まだ確かめていない目印を 2 つ作る。"""
    _two_low_meals(session, resident_id, staff_id)
    _record(session, resident_id, staff_id, 1, "sleep", "day", "poor")
    _record(session, resident_id, staff_id, 0, "sleep", "day", "poor")
    evaluate_change_flags(session, resident_id)
    flags = _flags(session, resident_id)
    assert {flag.rule_code for flag in flags} == {"meal_low", "sleep_poor"}
    return flags


def _confirmations(session, flag_id) -> list[ChangeFlagConfirmation]:
    return list(
        session.scalars(
            select(ChangeFlagConfirmation)
            .where(ChangeFlagConfirmation.change_flag_id == flag_id)
            .order_by(ChangeFlagConfirmation.id)
        )
    )


def test_confirm_makes_every_unconfirmed_flag_confirmed(
    client, session, make_staff, login_as, setup
):
    staff, resident_id = setup
    flags = _two_flags(session, resident_id, staff.id)
    confirmer = make_staff(display_name="確かめる人")
    login_as(confirmer.user_id)

    response = client.post(CONFIRM_URL.format(resident_id), json={"note": "本人は元気"})

    assert response.status_code == 200
    assert response.json() == {"confirmed": 2}
    session.expire_all()
    for flag in flags:
        assert flag.status == "confirmed"
        [confirmation] = _confirmations(session, flag.id)
        assert confirmation.confirmed_by == confirmer.id
        assert confirmation.note == "本人は元気"
        assert confirmation.streak_at_confirmation == flag.streak


@pytest.mark.parametrize("body", [{}, {"note": None}, {"note": ""}, {"note": "   "}])
def test_note_is_optional_and_blank_means_none(client, session, make_staff, login_as, setup, body):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff().user_id)

    assert client.post(CONFIRM_URL.format(resident_id), json=body).status_code == 200

    session.expire_all()
    [confirmation] = _confirmations(session, flag.id)
    assert confirmation.note is None


def _flags_after_two_low_meals(session, resident_id, staff_id) -> list[ChangeFlag]:
    _two_low_meals(session, resident_id, staff_id)
    evaluate_change_flags(session, resident_id)
    return _flags(session, resident_id)


def test_note_keeps_text_but_drops_surrounding_spaces(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff().user_id)

    client.post(CONFIRM_URL.format(resident_id), json={"note": "  本人は 元気  "})

    session.expire_all()
    assert [c.note for c in _confirmations(session, flag.id)] == ["本人は 元気"]


def test_note_length_is_counted_after_dropping_spaces(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff().user_id)

    # 前後に空白があっても、取れば 101 文字なら 422。100 文字なら通る
    over = client.post(CONFIRM_URL.format(resident_id), json={"note": " " + "あ" * 101 + " "})
    assert over.status_code == 422
    ok = client.post(CONFIRM_URL.format(resident_id), json={"note": "  " + "あ" * 100 + "  "})
    assert ok.status_code == 200
    session.expire_all()
    assert [c.note for c in _confirmations(session, flag.id)] == ["あ" * 100]


def test_note_up_to_100_characters_and_over_that_is_422(
    client, session, make_staff, login_as, setup
):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff().user_id)

    too_long = client.post(CONFIRM_URL.format(resident_id), json={"note": "あ" * 101})
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "validation_error"
    session.expire_all()
    assert flag.status == "unconfirmed"
    assert _confirmations(session, flag.id) == []

    exactly = client.post(CONFIRM_URL.format(resident_id), json={"note": "あ" * 100})
    assert exactly.status_code == 200


def test_nothing_to_confirm_is_409_already_confirmed(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    login_as(make_staff().user_id)

    # 目印が 1 つもない
    response = client.post(CONFIRM_URL.format(resident_id), json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_confirmed"

    # 確かめ済みしかない（2 人がほぼ同時に押したときの、後の人も同じ）。確かめた記録は増えない
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    assert client.post(CONFIRM_URL.format(resident_id), json={"note": "1 人目"}).status_code == 200
    again = client.post(CONFIRM_URL.format(resident_id), json={"note": "2 人目"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_confirmed"
    session.expire_all()
    assert [c.note for c in _confirmations(session, flag.id)] == ["1 人目"]


def test_cleared_flags_are_not_confirmed(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    [current] = _flags_after_two_low_meals(session, resident_id, staff.id)
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
    login_as(make_staff().user_id)

    assert client.post(CONFIRM_URL.format(resident_id), json={}).json() == {"confirmed": 1}

    session.expire_all()
    assert current.status == "confirmed"
    assert old.status == "cleared"
    assert _confirmations(session, old.id) == []


def test_confirmed_goes_back_when_it_continues_and_old_confirmation_stays(
    client, session, make_staff, login_as, setup
):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff(display_name="前の勤務の人").user_id)
    client.post(CONFIRM_URL.format(resident_id), json={"note": "夕食を様子見"})

    # さらに続いた（FR-010）：まだ確かめていないに戻り、前の確かめた記録は残る
    _record(session, resident_id, staff.id, 0, "meal", "lunch", "2")
    evaluate_change_flags(session, resident_id)
    session.expire_all()
    assert (flag.status, flag.streak) == ("unconfirmed", 3)
    assert len(_confirmations(session, flag.id)) == 1

    # 確かめ直すと、行が増える（前に確かめた人の記録も残る）
    login_as(make_staff(display_name="次の勤務の人").user_id)
    assert (
        client.post(CONFIRM_URL.format(resident_id), json={"note": "食欲が戻った"}).status_code
        == 200
    )
    session.expire_all()
    assert flag.status == "confirmed"
    assert [(c.note, c.streak_at_confirmation) for c in _confirmations(session, flag.id)] == [
        ("夕食を様子見", 2),
        ("食欲が戻った", 3),
    ]


@pytest.mark.parametrize("role", ["care_worker", "leader", "counselor", "director"])
def test_recording_staff_can_confirm(client, session, make_staff, login_as, setup, role):
    staff, resident_id = setup
    _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff(role=role).user_id)

    assert client.post(CONFIRM_URL.format(resident_id), json={}).status_code == 200


def test_clerk_and_family_cannot_confirm(client, session, make_staff, make_family, login_as, setup):
    staff, resident_id = setup
    [flag] = _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff(role="clerk").user_id)
    assert client.post(CONFIRM_URL.format(resident_id), json={}).status_code == 403

    family = make_family()
    login_as(family.user_id)
    assert client.post(CONFIRM_URL.format(resident_id), json={}).status_code == 403
    session.expire_all()
    assert flag.status == "unconfirmed"


def test_confirm_service_with_unknown_resident_is_not_found(session, setup):
    """API を通さずにサービスだけを呼んでも、入居者がいなければ 500 でなく NOT_FOUND。"""
    staff, _ = setup

    with pytest.raises(AppError) as error:
        confirm_change_flags(session, 2**40, staff.id, None)

    assert error.value.code == ErrorCode.NOT_FOUND


def test_confirm_not_logged_in_is_401(client, setup):
    _, resident_id = setup
    assert client.post(CONFIRM_URL.format(resident_id), json={}).status_code == 401


def test_confirm_unknown_resident_is_404(client, make_staff, login_as):
    login_as(make_staff().user_id)
    assert client.post(CONFIRM_URL.format(2**40), json={}).status_code == 404


def _other_facility_resident(session) -> Resident:
    other = Facility(name="ほかの施設")
    session.add(other)
    session.flush()
    resident = Resident(facility_id=other.id, name="架空 他施設", display_name="他 花子", room="1")
    session.add(resident)
    session.flush()
    return resident


def test_confirm_other_facility_resident_is_404(client, session, make_staff, login_as, setup):
    """ほかの施設の入居者は、ない入居者と同じ 404（様子のメモの API と同じ。#326・#327）。"""
    staff, _ = setup
    resident = _other_facility_resident(session)
    [flag] = _flags_after_two_low_meals(session, resident.id, staff.id)
    login_as(make_staff().user_id)

    response = client.post(CONFIRM_URL.format(resident.id), json={})

    assert response.status_code == 404
    session.expire_all()
    assert flag.status == "unconfirmed"


def test_get_other_facility_resident_is_404(client, session, make_staff, login_as, setup):
    """見る API も同じ（目印の中身に、記録の値・確かめた職員の名前が入るため）。"""
    staff, _ = setup
    resident = _other_facility_resident(session)
    _flags_after_two_low_meals(session, resident.id, staff.id)
    login_as(make_staff().user_id)

    assert client.get(URL.format(resident.id)).status_code == 404


def test_note_is_returned_as_plain_text(client, session, make_staff, login_as, setup):
    """`<script>` などは、そのまま文字として返す（実行・加工しない。FR-013）。"""
    staff, resident_id = setup
    _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff().user_id)
    note = "<script>alert(1)</script> {太郎|たろう}"
    client.post(CONFIRM_URL.format(resident_id), json={"note": note})

    data = client.get(URL.format(resident_id)).json()

    assert [c["note"] for c in data["current"][0]["confirmations"]] == [note]


def test_confirm_log_has_no_note(client, session, make_staff, login_as, setup, caplog):
    """ログに、ひとこと・入居者の氏名を出さない（FR-014）。"""
    staff, resident_id = setup
    _flags_after_two_low_meals(session, resident_id, staff.id)
    login_as(make_staff(display_name="ひみつの職員名").user_id)

    with caplog.at_level(logging.DEBUG):
        client.post(CONFIRM_URL.format(resident_id), json={"note": "ひみつのひとこと"})

    assert "ひみつのひとこと" not in caplog.text
    assert "ひみつの職員名" not in caplog.text
    assert "確かめた" in caplog.text


def test_confirm_makes_no_notification_or_email(client, session, make_staff, login_as, setup):
    staff, resident_id = setup
    _flags_after_two_low_meals(session, resident_id, staff.id)
    before = (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    )
    login_as(make_staff().user_id)

    client.post(CONFIRM_URL.format(resident_id), json={})

    assert (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    ) == before


def test_two_confirms_at_the_same_time_only_one_wins(engine):
    """2 人がほぼ同時に「確かめた」を押したら、先の人だけが残り、後の人は already_confirmed。

    入居者の行を順番待ちにしているので、後の人は先の人の確かめを見て、何もせずに断られる。
    """
    with _committed_resident(engine, with_low_meals=True) as ids:
        with Session(engine) as prepare:
            evaluate_change_flags(prepare, ids["resident"])
            prepare.commit()
        results: list[object] = []

        def work(number: int, barrier: threading.Barrier) -> None:
            with Session(engine) as worker:
                barrier.wait()
                try:
                    results.append(
                        confirm_change_flags(worker, ids["resident"], ids["staff"], f"{number}")
                    )
                    worker.commit()
                except AppError as error:
                    worker.rollback()
                    results.append(error.code)

        errors = _run_in_two_threads(work)
        with Session(engine) as check:
            rows = check.scalar(
                select(func.count())
                .select_from(ChangeFlagConfirmation)
                .where(
                    ChangeFlagConfirmation.change_flag_id.in_(
                        select(ChangeFlag.id).where(ChangeFlag.resident_id == ids["resident"])
                    )
                )
            )

    assert errors == []
    assert sorted(results, key=str) == [1, ErrorCode.ALREADY_CONFIRMED]
    assert rows == 1


def test_confirm_takes_locks_in_the_same_order_as_a_record_save(engine):
    """確かめる処理は、記録の保存から呼ばれる調べ直しと、同じ順番で行を押さえる（入居者 → 目印）。

    時間に頼らず、保存の側を手で再現する：保存が入居者の行を押さえたまま、確かめる側が待ちに入る
    のを待ち、そのあと保存が目印の行を押さえて終わる。確かめる側が目印の行を先に押さえる順番だと、
    互いに相手の行を待って止まり（deadlock detected）、どちらかが失敗する。
    """
    with _committed_resident(engine, with_low_meals=True) as ids:
        with Session(engine) as prepare:
            evaluate_change_flags(prepare, ids["resident"])
            prepare.commit()

        errors: list[BaseException] = []

        def confirm() -> None:
            try:
                with Session(engine) as worker:
                    confirm_change_flags(worker, ids["resident"], ids["staff"], None)
                    worker.commit()
            except BaseException as error:
                # 失敗はあとでまとめて確かめる
                errors.append(error)

        saver = Session(engine)
        thread = threading.Thread(target=confirm)
        try:
            # 保存（evaluate_change_flags と同じ順番）：まず入居者の行を押さえる
            saver.scalars(
                select(Resident.id)
                .where(Resident.id == ids["resident"])
                .with_for_update(key_share=True)
            ).one()
            thread.start()
            _wait_until_someone_waits_for_a_lock(engine)
            # 保存は、そのあと目印の行を押さえて終わる
            saver.scalars(
                select(ChangeFlag)
                .where(ChangeFlag.resident_id == ids["resident"], ChangeFlag.cleared_at.is_(None))
                .with_for_update()
            ).all()
            saver.commit()
            thread.join(timeout=10)
        finally:
            saver.rollback()
            saver.close()

        assert not thread.is_alive()
        assert errors == []


def _wait_until_someone_waits_for_a_lock(engine, seconds: float = 5.0) -> None:
    """どこかの接続が、ロックの待ちに入るまで待つ（最大 seconds 秒）。"""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with Session(engine) as probe:
            waiting = probe.scalar(text("SELECT count(*) FROM pg_locks WHERE NOT granted"))
        if waiting:
            return
        time.sleep(0.02)
    raise AssertionError("確かめる側が、ロックの待ちに入らなかった")


# --- 記録の保存・押し直し・取り消しから、目印が付く・消える（006-T005b・T008） ---

RECORDS_URL = "/api/staff/residents/{}/records"


def _put_record(client, resident_id, slot, value, days_ago=0):
    date_ = (TODAY - timedelta(days=days_ago)).isoformat()
    body = {"date": date_, "item": "meal", "slot": slot, "value": value}
    response = client.put(RECORDS_URL.format(resident_id), json=body)
    assert response.status_code == 200
    return response.json()


def _current_rules(session, resident_id) -> list[tuple[str, str]]:
    session.expire_all()
    return [(f.rule_code, f.status) for f in _flags(session, resident_id) if f.cleared_at is None]


def test_saving_a_record_makes_a_flag(client, session, setup, login_as):
    staff, resident_id = setup
    login_as(staff.user_id)
    _put_record(client, resident_id, "dinner", "2", days_ago=1)
    assert _current_rules(session, resident_id) == []

    # 2 食続けて「少し」以下になったところで、保存の API から目印が付く
    _put_record(client, resident_id, "breakfast", "0")

    assert _current_rules(session, resident_id) == [("meal_low", "unconfirmed")]


def test_pressing_again_clears_the_flag(client, session, setup, login_as):
    staff, resident_id = setup
    login_as(staff.user_id)
    _put_record(client, resident_id, "dinner", "2", days_ago=1)
    _put_record(client, resident_id, "breakfast", "0")

    # 今日の朝を「ほぼ全部」に押し直すと、当てはまらなくなって消える
    _put_record(client, resident_id, "breakfast", "8")

    assert _current_rules(session, resident_id) == []
    [flag] = _flags(session, resident_id)
    assert flag.status == "cleared"


def test_cancelling_a_record_clears_the_flag(client, session, setup, login_as):
    staff, resident_id = setup
    login_as(staff.user_id)
    _put_record(client, resident_id, "dinner", "2", days_ago=1)
    breakfast = _put_record(client, resident_id, "breakfast", "0")
    assert _current_rules(session, resident_id) == [("meal_low", "unconfirmed")]

    response = client.delete(f"/api/staff/records/{breakfast['id']}")

    assert response.status_code == 204
    assert _current_rules(session, resident_id) == []


def test_concurrent_new_records_through_save_record_do_not_deadlock(engine):
    """2 人が同時に、同じ入居者の別の食事区分を、保存の処理（save_record）で新しく記録しても、
    止まらない。

    保存の処理は、記録の行を `FOR UPDATE` で探し、外部キーで入居者の行に KEY SHARE を
    付けてから、目印を調べ直す。調べ直しの入居者の行のロックが FOR NO KEY UPDATE であれば、
    待ち合わない（R-03）。
    """
    with _committed_resident(engine, with_low_meals=False) as ids:

        def work(number: int, barrier: threading.Barrier) -> None:
            with Session(engine) as worker:
                barrier.wait()
                save_record(
                    worker,
                    resident_id=ids["resident"],
                    staff_id=ids["staff"],
                    record_date=today_jst(),
                    item="meal",
                    slot=("lunch", "dinner")[number],
                    value="0",
                )
                worker.commit()

        errors = _run_in_two_threads(work)
        with Session(engine) as check:
            flags = check.scalars(
                select(ChangeFlag.rule_code).where(
                    ChangeFlag.resident_id == ids["resident"], ChangeFlag.cleared_at.is_(None)
                )
            ).all()

    assert errors == []
    # 2 食とも「食べていない」なので、どちらが後でも目印は 1 つ
    assert flags == ["meal_low"]


# --- 入居者一覧に、目印と件数を返す（006-T011） ---


def test_resident_list_has_flags_and_count(client, session, setup, make_family, login_as):
    staff, flagged = setup
    plain = make_family().resident_id
    _two_low_meals(session, flagged, staff.id)
    evaluate_change_flags(session, flagged)
    login_as(staff.user_id)

    data = client.get("/api/staff/residents").json()
    rows = {row["id"]: row for row in data["residents"]}

    assert rows[flagged]["change_flag"] == {"has_flag": True, "has_unconfirmed": True}
    assert rows[plain]["change_flag"] is None
    assert data["unconfirmed_flag_count"] == get_flag_summary(session).unconfirmed_resident_count
    assert data["unconfirmed_flag_count"] >= 1
