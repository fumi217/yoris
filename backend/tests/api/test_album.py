"""アルバムの API のテスト（spec 005）。

- 005-T011：GET /api/files/{id} が、アルバムの写真を、条件に合う人にだけ返す
  （職員の役割・自分の入居者の写真・削除されていない・見せる設定。一覧と同じ判定）
- 005-T007・T008（載せる・見る）は、API を作るときに、このファイルに足す

写真は、テストの中で作った小さな架空の画像だけを使う（実在の人物の写真は使わない）。
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.album import AlbumPhoto
from app.models.core import Facility, Staff
from app.models.disclosure import DisclosureSetting
from app.models.files import UploadedFile
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache
from app.services.uploads import save_upload
from tests.helpers.images import fake_png, oversize_image

ALBUM_TYPES = ("image/jpeg", "image/png")


@pytest.fixture
def world(
    session: Session, redis, facility: Facility, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Facility]:
    """保存先は一時フォルダ。開示設定は、初期データ（アルバムは見せる）。"""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    yield facility
    clear_disclosure_cache(facility.id)


@pytest.fixture
def add_photo(session: Session, make_staff: Callable[..., Staff]) -> Callable[..., AlbumPhoto]:
    """入居者 resident_id の写真を 1 枚、載せた状態にする（ファイルと記録）。"""

    def add(
        resident_id: int, posted_at: datetime | None = None, comment: str | None = None
    ) -> AlbumPhoto:
        staff = make_staff(role="leader")
        saved = save_upload(
            session,
            data=fake_png(),
            purpose="album",
            uploaded_by=staff.id,
            allowed_types=ALBUM_TYPES,
        )
        photo = AlbumPhoto(
            resident_id=resident_id,
            file_id=saved.id,
            comment=comment,
            posted_by=staff.id,
            **({"posted_at": posted_at} if posted_at else {}),
        )
        session.add(photo)
        session.flush()
        return photo

    return add


def _hide_album(session: Session, facility: Facility) -> None:
    session.execute(
        update(DisclosureSetting)
        .where(
            DisclosureSetting.facility_id == facility.id,
            DisclosureSetting.target_type == "feature",
            DisclosureSetting.target_code == "album",
        )
        .values(visible=False)
    )
    session.flush()
    clear_disclosure_cache(facility.id)


def _open(client, photo: AlbumPhoto):
    assert photo.file_id is not None
    return client.get(f"/api/files/{photo.file_id}")


def test_not_logged_in_cannot_open_a_photo(client, world, add_photo, make_family):
    photo = add_photo(make_family().resident_id)

    assert _open(client, photo).status_code == 401


@pytest.mark.parametrize("role", ["care_worker", "leader", "counselor", "director"])
def test_album_staff_can_open_a_photo(
    client, world, add_photo, make_family, make_staff, login_as, role
):
    photo = add_photo(make_family().resident_id)
    login_as(make_staff(role=role).user_id)

    response = _open(client, photo)

    assert response.status_code == 200
    assert response.content == fake_png()
    # 保存した形式に固定し、形式を偽ったファイルを画面で実行させない
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    # 共有の置き場には覚えさせず、端末には 5 分だけ覚えさせる（FR-012 の長さ）
    assert response.headers["cache-control"] == "private, max-age=300"


def test_clerk_cannot_open_a_photo(client, world, add_photo, make_family, make_staff, login_as):
    photo = add_photo(make_family().resident_id)
    login_as(make_staff(role="clerk").user_id)

    assert _open(client, photo).status_code == 404


def test_family_can_open_their_own_residents_photo(client, world, add_photo, make_family, login_as):
    family = make_family()
    photo = add_photo(family.resident_id)
    login_as(family.user_id)

    response = _open(client, photo)

    assert response.status_code == 200
    assert response.content == fake_png()


def test_family_cannot_open_another_residents_photo(
    client, world, add_photo, make_family, login_as
):
    mine = make_family()
    other = make_family()
    photo = add_photo(other.resident_id)
    login_as(mine.user_id)

    # 一覧にも出ない写真は、URL を直接開いても 404（あるかどうかも知らせない）
    assert _open(client, photo).status_code == 404


def test_family_cannot_open_a_photo_while_the_album_is_hidden(
    client, session, world, add_photo, make_family, login_as
):
    family = make_family()
    photo = add_photo(family.resident_id)
    _hide_album(session, world)
    login_as(family.user_id)

    assert _open(client, photo).status_code == 404


def test_staff_can_still_open_a_photo_while_the_album_is_hidden(
    client, session, world, add_photo, make_family, make_staff, login_as
):
    # 職員の画面は、載せた写真を、見せない設定のときも表示する
    photo = add_photo(make_family().resident_id)
    _hide_album(session, world)
    login_as(make_staff(role="care_worker").user_id)

    assert _open(client, photo).status_code == 200


def test_a_deleted_photo_cannot_be_opened_by_anyone(
    client, session, world, add_photo, make_family, make_staff, login_as
):
    family = make_family()
    photo = add_photo(family.resident_id)
    photo.deleted_at = photo.posted_at  # 削除した記録（ファイルの行が残っていても開けない）
    session.flush()

    for user_id in (family.user_id, make_staff(role="leader").user_id):
        login_as(user_id)
        assert _open(client, photo).status_code == 404


def test_announcement_files_are_not_affected(client, session, world, make_staff, login_as):
    # お知らせの添付は、今までどおり、ログイン中の人が開ける
    staff = make_staff(role="clerk")
    saved = save_upload(session, data=fake_png(), purpose="announcement", uploaded_by=staff.id)
    login_as(staff.user_id)

    assert client.get(f"/api/files/{saved.id}").status_code == 200
    assert session.get(UploadedFile, saved.id) is not None


# --- 005-T010：家族の API（GET /api/family/album・GET /api/family/features） ---

BASE = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)  # 日本時間の 11/5 12:00


def test_features_tells_whether_the_album_is_shown(client, session, world, make_family, login_as):
    login_as(make_family().user_id)

    assert client.get("/api/family/features").json() == {"album": True}

    _hide_album(session, world)
    assert client.get("/api/family/features").json() == {"album": False}


def test_features_and_album_need_a_family_login(client, world, make_staff, login_as):
    assert client.get("/api/family/features").status_code == 401
    assert client.get("/api/family/album").status_code == 401

    login_as(make_staff().user_id)
    assert client.get("/api/family/features").status_code == 403
    assert client.get("/api/family/album").status_code == 403


def test_album_groups_photos_by_japan_day_newest_first(
    client, world, add_photo, make_family, login_as
):
    family = make_family()
    # UTC の 11/5 14:30 と 15:30 は、日本時間では 11/5 23:30 と 11/6 00:30（別の日）
    late = add_photo(family.resident_id, BASE + timedelta(hours=11, minutes=30), comment="夜")
    next_day = add_photo(family.resident_id, BASE + timedelta(hours=12, minutes=30))
    noon = add_photo(family.resident_id, BASE, comment="昼")
    login_as(family.user_id)

    body = client.get("/api/family/album").json()

    assert [day["date"] for day in body["days"]] == ["2026-11-06", "2026-11-05"]
    assert [photo["id"] for photo in body["days"][0]["photos"]] == [next_day.id]
    assert [photo["id"] for photo in body["days"][1]["photos"]] == [late.id, noon.id]
    first = body["days"][1]["photos"][0]
    assert first["comment"] == "夜"
    assert first["url"] == f"/api/files/{late.file_id}"
    assert body["days"][0]["photos"][0]["comment"] is None
    assert body["next_before"] is None


def test_album_shows_only_the_logged_in_familys_resident(
    client, world, add_photo, make_family, login_as
):
    mine = make_family()
    other = make_family()
    add_photo(other.resident_id)
    login_as(mine.user_id)

    # 入居者は、送らせない（クエリで指定しても、ほかの入居者の写真は出ない）
    body = client.get("/api/family/album", params={"resident_id": other.resident_id}).json()

    assert body == {"days": [], "next_before": None}


def test_album_is_404_while_it_is_hidden(client, session, world, add_photo, make_family, login_as):
    family = make_family()
    add_photo(family.resident_id)
    _hide_album(session, world)
    login_as(family.user_id)

    assert client.get("/api/family/album").status_code == 404


def test_album_default_is_twelve_and_continues_with_next_before(
    client, world, add_photo, make_family, login_as
):
    family = make_family()
    photos = [add_photo(family.resident_id, BASE + timedelta(minutes=n)) for n in range(15)]
    newest_first = [photo.id for photo in reversed(photos)]
    login_as(family.user_id)

    first = client.get("/api/family/album").json()
    ids_first = [p["id"] for day in first["days"] for p in day["photos"]]
    second = client.get("/api/family/album", params={"before": first["next_before"]}).json()
    ids_second = [p["id"] for day in second["days"] for p in day["photos"]]

    assert ids_first == newest_first[:12]
    assert ids_second == newest_first[12:]
    assert second["next_before"] is None


def test_album_limit_must_be_between_one_and_thirty(client, world, make_family, login_as):
    login_as(make_family().user_id)

    assert client.get("/api/family/album", params={"limit": 0}).status_code == 422
    assert client.get("/api/family/album", params={"limit": 31}).status_code == 422
    assert client.get("/api/family/album", params={"limit": 30}).status_code == 200


def test_album_returns_the_comment_as_is_without_interpreting_it(
    client, world, add_photo, make_family, login_as
):
    family = make_family()
    add_photo(family.resident_id, comment="<b>運動会</b> & <script>x</script>")
    login_as(family.user_id)

    body = client.get("/api/family/album").json()

    assert body["days"][0]["photos"][0]["comment"] == "<b>運動会</b> & <script>x</script>"


def test_the_url_of_a_listed_photo_can_be_opened_by_the_same_family(
    client, world, add_photo, make_family, login_as
):
    family = make_family()
    add_photo(family.resident_id)
    login_as(family.user_id)

    url = client.get("/api/family/album").json()["days"][0]["photos"][0]["url"]

    assert client.get(url).status_code == 200


# --- 005-T009・T007：職員の API（POST・GET /api/staff/residents/{id}/album） ---


def _post(client, resident_id, data=None, name="photo.png", content_type="image/png", **form):
    return client.post(
        f"/api/staff/residents/{resident_id}/album",
        files={"file": (name, fake_png() if data is None else data, content_type)},
        data=form,
    )


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_staff_can_post_a_photo_without_a_comment(
    client, session, world, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    staff = make_staff(role="care_worker")
    login_as(staff.user_id)

    response = _post(client, resident_id)

    assert response.status_code == 201
    body = response.json()
    assert body["comment"] is None
    assert body["url"].startswith("/api/files/")
    photo = session.get(AlbumPhoto, body["id"])
    assert photo is not None
    assert (photo.resident_id, photo.posted_by, photo.comment) == (resident_id, staff.id, None)
    saved = session.get(UploadedFile, photo.file_id)
    assert saved is not None
    assert (saved.purpose, saved.content_type) == ("album", "image/png")


def test_a_posted_photo_appears_in_the_familys_album(
    client, world, make_family, make_staff, login_as
):
    family = make_family()
    login_as(make_staff(role="leader").user_id)
    posted = _post(client, family.resident_id, comment="運動会").json()

    login_as(family.user_id)
    body = client.get("/api/family/album").json()

    assert body["days"][0]["photos"][0]["id"] == posted["id"]
    assert body["days"][0]["photos"][0]["comment"] == "運動会"
    assert client.get(posted["url"]).status_code == 200


def test_comment_is_optional_up_to_one_hundred_characters(
    client, world, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    login_as(make_staff(role="leader").user_id)

    assert _post(client, resident_id, comment="あ" * 100).status_code == 201
    too_long = _post(client, resident_id, comment="あ" * 101)
    assert (too_long.status_code, _code(too_long)) == (422, "validation_error")
    # 空の文字は「コメントなし」
    assert _post(client, resident_id, comment="").json()["comment"] is None


@pytest.mark.parametrize(
    ("data", "name", "content_type"),
    [
        (b"%PDF-1.4\n%fake\n", "photo.jpg", "image/jpeg"),  # 名前だけ .jpg の PDF
        (b"GIF89a" + b"\x00" * 16, "photo.png", "image/png"),
        (b"plain text", "photo.png", "image/png"),
    ],
)
def test_other_formats_are_invalid_file(
    client, world, make_family, make_staff, login_as, data, name, content_type
):
    resident_id = make_family().resident_id
    login_as(make_staff(role="leader").user_id)

    response = _post(client, resident_id, data=data, name=name, content_type=content_type)

    assert (response.status_code, _code(response)) == (422, "invalid_file")


def test_an_image_over_the_size_limit_is_invalid_file(
    client, world, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    login_as(make_staff(role="leader").user_id)

    response = _post(client, resident_id, data=oversize_image("png"))

    assert (response.status_code, _code(response)) == (422, "invalid_file")


def test_a_request_without_a_file_is_a_validation_error(
    client, world, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    login_as(make_staff(role="leader").user_id)

    response = client.post(f"/api/staff/residents/{resident_id}/album", data={"comment": "x"})

    assert (response.status_code, _code(response)) == (422, "validation_error")


def test_only_album_staff_can_post_a_photo(client, world, make_family, make_staff, login_as):
    family = make_family()
    assert _post(client, family.resident_id).status_code == 401

    for user_id in (make_staff(role="clerk").user_id, family.user_id):
        login_as(user_id)
        assert _post(client, family.resident_id).status_code == 403


def test_posting_for_an_unknown_resident_is_404(client, world, make_staff, login_as):
    login_as(make_staff(role="leader").user_id)

    assert _post(client, 999999999).status_code == 404


def test_staff_album_lists_undeleted_photos_newest_first(
    client, world, add_photo, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    old = add_photo(resident_id, BASE)
    new = add_photo(resident_id, BASE + timedelta(minutes=10), comment="新")
    gone = add_photo(resident_id, BASE + timedelta(minutes=5))
    gone.deleted_at = BASE
    gone.file_id = None
    add_photo(make_family().resident_id, BASE)  # ほかの入居者の写真
    login_as(make_staff(role="counselor").user_id)

    body = client.get(f"/api/staff/residents/{resident_id}/album").json()

    assert body["family_visible"] is True
    assert [photo["id"] for photo in body["photos"]] == [new.id, old.id]
    assert body["photos"][0]["comment"] == "新"


def test_staff_album_still_lists_photos_while_hidden_from_families(
    client, session, world, add_photo, make_family, make_staff, login_as
):
    resident_id = make_family().resident_id
    add_photo(resident_id)
    _hide_album(session, world)
    login_as(make_staff(role="leader").user_id)

    body = client.get(f"/api/staff/residents/{resident_id}/album").json()

    assert body["family_visible"] is False  # 画面に「いま家族には見せていません」を出す
    assert len(body["photos"]) == 1


def test_staff_album_is_for_album_staff_and_known_residents(
    client, world, make_family, make_staff, login_as
):
    family = make_family()
    url = f"/api/staff/residents/{family.resident_id}/album"
    assert client.get(url).status_code == 401

    for user_id in (make_staff(role="clerk").user_id, family.user_id):
        login_as(user_id)
        assert client.get(url).status_code == 403

    login_as(make_staff(role="leader").user_id)
    assert client.get("/api/staff/residents/999999999/album").status_code == 404
