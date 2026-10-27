"""当日中の記録の取り消し（001-T034）のテスト。

tests/conftest.py の client・session・make_staff・make_family・login_as を使う
（本物のセッションでログインする）。
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.clock import today_jst
from app.models.records import CareRecord, CareRecordHistory
from app.services.disclosure import get_disclosed_records


@pytest.fixture
def world(session, make_staff, make_family, login_as):
    family = make_family()
    staff = make_staff(display_name="職員A")
    login_as(staff.user_id)
    return {"resident": family.resident_id, "staff": staff}


def _record(session, world, day=None, slot="lunch", value="8") -> CareRecord:
    record = CareRecord(
        resident_id=world["resident"],
        date=day or today_jst(),
        item="meal",
        slot=slot,
        value=value,
        recorded_by=world["staff"].id,
    )
    session.add(record)
    session.flush()
    return record


def _cancel(client, record_id):
    return client.delete(f"/api/staff/records/{record_id}")


def test_cancel_today_record(client, session, world):
    record = _record(session, world)

    assert _cancel(client, record.id).status_code == 204

    session.refresh(record)
    assert record.deleted_at is not None
    assert record.deleted_by == world["staff"].id
    # 前の値を履歴に残す（取り消しは new_value が空。FR-005）
    [history] = session.scalars(
        select(CareRecordHistory).where(CareRecordHistory.care_record_id == record.id)
    ).all()
    assert (history.old_value, history.new_value) == ("8", None)


def test_cancelled_record_is_not_shown(client, session, world):
    record = _record(session, world)
    _cancel(client, record.id)

    # 家族の連絡帳からも、職員の見返しからも消える（Edge Cases）
    assert get_disclosed_records(session, world["resident"], today_jst(), today_jst()) == []
    book = client.get(f"/api/staff/residents/{world['resident']}/contact-book").json()
    assert book["records"] == []
    residents = client.get("/api/staff/residents").json()["residents"]
    row = next(r for r in residents if r["id"] == world["resident"])
    assert row["meals"]["lunch"] is False


def test_can_record_again_after_cancel(client, session, world):
    record = _record(session, world)
    _cancel(client, record.id)

    response = client.put(
        f"/api/staff/residents/{world['resident']}/records",
        json={"date": today_jst().isoformat(), "item": "meal", "slot": "lunch", "value": "5"},
    )

    # 取り消したあとは、同じ欄に新しく付け直せる（一意制約は取り消していないものだけ。R-04）
    assert response.status_code == 200
    assert response.json()["id"] != record.id


def test_past_record_is_409_not_today(client, session, world):
    record = _record(session, world, day=today_jst() - timedelta(days=1))

    response = _cancel(client, record.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_today"


def test_unknown_or_already_cancelled_is_404(client, session, world):
    record = _record(session, world)
    assert _cancel(client, record.id).status_code == 204

    assert _cancel(client, record.id).status_code == 404
    assert _cancel(client, 999_999_999).status_code == 404


def test_clerk_and_family_cannot_cancel(client, session, world, make_staff, make_family, login_as):
    record = _record(session, world)

    login_as(make_staff(role="clerk").user_id)
    assert _cancel(client, record.id).status_code == 403

    login_as(make_family().user_id)
    assert _cancel(client, record.id).status_code == 403
