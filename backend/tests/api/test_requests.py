"""家族の「知りたいこと」の API（001-T050）のテスト（001-T043）。

DB と Redis を使う（conftest.py の client・session・redis・make_family・login_as。
なければ手元では飛ばす）。ログインは、本物のセッション（Redis）を作って行う。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Facility
from app.models.disclosure import DisclosureSetting, Theme
from app.services.disclosure import clear_disclosure_cache


@pytest.fixture
def themes(session: Session, facility: Facility, redis) -> list[Theme]:
    """テーマを 5 つ作り、すべて見せる設定にする（テストの中だけ。最後に取り消される）。"""
    base = session.scalar(select(func.coalesce(func.max(Theme.sort_order), 0))) + 1
    made = [Theme(code=f"theme.test_{base}_{n}", emoji="😊", sort_order=base + n) for n in range(5)]
    session.add_all(made)
    session.flush()
    for theme in made:
        session.add(
            DisclosureSetting(
                facility_id=facility.id, target_type="theme", target_code=theme.code, visible=True
            )
        )
    session.flush()
    return made


@pytest.fixture
def family_client(client: TestClient, make_family, login_as) -> TestClient:
    login_as(make_family().user_id)
    return client


# --- ログイン・役割 ---


def test_not_logged_in_is_401(client):
    assert client.get("/api/family/themes").status_code == 401
    assert client.get("/api/family/requests").status_code == 401
    assert client.post("/api/family/requests", json={"theme_id": 1}).status_code == 401


def test_staff_cannot_use_the_family_api(client, make_staff, login_as, themes):
    login_as(make_staff("care_worker").user_id)

    assert client.get("/api/family/themes").status_code == 403
    assert client.post("/api/family/requests", json={"theme_id": themes[0].id}).status_code == 403


# --- テーマ ---


def test_themes_are_only_the_shown_ones(family_client, session, themes, facility):
    setting = session.scalars(
        select(DisclosureSetting).where(DisclosureSetting.target_code == themes[1].code)
    ).one()
    setting.visible = False
    session.flush()
    # 開示設定のキャッシュだけを消す（ログインのセッションも同じ Redis にあるので、全部は消さない）
    clear_disclosure_cache(facility.id)

    response = family_client.get("/api/family/themes")

    codes = {theme["code"] for theme in response.json()}
    assert response.status_code == 200
    assert themes[0].code in codes
    assert themes[1].code not in codes


# --- 送る ---


def test_request_is_created(family_client, themes):
    response = family_client.post("/api/family/requests", json={"theme_id": themes[0].id})

    assert response.status_code == 201
    data = response.json()
    assert data["theme_id"] == themes[0].id
    assert data["status"] == "waiting"
    assert data["days_ago"] == 0
    assert data["overdue"] is False


def test_fourth_request_is_409_request_limit(family_client, themes):
    for theme in themes[:3]:
        assert (
            family_client.post("/api/family/requests", json={"theme_id": theme.id}).status_code
            == 201
        )

    response = family_client.post("/api/family/requests", json={"theme_id": themes[3].id})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "request_limit"


def test_same_theme_is_409_theme_waiting(family_client, themes):
    family_client.post("/api/family/requests", json={"theme_id": themes[0].id})

    response = family_client.post("/api/family/requests", json={"theme_id": themes[0].id})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "theme_waiting"


def test_hidden_or_unknown_theme_is_422(family_client, themes):
    response = family_client.post("/api/family/requests", json={"theme_id": 999_999_999})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_resident_in_the_body_is_refused(family_client, themes):
    # 入居者は、ログイン中の家族から決める。本文に余分な項目があれば受け付けない
    response = family_client.post(
        "/api/family/requests", json={"theme_id": themes[0].id, "resident_id": 1}
    )

    assert response.status_code == 422


def test_write_without_fetch_header_is_403(family_client, themes):
    headers = {"X-Requested-With": ""}
    response = family_client.post(
        "/api/family/requests", json={"theme_id": themes[0].id}, headers=headers
    )

    assert response.status_code == 403


# --- 一覧 ---


def test_list_has_my_requests_only(client, make_family, login_as, themes):
    mine, other = make_family(), make_family()
    login_as(other.user_id)
    client.post("/api/family/requests", json={"theme_id": themes[0].id})
    login_as(mine.user_id)
    client.post("/api/family/requests", json={"theme_id": themes[1].id})

    response = client.get("/api/family/requests")

    assert response.status_code == 200
    assert [r["theme_id"] for r in response.json()] == [themes[1].id]


# --- 取り消す ---


def test_cancel_before_the_reply(family_client, themes):
    created = family_client.post("/api/family/requests", json={"theme_id": themes[0].id}).json()

    response = family_client.delete(f"/api/family/requests/{created['id']}")

    assert response.status_code == 204
    [listed] = family_client.get("/api/family/requests").json()
    assert listed["status"] == "cancelled"


def test_cannot_cancel_other_familys_request(client, make_family, login_as, themes):
    mine, other = make_family(), make_family()
    login_as(other.user_id)
    created = client.post("/api/family/requests", json={"theme_id": themes[0].id}).json()
    login_as(mine.user_id)

    response = client.delete(f"/api/family/requests/{created['id']}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cannot_cancel_after_the_reply(family_client, session, themes):
    from app.models.requests import Request

    created = family_client.post("/api/family/requests", json={"theme_id": themes[0].id}).json()
    session.get(Request, created["id"]).status = "answered"
    session.flush()

    response = family_client.delete(f"/api/family/requests/{created['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_replied"


# --- 返事が入った連絡帳の日付（reply_date。#403） ---


def _answer(session, request_id: int, staff_id: int, contact_book_date) -> None:
    """リクエストに返事を付けて、answered にする（職員の返事の保存と同じ形）。"""
    from sqlalchemy import select as _select

    from app.models.disclosure import ReplyTemplate
    from app.models.replies import Reply
    from app.models.requests import Request

    request = session.get(Request, request_id)
    template_id = session.scalars(
        _select(ReplyTemplate.id).where(ReplyTemplate.theme_id == request.theme_id)
    ).first()
    if template_id is None:
        template_id = session.scalars(_select(ReplyTemplate.id)).first()
    session.add(
        Reply(
            request_id=request_id,
            template_ids=[template_id],
            note=None,
            replied_by=staff_id,
            contact_book_date=contact_book_date,
        )
    )
    request.status = "answered"
    session.flush()


def test_list_has_the_reply_date_only_for_answered_requests(
    client, make_family, make_staff, login_as, session, themes
):
    from datetime import date

    family = make_family()
    staff = make_staff("care_worker")
    login_as(family.user_id)
    waiting = client.post("/api/family/requests", json={"theme_id": themes[0].id}).json()
    answered = client.post("/api/family/requests", json={"theme_id": themes[1].id}).json()
    cancelled = client.post("/api/family/requests", json={"theme_id": themes[2].id}).json()
    client.delete(f"/api/family/requests/{cancelled['id']}")
    # 返事が入った日は、今日より前（過去の連絡帳）。リクエストは、その前に送ったことにする
    from datetime import UTC, datetime

    from app.models.requests import Request

    session.get(Request, answered["id"]).created_at = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)
    reply_day = date(2026, 10, 20)
    _answer(session, answered["id"], staff.id, reply_day)

    rows = {row["id"]: row for row in client.get("/api/family/requests").json()}

    assert rows[answered["id"]]["reply_date"] == "2026-10-20"
    assert rows[waiting["id"]]["reply_date"] is None
    assert rows[cancelled["id"]]["reply_date"] is None
    assert rows[answered["id"]]["status"] == "answered"


def test_reply_date_is_not_shown_for_other_familys_requests(
    client, make_family, make_staff, login_as, session, themes
):
    from datetime import UTC, date, datetime

    from app.models.requests import Request

    mine = make_family()
    other = make_family()
    staff = make_staff("care_worker")
    login_as(other.user_id)
    theirs = client.post("/api/family/requests", json={"theme_id": themes[0].id}).json()
    session.get(Request, theirs["id"]).created_at = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)
    _answer(session, theirs["id"], staff.id, date(2026, 10, 21))

    login_as(mine.user_id)
    rows = client.get("/api/family/requests").json()

    # 自分の一覧に、ほかの家族のリクエストも返事の日付も出ない
    assert rows == []
