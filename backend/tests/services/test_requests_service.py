"""リクエストの作成・取り消し・一覧（001-T049）のテスト。

DB と Redis を使う（conftest.py の session・redis。なければ手元では飛ばす）。
各テストは 1 つのトランザクションの中で動かし、最後に取り消す。
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.models.core import Facility, FamilyAccount
from app.models.disclosure import DisclosureSetting, Theme
from app.models.requests import Request
from app.services.requests import (
    AlreadyReplied,
    RequestLimit,
    RequestNotFound,
    ThemeNotAvailable,
    ThemeWaiting,
    cancel_request,
    create_request,
    is_overdue,
    list_requests,
)

# --- DB を使わないテスト ---


def test_overdue_after_three_days_only_while_waiting():
    created = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
    assert not is_overdue("waiting", created, created + timedelta(days=2, hours=23))
    assert is_overdue("waiting", created, created + timedelta(days=3))
    # 返事がついた・取り消したものには出さない
    assert not is_overdue("answered", created, created + timedelta(days=5))
    assert not is_overdue("cancelled", created, created + timedelta(days=5))


# --- DB を使うテスト ---


@pytest.fixture
def themes(session: Session, facility: Facility) -> list[Theme]:
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


@pytest.fixture(autouse=True)
def _clear_cache(redis):
    """開示設定のキャッシュ（Redis）を、テストの前後で空にする。"""


@pytest.fixture
def family(make_family) -> FamilyAccount:
    return make_family()


def _user(family: FamilyAccount) -> CurrentUser:
    return CurrentUser(
        user_id=family.user_id,
        kind="family",
        role=None,
        staff_id=None,
        resident_id=family.resident_id,
        language="ja",
        display_name="x",
    )


def test_request_is_created_as_waiting(session, family, themes):
    request = create_request(session, _user(family), themes[0].id)

    assert request.status == "waiting"
    assert request.resident_id == family.resident_id
    assert request.theme_id == themes[0].id


def test_fourth_waiting_request_is_refused(session, family, themes):
    user = _user(family)
    for theme in themes[:3]:
        create_request(session, user, theme.id)

    with pytest.raises(RequestLimit):
        create_request(session, user, themes[3].id)


def test_same_theme_cannot_wait_twice(session, family, themes):
    user = _user(family)
    create_request(session, user, themes[0].id)

    with pytest.raises(ThemeWaiting):
        create_request(session, user, themes[0].id)


def test_same_theme_is_allowed_again_after_cancel_or_reply(session, family, themes):
    user = _user(family)
    first = create_request(session, user, themes[0].id)
    cancel_request(session, user, first.id)
    second = create_request(session, user, themes[0].id)
    # 返事がついた（answered）あとも、同じテーマをまた送れる
    second.status = "answered"
    session.flush()

    third = create_request(session, user, themes[0].id)

    assert third.status == "waiting"


def test_answered_and_cancelled_do_not_count_toward_the_limit(session, family, themes):
    user = _user(family)
    a = create_request(session, user, themes[0].id)
    b = create_request(session, user, themes[1].id)
    create_request(session, user, themes[2].id)
    cancel_request(session, user, a.id)
    b.status = "answered"
    session.flush()

    assert create_request(session, user, themes[3].id).status == "waiting"
    assert create_request(session, user, themes[4].id).status == "waiting"


def test_theme_not_shown_cannot_be_requested(session, family, themes, facility):
    setting = session.scalars(
        select(DisclosureSetting).where(DisclosureSetting.target_code == themes[0].code)
    ).one()
    setting.visible = False
    session.flush()

    with pytest.raises(ThemeNotAvailable):
        create_request(session, _user(family), themes[0].id)


def test_unknown_theme_is_refused(session, family, themes):
    with pytest.raises(ThemeNotAvailable):
        create_request(session, _user(family), 999_999_999)


def test_cancel_only_before_the_reply(session, family, themes):
    user = _user(family)
    request = create_request(session, user, themes[0].id)
    request.status = "answered"
    session.flush()

    with pytest.raises(AlreadyReplied):
        cancel_request(session, user, request.id)


def test_cancel_sets_status_and_time(session, family, themes):
    user = _user(family)
    request = create_request(session, user, themes[0].id)

    cancelled = cancel_request(session, user, request.id)

    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None


def test_cancel_twice_is_harmless(session, family, themes):
    user = _user(family)
    request = create_request(session, user, themes[0].id)
    cancel_request(session, user, request.id)

    assert cancel_request(session, user, request.id).status == "cancelled"


def test_other_familys_request_is_not_found(session, make_family, themes):
    mine, other = make_family(), make_family()
    request = create_request(session, _user(other), themes[0].id)

    with pytest.raises(RequestNotFound):
        cancel_request(session, _user(mine), request.id)
    # ない id と同じ扱い
    with pytest.raises(RequestNotFound):
        cancel_request(session, _user(mine), 999_999_999)
    # 取り消されていない
    assert session.get(Request, request.id).status == "waiting"


def test_list_shows_theme_and_days(session, family, themes):
    user = _user(family)
    request = create_request(session, user, themes[0].id)
    request.created_at = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
    session.flush()

    [view] = list_requests(session, user, at=datetime(2026, 10, 23, 3, 0, tzinfo=UTC))

    assert view.theme_code == themes[0].code
    assert view.status == "waiting"
    assert view.days_ago == 3
    assert view.overdue is True


def test_list_keeps_theme_name_after_it_is_hidden(session, family, themes):
    # 送ったあとにテーマが非開示になっても、送ったリクエストの一覧にはテーマ名が出る
    user = _user(family)
    create_request(session, user, themes[0].id)
    setting = session.scalars(
        select(DisclosureSetting).where(DisclosureSetting.target_code == themes[0].code)
    ).one()
    setting.visible = False
    session.flush()

    [view] = list_requests(session, user)

    assert view.theme_code == themes[0].code


def test_list_is_only_my_residents_and_newest_first(session, make_family, themes):
    mine, other = make_family(), make_family()
    create_request(session, _user(other), themes[0].id)
    first = create_request(session, _user(mine), themes[1].id)
    second = create_request(session, _user(mine), themes[2].id)

    views = list_requests(session, _user(mine))

    assert [view.id for view in views] == [second.id, first.id]
