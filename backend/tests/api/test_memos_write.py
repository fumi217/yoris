"""様子のメモを書く API のテスト（spec 007 の 007-T007。FR-001・FR-003・FR-004・FR-005・FR-020）。

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
DB と Redis は tests/conftest.py の session・redis を使う。
"""

import pytest
from sqlalchemy import func, select

from app.clock import today_jst
from app.inquiry.llm import LLMUnavailable
from app.memos.prompts import build_rewrite_prompt
from app.models.memos import CareMemo, CareMemoRevision
from tests.fakes.llm import text_response

ORIGINAL = "Hari ini Ibu kurang tersenyum dibanding biasanya, tapi makan siangnya habis."
REWRITTEN = "今日はいつもより笑顔が少なめでしたが、お昼ごはんは全部召し上がりました。"


@pytest.fixture
def writer(client, make_staff, make_family, login_as):
    """介護職員（表示言語：インドネシア語）でログインした状態と、架空の入居者。"""
    staff = make_staff(role="care_worker", display_name="シティ", language="id")
    resident = make_family(display_name="さくらさんの母")
    login_as(staff.user_id)
    return {"staff": staff, "resident_id": resident.resident_id}


def url(resident_id: int) -> str:
    return f"/api/staff/residents/{resident_id}/memos"


def create(client, resident_id: int, **changes):
    body = {"original_text": ORIGINAL, "source_lang": "id", **changes}
    return client.post(url(resident_id), json=body)


def revisions(session, memo_id: int) -> list[CareMemoRevision]:
    return list(
        session.scalars(
            select(CareMemoRevision)
            .where(CareMemoRevision.memo_id == memo_id)
            .order_by(CareMemoRevision.id)
        )
    )


# --- 下書き（原文を先に保存する。AI は呼ばない） ---


def test_create_saves_the_original_as_a_draft_without_calling_the_ai(
    client, session, fake_llm, writer
):
    response = create(client, writer["resident_id"])

    assert response.status_code == 201
    data = response.json()
    assert data["original_text"] == ORIGINAL
    assert data["source_lang"] == "id"
    assert data["status"] == "draft"
    assert data["rewritten_text"] is None
    assert data["memo_date"] == today_jst().isoformat()
    memo = session.get(CareMemo, data["id"])
    # 書いた職員は、ログイン中の職員から決める
    assert memo.author_staff_id == writer["staff"].id
    assert memo.resident_id == writer["resident_id"]
    # 下書きを作るだけでは、AI は呼ばない（「日本語にする」を押したときに呼ぶ）
    assert fake_llm.calls == []


def test_create_strips_surrounding_whitespace(client, writer):
    data = create(client, writer["resident_id"], original_text="  今日は元気でした。\n").json()

    assert data["original_text"] == "今日は元気でした。"


@pytest.mark.parametrize(
    "changes",
    [
        {"original_text": ""},
        {"original_text": "   \n "},
        {"original_text": "あ" * 501},
        {"source_lang": "fr"},
        {"source_lang": ""},
    ],
    ids=["empty", "blank", "too_long", "unknown_lang", "empty_lang"],
)
def test_create_rejects_invalid_input(client, session, writer, changes):
    before = session.scalar(select(func.count()).select_from(CareMemo))

    response = create(client, writer["resident_id"], **changes)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert session.scalar(select(func.count()).select_from(CareMemo)) == before


def test_create_accepts_exactly_500_characters(client, writer):
    assert create(client, writer["resident_id"], original_text="あ" * 500).status_code == 201


def test_create_ignores_no_extra_fields(client, writer):
    # 入居者・書いた職員・状態は、本文では決められない
    response = create(client, writer["resident_id"], author_staff_id=1, status="approved")

    assert response.status_code == 422


def test_create_for_an_unknown_resident_is_404(client, writer):
    response = create(client, 999999999)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- 役割 ---


@pytest.mark.parametrize("role", ["care_worker", "leader"])
def test_care_worker_and_leader_can_write(client, make_staff, make_family, login_as, role):
    resident = make_family()
    login_as(make_staff(role=role).user_id)

    assert create(client, resident.resident_id).status_code == 201


@pytest.mark.parametrize("role", ["clerk", "counselor", "director"])
def test_other_staff_are_forbidden(client, make_staff, make_family, login_as, role):
    resident = make_family()
    login_as(make_staff(role=role).user_id)

    assert create(client, resident.resident_id).status_code == 403
    assert client.get("/api/staff/memos").status_code == 403
    assert client.post("/api/staff/memos/1/rewrite").status_code == 403


def test_family_is_forbidden_and_logged_out_is_401(client, make_family, login_as):
    family = make_family()

    assert create(client, family.resident_id).status_code == 401
    login_as(family.user_id)
    assert create(client, family.resident_id).status_code == 403
    assert client.get("/api/staff/memos").status_code == 403


# --- 「日本語にする」 ---


def test_rewrite_saves_the_japanese_text_and_a_revision(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(text_response(REWRITTEN))

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 200
    data = response.json()
    # 整えた日本語が出て、原文も残っている（シナリオ 1）
    assert data["rewritten_text"] == REWRITTEN
    assert data["original_text"] == ORIGINAL
    assert data["status"] == "draft"
    # 訳し戻しは、ミニマム版ではしない（作り込みの 007-T017 で足す）
    assert data["back_translation"] is None
    [revision] = revisions(session, memo_id)
    assert (revision.original_text, revision.rewritten_text) == (ORIGINAL, REWRITTEN)
    assert revision.model == "fake"
    assert revision.latency_ms is not None


def test_rewrite_sends_only_the_fixed_instructions_and_the_original(
    client, session, fake_llm, writer
):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(text_response(REWRITTEN))

    client.post(f"/api/staff/memos/{memo_id}/rewrite")

    [call] = fake_llm.calls
    # 固定の指示（system）と原文（user）だけ。ツールは渡さない（FR-005）
    assert call.messages == [
        {"role": "system", "content": build_rewrite_prompt("id")},
        {"role": "user", "content": ORIGINAL},
    ]
    assert call.tools is None
    # 入居者の呼び名・氏名・職員の名前は、AI に渡さない
    sent = " ".join(message["content"] for message in call.messages)
    for private in ("さくらさんの母", "シティ"):
        assert private not in sent


def test_rewrite_again_adds_a_second_revision(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(text_response(REWRITTEN), text_response("今日は笑顔が少なめでした。"))

    client.post(f"/api/staff/memos/{memo_id}/rewrite")
    data = client.post(f"/api/staff/memos/{memo_id}/rewrite").json()

    assert data["rewritten_text"] == "今日は笑顔が少なめでした。"
    assert [r.rewritten_text for r in revisions(session, memo_id)] == [
        REWRITTEN,
        "今日は笑顔が少なめでした。",
    ]


def test_when_the_ai_is_down_the_original_stays_and_nothing_is_counted(
    client, session, fake_llm, writer
):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(LLMUnavailable("timeout"))

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_unavailable"
    # 原文は消えず、整えた日本語も履歴もない（やり直しの回数に数えない。R-09・シナリオ 5）
    memo = client.get(f"/api/staff/memos/{memo_id}").json()
    assert memo["original_text"] == ORIGINAL
    assert memo["rewritten_text"] is None
    assert revisions(session, memo_id) == []
    # 時間をおいて、もう一度押せる
    fake_llm.add(text_response(REWRITTEN))
    assert client.post(f"/api/staff/memos/{memo_id}/rewrite").status_code == 200
    assert len(revisions(session, memo_id)) == 1


def test_an_empty_answer_is_treated_as_the_ai_being_down(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(text_response("   "))

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 503
    assert revisions(session, memo_id) == []


def test_rewrite_is_only_for_draft_or_returned(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    memo = session.get(CareMemo, memo_id)
    memo.status = "approved"
    session.flush()

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert fake_llm.calls == []


def test_returned_memo_can_be_rewritten_again(client, fake_llm, session, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    session.get(CareMemo, memo_id).status = "returned"
    session.flush()
    fake_llm.add(text_response(REWRITTEN))

    assert client.post(f"/api/staff/memos/{memo_id}/rewrite").status_code == 200


def test_text_is_returned_as_plain_text(client, session, fake_llm, writer):
    # 原文・整えた日本語は、そのまま文字として返す（タグは実行されない。FR-017）
    memo_id = create(
        client, writer["resident_id"], original_text="<script>alert(1)</script>"
    ).json()["id"]
    fake_llm.add(text_response("<b>整えた</b>"))

    data = client.post(f"/api/staff/memos/{memo_id}/rewrite").json()

    assert data["original_text"] == "<script>alert(1)</script>"
    assert data["rewritten_text"] == "<b>整えた</b>"


# --- 一覧・1 つ ---


def test_list_has_only_my_memos_and_can_be_filtered(
    client, session, make_staff, make_family, writer
):
    other_resident = make_family().resident_id
    mine_a = create(client, writer["resident_id"]).json()["id"]
    mine_b = create(client, other_resident).json()["id"]
    # ほかの職員のメモは、一覧に出ない
    other_staff = make_staff(role="care_worker")
    session.add(
        CareMemo(
            resident_id=writer["resident_id"],
            author_staff_id=other_staff.id,
            memo_date=today_jst(),
            source_lang="ja",
            original_text="ほかの職員のメモ",
        )
    )
    session.flush()

    everything = client.get("/api/staff/memos").json()
    by_resident = client.get(f"/api/staff/memos?resident_id={writer['resident_id']}").json()
    by_day = client.get(f"/api/staff/memos?date={today_jst().isoformat()}").json()
    other_day = client.get("/api/staff/memos?date=2000-01-01").json()

    assert [m["id"] for m in everything if m["id"] in (mine_a, mine_b)] == [mine_b, mine_a]
    assert all(m["original_text"] != "ほかの職員のメモ" for m in everything)
    assert [m["id"] for m in by_resident] == [mine_a]
    assert {mine_a, mine_b} <= {m["id"] for m in by_day}
    assert other_day == []


def test_other_staffs_memo_is_404_for_get_and_rewrite(
    client, session, make_staff, fake_llm, writer
):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    # ほかの介護職員・リーダーが、id を指定して開く・整えようとする
    for role in ("care_worker", "leader"):
        other = make_staff(role=role)
        client.cookies.clear()
        from app.auth.sessions import SESSION_COOKIE, create_session

        client.cookies.set(SESSION_COOKIE, create_session(other.user_id))

        get = client.get(f"/api/staff/memos/{memo_id}")
        post = client.post(f"/api/staff/memos/{memo_id}/rewrite")

        assert get.status_code == 404 and get.json()["error"]["code"] == "not_found"
        assert post.status_code == 404
    assert fake_llm.calls == []


def test_unknown_memo_is_404(client, writer):
    assert client.get("/api/staff/memos/999999999").status_code == 404
    assert client.post("/api/staff/memos/999999999/rewrite").status_code == 404
