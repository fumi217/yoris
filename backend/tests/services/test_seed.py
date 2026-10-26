"""初期データ（001-T015）。本物の DB に流して確かめる。

手元の開発の DB には、すでに初期データや手で入れた人がいることがある。
施設の中身は、テスト用の新しい施設に入れて確かめ、seed() 全体は「2 回目で増えないか」で確かめる。
"""

from datetime import date

from sqlalchemy import func, select

from app.auth.login_ids import next_login_ids
from app.models.core import STAFF_ROLES, Facility, FamilyAccount, Resident, Staff, User
from app.models.records import CareRecord
from app.models.visits import VisitReservation
from app.seed.__main__ import seed
from app.seed.people import RESIDENT_COUNT, STAFF, add_people

TODAY = date(2026, 10, 23)


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
    before = (_count(session, User), _count(session, Resident), _count(session, CareRecord))

    assert seed(session, today=TODAY) is False
    assert (_count(session, User), _count(session, Resident), _count(session, CareRecord)) == before
