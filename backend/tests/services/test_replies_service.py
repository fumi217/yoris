"""返事の保存（001-T052）と、家族に出す返事の共通の関数（001-T054）のテスト。

ふつうのテストは tests/conftest.py の session を使う（テストごとに取り消す）。
2 人がほぼ同時に返事をするテストだけは、2 本のスレッドが本当に commit するので、
最後に作った行を消す。
"""

import threading
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clock import today_jst
from app.models.core import Facility, Resident, Staff, User
from app.models.disclosure import ReplyTemplate, Theme
from app.models.replies import Reply
from app.models.requests import Request
from app.seed.themes import add_themes
from app.services.disclosure import get_active_replies
from app.services.replies import AlreadyReplied, ReplyError, save_reply


def _theme(session: Session, code: str) -> Theme:
    return session.scalars(select(Theme).where(Theme.code == code)).one()


def _templates(session: Session, theme: Theme) -> list[int]:
    return list(
        session.scalars(
            select(ReplyTemplate.id)
            .where(ReplyTemplate.theme_id == theme.id)
            .order_by(ReplyTemplate.sort_order)
        )
    )


@pytest.fixture
def world(session, make_staff, make_family):
    add_themes(session)
    theme = _theme(session, "theme.daily_life")
    family = make_family()
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    return {
        "resident": family.resident_id,
        "request": request,
        "theme": theme,
        "staff": make_staff(display_name="職員A"),
        "templates": _templates(session, theme),
    }


def test_note_is_trimmed_and_empty_note_is_none(session, world):
    reply = save_reply(
        session,
        request_id=world["request"].id,
        staff_id=world["staff"].id,
        template_ids=[world["templates"][0], world["templates"][0]],
        note="   ",
    )

    # 同じ定型文を 2 回選んでも 1 つ。空の書き足しは None
    assert reply.template_ids == [world["templates"][0]]
    assert reply.note is None
    assert reply.contact_book_date == today_jst()


def test_active_replies_for_family(session, world):
    save_reply(
        session,
        request_id=world["request"].id,
        staff_id=world["staff"].id,
        template_ids=world["templates"][1::-1],  # 2 つ目 → 1 つ目の順に選ぶ
        note="今日は笑顔でした",
    )
    today = today_jst()

    [reply] = get_active_replies(session, world["resident"], today, today)

    assert reply.theme_code == "theme.daily_life"
    codes = dict(session.execute(select(ReplyTemplate.id, ReplyTemplate.code)).all())
    # 選んだ順のまま、定型文のコードを返す
    assert reply.template_codes == [codes[t] for t in world["templates"][1::-1]]
    assert reply.note == "今日は笑顔でした"
    assert reply.replied_by_name == "職員A"
    assert (reply.read, reply.edited) == (False, False)
    # 連絡帳の日付が期間の外なら返らない
    assert (
        get_active_replies(session, world["resident"], today + timedelta(1), today + timedelta(2))
        == []
    )


def test_active_replies_are_per_resident(session, world, make_family):
    save_reply(
        session,
        request_id=world["request"].id,
        staff_id=world["staff"].id,
        template_ids=world["templates"][:1],
    )
    other = make_family()
    today = today_jst()

    # ほかの入居者の返事は返らない
    assert get_active_replies(session, other.resident_id, today, today) == []


# --- 2 人がほぼ同時に返事をする（R-07。2 本のスレッドが本当に commit する） ---


@pytest.fixture
def committed(engine) -> Iterator[dict]:
    with Session(engine) as db:
        created_themes = not db.scalars(select(Theme).limit(1)).first()
        add_themes(db)
        theme = _theme(db, "theme.daily_life")
        facility = Facility(name="テスト施設（同時の返事）")
        db.add(facility)
        db.flush()
        resident = Resident(
            facility_id=facility.id, name="架空 同時", display_name="同時", room="900"
        )
        users = [User(kind="staff", login_id=f"s9{n}999", password_hash="x") for n in (8, 9)]
        db.add_all([resident, *users])
        db.flush()
        staff = [
            Staff(
                user_id=u.id, facility_id=facility.id, display_name=f"職員{n}", role="care_worker"
            )
            for n, u in enumerate(users)
        ]
        db.add_all(staff)
        db.flush()
        request = Request(resident_id=resident.id, theme_id=theme.id)
        db.add(request)
        db.commit()
        data = {
            "facility": facility.id,
            "resident": resident.id,
            "users": [u.id for u in users],
            "staff": [s.id for s in staff],
            "request": request.id,
            "templates": _templates(db, theme),
        }
    try:
        yield data
    finally:
        with Session(engine) as db:
            db.execute(delete(Reply).where(Reply.request_id == data["request"]))
            db.execute(delete(Request).where(Request.id == data["request"]))
            db.execute(delete(Staff).where(Staff.id.in_(data["staff"])))
            db.execute(delete(User).where(User.id.in_(data["users"])))
            db.execute(delete(Resident).where(Resident.id == data["resident"]))
            db.execute(delete(Facility).where(Facility.id == data["facility"]))
            if created_themes:
                db.execute(delete(ReplyTemplate))
                db.execute(delete(Theme))
            db.commit()


def test_simultaneous_replies_save_only_the_first(engine, committed):
    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def run(index: int) -> None:
        with Session(engine) as db:
            barrier.wait()
            try:
                reply = save_reply(
                    db,
                    request_id=committed["request"],
                    staff_id=committed["staff"][index],
                    template_ids=committed["templates"][index : index + 1],
                )
                db.commit()
                results[index] = reply.id
            except ReplyError as error:
                db.rollback()
                results[index] = error

    threads = [threading.Thread(target=run, args=(n,)) for n in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sum(isinstance(r, int) for r in results) == 1
    assert [type(r) for r in results if not isinstance(r, int)] == [AlreadyReplied]
    with Session(engine) as db:
        assert db.scalar(select(Request.status).where(Request.id == committed["request"])) == (
            "answered"
        )
