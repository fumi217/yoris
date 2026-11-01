"""職員の入居者一覧の API（001-T028・004-T030）のテスト。

tests/conftest.py の client・make_staff・make_family・login_as を使う
（本物のセッションでログインする）。
"""

from datetime import timedelta

import pytest

from app.clock import today_jst
from app.models.records import CareRecord


def _rows(client, **params):
    response = client.get("/api/staff/residents", params=params)
    assert response.status_code == 200
    return response.json()


def _row(data, resident_id):
    return next(row for row in data["residents"] if row["id"] == resident_id)


def _record(session, resident_id, staff_id, item, slot, value, day=None, deleted=False):
    record = CareRecord(
        resident_id=resident_id,
        date=day or today_jst(),
        item=item,
        slot=slot,
        value=value,
        recorded_by=staff_id,
    )
    session.add(record)
    session.flush()
    if deleted:
        record.deleted_at = record.recorded_at
        session.flush()


@pytest.mark.parametrize("role", ["care_worker", "leader", "counselor", "director"])
def test_recording_staff_can_open(client, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.get("/api/staff/residents").status_code == 200


def test_clerk_and_family_cannot_open(client, make_staff, make_family, login_as):
    # 事務員は職員の画面を開けない（spec 001 の contracts、PR #45）
    login_as(make_staff(role="clerk").user_id)
    assert client.get("/api/staff/residents").status_code == 403

    login_as(make_family().user_id)
    assert client.get("/api/staff/residents").status_code == 403


def test_not_logged_in_is_401(client):
    assert client.get("/api/staff/residents").status_code == 401


def test_shows_recorded_and_unrecorded(client, session, make_staff, make_family, login_as):
    staff = make_staff()
    family = make_family()
    resident_id = family.resident_id
    _record(session, resident_id, staff.id, "meal", "breakfast", "8")
    _record(session, resident_id, staff.id, "sleep", "day", "good")
    # 取り消した記録と、ほかの日の記録は数えない
    _record(session, resident_id, staff.id, "meal", "lunch", "5", deleted=True)
    _record(session, resident_id, staff.id, "mood", "day", "smile", day=today_jst() - timedelta(1))
    login_as(staff.user_id)

    data = _rows(client)
    row = _row(data, resident_id)

    assert data["date"] == today_jst().isoformat()
    assert row["meals"] == {"breakfast": True, "lunch": False, "dinner": False, "snack": False}
    assert (row["mood"], row["sleep"]) == (False, True)
    assert row["display_name"] == "テスト 花子"


def test_date_can_be_chosen(client, session, make_staff, make_family, login_as):
    staff = make_staff()
    family = make_family()
    yesterday = today_jst() - timedelta(days=1)
    _record(session, family.resident_id, staff.id, "mood", "day", "low", day=yesterday)
    login_as(staff.user_id)

    row = _row(_rows(client, date=yesterday.isoformat()), family.resident_id)

    assert row["mood"] is True


def test_residents_are_in_order_of_moving_in(client, make_staff, make_family, login_as):
    first = make_family(name="さき")
    second = make_family(name="あと")
    login_as(make_staff().user_id)

    ids = [row["id"] for row in _rows(client)["residents"]]

    # 入居の順（residents.id の小さい順。docs/画面設計.md の「4」）
    assert ids.index(first.resident_id) < ids.index(second.resident_id)


def test_waiting_messages_are_counted_per_resident(
    client, make_staff, make_family, login_as, monkeypatch
):
    family = make_family()
    staff = make_staff()
    calls = []

    def fake_count(session, user):
        calls.append(user.staff_id)
        return {family.resident_id: 2}

    # 件数の数え方（苦情の見え方など）は spec 004 のテストで確かめている。ここでは、つなぎ方だけ
    monkeypatch.setattr(
        "app.api.staff.residents.count_waiting_staff_messages_by_resident", fake_count
    )
    login_as(staff.user_id)

    data = _rows(client)

    assert _row(data, family.resident_id)["waiting_messages"] == 2
    # ログイン中の職員を渡して、1 回だけ数える（1 人ずつ数えない）
    assert calls == [staff.id]


def test_no_messages_means_zero(client, make_staff, make_family, login_as):
    family = make_family()
    login_as(make_staff().user_id)

    assert _row(_rows(client), family.resident_id)["waiting_messages"] == 0


def test_waiting_requests_are_counted(client, session, make_staff, make_family, login_as):
    from sqlalchemy import select

    from app.models.disclosure import Theme
    from app.models.requests import Request
    from app.seed.themes import add_themes

    add_themes(session)
    themes = session.scalars(select(Theme.id).order_by(Theme.sort_order)).all()
    family = make_family()
    other = make_family()
    session.add_all(
        [
            Request(resident_id=family.resident_id, theme_id=themes[0]),
            Request(resident_id=family.resident_id, theme_id=themes[1]),
            # 返事のついた・取り消したリクエストは数えない
            Request(resident_id=family.resident_id, theme_id=themes[2], status="answered"),
            Request(resident_id=family.resident_id, theme_id=themes[3], status="cancelled"),
        ]
    )
    session.flush()
    login_as(make_staff().user_id)

    data = _rows(client)

    assert _row(data, family.resident_id)["waiting_requests"] == 2
    assert _row(data, other.resident_id)["waiting_requests"] == 0
