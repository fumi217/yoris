"""前日 20 時の面会の知らせ（003-T034）のテスト（003-T029）。

テストごとに取り消す session を使う。日付は、初期データの予約とぶつからないよう、
ずっと先（2031 年）にする。時刻は at で渡す（日本時間）。
"""

import sys
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from app.jobs import run as run_module
from app.jobs import visit_reminder
from app.jobs.visit_reminder import create_visit_reminders
from app.models.notifications import EmailOutbox, Notification
from app.models.visits import VisitReservation

JST = timezone(timedelta(hours=9))
VISIT_DAY = date(2031, 3, 11)  # 面会の日
EVENING = datetime(2031, 3, 10, 20, 0, tzinfo=JST)  # 前日の 20:00


@pytest.fixture
def add_reservation(session: Session, facility, make_family, make_staff):
    """家族と、その入居者の面会予約を作る。返すのは (予約, 家族)。"""
    hour = iter(range(9, 24, 2))  # 面会は 1 時間 30 分。重ならないよう 2 時間ずつ

    def add(visit_date: date = VISIT_DAY, status: str = "booked", family=None):
        family = family or make_family()
        start = time(next(hour), 0)
        starts_at = datetime.combine(visit_date, start, tzinfo=JST).astimezone(UTC)
        reservation = VisitReservation(
            facility_id=facility.id,
            resident_id=family.resident_id,
            visit_date=visit_date,
            start_time=start,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=90),
            party_size=1,
            status=status,
            cancel_reason="理由" if status == "cancelled_by_staff" else None,
            cancelled_by_staff_id=None,
        )
        if status == "cancelled_by_staff":
            reservation.cancelled_by_staff_id = make_staff().id
        session.add(reservation)
        session.flush()
        return reservation, family

    return add


def _reminders(session: Session, reservation_ids: list[int]) -> list[Notification]:
    return list(
        session.scalars(
            select(Notification)
            .where(
                Notification.kind == "visit_reminder",
                Notification.visit_reservation_id.in_(reservation_ids),
            )
            .order_by(Notification.id)
        )
    )


def test_nothing_is_made_before_20_oclock(session, add_reservation):
    reservation, _ = add_reservation()

    created = create_visit_reminders(session, datetime(2031, 3, 10, 19, 59, tzinfo=JST))

    assert created == 0
    assert _reminders(session, [reservation.id]) == []


def test_after_20_oclock_makes_one_for_each_booked_visit_tomorrow(session, add_reservation):
    tomorrow, family = add_reservation()
    other, other_family = add_reservation()
    today, _ = add_reservation(visit_date=date(2031, 3, 10))
    day_after, _ = add_reservation(visit_date=date(2031, 3, 12))
    cancelled, _ = add_reservation(status="cancelled_by_staff")

    create_visit_reminders(session, EVENING)

    made = _reminders(session, [r.id for r in (tomorrow, other, today, day_after, cancelled)])
    assert {n.visit_reservation_id for n in made} == {tomorrow.id, other.id}
    assert {n.family_account_id for n in made} == {family.id, other_family.id}


def test_calling_again_in_the_20_oclock_hour_adds_nothing(session, add_reservation):
    reservation, _ = add_reservation()

    first = create_visit_reminders(session, EVENING)
    second = create_visit_reminders(session, EVENING + timedelta(minutes=1))
    third = create_visit_reminders(session, EVENING + timedelta(minutes=30))

    assert first >= 1
    assert (second, third) == (0, 0)
    assert len(_reminders(session, [reservation.id])) == 1


def test_a_late_first_call_still_makes_it_until_midnight(session, add_reservation):
    reservation, _ = add_reservation()

    create_visit_reminders(session, datetime(2031, 3, 10, 23, 59, tzinfo=JST))

    assert len(_reminders(session, [reservation.id])) == 1


def test_after_midnight_the_old_tomorrow_is_not_made(session, add_reservation):
    reservation, _ = add_reservation()

    # 面会の日の 0 時を過ぎると、「翌日」は 1 日先になる。当日になった予約には作らない
    create_visit_reminders(session, datetime(2031, 3, 11, 0, 5, tzinfo=JST))

    assert _reminders(session, [reservation.id]) == []


def test_it_uses_japan_time_whatever_the_given_timezone(session, add_reservation):
    reservation, _ = add_reservation()

    # UTC の 10 日 11:00 は、日本では 10 日 20:00
    create_visit_reminders(session, datetime(2031, 3, 10, 11, 0, tzinfo=UTC))

    assert len(_reminders(session, [reservation.id])) == 1


def test_the_email_has_only_the_date_and_link(session, add_reservation, monkeypatch):
    monkeypatch.setattr(
        "app.services.notifications.get_settings",
        lambda: SimpleNamespace(app_base_url="http://app.test"),
    )
    reservation, family = add_reservation()

    create_visit_reminders(session, EVENING)

    notice = _reminders(session, [reservation.id])[0]
    outbox = session.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.template == "visit_reminder")
        .order_by(EmailOutbox.id.desc())
    ).first()
    assert notice.family_account_id == family.id
    assert outbox is not None
    # 渡すのは日時とリンクだけ（入居者名・理由は入らない。FR-014）
    assert set(outbox.params) == {"lang", "visit_at", "link"}
    assert outbox.params["visit_at"].endswith("9:00")
    assert outbox.params["link"] == "http://app.test/family/visits"


def test_one_failure_does_not_stop_the_others(session, add_reservation, monkeypatch):
    first, _ = add_reservation()
    second, _ = add_reservation()
    real = visit_reminder.create_visit_notice

    def flaky(db, reservation_id, kind):
        if reservation_id == first.id:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))
        return real(db, reservation_id, kind)

    monkeypatch.setattr(visit_reminder, "create_visit_notice", flaky)

    create_visit_reminders(session, EVENING)

    assert _reminders(session, [first.id]) == []
    assert len(_reminders(session, [second.id])) == 1


def test_a_visit_without_a_family_account_is_skipped(session, add_reservation, monkeypatch):
    first, _ = add_reservation()
    second, _ = add_reservation()
    real = visit_reminder.create_visit_notice

    def no_family(db, reservation_id, kind):
        if reservation_id == first.id:
            raise NoResultFound()
        return real(db, reservation_id, kind)

    monkeypatch.setattr(visit_reminder, "create_visit_notice", no_family)

    create_visit_reminders(session, EVENING)

    assert _reminders(session, [first.id]) == []
    assert len(_reminders(session, [second.id])) == 1


def test_a_real_duplicate_is_stopped_by_the_database_rule(session, add_reservation):
    reservation, family = add_reservation()
    create_visit_reminders(session, EVENING)

    # 探す条件をすり抜けて 2 回目を作ろうとしても、一意の決まりで IntegrityError になる
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(
                Notification(
                    family_account_id=family.id,
                    kind="visit_reminder",
                    visit_reservation_id=reservation.id,
                )
            )
            session.flush()


class _Recorder:
    def __init__(self):
        self.calls: list[str] = []


@contextmanager
def _fake_session(_engine):
    class FakeSession:
        def commit(self):
            pass

        def rollback(self):
            pass

    yield FakeSession()


def test_run_jobs_makes_the_reminders_and_then_sends_mail(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(run_module, "get_engine", lambda: None)
    monkeypatch.setattr(run_module, "Session", _fake_session)
    monkeypatch.setattr(
        run_module, "create_visit_reminders", lambda db, at: recorder.calls.append("reminders")
    )
    monkeypatch.setattr(run_module, "deliver_pending", lambda db: recorder.calls.append("mail"))

    run_module.run_jobs()

    assert recorder.calls == ["reminders", "mail"]


def test_run_jobs_still_sends_mail_when_making_reminders_fails(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(run_module, "get_engine", lambda: None)
    monkeypatch.setattr(run_module, "Session", _fake_session)

    def broken(db, at):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_module, "create_visit_reminders", broken)
    monkeypatch.setattr(run_module, "deliver_pending", lambda db: recorder.calls.append("mail"))

    run_module.run_jobs()

    assert recorder.calls == ["mail"]


def test_the_time_can_be_given_by_hand(monkeypatch):
    given: list[datetime | None] = []
    monkeypatch.setattr(run_module, "run_jobs", lambda at=None: given.append(at))
    monkeypatch.setattr(sys, "argv", ["visit_reminder", "--at", "2031-03-10T20:00:00+09:00"])
    monkeypatch.setattr("app.logging.configure_logging", lambda: None)

    visit_reminder.main()

    assert given == [EVENING]


def test_the_time_by_hand_needs_a_timezone(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["visit_reminder", "--at", "2031-03-10T20:00:00"])
    monkeypatch.setattr("app.logging.configure_logging", lambda: None)

    with pytest.raises(SystemExit):
        visit_reminder.main()
