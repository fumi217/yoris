"""家族の面会予約の API（003-T011）のテスト（003-T006・T007）。

ログイン中の人は dependency_overrides で差し替える。時刻は app.clock.now を差し替えて固定する。
DB を使うテストは、tests/conftest.py の session を使う（テストごとに取り消す）。
同時の予約は tests/services/test_visits.py で、2 本のスレッドで確かめている。
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_current_user
from app.clock import JST
from app.db import get_session
from app.main import create_app
from app.models.core import Facility, Resident
from app.seed.visits import add_visit_settings

FETCH = {"X-Requested-With": "fetch"}
AT = datetime(2026, 10, 23, 12, 0, tzinfo=JST).astimezone(UTC)


def _user(kind: str, resident_id: int | None = None) -> CurrentUser:
    return CurrentUser(
        user_id=1,
        kind=kind,
        role="care_worker" if kind == "staff" else None,
        staff_id=1 if kind == "staff" else None,
        resident_id=resident_id,
        language="ja",
        display_name="x",
    )


def _client(user: CurrentUser | None, session: Session | None = None) -> TestClient:
    app = create_app()
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user

    def _session() -> Iterator[Session | None]:
        yield session

    app.dependency_overrides[get_session] = _session
    return TestClient(app)


BOOK = {"visit_date": "2026-10-28", "start_time": "10:30", "party_size": 2}


# --- DB を使わないテスト（CI でも動く） ---


def test_staff_cannot_use_family_api():
    client = _client(_user("staff"))

    assert client.post("/api/family/visits", json=BOOK, headers=FETCH).status_code == 403
    assert (
        client.get("/api/family/visits/availability?from=2026-10-26&to=2026-10-30").status_code
        == 403
    )


def test_not_logged_in_is_401():
    assert _client(None).post("/api/family/visits", json=BOOK, headers=FETCH).status_code == 401


def test_resident_in_body_is_rejected():
    # 入居者は送らせない（ログイン中の家族から決める。R-05）
    body = {**BOOK, "resident_id": 999}

    response = _client(_user("family", 1)).post("/api/family/visits", json=body, headers=FETCH)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_party_size_zero_is_422():
    body = {**BOOK, "party_size": 0}

    response = _client(_user("family", 1)).post("/api/family/visits", json=body, headers=FETCH)

    assert response.status_code == 422


# --- DB を使うテスト ---


@pytest.fixture
def clients(session: Session, monkeypatch) -> dict[str, TestClient]:
    monkeypatch.setattr("app.clock.now", lambda: AT)
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    add_visit_settings(session, facility_id=facility.id)
    residents = [
        Resident(facility_id=facility.id, name=f"架空 {n}", display_name=f"テスト{n}", room="101")
        for n in (1, 2, 3)
    ]
    session.add_all(residents)
    session.flush()
    return {
        name: _client(_user("family", r.id), session)
        for name, r in zip(("a", "b", "c"), residents, strict=True)
    }


def _post(client: TestClient, **kwargs):
    return client.post("/api/family/visits", json={**BOOK, **kwargs}, headers=FETCH)


def test_booking_is_confirmed(clients):
    response = _post(clients["a"])

    assert response.status_code == 201
    data = response.json()
    assert (data["visit_date"], data["start_time"], data["party_size"], data["status"]) == (
        "2026-10-28",
        "10:30:00",
        2,
        "booked",
    )


@pytest.mark.parametrize(
    ("first", "second", "code"),
    [
        (("a", "10:30"), ("b", "10:00"), "visit_overlap"),
        (("a", "10:00"), ("a", "14:00"), "visit_already_booked_day"),
    ],
)
def test_conflicts_are_409(clients, first, second, code):
    assert _post(clients[first[0]], start_time=first[1]).status_code == 201

    response = _post(clients[second[0]], start_time=second[1])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


def test_day_full_is_409(clients):
    _post(clients["a"], start_time="10:00")
    _post(clients["b"], start_time="13:00")

    response = _post(clients["c"], start_time="15:00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "visit_day_full"


def test_deadline_and_range(clients, monkeypatch):
    # 4 週間より先は 422
    assert _post(clients["a"], visit_date="2026-11-21").json()["error"]["code"] == (
        "visit_out_of_range"
    )
    # 前日 17 時を過ぎた明日の予約は 409
    monkeypatch.setattr(
        "app.clock.now", lambda: datetime(2026, 10, 23, 17, 0, tzinfo=JST).astimezone(UTC)
    )
    response = _post(clients["a"], visit_date="2026-10-24")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "visit_deadline_passed"


def test_availability_hides_other_families(clients):
    _post(clients["a"], start_time="10:30", party_size=5)

    response = clients["b"].get("/api/family/visits/availability?from=2026-10-28&to=2026-10-28")

    assert response.status_code == 200
    [day] = response.json()["days"]
    # 返すのは決まった項目だけ（ほかの家族の名前・入居者名・人数・選べない理由は入らない）
    assert set(day) == {"date", "closed", "mine", "start_times"}
    assert all(set(slot) == {"start_time", "selectable"} for slot in day["start_times"])
    assert day["mine"] is False
    selectable = {slot["start_time"]: slot["selectable"] for slot in day["start_times"]}
    assert selectable["10:00:00"] is False
    assert selectable["13:00:00"] is True


def test_availability_mine_and_full_day(clients):
    _post(clients["a"], start_time="10:00")
    _post(clients["b"], start_time="13:00")

    url = "/api/family/visits/availability?from=2026-10-28&to=2026-10-28"
    [mine] = clients["a"].get(url).json()["days"]
    [full] = clients["c"].get(url).json()["days"]

    assert mine["mine"] is True
    # 2 組入った日は、どれも選べない
    assert not any(slot["selectable"] for slot in full["start_times"])


# --- 自分の予約を見て取り消す（003-T015。User Story 2） ---


def _mine(client: TestClient) -> list[dict]:
    response = client.get("/api/family/visits")
    assert response.status_code == 200
    return response.json()


def _cancel(client: TestClient, reservation_id: int):
    return client.delete(f"/api/family/visits/{reservation_id}", headers=FETCH)


def test_my_reservations_are_only_mine(clients):
    mine = _post(clients["a"]).json()["id"]
    _post(clients["b"], start_time="13:00")

    rows = _mine(clients["a"])

    # 自分の入居者の予約だけ（FR-006・FR-015）
    assert [row["id"] for row in rows] == [mine]
    assert rows[0]["party_size"] == 2
    assert rows[0]["status"] == "booked"
    assert rows[0]["can_cancel"] is True
    assert rows[0]["cancel_reason"] is None


def test_cancel_before_deadline_frees_the_time(clients):
    reservation = _post(clients["a"]).json()["id"]

    assert _cancel(clients["a"], reservation).status_code == 204

    # 取り消した予約は、状態がわかるように一覧に残る
    [row] = _mine(clients["a"])
    assert (row["status"], row["can_cancel"]) == ("cancelled_by_family", False)
    # その時間がまた選べる（FR-007）
    assert _post(clients["b"]).status_code == 201


def test_cancel_after_deadline_is_409(clients, monkeypatch):
    # 10/23 12:00 に、翌日（10/24）の面会を予約する
    reservation = _post(clients["a"], visit_date="2026-10-24").json()["id"]
    # 前日（10/23）の 17 時を過ぎた
    monkeypatch.setattr(
        "app.clock.now", lambda: datetime(2026, 10, 23, 17, 1, tzinfo=JST).astimezone(UTC)
    )

    assert _mine(clients["a"])[0]["can_cancel"] is False
    response = _cancel(clients["a"], reservation)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "visit_deadline_passed"


def test_cancel_others_reservation_is_404(clients):
    reservation = _post(clients["a"]).json()["id"]

    # ほかの家族の予約の id は、ないものと同じ 404（存在するかも知らせない。SC-004）
    response = _cancel(clients["b"], reservation)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _cancel(clients["a"], 999_999_999).status_code == 404
    # A の予約は残っている
    assert _mine(clients["a"])[0]["status"] == "booked"


def test_cancel_twice_is_404(clients):
    reservation = _post(clients["a"]).json()["id"]
    assert _cancel(clients["a"], reservation).status_code == 204

    assert _cancel(clients["a"], reservation).status_code == 404


def test_staff_cancel_reason_is_returned_as_text(clients, session):
    from app.models.core import Staff, User
    from app.models.visits import VisitReservation

    reservation_id = _post(clients["a"]).json()["id"]
    user = User(kind="staff", login_id="s99901", password_hash="x")
    session.add(user)
    session.flush()
    reservation = session.get(VisitReservation, reservation_id)
    staff = Staff(
        user_id=user.id, facility_id=reservation.facility_id, display_name="職員", role="clerk"
    )
    session.add(staff)
    session.flush()
    reservation.status = "cancelled_by_staff"
    reservation.cancelled_by_staff_id = staff.id
    reservation.cancel_reason = "<b>感染症</b>のため"
    session.flush()

    [row] = _mine(clients["a"])

    # 施設が取り消した理由は、文字としてそのまま返る（画面でも文字としてだけ出す。FR-016）
    assert row["status"] == "cancelled_by_staff"
    assert row["cancel_reason"] == "<b>感染症</b>のため"
    assert row["can_cancel"] is False


def test_past_reservations_are_not_listed(clients, monkeypatch):
    _post(clients["a"])
    # 面会の日（10/28）を過ぎた
    monkeypatch.setattr(
        "app.clock.now", lambda: datetime(2026, 10, 29, 9, 0, tzinfo=JST).astimezone(UTC)
    )

    assert _mine(clients["a"]) == []
