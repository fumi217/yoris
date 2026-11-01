"""記録の API（001-T027）のテスト（001-T024）。

ログイン中の人は、FastAPI の dependency_overrides で差し替えて渡す（Redis を使わずに済む）。
DB を使うテストは、tests/conftest.py の session を使う（テストごとに取り消す）。
"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_current_user
from app.clock import today_jst
from app.db import get_session
from app.main import create_app
from app.models.core import Facility, Resident, Staff, User
from app.models.records import CareRecord, CareRecordHistory

FETCH = {"X-Requested-With": "fetch"}


def _user(kind: str, role: str | None = None, staff_id: int | None = None) -> CurrentUser:
    return CurrentUser(
        user_id=1,
        kind=kind,
        role=role,
        staff_id=staff_id,
        resident_id=1 if kind == "family" else None,
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


def _body(**kwargs) -> dict:
    body = {"date": today_jst().isoformat(), "item": "meal", "slot": "lunch", "value": "8"}
    body.update(kwargs)
    return body


# --- DB を使わないテスト（CI でも動く） ---


@pytest.mark.parametrize(
    "user",
    [_user("family"), _user("staff", "clerk", staff_id=1)],
    ids=["family", "clerk"],
)
def test_family_and_clerk_cannot_record(user):
    response = _client(user).put("/api/staff/residents/1/records", json=_body(), headers=FETCH)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_not_logged_in_is_401():
    response = _client(None).put("/api/staff/residents/1/records", json=_body(), headers=FETCH)

    assert response.status_code == 401


def test_write_without_fetch_header_is_403():
    client = _client(_user("staff", "care_worker", staff_id=1))

    response = client.put("/api/staff/residents/1/records", json=_body())

    assert response.status_code == 403


# --- DB を使うテスト ---


@pytest.fixture
def setup(session: Session) -> dict:
    """架空の施設・入居者と、記録できる職員の client を作る。"""
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    resident = Resident(
        facility_id=facility.id,
        name="架空 花子",
        name_kana="かくう",
        name_romaji="Kaku",
        room="101",
    )
    user = User(kind="staff", login_id="s90001", password_hash="x")
    session.add_all([resident, user])
    session.flush()
    staff = Staff(
        user_id=user.id, facility_id=facility.id, display_name="職員1", role="care_worker"
    )
    session.add(staff)
    session.flush()
    client = _client(_user("staff", "care_worker", staff_id=staff.id), session)
    return {"client": client, "resident": resident.id, "staff": staff.id, "session": session}


def _put(setup: dict, resident_id: int | None = None, **kwargs):
    resident_id = resident_id or setup["resident"]
    return setup["client"].put(
        f"/api/staff/residents/{resident_id}/records", json=_body(**kwargs), headers=FETCH
    )


def test_record_is_saved(setup):
    response = _put(setup)

    assert response.status_code == 200
    data = response.json()
    assert (data["item"], data["slot"], data["value"]) == ("meal", "lunch", "8")
    record = setup["session"].get(CareRecord, data["id"])
    assert record.recorded_by == setup["staff"]


def test_pressing_again_overwrites_and_keeps_history(setup):
    first = _put(setup, value="8").json()
    second = _put(setup, value="5").json()

    # 同じ「入居者×日付×項目×区分」は 1 つだけ
    assert second["id"] == first["id"]
    assert second["value"] == "5"
    session = setup["session"]
    active = session.scalar(
        select(func.count())
        .select_from(CareRecord)
        .where(CareRecord.resident_id == setup["resident"], CareRecord.deleted_at.is_(None))
    )
    assert active == 1
    # 前の値が履歴に残る（FR-005）
    [history] = session.scalars(
        select(CareRecordHistory).where(CareRecordHistory.care_record_id == first["id"])
    ).all()
    assert (history.old_value, history.new_value) == ("8", "5")


def test_invalid_value_is_422(setup):
    response = _put(setup, item="mood", slot="day", value="8")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_date_out_of_range_is_422(setup):
    response = _put(setup, date=(today_jst() - timedelta(days=4)).isoformat())

    assert response.status_code == 422


def test_pressing_a_past_record_again_is_409(setup):
    yesterday = (today_jst() - timedelta(days=1)).isoformat()
    assert _put(setup, date=yesterday, value="8").status_code == 200

    response = _put(setup, date=yesterday, value="5")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_today"


def test_unknown_resident_is_404(setup):
    response = _put(setup, resident_id=999_999_999)

    assert response.status_code == 404


def test_extra_field_is_rejected(setup):
    # 入居者は URL で決める。本文に余分な項目があれば受け付けない
    response = _put(setup, resident_id_in_body=1)

    assert response.status_code == 422
