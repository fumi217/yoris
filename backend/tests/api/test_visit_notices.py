"""面会予約のお知らせ（003-T031・T032）のテスト（003-T028）。

予約の確定と施設からの取り消しで、家族へのお知らせとメールの送る予定が、
同じトランザクションで 1 件ずつできる。
tests/conftest.py の client・session・facility・make_staff・make_family・login_as を使う。
時刻は日本時間の 10/23 12:00 に固定する。メールを送る関数は差し替える（本物は送らない）。
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.clock import JST
from app.models.notifications import EmailOutbox, Notification
from app.models.visits import VisitReservation
from app.seed.visits import add_visit_settings

AT = datetime(2026, 10, 23, 12, 0, tzinfo=JST).astimezone(UTC)
DAY = date(2026, 10, 28)


@pytest.fixture(autouse=True)
def sent(monkeypatch) -> list[int]:
    """メールを送る関数を差し替える。呼ばれた email_outbox の id が入る。"""
    calls: list[int] = []
    monkeypatch.setattr("app.api.admin.visits.send_email_now", calls.append)
    monkeypatch.setattr("app.api.family.visits.send_email_now", calls.append)
    return calls


@pytest.fixture
def world(session, facility, make_staff, make_family, monkeypatch):
    monkeypatch.setattr("app.clock.now", lambda: AT)
    add_visit_settings(session, facility_id=facility.id)
    return {
        "family": make_family(display_name="佐藤さんの母"),
        "staff": make_staff(role="care_worker"),
    }


def _book(client, login_as, world) -> int:
    login_as(world["family"].user_id)
    response = client.post(
        "/api/family/visits",
        json={"visit_date": DAY.isoformat(), "start_time": "13:00", "party_size": 2},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _notices(session, reservation_id: int, kind: str) -> list[Notification]:
    return list(
        session.scalars(
            select(Notification).where(
                Notification.visit_reservation_id == reservation_id, Notification.kind == kind
            )
        )
    )


def _outbox(session, ids: list[int]) -> list[EmailOutbox]:
    return list(session.scalars(select(EmailOutbox).where(EmailOutbox.id.in_(ids))))


def test_booking_creates_a_confirmed_notice_and_mail(client, session, world, login_as, sent):
    reservation_id = _book(client, login_as, world)

    [notice] = _notices(session, reservation_id, "visit_confirmed")
    assert notice.family_account_id == world["family"].id
    [mail] = _outbox(session, sent)
    assert mail.template == "visit_confirmed"
    # メールに渡すのは日時（とリンク）だけ。入居者名は入れない（FR-014）
    assert set(mail.params) <= {"visit_at", "link"}
    assert "佐藤" not in str(mail.params)


def test_staff_cancel_creates_a_cancelled_notice_without_reason(
    client, session, world, login_as, sent
):
    reservation_id = _book(client, login_as, world)
    sent.clear()
    login_as(world["staff"].user_id)

    response = client.post(
        f"/api/admin/visits/{reservation_id}/cancel", json={"reason": "体調がすぐれないため"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled_by_staff"
    # 取り消した職員・日時・理由が残る（FR-012）
    reservation = session.get(VisitReservation, reservation_id)
    session.refresh(reservation)
    assert reservation.cancelled_by_staff_id == world["staff"].id
    assert reservation.cancelled_at is not None
    assert reservation.cancel_reason == "体調がすぐれないため"
    [notice] = _notices(session, reservation_id, "visit_cancelled")
    assert notice.family_account_id == world["family"].id
    [mail] = _outbox(session, sent)
    assert mail.template == "visit_cancelled"
    # メールに理由・入居者名は入れない（アプリの予約の画面で見せる。FR-014）
    assert "体調" not in str(mail.params)
    assert "佐藤" not in str(mail.params)


def test_script_in_reason_is_returned_as_text(client, session, world, login_as):
    reservation_id = _book(client, login_as, world)
    login_as(world["staff"].user_id)
    reason = "<script>alert(1)</script>"

    response = client.post(f"/api/admin/visits/{reservation_id}/cancel", json={"reason": reason})

    # 文字として、そのまま返る（画面でも文字としてだけ出す。FR-016）
    assert response.json()["cancel_reason"] == reason
    login_as(world["family"].user_id)
    [mine] = client.get("/api/family/visits").json()
    assert mine["cancel_reason"] == reason


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "あ" * 201}])
def test_staff_cancel_needs_a_reason(client, session, world, login_as, body):
    reservation_id = _book(client, login_as, world)
    login_as(world["staff"].user_id)

    assert client.post(f"/api/admin/visits/{reservation_id}/cancel", json=body).status_code == 422
    assert _notices(session, reservation_id, "visit_cancelled") == []


def test_failed_cancel_creates_no_notice(client, session, world, login_as):
    reservation_id = _book(client, login_as, world)
    login_as(world["staff"].user_id)
    assert (
        client.post(
            f"/api/admin/visits/{reservation_id}/cancel", json={"reason": "理由"}
        ).status_code
        == 200
    )

    # もう取り消した予約は 404。お知らせは増えない（取り消しが失敗したら、お知らせもできない）
    response = client.post(f"/api/admin/visits/{reservation_id}/cancel", json={"reason": "理由"})

    assert response.status_code == 404
    assert len(_notices(session, reservation_id, "visit_cancelled")) == 1


def test_family_cancel_creates_no_notice(client, session, world, login_as, sent):
    reservation_id = _book(client, login_as, world)
    sent.clear()

    assert client.delete(f"/api/family/visits/{reservation_id}").status_code == 204

    # 家族が自分で取り消したときは、お知らせを作らない（R-07）
    assert _notices(session, reservation_id, "visit_cancelled") == []
    assert sent == []


def test_closing_a_day_notifies_each_cancelled_family(
    client, session, world, login_as, make_staff, sent
):
    reservation_id = _book(client, login_as, world)
    sent.clear()
    login_as(make_staff(role="clerk").user_id)

    response = client.post(
        "/api/admin/visit-closed-days",
        json={"date": DAY.isoformat(), "confirm_cancel": True, "reason": "感染症の予防のため"},
    )

    # 休みにするために取り消した予約にも、施設が取り消したお知らせが届く（R-08）
    assert response.status_code == 201
    assert len(_notices(session, reservation_id, "visit_cancelled")) == 1
    assert len(sent) == 1


def test_staff_cancel_by_family_is_forbidden(client, session, world, login_as):
    reservation_id = _book(client, login_as, world)

    # 家族は、職員の取り消しの API を使えない
    response = client.post(f"/api/admin/visits/{reservation_id}/cancel", json={"reason": "理由"})

    assert response.status_code == 403
    count = session.scalar(
        select(func.count()).select_from(Notification).where(Notification.kind == "visit_cancelled")
    )
    assert count == 0


# --- 面会の画面を開いたら、面会のお知らせを読んだことにする（#272） ---

READ_URL = "/api/family/visits/notices/read"


def test_opening_visits_marks_visit_notices_read(client, session, world, login_as):
    reservation_id = _book(client, login_as, world)
    # 面会以外のお知らせ（まとめ）には触らない
    other_kind = Notification(family_account_id=world["family"].id, kind="daily_digest")
    session.add(other_kind)
    session.flush()

    response = client.post(READ_URL)

    assert response.status_code == 204
    [notice] = _notices(session, reservation_id, "visit_confirmed")
    session.refresh(notice)
    session.refresh(other_kind)
    assert notice.read_at is not None
    assert other_kind.read_at is None
    # 何度呼んでも同じ
    assert client.post(READ_URL).status_code == 204


def test_other_family_visit_notices_stay_unread(client, session, world, login_as, make_family):
    other = make_family(display_name="べつの入居者")
    login_as(other.user_id)
    response = client.post(
        "/api/family/visits",
        json={"visit_date": DAY.isoformat(), "start_time": "10:00", "party_size": 1},
    )
    assert response.status_code == 201
    other_reservation = response.json()["id"]

    login_as(world["family"].user_id)
    assert client.post(READ_URL).status_code == 204

    [notice] = _notices(session, other_reservation, "visit_confirmed")
    session.refresh(notice)
    assert notice.read_at is None


def test_staff_cannot_mark_visit_notices_read(client, world, login_as):
    login_as(world["staff"].user_id)

    assert client.post(READ_URL).status_code == 403
