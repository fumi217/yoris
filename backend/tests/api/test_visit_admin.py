"""面会予約の施設側の API（003-T022〜T024）のテスト（003-T019）。

tests/conftest.py の client・session・facility・make_staff・make_family・login_as を使う。
時刻は app.clock.now を差し替えて、日本時間の 10/23 12:00 に固定する。
"""

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

from app.clock import JST
from app.models.visits import VisitClosedDay, VisitReservation, VisitStartTime
from app.seed.visits import add_visit_settings
from app.services.visit_rules import visit_range

AT = datetime(2026, 10, 23, 12, 0, tzinfo=JST).astimezone(UTC)
DAY = date(2026, 10, 28)


@pytest.fixture
def world(session, facility, make_staff, make_family, login_as, monkeypatch):
    monkeypatch.setattr("app.clock.now", lambda: AT)
    add_visit_settings(session, facility_id=facility.id)
    clerk = make_staff(role="clerk")
    login_as(clerk.user_id)
    return {
        "facility": facility,
        "clerk": clerk,
        "family": make_family(display_name="佐藤さんの母"),
    }


def _reserve(session, world, day=DAY, start=time(10, 0), resident_id=None) -> VisitReservation:
    starts_at, ends_at = visit_range(day, start)
    reservation = VisitReservation(
        facility_id=world["facility"].id,
        resident_id=resident_id or world["family"].resident_id,
        visit_date=day,
        start_time=start,
        starts_at=starts_at,
        ends_at=ends_at,
        party_size=2,
    )
    session.add(reservation)
    session.flush()
    return reservation


# --- 開始時刻の候補と、1 日の組数（FR-009） ---


def test_get_settings(client, world):
    data = client.get("/api/admin/visit-settings").json()

    assert data["daily_limit"] == 2
    assert data["start_times"][0] == "10:00:00"
    assert data["start_times"][-1] == "15:30:00"


def test_put_settings_keeps_existing_reservations(client, session, world):
    reservation = _reserve(session, world, start=time(10, 0))

    response = client.put(
        "/api/admin/visit-settings", json={"daily_limit": 3, "start_times": ["13:00", "14:00"]}
    )

    assert response.status_code == 200
    assert response.json() == {"daily_limit": 3, "start_times": ["13:00:00", "14:00:00"]}
    # 10:00 は候補から外れた（行は残し、active を false にする）
    ten = session.scalars(
        select(VisitStartTime).where(
            VisitStartTime.facility_id == world["facility"].id,
            VisitStartTime.start_time == time(10, 0),
        )
    ).one()
    assert ten.active is False
    # すでに入っている 10:00 の予約は、そのまま残る
    session.refresh(reservation)
    assert reservation.status == "booked"


@pytest.mark.parametrize(
    "body",
    [
        {"daily_limit": 2, "start_times": ["15:31"]},  # 30 分刻みでない
        {"daily_limit": 2, "start_times": ["16:00"]},  # 終わりが 17:30（17:00 を超える）
        {"daily_limit": 2, "start_times": ["09:30"]},  # 10:00 より前
        {"daily_limit": 0, "start_times": ["10:00"]},  # 組数は 1 以上
        {"daily_limit": 2, "start_times": []},  # 候補は 1 つ以上
    ],
)
def test_put_settings_rejects_out_of_rules(client, world, body):
    assert client.put("/api/admin/visit-settings", json=body).status_code == 422


# --- 休みの日（FR-010・R-08） ---


def test_close_and_open_a_day(client, session, world):
    response = client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()})

    assert response.status_code == 201
    closed = response.json()
    assert (closed["closed_date"], closed["cancelled"]) == (DAY.isoformat(), 0)
    listed = client.get(f"/api/admin/visit-closed-days?from={DAY}&to={DAY}").json()
    assert [row["id"] for row in listed] == [closed["id"]]

    assert client.delete(f"/api/admin/visit-closed-days/{closed['id']}").status_code == 204
    assert client.get(f"/api/admin/visit-closed-days?from={DAY}&to={DAY}").json() == []


def test_closing_a_day_with_reservations_needs_confirmation(client, session, world):
    reservation = _reserve(session, world)

    response = client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()})

    # 予約が入っていると、件数つきで 409（気づかずに休みにしないように）
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "visit_day_has_reservations"
    assert response.json()["error"]["details"] == {"count": 1}
    session.refresh(reservation)
    assert reservation.status == "booked"


def test_closing_with_confirm_cancels_reservations(client, session, world):
    reservation = _reserve(session, world)

    response = client.post(
        "/api/admin/visit-closed-days",
        json={"date": DAY.isoformat(), "confirm_cancel": True, "reason": "感染症の予防のため"},
    )

    assert response.status_code == 201
    assert response.json()["cancelled"] == 1
    session.refresh(reservation)
    # その日の予約は、職員の取り消しになる（理由と、取り消した職員が残る）
    assert reservation.status == "cancelled_by_staff"
    assert reservation.cancel_reason == "感染症の予防のため"
    assert reservation.cancelled_by_staff_id == world["clerk"].id


def test_confirm_without_reason_is_422(client, session, world):
    _reserve(session, world)

    response = client.post(
        "/api/admin/visit-closed-days", json={"date": DAY.isoformat(), "confirm_cancel": True}
    )

    assert response.status_code == 422


def test_closed_day_cannot_be_booked(client, session, world, login_as):
    client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()})
    login_as(world["family"].user_id)

    # 休みの日は、空きがすべて選べず、予約は 409（FR-010）
    days = client.get(f"/api/family/visits/availability?from={DAY}&to={DAY}").json()["days"]
    assert days[0]["closed"] is True
    assert not any(slot["selectable"] for slot in days[0]["start_times"])
    response = client.post(
        "/api/family/visits",
        json={"visit_date": DAY.isoformat(), "start_time": "10:00", "party_size": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "visit_closed_day"


def test_past_day_cannot_be_closed(client, world):
    response = client.post("/api/admin/visit-closed-days", json={"date": "2026-10-22"})

    assert response.status_code == 422


def test_closing_twice_returns_the_same_day(client, session, world):
    first = client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()}).json()
    second = client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()}).json()

    assert first["id"] == second["id"]
    count = len(
        session.scalars(
            select(VisitClosedDay).where(VisitClosedDay.facility_id == world["facility"].id)
        ).all()
    )
    assert count == 1


# --- 予約の一覧と、今日の面会予定（FR-011） ---


def test_reservation_list_for_all_staff(client, session, world, make_staff, login_as):
    reservation = _reserve(session, world)
    login_as(make_staff(role="care_worker").user_id)

    rows = client.get(f"/api/admin/visits?from={DAY}&to={DAY}").json()

    [row] = rows
    assert row["id"] == reservation.id
    assert row["resident_name"] == "佐藤さんの母"
    assert (row["party_size"], row["status"]) == (2, "booked")


def test_today_visits(client, session, world, make_staff, login_as):
    today = date(2026, 10, 23)
    reservation = _reserve(session, world, day=today, start=time(13, 0))
    _reserve(session, world, day=DAY)  # 今日でない予約は出ない
    login_as(make_staff(role="leader").user_id)

    rows = client.get("/api/staff/visits/today").json()

    assert [row["id"] for row in rows] == [reservation.id]


# --- 役割（R-06） ---


@pytest.mark.parametrize("role", ["care_worker", "leader"])
def test_settings_only_clerk_counselor_director(client, world, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.get("/api/admin/visit-settings").status_code == 403
    assert (
        client.post("/api/admin/visit-closed-days", json={"date": DAY.isoformat()}).status_code
        == 403
    )


def test_family_cannot_use_staff_visit_apis(client, world, login_as):
    login_as(world["family"].user_id)

    assert client.get("/api/admin/visit-settings").status_code == 403
    assert client.get(f"/api/admin/visits?from={DAY}&to={DAY}").status_code == 403
    assert client.get("/api/staff/visits/today").status_code == 403
