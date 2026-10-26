"""リクエストのサンプル（001-T058）のテスト。DB を使う（なければ手元では飛ばす）。"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.clock import today_jst
from app.models.disclosure import Theme
from app.models.notifications import EmailOutbox, Notification
from app.models.replies import Reply
from app.models.requests import Request
from app.seed.requests import add_sample_requests
from app.seed.themes import add_themes
from app.services.disclosure import get_active_replies


def _themes(session, count=3) -> list[int]:
    base = session.scalar(select(func.coalesce(func.max(Theme.sort_order), 0))) + 1
    themes = [
        Theme(code=f"theme.seed_{base}_{n}", emoji="😊", sort_order=base + n) for n in range(count)
    ]
    session.add_all(themes)
    session.flush()
    return [theme.id for theme in themes]


def test_sample_without_staff_has_waiting_and_cancelled_only(session, make_family):
    family = make_family()

    added = add_sample_requests(
        session, resident_ids=[family.resident_id], theme_ids=_themes(session)
    )

    statuses = sorted(
        session.scalars(select(Request.status).where(Request.resident_id == family.resident_id))
    )
    assert added == 3
    assert statuses == ["cancelled", "waiting", "waiting"]


def test_sample_respects_the_rules(session, make_family):
    # 返事待ちは 3 件まで・同じテーマは 1 件まで。サンプルも決まりの中に収まる
    family = make_family()
    add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=_themes(session))

    waiting = list(
        session.scalars(
            select(Request).where(
                Request.resident_id == family.resident_id, Request.status == "waiting"
            )
        )
    )
    assert len(waiting) <= 3
    assert len({request.theme_id for request in waiting}) == len(waiting)


def test_sample_is_not_added_twice(session, make_family):
    family = make_family()
    theme_ids = _themes(session)
    add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=theme_ids)

    assert add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=theme_ids) == 0


def test_sample_needs_enough_themes(session, make_family):
    family = make_family()

    assert add_sample_requests(session, resident_ids=[family.resident_id], theme_ids=[1, 2]) == 0


# --- 返事あり（001-T058）---


def _real_theme_ids(session) -> list[int]:
    add_themes(session)
    return list(session.scalars(select(Theme.id).order_by(Theme.sort_order)))


def _replies_of(session, resident_id: int) -> list[Reply]:
    return list(
        session.scalars(
            select(Reply)
            .join(Request, Request.id == Reply.request_id)
            .where(Request.resident_id == resident_id)
        )
    )


def test_sample_with_staff_adds_an_answered_request_with_a_reply(session, make_family, make_staff):
    family = make_family()
    staff = make_staff()

    added = add_sample_requests(
        session,
        resident_ids=[family.resident_id],
        theme_ids=_real_theme_ids(session),
        staff_id=staff.id,
    )

    statuses = sorted(
        session.scalars(select(Request.status).where(Request.resident_id == family.resident_id))
    )
    assert added == 4
    assert statuses == ["answered", "cancelled", "waiting", "waiting"]
    reply = _replies_of(session, family.resident_id)[0]
    assert len(_replies_of(session, family.resident_id)) == 1
    assert reply.replied_by == staff.id
    assert 1 <= len(reply.template_ids) <= 2
    assert reply.read_at is None
    # 返事は、送った日（2 日前）の連絡帳に入る。今日の連絡帳でも、未読として一番上に出る
    assert reply.contact_book_date == today_jst() - timedelta(days=2)


def test_answered_sample_shows_as_an_unread_reply_and_notice(session, make_family, make_staff):
    family = make_family()
    staff = make_staff()
    outbox_before = session.scalar(select(func.count(EmailOutbox.id)))
    add_sample_requests(
        session,
        resident_ids=[family.resident_id],
        theme_ids=_real_theme_ids(session),
        staff_id=staff.id,
    )

    replies = get_active_replies(session, family.resident_id, date.min, date.max)
    notice = session.scalars(
        select(Notification).where(Notification.family_account_id == family.id)
    ).one()

    assert [reply.read for reply in replies] == [False]
    assert notice.kind == "reply"
    assert notice.family_account_id == family.id
    assert notice.read_at is None
    # メールは作らない（開発で、入居者の数だけメールが出ないように）
    assert session.scalar(select(func.count(EmailOutbox.id))) == outbox_before


def test_answered_sample_is_not_added_twice(session, make_family, make_staff):
    family = make_family()
    staff = make_staff()
    theme_ids = _real_theme_ids(session)
    add_sample_requests(
        session, resident_ids=[family.resident_id], theme_ids=theme_ids, staff_id=staff.id
    )

    again = add_sample_requests(
        session, resident_ids=[family.resident_id], theme_ids=theme_ids, staff_id=staff.id
    )

    assert again == 0
    assert len(_replies_of(session, family.resident_id)) == 1


def test_no_answered_sample_without_a_template(session, make_family, make_staff):
    # 定型文のないテーマ（テスト用に作ったもの）では、返事を作れないので、返事ありは足さない
    family = make_family()
    staff = make_staff()

    added = add_sample_requests(
        session,
        resident_ids=[family.resident_id],
        theme_ids=_themes(session, count=5),
        staff_id=staff.id,
    )

    assert added == 3


def test_answered_reply_date_does_not_depend_on_the_time_of_the_day(
    session, make_family, make_staff, monkeypatch
):
    # 日本時間の 22:00 に流しても、送った 3 時間後が翌日にならない（返事の日付がずれない）
    fixed = datetime(2026, 10, 26, 13, 0, tzinfo=UTC)  # 日本時間の 22:00
    monkeypatch.setattr("app.seed.requests.now", lambda: fixed)
    family = make_family()
    staff = make_staff()

    add_sample_requests(
        session,
        resident_ids=[family.resident_id],
        theme_ids=_real_theme_ids(session),
        staff_id=staff.id,
    )

    reply = _replies_of(session, family.resident_id)[0]
    assert reply.contact_book_date == date(2026, 10, 24)
    # 返事の時刻の日付（日本時間）と、連絡帳の日付が一致する（返事の日付は、返事をした日）
    assert today_jst(reply.replied_at) == reply.contact_book_date
