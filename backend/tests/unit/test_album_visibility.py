"""家族に出すアルバムの写真の共通の関数（005-T004）のテスト（005-T006）。

DB と Redis は、tests/conftest.py の session と redis（テスト用の 15 番）を使う。
DB はテストごとに取り消し、Redis はテストの前後で空にする。写真は、テストの中で作った
小さな架空の画像だけを使う（実在の人物の写真は使わない）。
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.album import AlbumPhoto
from app.models.core import Facility, Resident, Staff, User
from app.models.disclosure import DisclosureSetting
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.album import (
    MAX_PAGE_SIZE,
    can_family_view_photo,
    count_new_photos,
    get_visible_album_photos,
)
from app.services.disclosure import clear_disclosure_cache
from app.services.uploads import save_upload
from tests.helpers.images import fake_png

START = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
ALBUM_TYPES = ("image/jpeg", "image/png")


@pytest.fixture
def world(
    session: Session, redis, facility: Facility, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict]:
    """架空の入居者 2 人と職員 1 人、開示設定（アルバムは見せる）。保存先は一時フォルダ。"""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    residents = [
        Resident(
            facility_id=facility.id,
            name=f"架空 {n}",
            name_kana="かくう",
            name_romaji="Kaku",
            room=str(n),
        )
        for n in (1, 2)
    ]
    user = User(kind="staff", login_id="s90021", password_hash="x")
    session.add_all([*residents, user])
    session.flush()
    staff = Staff(user_id=user.id, facility_id=facility.id, display_name="職員A", role="leader")
    session.add(staff)
    session.flush()
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield {
        "facility": facility.id,
        "a": residents[0].id,
        "b": residents[1].id,
        "staff": staff.id,
    }
    clear_disclosure_cache(facility.id)


@pytest.fixture
def add_photo(session: Session, world: dict) -> Callable[..., AlbumPhoto]:
    def add(resident: str = "a", minutes: int = 0, comment: str | None = None) -> AlbumPhoto:
        saved = save_upload(
            session,
            data=fake_png(),
            purpose="album",
            uploaded_by=world["staff"],
            allowed_types=ALBUM_TYPES,
        )
        photo = AlbumPhoto(
            resident_id=world[resident],
            file_id=saved.id,
            comment=comment,
            posted_by=world["staff"],
            posted_at=START + timedelta(minutes=minutes),
        )
        session.add(photo)
        session.flush()
        return photo

    return add


def _hide_album(session: Session, world: dict) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == world["facility"],
            DisclosureSetting.target_type == "feature",
            DisclosureSetting.target_code == "album",
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(world["facility"])


def test_own_residents_photo_can_be_viewed(session, world, add_photo):
    photo = add_photo("a")

    assert can_family_view_photo(session, photo, world["a"]) is True


def test_another_residents_photo_cannot_be_viewed(session, world, add_photo):
    photo = add_photo("a")

    assert can_family_view_photo(session, photo, world["b"]) is False


def test_deleted_photo_cannot_be_viewed(session, world, add_photo):
    photo = add_photo("a")
    photo.deleted_at = START
    photo.file_id = None
    session.flush()

    assert can_family_view_photo(session, photo, world["a"]) is False


def test_nothing_can_be_viewed_while_the_album_is_hidden(session, world, add_photo):
    photo = add_photo("a")
    _hide_album(session, world)

    assert can_family_view_photo(session, photo, world["a"]) is False
    assert get_visible_album_photos(session, world["a"]).photos == []


def test_photos_come_newest_first_and_only_own(session, world, add_photo):
    old = add_photo("a", minutes=0, comment="朝")
    new = add_photo("a", minutes=10, comment=None)
    add_photo("b", minutes=5)  # ほかの入居者の写真は出ない

    page = get_visible_album_photos(session, world["a"])

    assert [photo.id for photo in page.photos] == [new.id, old.id]
    assert page.photos[1].comment == "朝"
    assert page.photos[0].comment is None
    assert page.next_before is None


def test_deleted_photos_are_not_listed(session, world, add_photo):
    kept = add_photo("a", minutes=0)
    gone = add_photo("a", minutes=5)
    gone.deleted_at = START
    gone.file_id = None
    session.flush()

    page = get_visible_album_photos(session, world["a"])

    assert [photo.id for photo in page.photos] == [kept.id]


def test_empty_album_returns_no_photos(session, world):
    page = get_visible_album_photos(session, world["a"])

    assert page.photos == []
    assert page.next_before is None


def test_pages_are_cut_by_limit_and_continue_with_before(session, world, add_photo):
    photos = [add_photo("a", minutes=n) for n in range(5)]  # 古い → 新しい
    newest_first = [photo.id for photo in reversed(photos)]

    first = get_visible_album_photos(session, world["a"], limit=2)
    second = get_visible_album_photos(session, world["a"], before=first.next_before, limit=2)
    third = get_visible_album_photos(session, world["a"], before=second.next_before, limit=2)

    assert [photo.id for photo in first.photos] == newest_first[:2]
    assert first.next_before == newest_first[1]
    assert [photo.id for photo in second.photos] == newest_first[2:4]
    assert [photo.id for photo in third.photos] == newest_first[4:]
    assert third.next_before is None  # 最後のページ


def test_limit_is_kept_within_the_maximum(session, world, add_photo):
    for n in range(MAX_PAGE_SIZE + 3):
        add_photo("a", minutes=n)

    assert len(get_visible_album_photos(session, world["a"], limit=1000).photos) == MAX_PAGE_SIZE
    assert len(get_visible_album_photos(session, world["a"], limit=0).photos) == 1


def test_count_new_photos_is_zero_while_the_album_is_hidden(session, world, add_photo):
    add_photo("a", minutes=0)
    _hide_album(session, world)

    assert count_new_photos(session, world["a"], START, START + timedelta(minutes=60)) == 0


def test_before_of_another_residents_photo_returns_nothing(session, world, add_photo):
    add_photo("a", minutes=0)
    other = add_photo("b", minutes=5)

    page = get_visible_album_photos(session, world["a"], before=other.id)

    assert page.photos == []
    assert page.next_before is None


def test_a_deleted_photo_can_still_be_the_cursor(session, world, add_photo):
    # 前のページの最後の写真が、続きを読む前に削除されても、続きを読める
    older = add_photo("a", minutes=0)
    last_of_page = add_photo("a", minutes=5)
    add_photo("a", minutes=10)
    last_of_page.deleted_at = START
    last_of_page.file_id = None
    session.flush()

    page = get_visible_album_photos(session, world["a"], before=last_of_page.id)

    assert [photo.id for photo in page.photos] == [older.id]


def test_default_page_size_is_twelve(session, world, add_photo):
    # 12 枚は、2・3・4 列のどれでも割り切れ、最初の読み込みを軽くする（#298 の相談で決定）
    for n in range(15):
        add_photo("a", minutes=n)

    page = get_visible_album_photos(session, world["a"])

    assert len(page.photos) == 12
    assert page.next_before is not None  # 続きがある


def test_unknown_before_returns_nothing(session, world, add_photo):
    add_photo("a")

    page = get_visible_album_photos(session, world["a"], before=999999999)

    assert page.photos == []
    assert page.next_before is None


def test_count_new_photos_counts_only_undeleted_in_the_period(session, world, add_photo):
    add_photo("a", minutes=0)
    add_photo("a", minutes=30)
    deleted = add_photo("a", minutes=40)
    deleted.deleted_at = START
    deleted.file_id = None
    add_photo("a", minutes=120)  # 期間のあと
    add_photo("b", minutes=10)  # ほかの入居者
    session.flush()

    count = count_new_photos(session, world["a"], START, START + timedelta(minutes=60))

    assert count == 2
