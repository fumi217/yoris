"""20 時のまとめ（001-T065・T066）と、アルバムの写真（005-T025）のテスト。SC-010・research.md R-13。

テストごとに取り消す session を使う。日付は、初期データの記録とぶつからないよう、
ずっと先（2031 年）にする。時刻は at で渡す（日本時間）。
2031-03-09 は日曜、2031-03-10 は月曜。
"""

import logging
from collections.abc import Callable
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.jobs import digest
from app.jobs import run as run_module
from app.jobs.digest import create_digests
from app.models.album import AlbumPhoto
from app.models.core import Resident, User
from app.models.disclosure import DisclosureSetting
from app.models.files import UploadedFile
from app.models.notifications import DigestRun, EmailOutbox, Notification, NotificationSetting
from app.models.records import DAY_SLOT, VALUES, CareRecord
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache
from app.services.mail import deliver_pending
from app.services.uploads import save_upload
from tests.helpers.images import fake_png

JST = timezone(timedelta(hours=9))
SUNDAY = date(2031, 3, 9)
MONDAY = date(2031, 3, 10)
TUESDAY = date(2031, 3, 11)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=JST)


@pytest.fixture
def world(session: Session, redis, facility, make_family, make_staff):
    """開示設定は、初期データ（記録項目はすべて見せる）。家族 1 組と、記録する職員。"""
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield SimpleNamespace(facility=facility, family=make_family(), staff=make_staff())
    clear_disclosure_cache(facility.id)


def record(session: Session, world, recorded_at: datetime, item: str = "meal", day=None) -> None:
    """記録を 1 件足す（記録した日時を指定する。日付は、既定では記録した日）。"""
    session.add(
        CareRecord(
            resident_id=world.family.resident_id,
            date=day or recorded_at.astimezone(JST).date(),
            item=item,
            slot="lunch" if item == "meal" else DAY_SLOT,
            value=VALUES[item][0],
            recorded_by=world.staff.id,
            recorded_at=recorded_at,
        )
    )
    session.flush()


def digests(session: Session, world) -> list[Notification]:
    return list(
        session.scalars(
            select(Notification)
            .where(
                Notification.family_account_id == world.family.id,
                Notification.kind.in_(("daily_digest", "weekly_digest")),
            )
            .order_by(Notification.id)
        )
    )


def runs(session: Session, world) -> list[DigestRun]:
    return list(
        session.scalars(
            select(DigestRun)
            .where(DigestRun.family_account_id == world.family.id)
            .order_by(DigestRun.id)
        )
    )


def set_settings(session: Session, world, **values) -> None:
    session.add(NotificationSetting(family_account_id=world.family.id, **values))
    session.flush()


def test_makes_the_daily_digest_for_a_day_with_records(session, world):
    record(session, world, at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))

    [notice] = digests(session, world)
    assert notice.kind == "daily_digest"
    assert notice.period_end == at(MONDAY, 20)
    # 前回のまとめがないときは、1 日前の 20:00 から
    assert notice.period_start == at(MONDAY, 20) - timedelta(days=1)


def test_the_mail_has_no_record_content(session, world):
    record(session, world, at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))

    email = session.get(User, world.family.user_id).email
    [outbox] = session.scalars(select(EmailOutbox).where(EmailOutbox.to_email == email)).all()
    assert outbox.template == "daily_digest"
    # 渡すのは言語とリンクだけ。記録の中身（食事の量など）は入れない（SC-010）
    assert set(outbox.params) <= {"lang", "link"}


def test_the_same_time_twice_makes_it_once(session, world):
    record(session, world, at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))
    create_digests(session, at(MONDAY, 20))

    assert len(digests(session, world)) == 1
    assert len(runs(session, world)) == 1


def test_many_calls_in_the_8pm_hour_make_it_once(session, world):
    record(session, world, at(MONDAY, 10))

    for minute in range(0, 60, 7):
        create_digests(session, at(MONDAY, 20, minute))

    assert len(digests(session, world)) == 1


def test_a_day_without_records_makes_nothing_and_leaves_no_run(session, world):
    create_digests(session, at(MONDAY, 20))

    assert digests(session, world) == []
    # 残すのは、作ったまとめだけ（仕様：どの家族のどのまとめを作ったか）
    assert runs(session, world) == []


def test_the_previous_digest_is_the_last_one_made(session, world):
    # 月曜はまとめを作り、火曜は記録がなく、水曜に記録がある。水曜の期間は、作った最後のまとめ
    # （月曜 20:00）のあとから。火曜に記録があれば、その分も水曜のまとめに入る
    record(session, world, at(MONDAY, 10))
    create_digests(session, at(MONDAY, 20))
    create_digests(session, at(TUESDAY, 20))  # 記録なし（何も作らず、何も残さない）
    record(session, world, at(TUESDAY + timedelta(days=1), 10))

    create_digests(session, at(TUESDAY + timedelta(days=1), 20))

    wednesday = digests(session, world)[-1]
    assert wednesday.period_start == at(MONDAY, 20)
    assert [run.period_end for run in runs(session, world)] == [
        at(MONDAY, 20),
        at(TUESDAY + timedelta(days=1), 20),
    ]


def test_only_hidden_items_make_nothing(session, world):
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world.facility.id,
            DisclosureSetting.target_type == "item",
            DisclosureSetting.target_code == "meal",
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(world.facility.id)
    record(session, world, at(MONDAY, 10), item="meal")

    create_digests(session, at(MONDAY, 20))

    assert digests(session, world) == []


def test_only_items_the_family_did_not_choose_make_nothing(session, world):
    set_settings(session, world, notify_items=["mood"])
    record(session, world, at(MONDAY, 10), item="meal")

    create_digests(session, at(MONDAY, 20))
    assert digests(session, world) == []

    record(session, world, at(TUESDAY, 10), item="mood")
    create_digests(session, at(TUESDAY, 20))
    assert len(digests(session, world)) == 1


def test_nothing_before_8pm(session, world):
    record(session, world, at(MONDAY, 10))

    assert create_digests(session, at(MONDAY, 19, 59)) == 0

    assert digests(session, world) == []
    assert runs(session, world) == []


def test_a_late_first_call_still_makes_todays_digest_with_the_8pm_end(session, world):
    record(session, world, at(MONDAY, 10))

    create_digests(session, at(MONDAY, 23, 30))

    [notice] = digests(session, world)
    assert notice.period_end == at(MONDAY, 20)  # 締めは、呼ばれた時刻ではなく 20:00


def test_a_record_after_8pm_goes_into_the_next_digest(session, world):
    record(session, world, at(MONDAY, 20, 30), item="mood")  # 20:00 より後

    create_digests(session, at(MONDAY, 20, 5))
    assert digests(session, world) == []

    create_digests(session, at(TUESDAY, 20))
    [notice] = digests(session, world)
    # 前回のまとめ（月曜 20:00）のあとから
    assert notice.period_start == at(MONDAY, 20)
    assert notice.period_end == at(TUESDAY, 20)


def test_a_record_made_later_for_an_older_date_is_included(session, world):
    # 3 日前の分を、今日あとから記録した（記録の日付は古いが、記録した日時は新しい）
    record(session, world, at(MONDAY, 10), day=MONDAY - timedelta(days=3))

    create_digests(session, at(MONDAY, 20))

    assert len(digests(session, world)) == 1


def test_frequency_none_makes_nothing(session, world):
    set_settings(session, world, frequency="none")
    record(session, world, at(SUNDAY, 10))

    create_digests(session, at(SUNDAY, 20))

    assert digests(session, world) == []
    assert runs(session, world) == []


def test_weekly_family_gets_it_only_on_sunday(session, world):
    set_settings(session, world, frequency="weekly")
    record(session, world, at(SUNDAY - timedelta(days=2), 10))  # 金曜の記録

    create_digests(session, at(SUNDAY - timedelta(days=1), 20))  # 土曜の 20 時
    assert digests(session, world) == []

    create_digests(session, at(SUNDAY, 20))
    [notice] = digests(session, world)
    assert notice.kind == "weekly_digest"
    assert notice.period_start == at(SUNDAY, 20) - timedelta(days=7)
    assert [run.kind for run in runs(session, world)] == ["weekly"]


def test_daily_family_gets_only_the_daily_one_on_sunday(session, world):
    record(session, world, at(SUNDAY, 10))

    create_digests(session, at(SUNDAY, 20))

    assert [notice.kind for notice in digests(session, world)] == ["daily_digest"]


def test_a_family_without_a_settings_row_is_treated_as_daily_with_all_items(session, world):
    record(session, world, at(MONDAY, 10), item="sleep")

    create_digests(session, at(MONDAY, 20))

    assert [notice.kind for notice in digests(session, world)] == ["daily_digest"]


def test_the_unique_rule_stops_the_same_digest_made_at_once(session, world):
    # run_jobs() と手で動かすコマンドが重なって、同じまとめを同時に作ろうとしたとき、
    # 2 つ目は DB の一意の決まりで断られる（先に digest_runs に書くので、お知らせは増えない）
    record(session, world, at(MONDAY, 10))
    resident_id = world.family.resident_id
    args = (
        session,
        world.family.id,
        resident_id,
        ["meal", "mood", "sleep"],
        True,  # notify_album
        "daily",
        at(MONDAY, 20),
    )

    assert digest._create_one(*args) is True
    with pytest.raises(IntegrityError), session.begin_nested():
        digest._create_one(*args)

    assert len(digests(session, world)) == 1


def test_one_family_failing_does_not_stop_the_others(session, world, make_family, monkeypatch):
    other = make_family(name="べつの入居者")
    session.add(
        CareRecord(
            resident_id=other.resident_id,
            date=MONDAY,
            item="meal",
            slot="lunch",
            value=VALUES["meal"][0],
            recorded_by=world.staff.id,
            recorded_at=at(MONDAY, 10),
        )
    )
    record(session, world, at(MONDAY, 10))
    real = digest._create_one

    def fail_for_the_first(session, family_account_id, *rest):
        if family_account_id == world.family.id:
            raise IntegrityError("x", {}, Exception("先に作られた"))
        return real(session, family_account_id, *rest)

    monkeypatch.setattr(digest, "_create_one", fail_for_the_first)

    create_digests(session, at(MONDAY, 20))

    assert digests(session, world) == []
    created = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.family_account_id == other.id, Notification.kind == "daily_digest")
    )
    assert created == 1


def test_an_unexpected_error_for_one_family_is_logged_and_the_others_continue(
    session, world, make_family, monkeypatch, caplog
):
    other = make_family(name="べつの入居者")
    session.add(
        CareRecord(
            resident_id=other.resident_id,
            date=MONDAY,
            item="meal",
            slot="lunch",
            value=VALUES["meal"][0],
            recorded_by=world.staff.id,
            recorded_at=at(MONDAY, 10),
        )
    )
    record(session, world, at(MONDAY, 10))
    real = digest._create_one

    def broken_for_the_first(session, family_account_id, *rest):
        if family_account_id == world.family.id:
            raise RuntimeError("ひみつのエラーの文面")
        return real(session, family_account_id, *rest)

    monkeypatch.setattr(digest, "_create_one", broken_for_the_first)
    caplog.set_level(logging.ERROR, logger="app")

    create_digests(session, at(MONDAY, 20))

    # 失敗した家族の分だけ、作られない。ほかの家族の分は、作られる
    assert digests(session, world) == []
    assert runs(session, world) == []
    created = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.family_account_id == other.id, Notification.kind == "daily_digest")
    )
    assert created == 1
    # ログには、家族の id・種類・エラーの種類だけ。エラーの文面（値が入りうる）は出さない
    assert f"family_account_id={world.family.id}" in caplog.text
    assert "kind=daily" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "ひみつのエラーの文面" not in caplog.text


# --- run_jobs() からの呼び出し ---


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


def _stub_run_jobs(monkeypatch, recorder: _Recorder) -> None:
    monkeypatch.setattr(run_module, "get_engine", lambda: None)
    monkeypatch.setattr(run_module, "Session", _fake_session)
    monkeypatch.setattr(
        run_module, "create_visit_reminders", lambda db, at: recorder.calls.append("reminders")
    )
    monkeypatch.setattr(run_module, "deliver_pending", lambda db: recorder.calls.append("mail"))


def test_run_jobs_makes_the_digests_before_sending_mail(monkeypatch):
    recorder = _Recorder()
    _stub_run_jobs(monkeypatch, recorder)
    monkeypatch.setattr(
        run_module, "create_digests", lambda db, at: recorder.calls.append("digests")
    )

    run_module.run_jobs()

    assert recorder.calls == ["reminders", "digests", "mail"]


def test_run_jobs_still_sends_mail_when_making_digests_fails(monkeypatch):
    recorder = _Recorder()
    _stub_run_jobs(monkeypatch, recorder)

    def broken(db, at):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_module, "create_digests", broken)

    run_module.run_jobs()

    assert recorder.calls == ["reminders", "mail"]


def test_the_time_can_be_given_by_hand(monkeypatch):
    import sys

    given: list[datetime | None] = []
    monkeypatch.setattr(run_module, "run_jobs", lambda at=None: given.append(at))
    monkeypatch.setattr(sys, "argv", ["digest", "--at", "2031-03-10T20:00:00+09:00"])
    monkeypatch.setattr("app.logging.configure_logging", lambda: None)

    digest.main()

    assert given == [at(MONDAY, 20)]


# ---- アルバムの写真（005-T025。FR-017〜019・SC-007） ----

ALBUM_TYPES = ("image/jpeg", "image/png")


@pytest.fixture
def add_photo(
    session: Session, world, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., AlbumPhoto]:
    """家族の入居者の写真を 1 枚、載せた状態にする（保存先は一時フォルダ）。"""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    def add(posted_at: datetime, comment: str | None = None) -> AlbumPhoto:
        saved = save_upload(
            session,
            data=fake_png(),
            purpose="album",
            uploaded_by=world.staff.id,
            allowed_types=ALBUM_TYPES,
        )
        photo = AlbumPhoto(
            resident_id=world.family.resident_id,
            file_id=saved.id,
            comment=comment,
            posted_by=world.staff.id,
            posted_at=posted_at,
        )
        session.add(photo)
        session.flush()
        return photo

    return add


def hide_album(session: Session, world) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world.facility.id,
            DisclosureSetting.target_type == "feature",
            DisclosureSetting.target_code == "album",
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(world.facility.id)


def test_a_day_with_only_photos_makes_a_digest_with_album(session, world, add_photo):
    add_photo(at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))

    [notice] = digests(session, world)
    assert notice.kind == "daily_digest"
    assert (notice.has_album, notice.has_records) == (True, False)
    assert [run.kind for run in runs(session, world)] == ["daily"]


def test_a_day_with_only_records_has_no_album(session, world, add_photo):
    record(session, world, at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))

    [notice] = digests(session, world)
    assert (notice.has_album, notice.has_records) == (False, True)


def test_records_and_photos_make_one_digest_with_both(session, world, add_photo):
    record(session, world, at(MONDAY, 10))
    add_photo(at(MONDAY, 11))

    create_digests(session, at(MONDAY, 20))

    [notice] = digests(session, world)
    assert (notice.has_album, notice.has_records) == (True, True)


def test_three_photos_make_only_one_notice(session, world, add_photo):
    for hour in (9, 10, 11):
        add_photo(at(MONDAY, hour))

    create_digests(session, at(MONDAY, 20))

    assert len(digests(session, world)) == 1


def test_a_photo_digest_made_twice_at_the_same_time_is_made_once(session, world, add_photo):
    add_photo(at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))
    create_digests(session, at(MONDAY, 20))

    assert len(digests(session, world)) == 1
    assert len(runs(session, world)) == 1


def test_a_deleted_photo_is_not_counted(session, world, add_photo):
    photo = add_photo(at(MONDAY, 10))
    photo.deleted_at = at(MONDAY, 12)
    photo.deleted_by = world.staff.id
    session.flush()

    create_digests(session, at(MONDAY, 20))

    assert digests(session, world) == []
    assert runs(session, world) == []


def test_a_photo_after_8pm_goes_into_the_next_digest(session, world, add_photo):
    add_photo(at(MONDAY, 21))

    create_digests(session, at(MONDAY, 22))  # 締めは 20:00 なので、21 時の写真は入らない
    assert digests(session, world) == []

    create_digests(session, at(TUESDAY, 20))
    [notice] = digests(session, world)
    assert notice.has_album is True


def test_no_records_and_no_photos_make_nothing_and_leave_no_run(session, world, add_photo):
    create_digests(session, at(MONDAY, 20))

    assert digests(session, world) == []
    assert runs(session, world) == []


def test_without_notify_album_photos_are_left_out(session, world, add_photo):
    set_settings(session, world, notify_album=False)
    add_photo(at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))
    assert digests(session, world) == []
    assert runs(session, world) == []

    record(session, world, at(MONDAY, 11))
    create_digests(session, at(MONDAY, 20))
    [notice] = digests(session, world)
    assert (notice.has_album, notice.has_records) == (False, True)


def test_a_hidden_album_leaves_photos_out(session, world, add_photo):
    hide_album(session, world)
    add_photo(at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))
    assert digests(session, world) == []
    assert runs(session, world) == []

    record(session, world, at(MONDAY, 11))
    create_digests(session, at(MONDAY, 20))
    [notice] = digests(session, world)
    assert (notice.has_album, notice.has_records) == (False, True)


def test_frequency_none_ignores_photos(session, world, add_photo):
    set_settings(session, world, frequency="none")
    add_photo(at(SUNDAY, 10))

    create_digests(session, at(SUNDAY, 20))

    assert digests(session, world) == []
    assert runs(session, world) == []


def test_a_weekly_family_counts_the_photos_of_the_week(session, world, add_photo):
    set_settings(session, world, frequency="weekly")
    add_photo(at(SUNDAY - timedelta(days=3), 10))

    create_digests(session, at(SUNDAY, 20))

    [notice] = digests(session, world)
    assert notice.kind == "weekly_digest"
    assert (notice.has_album, notice.has_records) == (True, False)


def test_the_mail_and_notice_have_no_photo_content(session, world, add_photo):
    photo = add_photo(at(MONDAY, 10), comment="とても楽しそうでした")

    create_digests(session, at(MONDAY, 20))

    email = session.get(User, world.family.user_id).email
    [outbox] = session.scalars(select(EmailOutbox).where(EmailOutbox.to_email == email)).all()
    # 渡すのは、言語・リンク・文面を選ぶ真偽だけ。写真・ファイル名・コメント・入居者名は入れない
    # （FR-019）
    assert set(outbox.params) <= {"lang", "link", "has_album", "has_records"}
    resident = session.get(Resident, world.family.resident_id)
    storage_key = session.get(UploadedFile, photo.file_id).storage_key
    text = str(outbox.params)
    secrets = ("とても楽しそうでした", resident.name, resident.name_kana, resident.name_romaji)
    for secret in (*secrets, storage_key):
        assert secret not in text
    [notice] = digests(session, world)
    assert photo.comment not in str(vars(notice))


def test_the_photo_digest_mail_is_built_from_the_stored_row(session, world, add_photo, monkeypatch):
    # 真偽値の params（has_album・has_records）が、DB（JSONB）を通っても壊れず、
    # 配る処理（build_message・deliver_pending）まで届くことを確かめる
    monkeypatch.setenv("MAIL_FROM", "no-reply@example.com")
    monkeypatch.setenv("APP_BASE_URL", "http://app.test")
    add_photo(at(MONDAY, 10))

    create_digests(session, at(MONDAY, 20))

    email = session.get(User, world.family.user_id).email
    session.expire_all()  # DB から読み直す
    [outbox] = session.scalars(select(EmailOutbox).where(EmailOutbox.to_email == email)).all()
    assert outbox.params["has_album"] is True
    assert outbox.params["has_records"] is False

    sent = []
    assert deliver_pending(session, ids=[outbox.id], send=sent.append) == 1
    assert sent[0]["Subject"] == "アルバムに新しい写真が載りました"
    assert outbox.sent_at is not None
