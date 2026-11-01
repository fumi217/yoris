"""様子のメモの承認の API のテスト（spec 007 の 007-T020。FR-011〜FR-015）。

DB と Redis は tests/conftest.py の session・redis を使う。
ほぼ同時の操作は、同じ session の中では本当に同時にできないので、「先の操作が済んだあとに、
あとの操作を送る」形で、条件つきの更新が先の 1 つだけを通すことを確かめる。
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.core import Facility, Resident, Staff, User
from app.models.memos import CareMemo

NOW = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
BASE = "/api/staff/memo-approvals"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr("app.clock.now", lambda: NOW)


@pytest.fixture
def world(client, session, make_staff, make_family, login_as):
    """書いた介護職員、リーダー 2 人、施設長、入居者 1 人。ログインはリーダー A。"""
    writer = make_staff(role="care_worker", display_name="シティ", language="id")
    leader = make_staff(role="leader", display_name="リーダーA")
    other_leader = make_staff(role="leader", display_name="リーダーB")
    director = make_staff(role="director", display_name="施設長")
    resident = make_family(name="さくら 花子")
    login_as(leader.user_id)
    return {
        "writer": writer,
        "leader": leader,
        "other_leader": other_leader,
        "director": director,
        "resident_id": resident.resident_id,
        "facility_id": writer.facility_id,
    }


def add_memo(
    session, world, *, author=None, status="pending", confirmed_ago=timedelta(hours=1), **changes
) -> CareMemo:
    """架空のメモ。confirmed_ago が None なら、まだ「確かめました」を押していない下書き。"""
    values = {
        "resident_id": world["resident_id"],
        "author_staff_id": (author or world["writer"]).id,
        "memo_date": NOW.date(),
        "source_lang": "id",
        "original_text": "Hari ini beliau banyak tersenyum.",
        "rewritten_text": "今日は、よく笑っていました。",
        "back_translation": "今日は、たくさん笑っていました。",
        "status": status,
        "confirmed_at": None if confirmed_ago is None else NOW - confirmed_ago,
        **changes,
    }
    memo = CareMemo(**values)
    session.add(memo)
    session.flush()
    return memo


def refreshed(session, memo: CareMemo) -> CareMemo:
    session.refresh(memo)
    return memo


def other_facility_memo(session) -> CareMemo:
    """ほかの施設の入居者について、ほかの施設の職員が書いて確かめたメモ。"""
    facility = Facility(name="ほかの施設")
    session.add(facility)
    session.flush()
    resident = Resident(
        facility_id=facility.id,
        name="架空 遠方",
        name_kana="かくう",
        name_romaji="Kaku",
        room="9",
    )
    user = User(kind="staff", login_id="s99999", password_hash="x")
    session.add_all([resident, user])
    session.flush()
    staff = Staff(
        user_id=user.id, facility_id=facility.id, display_name="遠方の職員", role="care_worker"
    )
    session.add(staff)
    session.flush()
    memo = CareMemo(
        resident_id=resident.id,
        author_staff_id=staff.id,
        memo_date=NOW.date(),
        source_lang="ja",
        original_text="ほかの施設のメモです。",
        rewritten_text="ほかの施設のメモです。",
        status="pending",
        confirmed_at=NOW - timedelta(hours=2),
    )
    session.add(memo)
    session.flush()
    return memo


# --- 承認する ---


def test_leader_approves_and_who_and_when_are_kept(client, session, world):
    memo = add_memo(session, world)

    response = client.post(f"{BASE}/{memo.id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    memo = refreshed(session, memo)
    assert memo.status == "approved"
    assert memo.approved_by == world["leader"].id
    assert memo.approved_at == NOW


def test_director_can_approve(client, session, world, login_as):
    memo = add_memo(session, world)
    login_as(world["director"].user_id)

    assert client.post(f"{BASE}/{memo.id}/approve").status_code == 200


def test_the_author_cannot_approve_even_if_a_leader(client, session, world):
    memo = add_memo(session, world, author=world["leader"])

    response = client.post(f"{BASE}/{memo.id}/approve")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_approval"
    memo = refreshed(session, memo)
    assert (memo.status, memo.approved_by) == ("pending", None)


def test_the_author_cannot_return_their_own_memo_either(client, session, world):
    memo = add_memo(session, world, author=world["leader"])

    response = client.post(f"{BASE}/{memo.id}/return", json={"reason": "直します"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_approval"
    assert refreshed(session, memo).status == "pending"


@pytest.mark.parametrize("role", ["care_worker", "counselor", "clerk"])
def test_other_roles_cannot_approve_return_or_unpublish_or_list(
    client, session, world, make_staff, login_as, role
):
    memo = add_memo(session, world)
    login_as(make_staff(role=role).user_id)

    assert client.post(f"{BASE}/{memo.id}/approve").status_code == 403
    assert client.post(f"{BASE}/{memo.id}/return", json={"reason": "x"}).status_code == 403
    assert client.post(f"{BASE}/{memo.id}/unpublish", json={"reason": "x"}).status_code == 403
    assert client.get(BASE).status_code == 403
    assert refreshed(session, memo).status == "pending"


def test_a_family_cannot_use_it(client, session, world, make_family, login_as):
    memo = add_memo(session, world)
    login_as(make_family().user_id)

    assert client.post(f"{BASE}/{memo.id}/approve").status_code == 403
    assert client.get(BASE).status_code == 403
    assert client.get(f"{BASE}/count").status_code == 403


def test_not_logged_in_is_401(client, session, world):
    client.cookies.clear()

    assert client.get(BASE).status_code == 401


def test_the_one_who_acts_first_wins_the_other_gets_409(client, session, world, login_as):
    memo = add_memo(session, world)
    assert client.post(f"{BASE}/{memo.id}/approve").status_code == 200
    login_as(world["other_leader"].user_id)

    late_return = client.post(f"{BASE}/{memo.id}/return", json={"reason": "遅れました"})
    late_approve = client.post(f"{BASE}/{memo.id}/approve")

    for response in (late_return, late_approve):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_state"
    memo = refreshed(session, memo)
    assert (memo.status, memo.approved_by, memo.returned_by) == (
        "approved",
        world["leader"].id,
        None,
    )


@pytest.mark.parametrize("status", ["approved", "returned", "withdrawn"])
def test_a_memo_that_is_not_pending_cannot_be_approved(client, session, world, status):
    memo = add_memo(session, world, status=status)

    response = client.post(f"{BASE}/{memo.id}/approve")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert refreshed(session, memo).status == status


# --- 戻す ---


def test_return_keeps_who_when_and_why_and_the_writer_sees_the_reason(
    client, session, world, login_as
):
    memo = add_memo(session, world)

    response = client.post(f"{BASE}/{memo.id}/return", json={"reason": "  お名前が入っています  "})

    assert response.status_code == 200
    assert response.json()["status"] == "returned"
    memo = refreshed(session, memo)
    assert (memo.returned_by, memo.returned_at) == (world["leader"].id, NOW)
    assert memo.return_reason == "お名前が入っています"
    assert memo.approved_by is None
    # 書いた職員の画面に、戻された理由が出る（FR-013）
    login_as(world["writer"].user_id)
    shown = client.get(f"/api/staff/memos/{memo.id}").json()
    assert (shown["status"], shown["return_reason"]) == ("returned", "お名前が入っています")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": ""},
        {"reason": "   \n "},
        {"reason": "あ" * 201},
        {"reason": "x", "status": "approved"},
    ],
    ids=["missing", "empty", "blank", "too_long", "extra_field"],
)
def test_return_and_unpublish_need_a_reason_of_1_to_200_characters(client, session, world, body):
    pending = add_memo(session, world)
    approved = add_memo(session, world, status="approved")

    for url in (f"{BASE}/{pending.id}/return", f"{BASE}/{approved.id}/unpublish"):
        response = client.post(url, json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert refreshed(session, pending).status == "pending"
    assert refreshed(session, approved).status == "approved"


def test_a_reason_of_exactly_200_characters_is_accepted(client, session, world):
    memo = add_memo(session, world)

    assert client.post(f"{BASE}/{memo.id}/return", json={"reason": "あ" * 200}).status_code == 200


# --- 公開を取り下げる ---


def test_unpublish_returns_it_to_the_writer_and_keeps_who_when_and_why(
    client, session, world, login_as
):
    memo = add_memo(
        session,
        world,
        status="approved",
        approved_by=world["other_leader"].id,
        approved_at=NOW - timedelta(minutes=30),
    )

    response = client.post(
        f"{BASE}/{memo.id}/unpublish", json={"reason": "医療の判断が入っていました"}
    )

    assert response.status_code == 200
    # 「承認済み」でなくなるので、家族に出す共通の関数（status = 'approved' だけを返す）から消える
    memo = refreshed(session, memo)
    assert memo.status == "returned"
    assert (memo.unpublished_by, memo.unpublished_at) == (world["leader"].id, NOW)
    assert memo.unpublish_reason == "医療の判断が入っていました"
    # 承認の記録は消さずに残す
    assert (memo.approved_by, memo.return_reason) == (world["other_leader"].id, None)
    # 書いた職員の画面には、取り下げた理由が「戻された理由」として出る
    login_as(world["writer"].user_id)
    shown = client.get(f"/api/staff/memos/{memo.id}").json()
    assert (shown["status"], shown["return_reason"]) == ("returned", "医療の判断が入っていました")


def test_the_writer_sees_the_newer_of_the_two_reasons(client, session, world, login_as):
    # 取り下げられ、直して出し直し、今度は戻された：新しい「戻した理由」を出す
    memo = add_memo(
        session,
        world,
        status="returned",
        unpublished_by=world["leader"].id,
        unpublished_at=NOW - timedelta(days=1),
        unpublish_reason="古い取り下げの理由",
        returned_by=world["leader"].id,
        returned_at=NOW - timedelta(hours=1),
        return_reason="新しい戻した理由",
    )
    login_as(world["writer"].user_id)

    assert client.get(f"/api/staff/memos/{memo.id}").json()["return_reason"] == "新しい戻した理由"


def test_unpublish_works_only_on_an_approved_memo(client, session, world):
    memo = add_memo(session, world)

    response = client.post(f"{BASE}/{memo.id}/unpublish", json={"reason": "まだ承認前です"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert refreshed(session, memo).status == "pending"


def test_the_author_may_unpublish_their_own_approved_memo(client, session, world):
    # 承認と違い、公開を止める操作なので、本人でもよい（契約：L・D）
    memo = add_memo(session, world, author=world["leader"], status="approved")

    response = client.post(f"{BASE}/{memo.id}/unpublish", json={"reason": "書き間違えました"})

    assert response.status_code == 200
    assert refreshed(session, memo).status == "returned"


# --- 見つからない（ほかの施設・下書き） ---


def test_another_facilitys_memo_is_404_for_every_operation(client, session, world):
    memo = other_facility_memo(session)

    assert client.post(f"{BASE}/{memo.id}/approve").status_code == 404
    assert client.post(f"{BASE}/{memo.id}/return", json={"reason": "x"}).status_code == 404
    assert client.post(f"{BASE}/{memo.id}/unpublish", json={"reason": "x"}).status_code == 404
    assert refreshed(session, memo).status == "pending"


def test_a_draft_that_was_never_confirmed_is_404_to_the_leader(client, session, world):
    draft = add_memo(session, world, status="draft", confirmed_ago=None)

    assert client.post(f"{BASE}/{draft.id}/approve").status_code == 404
    assert client.post(f"{BASE}/{draft.id}/return", json={"reason": "x"}).status_code == 404
    assert refreshed(session, draft).status == "draft"


def test_an_unknown_memo_is_404(client, world):
    assert client.post(f"{BASE}/999999999/approve").status_code == 404


# --- 一覧 ---


def test_list_shows_pending_memos_longest_waiting_first_with_the_waiting_time(
    client, session, world
):
    new = add_memo(session, world, confirmed_ago=timedelta(minutes=90), original_text="新しい")
    old = add_memo(
        session,
        world,
        confirmed_ago=timedelta(hours=25),
        original_text="<script>alert(1)</script>",
        warnings=["other_name"],
    )
    just_24 = add_memo(session, world, confirmed_ago=timedelta(hours=24), original_text="ちょうど")
    add_memo(session, world, status="approved")
    add_memo(session, world, status="returned")
    add_memo(session, world, status="withdrawn")
    add_memo(session, world, status="draft", confirmed_ago=None)

    data = client.get(BASE).json()

    assert [item["id"] for item in data] == [old.id, just_24.id, new.id]
    by_id = {item["id"]: item for item in data}
    assert (by_id[old.id]["waiting_minutes"], by_id[old.id]["overdue"]) == (25 * 60, True)
    # 24 時間ちょうどから「1 日以上待っています」
    assert (by_id[just_24.id]["waiting_minutes"], by_id[just_24.id]["overdue"]) == (24 * 60, True)
    assert (by_id[new.id]["waiting_minutes"], by_id[new.id]["overdue"]) == (90, False)
    # 画面に必要なものが入っている。タグは実行されず、そのままの文字で返る（FR-017）
    first = by_id[old.id]
    assert first["resident_name"] == "さくら 花子"
    assert first["author_name"] == "シティ"
    assert first["original_text"] == "<script>alert(1)</script>"
    assert first["rewritten_text"] == "今日は、よく笑っていました。"
    assert first["back_translation"] == "今日は、たくさん笑っていました。"
    assert first["warnings"] == ["other_name"]
    assert first["confirmed_at"] is not None


def test_list_does_not_show_another_facilitys_memo(client, session, world):
    other_facility_memo(session)
    mine = add_memo(session, world)

    assert [item["id"] for item in client.get(BASE).json()] == [mine.id]


def test_list_of_approved_memos_is_for_finding_what_to_unpublish(client, session, world):
    older = add_memo(session, world, status="approved", approved_at=NOW - timedelta(hours=5))
    newer = add_memo(session, world, status="approved", approved_at=NOW - timedelta(hours=1))
    add_memo(session, world)

    data = client.get(BASE, params={"status": "approved"}).json()

    assert [item["id"] for item in data] == [newer.id, older.id]
    # 経過時間は承認待ちのときだけ
    assert all(item["waiting_minutes"] is None and item["overdue"] is False for item in data)
    assert data[0]["approved_at"] is not None


def test_list_of_approved_memos_shows_only_the_newest_50(client, session, world):
    memos = [
        add_memo(session, world, status="approved", approved_at=NOW - timedelta(minutes=minutes))
        for minutes in range(52)
    ]

    data = client.get(BASE, params={"status": "approved"}).json()

    # 承認した日時の新しい方から 50 件（いちばん古い 2 件は出ない）
    assert [item["id"] for item in data] == [memo.id for memo in memos[:50]]


def test_list_of_pending_memos_is_not_limited(client, session, world):
    memos = [add_memo(session, world, confirmed_ago=timedelta(minutes=m + 1)) for m in range(52)]

    # 承認待ちは、全部出す（見落とすと、家族に届くのが遅れるため）
    assert len(client.get(BASE).json()) == len(memos)


def test_list_tells_which_memos_the_logged_in_staff_wrote(client, session, world, login_as):
    # 本人かどうかは、表示名ではなく職員の id で決めてサーバーが返す
    mine = add_memo(session, world, author=world["leader"])
    theirs = add_memo(session, world)

    data = {item["id"]: item["is_own"] for item in client.get(BASE).json()}
    assert data == {mine.id: True, theirs.id: False}

    login_as(world["other_leader"].user_id)
    data = {item["id"]: item["is_own"] for item in client.get(BASE).json()}
    assert data == {mine.id: False, theirs.id: False}


def test_the_result_of_an_operation_also_has_is_own(client, session, world):
    memo = add_memo(session, world)

    assert client.post(f"{BASE}/{memo.id}/approve").json()["is_own"] is False


def test_list_rejects_an_unknown_status(client, world):
    assert client.get(BASE, params={"status": "draft"}).status_code == 422


def test_a_returned_memo_goes_back_to_the_list_after_the_writer_confirms_again(
    client, session, world
):
    # 戻したメモは一覧から消え、書いた職員が直して「確かめました」を押す（007-T018）と、また載る
    memo = add_memo(session, world)
    client.post(f"{BASE}/{memo.id}/return", json={"reason": "直してください"})
    assert client.get(BASE).json() == []

    memo = refreshed(session, memo)
    memo.status = "pending"
    session.flush()

    assert [item["id"] for item in client.get(BASE).json()] == [memo.id]


# --- 件数（FR-015） ---


def test_count_is_the_pending_memos_of_the_whole_facility_including_the_leaders_own(
    client, session, world
):
    add_memo(session, world)
    add_memo(session, world, author=world["leader"])
    add_memo(session, world, status="approved")
    add_memo(session, world, status="draft", confirmed_ago=None)
    other_facility_memo(session)

    response = client.get(f"{BASE}/count")

    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_count_is_null_for_roles_that_cannot_approve(client, session, world, make_staff, login_as):
    add_memo(session, world)

    for role in ("care_worker", "counselor", "clerk"):
        login_as(make_staff(role=role).user_id)
        assert client.get(f"{BASE}/count").json() == {"count": None}

    login_as(world["director"].user_id)
    assert client.get(f"{BASE}/count").json() == {"count": 1}
