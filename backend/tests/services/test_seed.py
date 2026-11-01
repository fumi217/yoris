"""初期データ（001-T015）。本物の DB に流して確かめる。

手元の開発の DB には、すでに初期データや手で入れた人がいることがある。
施設の中身は、テスト用の新しい施設に入れて確かめ、seed() 全体は「2 回目で増えないか」で確かめる。
"""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.auth.login_ids import next_login_ids
from app.models.album import AlbumPhoto
from app.models.change_flags import ChangeFlag, ChangeRule
from app.models.core import STAFF_ROLES, Facility, FamilyAccount, Resident, Staff, User
from app.models.files import UploadedFile
from app.models.records import CareRecord
from app.models.visits import VisitReservation
from app.seed.__main__ import seed
from app.seed.album import SAMPLE_SCENES, add_sample_photos, landscape_png
from app.seed.people import RESIDENT_COUNT, STAFF, add_people
from app.services.uploads import read_upload

TODAY = date(2026, 10, 23)


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """seed はデモの写真のファイルを書くので、保存先は一時フォルダにする（本物を汚さない）。"""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_add_people_fills_a_new_facility(session):
    # 施設は 1 つの決まりだが、手元の DB の施設にはもう人がいることがあるので、
    # テストの中だけ 2 つ目を作る（テストの最後に取り消すので残らない）
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()

    assert len(add_people(session, facility_id=facility.id)) == len(STAFF)

    residents = session.scalar(
        select(func.count()).select_from(Resident).where(Resident.facility_id == facility.id)
    )
    families = session.scalar(
        select(func.count())
        .select_from(FamilyAccount)
        .join(Resident, Resident.id == FamilyAccount.resident_id)
        .where(Resident.facility_id == facility.id)
    )
    roles = set(session.scalars(select(Staff.role).where(Staff.facility_id == facility.id)))
    assert residents == RESIDENT_COUNT
    # 入居者 1 人に、家族アカウントが 1 つ
    assert families == RESIDENT_COUNT
    assert roles == set(STAFF_ROLES)
    staff_languages = set(
        session.scalars(
            select(User.language)
            .join(Staff, Staff.user_id == User.id)
            .where(Staff.facility_id == facility.id)
        )
    )
    # 外国人の職員（spec 007 で母国語のメモを試す）がいる
    assert staff_languages == {"ja", "id", "en"}
    # 職種は全員に入れる。看護師なども、役割は care_worker で職種で分かる（#263）
    occupations = dict(
        session.execute(
            select(Staff.display_name, Staff.occupation).where(Staff.facility_id == facility.id)
        ).all()
    )
    assert None not in occupations.values()
    assert occupations["西村"] == "nurse"
    assert occupations["原田"] == "functional_trainer"
    assert occupations["青木"] == "care_manager"
    # 入居者の名前（#389）：フルネーム・読み・ローマ字が入り、重ならない。続柄も入る
    names = session.execute(
        select(Resident.name, Resident.name_kana, Resident.name_romaji, FamilyAccount.relationship)
        .join(FamilyAccount, FamilyAccount.resident_id == Resident.id)
        .where(Resident.facility_id == facility.id)
        .order_by(Resident.id)
    ).all()
    assert names[0] == ("佐藤 文江", "さとう ふみえ", "Sato Fumie", "daughter")
    assert len({row.name for row in names}) == RESIDENT_COUNT
    assert all(" " in row.name and "さんの" not in row.name for row in names)
    assert all(row.name_romaji.isascii() for row in names)
    assert {"daughter", "son", "spouse", "grandchild"} <= {row.relationship for row in names}

    # 2 回目は、もう入居者がいるので何もしない
    assert add_people(session, facility_id=facility.id) == []


def test_add_people_keeps_one_director(session):
    # 決済の申し込みで、施設と施設長がもうある
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    [login_id] = next_login_ids(session, 1)
    director = User(kind="staff", login_id=login_id, password_hash="x")
    session.add(director)
    session.flush()
    session.add(
        Staff(user_id=director.id, facility_id=facility.id, display_name="施設長", role="director")
    )
    session.flush()

    added = add_people(session, facility_id=facility.id)

    assert "director" not in {staff.role for staff in added}
    directors = session.scalar(
        select(func.count())
        .select_from(Staff)
        .where(Staff.facility_id == facility.id, Staff.role == "director")
    )
    assert directors == 1


def test_seed_twice_adds_nothing(session):
    fresh = seed(session, today=TODAY)
    if fresh:
        # 空の DB（CI）では、デモ用の記録と予約も入る
        assert _count(session, CareRecord) > 0
        assert _count(session, VisitReservation) > 0
    # 変化の決まりは 3 つ（spec 006）
    assert _count(session, ChangeRule) == 3
    before = (
        _count(session, User),
        _count(session, Resident),
        _count(session, CareRecord),
        _count(session, ChangeRule),
    )

    assert seed(session, today=TODAY) is False
    assert (
        _count(session, User),
        _count(session, Resident),
        _count(session, CareRecord),
        _count(session, ChangeRule),
    ) == before


def test_seed_makes_a_demo_flag(session):
    # 空の DB（CI）だけ、デモ用の目印が付く（人がいる手元の DB では、足されない）
    if not seed(session, today=TODAY):
        pytest.skip("人がいる DB では、デモの目印は足されない")
    first = session.scalar(select(Resident.id).order_by(Resident.id))
    flags = session.scalars(
        select(ChangeFlag).where(ChangeFlag.resident_id == first, ChangeFlag.cleared_at.is_(None))
    ).all()
    assert [(f.rule_code, f.status, f.streak) for f in flags] == [("meal_low", "unconfirmed", 2)]


def test_album_sample_photos_are_added_once(session, make_family, make_staff):
    resident_id = make_family().resident_id
    staff_id = make_staff(role="care_worker").id

    assert add_sample_photos(session, resident_id=resident_id, staff_id=staff_id) == len(
        SAMPLE_SCENES
    )

    photos = session.scalars(select(AlbumPhoto).where(AlbumPhoto.resident_id == resident_id)).all()
    assert len(photos) == len(SAMPLE_SCENES)
    for photo in photos:
        uploaded = session.get(UploadedFile, photo.file_id)
        assert uploaded is not None
        assert (uploaded.purpose, uploaded.content_type) == ("album", "image/png")
        # 保存先にファイルがあり、PNG として始まっている
        assert read_upload(uploaded.storage_key).startswith(b"\x89PNG")
        assert photo.comment is None or len(photo.comment) <= 100
    assert any(photo.comment is None for photo in photos)  # コメントなしの写真も 1 枚ある
    # 2 回目は足さない
    assert add_sample_photos(session, resident_id=resident_id, staff_id=staff_id) == 0
    assert _count(session, AlbumPhoto) >= len(SAMPLE_SCENES)


def test_landscape_png_is_a_small_real_png():
    for scene in SAMPLE_SCENES:
        data = landscape_png(scene)

        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(data) < 50_000  # リポジトリにも保存先にも、重くならない


def test_seed_adds_album_photos_for_the_first_resident_only(session):
    # 空の DB（CI）だけ、デモの写真が入る（人がいる手元の DB では、足されない）
    if not seed(session, today=TODAY):
        pytest.skip("人がいる DB では、デモの写真は足されない")
    first = session.scalar(select(Resident.id).order_by(Resident.id))
    owners = set(session.scalars(select(AlbumPhoto.resident_id)))

    assert owners == {first}
