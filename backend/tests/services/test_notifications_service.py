"""返事のお知らせとメールの送る予定（001-T051）のテスト。

ふつうのテストは tests/conftest.py の session を使う（テストごとに取り消す）。
"""

import json
from datetime import UTC, date, datetime, time
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.core import FamilyAccount, User
from app.models.disclosure import ReplyTemplate, Theme
from app.models.inquiry import InquiryConversation, InquiryMessage, StaffMessage
from app.models.notifications import EmailOutbox, Notification, NotificationSetting
from app.models.requests import Request
from app.models.visits import VisitReservation
from app.seed.themes import add_themes
from app.services.notifications import (
    create_reply_notice,
    create_staff_message_reply_notice,
    create_visit_notice,
)
from app.services.replies import save_reply

NOTE = "ひみつの書き足しの文"


@pytest.fixture
def world(session: Session, make_staff, make_family):
    add_themes(session)
    theme = session.scalars(select(Theme).where(Theme.code == "theme.daily_life")).one()
    template_ids = list(
        session.scalars(select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id))
    )
    staff = make_staff(display_name="ひみつの職員名")
    family = make_family(display_name="ひみつの入居者名")
    other_family = make_family(display_name="べつの入居者")
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    reply = save_reply(
        session,
        request_id=request.id,
        staff_id=staff.id,
        template_ids=template_ids[:2],
        note=NOTE,
    )
    return {"family": family, "other_family": other_family, "reply": reply}


def test_makes_nothing_when_the_family_turned_reply_notices_off(session, world):
    # 通知設定で「知りたいことへの返事」を外している家族（FR-023）。連絡帳の返事は、通知とは別
    session.add(NotificationSetting(family_account_id=world["family"].id, notify_reply=False))
    session.flush()

    assert create_reply_notice(session, world["reply"].id) is None

    assert session.scalars(select(Notification)).all() == []
    assert session.scalars(select(EmailOutbox)).all() == []


def test_makes_the_notice_when_the_setting_row_says_yes_or_is_missing(session, world):
    # 行がなくても（初めの設定）、行が「通知する」でも、作る。頻度の設定には、かかわらない
    session.add(
        NotificationSetting(
            family_account_id=world["family"].id, notify_reply=True, frequency="none"
        )
    )
    session.flush()

    assert create_reply_notice(session, world["reply"].id) is not None
    assert len(session.scalars(select(Notification)).all()) == 1


def test_creates_notification_and_outbox_for_the_family(session, world):
    outbox_id = create_reply_notice(session, world["reply"].id)

    notification = session.scalars(select(Notification)).one()
    assert notification.kind == "reply"
    assert notification.reply_id == world["reply"].id
    assert notification.family_account_id == world["family"].id
    assert notification.read_at is None

    outbox = session.get(EmailOutbox, outbox_id)
    assert outbox is not None
    assert outbox.template == "reply"
    assert outbox.sent_at is None
    assert outbox.to_email.endswith("@example.test")


def test_returns_the_outbox_id(session, world):
    outbox_id = create_reply_notice(session, world["reply"].id)

    assert isinstance(outbox_id, int)
    assert session.scalars(select(EmailOutbox.id)).one() == outbox_id


def _app_url(monkeypatch: pytest.MonkeyPatch, url: str | None) -> None:
    """アプリの URL（APP_BASE_URL）を、このテストの中だけ決める。"""
    monkeypatch.setattr(
        "app.services.notifications.get_settings", lambda: SimpleNamespace(app_base_url=url)
    )


def test_outbox_params_have_only_the_link(session, world, monkeypatch):
    _app_url(monkeypatch, "http://app.test")
    outbox_id = create_reply_notice(session, world["reply"].id)

    params = session.get(EmailOutbox, outbox_id).params
    assert params == {"lang": "ja", "link": "http://app.test/family"}
    # 返事の中身・職員の名前・入居者の名前は、メールの材料に入らない（SC-010）
    text = json.dumps(params, ensure_ascii=False)
    for secret in (NOTE, "ひみつの職員名", "ひみつの入居者名"):
        assert secret not in text


def test_no_link_when_the_app_url_is_not_set(session, world, monkeypatch):
    # リンクを入れないと、メールの文面の側が、アプリの URL に戻る（開けないリンクにならない）
    _app_url(monkeypatch, None)
    outbox_id = create_reply_notice(session, world["reply"].id)

    assert session.get(EmailOutbox, outbox_id).params == {"lang": "ja"}


def _set_language(session, family_id, language):
    family = session.get(FamilyAccount, family_id)
    session.get(User, family.user_id).language = language
    session.flush()


@pytest.mark.parametrize("language", ["id", "en"])
def test_reply_notice_carries_the_family_language(session, world, monkeypatch, language):
    # メールは家族の表示言語で送る（001-T084）。言語は params に入れる
    _app_url(monkeypatch, "http://app.test")
    _set_language(session, world["family"].id, language)

    outbox_id = create_reply_notice(session, world["reply"].id)

    assert session.get(EmailOutbox, outbox_id).params["lang"] == language


@pytest.mark.parametrize(
    ("language", "expected"),
    [("id", "Sen, 26 Okt 13:00"), ("en", "Mon, Oct 26 13:00")],
)
def test_visit_notice_writes_the_date_in_the_family_language(
    session, visit_world, monkeypatch, language, expected
):
    _app_url(monkeypatch, "http://app.test")
    _set_language(session, visit_world["family"].id, language)

    outbox_id = create_visit_notice(session, visit_world["reservation"].id, "visit_confirmed")

    params = session.get(EmailOutbox, outbox_id).params
    assert params["lang"] == language
    assert params["visit_at"] == expected


def test_other_family_gets_nothing(session, world):
    create_reply_notice(session, world["reply"].id)

    families = set(session.scalars(select(Notification.family_account_id)))
    assert families == {world["family"].id}
    assert world["other_family"].id not in families


def test_does_not_commit(session, world):
    # 呼んだ API が最後に 1 回だけ commit する。ここでは、まだ確定していない（flush だけ）
    create_reply_notice(session, world["reply"].id)

    assert session.in_transaction()
    session.rollback()
    assert session.scalars(select(Notification)).first() is None
    assert session.scalars(select(EmailOutbox)).first() is None


# --- 職員の返事（問い合わせ AI のメッセージへの返事。004-T028）---


@pytest.fixture
def message_world(session: Session, make_family):
    """家族 2 組と、1 組目の入居者についての、職員に渡したメッセージ。"""
    family = make_family(display_name="ひみつの入居者名")
    other_family = make_family(display_name="べつの入居者")
    conversation = InquiryConversation(family_account_id=family.id, resident_id=family.resident_id)
    session.add(conversation)
    session.flush()
    origin = InquiryMessage(
        conversation_id=conversation.id, sender="family", body="ひみつの質問の文"
    )
    session.add(origin)
    session.flush()
    message = StaffMessage(
        conversation_id=conversation.id,
        resident_id=family.resident_id,
        origin_message_id=origin.id,
        category="other",
        summary="ひみつの要約",
    )
    session.add(message)
    session.flush()
    return {"family": family, "other_family": other_family, "message": message}


def test_staff_message_reply_notice_for_the_family(session, message_world, monkeypatch):
    _app_url(monkeypatch, "http://app.test")

    outbox_id = create_staff_message_reply_notice(session, message_world["message"].id)

    notice = session.scalars(
        select(Notification).where(Notification.staff_message_id == message_world["message"].id)
    ).one()
    assert notice.kind == "staff_message_reply"
    assert notice.reply_id is None
    assert notice.family_account_id == message_world["family"].id
    assert notice.read_at is None
    outbox = session.get(EmailOutbox, outbox_id)
    assert outbox is not None
    assert isinstance(outbox_id, int)
    assert outbox.template == "staff_message_reply"
    assert outbox.sent_at is None
    assert outbox.to_email.endswith("@example.test")
    # 渡すのはリンクと言語だけ（「お問い合わせ」の画面へ）。質問・要約・入居者名は入らない（SC-010）
    assert outbox.params == {"lang": "ja", "link": "http://app.test/family/inquiry"}
    text = json.dumps(outbox.params, ensure_ascii=False)
    for secret in ("ひみつの質問の文", "ひみつの要約", "ひみつの入居者名"):
        assert secret not in text


def test_staff_message_reply_notice_has_no_link_without_the_app_url(
    session, message_world, monkeypatch
):
    _app_url(monkeypatch, None)

    outbox_id = create_staff_message_reply_notice(session, message_world["message"].id)

    assert session.get(EmailOutbox, outbox_id).params == {"lang": "ja"}


def test_staff_message_reply_notice_goes_only_to_that_family(session, message_world):
    create_staff_message_reply_notice(session, message_world["message"].id)

    families = set(session.scalars(select(Notification.family_account_id)))
    assert message_world["other_family"].id not in families


def test_staff_message_reply_notice_does_not_commit(session, message_world):
    create_staff_message_reply_notice(session, message_world["message"].id)

    session.rollback()
    assert session.scalars(select(Notification)).first() is None
    assert session.scalars(select(EmailOutbox)).first() is None


# --- 面会予約のお知らせ（003-T030）---


@pytest.fixture
def visit_world(session: Session, facility, make_family):
    """家族 2 組と、1 組目の入居者の面会予約（2026-10-26 月曜 13:00。職員が取り消した理由つき）。"""
    family = make_family(display_name="ひみつの入居者名")
    other_family = make_family(display_name="べつの入居者")
    reservation = VisitReservation(
        facility_id=facility.id,
        resident_id=family.resident_id,
        visit_date=date(2026, 10, 26),
        start_time=time(13, 0),
        starts_at=datetime(2026, 10, 26, 4, 0, tzinfo=UTC),
        ends_at=datetime(2026, 10, 26, 5, 30, tzinfo=UTC),
        party_size=2,
        cancel_reason="ひみつの取り消しの理由",
    )
    session.add(reservation)
    session.flush()
    return {"family": family, "other_family": other_family, "reservation": reservation}


@pytest.mark.parametrize("kind", ["visit_confirmed", "visit_cancelled", "visit_reminder"])
def test_visit_notice_for_the_family(session, visit_world, kind, monkeypatch):
    _app_url(monkeypatch, "http://app.test")

    outbox_id = create_visit_notice(session, visit_world["reservation"].id, kind)

    notice = session.scalars(
        select(Notification).where(
            Notification.visit_reservation_id == visit_world["reservation"].id
        )
    ).one()
    assert notice.kind == kind
    assert notice.family_account_id == visit_world["family"].id
    assert notice.read_at is None
    outbox = session.get(EmailOutbox, outbox_id)
    assert outbox is not None
    assert isinstance(outbox_id, int)
    assert outbox.template == kind
    assert outbox.sent_at is None
    assert outbox.to_email.endswith("@example.test")
    # 渡すのは、面会の日時とリンクと言語だけ（FR-014）
    assert outbox.params == {
        "lang": "ja",
        "visit_at": "10月26日（月）13:00",
        "link": "http://app.test/family/visits",
    }


def test_visit_notice_has_no_resident_name_or_reason(session, visit_world, monkeypatch):
    _app_url(monkeypatch, "http://app.test")

    outbox_id = create_visit_notice(session, visit_world["reservation"].id, "visit_cancelled")

    text = json.dumps(session.get(EmailOutbox, outbox_id).params, ensure_ascii=False)
    for secret in ("ひみつの入居者名", "ひみつの取り消しの理由"):
        assert secret not in text


def test_visit_notice_has_no_link_without_the_app_url(session, visit_world, monkeypatch):
    _app_url(monkeypatch, None)

    outbox_id = create_visit_notice(session, visit_world["reservation"].id, "visit_confirmed")

    assert session.get(EmailOutbox, outbox_id).params == {
        "lang": "ja",
        "visit_at": "10月26日（月）13:00",
    }


def test_confirmed_then_cancelled_are_both_allowed(session, visit_world):
    create_visit_notice(session, visit_world["reservation"].id, "visit_confirmed")
    create_visit_notice(session, visit_world["reservation"].id, "visit_cancelled")

    kinds = sorted(session.scalars(select(Notification.kind)))
    assert kinds == ["visit_cancelled", "visit_confirmed"]


def test_reminder_is_only_once_per_reservation(session, visit_world):
    create_visit_notice(session, visit_world["reservation"].id, "visit_reminder")

    # 前日の知らせは、同じ予約に 2 回送らない（20 時台に何度呼ばれても増えない）
    with pytest.raises(IntegrityError):
        create_visit_notice(session, visit_world["reservation"].id, "visit_reminder")
        session.flush()


def test_visit_notice_goes_only_to_that_family(session, visit_world):
    create_visit_notice(session, visit_world["reservation"].id, "visit_confirmed")

    families = set(session.scalars(select(Notification.family_account_id)))
    assert visit_world["other_family"].id not in families


def test_visit_notice_does_not_commit(session, visit_world):
    create_visit_notice(session, visit_world["reservation"].id, "visit_confirmed")

    session.rollback()
    assert session.scalars(select(Notification)).first() is None
    assert session.scalars(select(EmailOutbox)).first() is None


def test_visit_notice_rejects_other_kinds(session, visit_world):
    with pytest.raises(ValueError):
        create_visit_notice(session, visit_world["reservation"].id, "reply")
