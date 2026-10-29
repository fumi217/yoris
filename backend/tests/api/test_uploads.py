"""ファイルの共通の処理（001-T067。FR-025・FR-034・research.md R-10）のテスト。

- 保存の処理 save_upload：形式は先頭のバイトで確かめる（拡張子・送られた Content-Type は見ない）、
  10MB まで、推測できない名前で UPLOAD_DIR に保存する
- 配る API GET /api/files/{id}：ログインが要る。アルバムの写真は、005-T011 で条件を足すまで開けない

画像は、テストの中で作った小さなバイト列だけを使う（実在の人物の写真は使わない）。
"""

import re
from pathlib import Path

import pytest

from app.errors import AppError, ErrorCode
from app.models.files import MAX_UPLOAD_BYTES, UploadedFile
from app.services.uploads import detect_content_type, save_upload
from tests.helpers.images import fake_jpeg, fake_png, pdf_named_jpg

ALBUM_TYPES = ("image/jpeg", "image/png")

PDF = b"%PDF-1.4\n%fake\n"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """保存先を、テストごとの一時フォルダにする（開発の保存先を汚さない）。"""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PDF, "application/pdf"),
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
    ],
)
def test_content_type_is_decided_by_the_first_bytes(data, expected):
    assert detect_content_type(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        b"GIF89a" + b"\x00" * 16,
        b"hello, this is text",
        b"<html><script>alert(1)</script></html>",
        b"\xff\xd8",  # JPEG の途中までしかない（先頭の 3 バイトに足りない）
        b"",
    ],
)
def test_other_formats_and_empty_data_are_not_accepted(data):
    assert detect_content_type(data) is None


def test_a_pdf_named_jpg_is_a_pdf(session, make_staff, upload_dir):
    # save_upload は名前を受け取らない。中身だけで形式を決める
    staff = make_staff()

    saved = save_upload(session, data=PDF, purpose="announcement", uploaded_by=staff.id)

    assert saved.content_type == "application/pdf"


@pytest.mark.parametrize("data", [b"GIF89a" + b"\x00" * 16, b"plain text", b""])
def test_unsupported_data_is_invalid_file(session, make_staff, upload_dir, data):
    staff = make_staff()

    with pytest.raises(AppError) as error:
        save_upload(session, data=data, purpose="announcement", uploaded_by=staff.id)

    assert error.value.code == ErrorCode.INVALID_FILE
    assert list(upload_dir.iterdir()) == []  # 断ったものは保存しない


def test_exactly_the_size_limit_is_accepted_and_one_byte_over_is_not(
    session, make_staff, upload_dir
):
    staff = make_staff()
    at_limit = PDF + b"0" * (MAX_UPLOAD_BYTES - len(PDF))
    over = at_limit + b"0"

    saved = save_upload(session, data=at_limit, purpose="announcement", uploaded_by=staff.id)
    assert saved.size_bytes == MAX_UPLOAD_BYTES

    with pytest.raises(AppError) as error:
        save_upload(session, data=over, purpose="announcement", uploaded_by=staff.id)
    assert error.value.code == ErrorCode.INVALID_FILE


def test_saved_with_an_unguessable_name_and_a_row(session, make_staff, upload_dir):
    staff = make_staff()

    first = save_upload(session, data=PNG, purpose="album", uploaded_by=staff.id)
    second = save_upload(session, data=PNG, purpose="album", uploaded_by=staff.id)

    assert first.storage_key != second.storage_key
    # 元のファイル名や拡張子を持たない、長いランダムな文字列
    assert re.fullmatch(r"[A-Za-z0-9_-]{32,}", first.storage_key)
    assert (upload_dir / first.storage_key).read_bytes() == PNG
    row = session.get(UploadedFile, first.id)
    assert row is not None
    assert (row.content_type, row.size_bytes, row.purpose, row.uploaded_by) == (
        "image/png",
        len(PNG),
        "album",
        staff.id,
    )


def test_not_logged_in_gets_401(client, session, make_staff, upload_dir):
    saved = save_upload(session, data=PDF, purpose="announcement", uploaded_by=make_staff().id)

    response = client.get(f"/api/files/{saved.id}")

    assert response.status_code == 401


def test_staff_and_family_can_open_an_announcement_file(
    client, session, make_staff, make_family, login_as, upload_dir
):
    staff = make_staff()
    family = make_family()
    saved = save_upload(session, data=PDF, purpose="announcement", uploaded_by=staff.id)

    for user_id in (staff.user_id, family.user_id):
        login_as(user_id)
        response = client.get(f"/api/files/{saved.id}")

        assert response.status_code == 200
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-content-type-options"] == "nosniff"


def test_the_content_type_is_fixed_to_the_saved_one(
    client, session, make_staff, login_as, upload_dir
):
    # 画面の一部として実行されないように、保存した形式の Content-Type だけを返す
    staff = make_staff()
    saved = save_upload(session, data=PNG, purpose="announcement", uploaded_by=staff.id)
    login_as(staff.user_id)

    response = client.get(f"/api/files/{saved.id}")

    assert response.headers["content-type"] == "image/png"


def test_unknown_id_is_404(client, make_staff, login_as, upload_dir):
    login_as(make_staff().user_id)

    assert client.get("/api/files/999999999").status_code == 404


def test_album_file_without_a_photo_record_cannot_be_opened(
    client, session, make_staff, login_as, upload_dir
):
    # アルバムの写真は、album_photos の記録がないと、職員でも開けない
    # （条件は services/album.py の can_open_album_file。tests/api/test_album.py で確かめる）
    staff = make_staff()
    saved = save_upload(session, data=JPEG, purpose="album", uploaded_by=staff.id)
    login_as(staff.user_id)

    assert client.get(f"/api/files/{saved.id}").status_code == 404


@pytest.mark.parametrize("data", [fake_jpeg(), fake_png()])
def test_album_types_accept_jpeg_and_png(session, make_staff, upload_dir, data):
    staff = make_staff()

    saved = save_upload(
        session, data=data, purpose="album", uploaded_by=staff.id, allowed_types=ALBUM_TYPES
    )

    assert saved.content_type in ALBUM_TYPES


def test_album_types_refuse_pdf_even_when_named_jpg(session, make_staff, upload_dir):
    staff = make_staff()
    _name, pdf = pdf_named_jpg()

    with pytest.raises(AppError) as error:
        save_upload(
            session, data=pdf, purpose="album", uploaded_by=staff.id, allowed_types=ALBUM_TYPES
        )

    assert error.value.code == ErrorCode.INVALID_FILE
    assert list(upload_dir.iterdir()) == []  # 断ったものは保存しない


def test_without_allowed_types_pdf_is_still_accepted(session, make_staff, upload_dir):
    # 既定は今までどおり（お知らせの添付は PDF を受け付ける）
    staff = make_staff()
    _name, pdf = pdf_named_jpg()

    saved = save_upload(session, data=pdf, purpose="announcement", uploaded_by=staff.id)

    assert saved.content_type == "application/pdf"
