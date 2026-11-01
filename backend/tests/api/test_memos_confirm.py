"""様子のメモの訳し戻し・直す・確かめました・取り下げのテスト（spec 007 の 007-T016。FR-007〜010）。

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
DB と Redis は tests/conftest.py の session・redis を使う。一覧の確かめは、開発用の DB に残った
行に左右されないよう、このテストで作った id があるか／ないかで見る。
"""

import pytest
from sqlalchemy import select

from app.inquiry.llm import LLMUnavailable
from app.memos.prompts import build_back_translation_prompt
from app.models.memos import CareMemo, CareMemoRevision
from tests.fakes.llm import text_response

ORIGINAL = "Hari ini Ibu kurang tersenyum dibanding biasanya, tapi makan siangnya habis."
REWRITTEN = "今日はいつもより笑顔が少なめでしたが、お昼ごはんは全部召し上がりました。"
BACK = "Hari ini senyumnya lebih sedikit dari biasanya, tetapi makan siangnya habis semua."
EDITED = "今日はいつもより笑顔が少なく、お昼ごはんは全部召し上がりました。"
BACK_EDITED = "Hari ini senyumnya lebih sedikit, dan makan siangnya habis semua."


@pytest.fixture
def writer(client, make_staff, make_family, login_as):
    """介護職員（表示言語：インドネシア語）でログインした状態と、架空の入居者。"""
    staff = make_staff(role="care_worker", display_name="シティ", language="id")
    resident = make_family(name="さくら 花子")
    login_as(staff.user_id)
    return {"staff": staff, "resident_id": resident.resident_id}


def create(client, resident_id: int, **changes) -> int:
    body = {"original_text": ORIGINAL, "source_lang": "id", **changes}
    response = client.post(f"/api/staff/residents/{resident_id}/memos", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def rewrite(client, memo_id: int, **body):
    return client.post(f"/api/staff/memos/{memo_id}/rewrite", json=body or None)


def ready(client, fake_llm, resident_id: int) -> int:
    """下書きを作って「日本語にする」まで済ませた、確かめられる状態のメモの id。"""
    memo_id = create(client, resident_id)
    fake_llm.add(text_response(REWRITTEN), text_response(BACK))
    assert rewrite(client, memo_id).status_code == 200
    fake_llm.calls.clear()
    return memo_id


def revisions(session, memo_id: int) -> list[CareMemoRevision]:
    return list(
        session.scalars(
            select(CareMemoRevision)
            .where(CareMemoRevision.memo_id == memo_id)
            .order_by(CareMemoRevision.id)
        )
    )


def memo_row(session, memo_id: int) -> CareMemo:
    memo = session.get(CareMemo, memo_id)
    session.refresh(memo)
    return memo


def set_status(session, memo_id: int, status: str) -> None:
    session.get(CareMemo, memo_id).status = status
    session.flush()


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- 訳し戻し（FR-007） ---


def test_rewrite_adds_the_back_translation_from_the_rewritten_text_only(client, fake_llm, writer):
    memo_id = create(client, writer["resident_id"])
    fake_llm.add(text_response(REWRITTEN), text_response(BACK))

    data = rewrite(client, memo_id).json()

    # 原文・整えた日本語・訳し戻しの 3 つが並ぶ
    assert (data["original_text"], data["rewritten_text"], data["back_translation"]) == (
        ORIGINAL,
        REWRITTEN,
        BACK,
    )
    # 訳し戻しの AI には、整えた日本語だけを渡す。原文は渡さない
    _, second = fake_llm.calls
    assert second.messages == [
        {"role": "system", "content": build_back_translation_prompt("id")},
        {"role": "user", "content": REWRITTEN},
    ]


def test_japanese_staff_gets_no_back_translation(
    client, make_staff, make_family, login_as, fake_llm
):
    staff = make_staff(role="care_worker", language="ja")
    resident = make_family()
    login_as(staff.user_id)
    memo_id = create(
        client, resident.resident_id, original_text="きょうは元気でした", source_lang="ja"
    )
    fake_llm.add(text_response("今日は、元気でした。"))

    data = rewrite(client, memo_id).json()

    assert len(fake_llm.calls) == 1
    assert data["back_translation"] is None
    # 日本語の職員は、訳し戻しなしで確かめられる（FR-007）
    assert client.post(f"/api/staff/memos/{memo_id}/confirm").json()["status"] == "pending"


def test_when_the_back_translation_stops_nothing_is_saved(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"])
    # 整えるのは通り、訳し戻しで止まった
    fake_llm.add(text_response(REWRITTEN), LLMUnavailable("timeout"))

    response = rewrite(client, memo_id)

    assert response.status_code == 503
    assert error_code(response) == "ai_unavailable"
    memo = memo_row(session, memo_id)
    assert (memo.rewritten_text, memo.back_translation) == (None, None)
    assert revisions(session, memo_id) == []


def test_rewrite_rejects_unknown_fields(client, fake_llm, writer):
    memo_id = create(client, writer["resident_id"])

    response = rewrite(client, memo_id, status="approved")

    assert response.status_code == 422
    assert fake_llm.calls == []


# --- 整えた日本語を直したあとは、訳し戻しだけ（back_translate_only） ---


def test_editing_the_rewritten_text_then_back_translating_only(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    edited = client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED}).json()
    # 古い訳し戻しは消える（直した文の訳し戻しではないため）
    assert (edited["rewritten_text"], edited["back_translation"]) == (EDITED, None)
    fake_llm.add(text_response(BACK_EDITED))

    data = rewrite(client, memo_id, back_translate_only=True).json()

    # 整え直さず、訳し戻しを 1 回だけ呼ぶ。渡すのは直した整えた日本語だけ
    [call] = fake_llm.calls
    assert call.messages == [
        {"role": "system", "content": build_back_translation_prompt("id")},
        {"role": "user", "content": EDITED},
    ]
    assert (data["rewritten_text"], data["back_translation"]) == (EDITED, BACK_EDITED)
    # 履歴は 1 件増える（直したあとの文で。やり直しの回数に数える）
    last = revisions(session, memo_id)[-1]
    assert (last.original_text, last.rewritten_text, last.back_translation) == (
        ORIGINAL,
        EDITED,
        BACK_EDITED,
    )
    assert len(revisions(session, memo_id)) == 2


def test_back_translate_only_needs_a_rewritten_text(client, fake_llm, writer):
    memo_id = create(client, writer["resident_id"])

    response = rewrite(client, memo_id, back_translate_only=True)

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"
    assert fake_llm.calls == []


def test_back_translate_only_is_not_for_japanese_staff(
    client, make_staff, make_family, login_as, fake_llm
):
    staff = make_staff(role="care_worker", language="ja")
    resident = make_family()
    login_as(staff.user_id)
    memo_id = create(
        client, resident.resident_id, original_text="きょうは元気でした", source_lang="ja"
    )
    fake_llm.add(text_response("今日は、元気でした。"))
    rewrite(client, memo_id)
    fake_llm.calls.clear()

    response = rewrite(client, memo_id, back_translate_only=True)

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"
    assert fake_llm.calls == []


def test_back_translate_only_when_the_ai_is_down_keeps_the_edit(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED})
    fake_llm.add(LLMUnavailable("timeout"))

    response = rewrite(client, memo_id, back_translate_only=True)

    assert response.status_code == 503
    memo = memo_row(session, memo_id)
    # 直した文は残り、履歴は増えない（やり直しの回数に数えない）
    assert (memo.rewritten_text, memo.back_translation) == (EDITED, None)
    assert len(revisions(session, memo_id)) == 1


def test_back_translate_only_counts_toward_the_rewrite_limit(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    # 履歴を 4 件足して 5 件にする
    for _ in range(4):
        fake_llm.add(text_response(BACK))
        assert rewrite(client, memo_id, back_translate_only=True).status_code == 200
    fake_llm.calls.clear()
    assert len(revisions(session, memo_id)) == 5

    response = rewrite(client, memo_id, back_translate_only=True)

    assert response.status_code == 409
    assert error_code(response) == "rewrite_limit"
    assert fake_llm.calls == []


# --- 原文・整えた日本語を直す（FR-008） ---


def test_editing_the_original_clears_the_rewrite_and_the_back_translation(
    client, session, fake_llm, writer
):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    new_original = "Ibu tidak mau makan karena pusing, lalu jatuh di kamar mandi."

    data = client.patch(f"/api/staff/memos/{memo_id}", json={"original_text": new_original}).json()

    # 直した原文から作ったものではなくなるので、整えた日本語・訳し戻しは消す。履歴は残る
    assert data["original_text"] == new_original
    assert (data["rewritten_text"], data["back_translation"]) == (None, None)
    assert len(revisions(session, memo_id)) == 1
    # 印は、原文だけで付く分を付け直す（急変の言葉）
    assert data["warnings"] == ["urgent_words"]
    assert fake_llm.calls == []


def test_editing_both_keeps_the_sent_rewritten_text(client, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    new_original = "Ibu kurang tersenyum, tapi makan siangnya habis."

    data = client.patch(
        f"/api/staff/memos/{memo_id}",
        json={"original_text": new_original, "rewritten_text": EDITED},
    ).json()

    assert (data["original_text"], data["rewritten_text"]) == (new_original, EDITED)
    assert data["back_translation"] is None


def test_editing_the_rewritten_text_redoes_the_warnings(client, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    data = client.patch(
        f"/api/staff/memos/{memo_id}",
        json={"rewritten_text": "今日は、お医者さんの薬を飲みました。"},
    ).json()

    assert "medical_added" in data["warnings"]


def test_the_rewritten_text_cannot_be_written_before_the_first_rewrite(client, writer):
    memo_id = create(client, writer["resident_id"])

    response = client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED})

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"


def test_the_original_can_be_edited_before_the_first_rewrite(client, writer):
    memo_id = create(client, writer["resident_id"])

    data = client.patch(
        f"/api/staff/memos/{memo_id}", json={"original_text": "  Ibu sehat.  "}
    ).json()

    assert data["original_text"] == "Ibu sehat."


@pytest.mark.parametrize("status", ["pending", "approved", "withdrawn"])
def test_only_draft_or_returned_can_be_edited(client, session, fake_llm, writer, status):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, status)

    response = client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED})

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"
    assert memo_row(session, memo_id).rewritten_text == REWRITTEN


def test_a_returned_memo_can_be_edited(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, "returned")

    response = client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED})

    assert response.status_code == 200
    assert response.json()["status"] == "returned"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"original_text": ""},
        {"original_text": "  \n "},
        {"original_text": "あ" * 501},
        {"rewritten_text": ""},
        {"rewritten_text": "あ" * 1001},
        {"status": "approved"},
        {"rewritten_text": EDITED, "back_translation": "x"},
    ],
    ids=[
        "nothing",
        "empty_original",
        "blank_original",
        "long_original",
        "empty_rewritten",
        "long_rewritten",
        "status",
        "back_translation",
    ],
)
def test_edit_rejects_invalid_input(client, session, fake_llm, writer, body):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    response = client.patch(f"/api/staff/memos/{memo_id}", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert memo_row(session, memo_id).rewritten_text == REWRITTEN


def test_edit_accepts_the_longest_texts(client, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    response = client.patch(
        f"/api/staff/memos/{memo_id}",
        json={"original_text": "あ" * 500, "rewritten_text": "い" * 1000},
    )

    assert response.status_code == 200


def test_edited_text_is_returned_as_plain_text(client, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    data = client.patch(
        f"/api/staff/memos/{memo_id}", json={"rewritten_text": "<script>alert(1)</script>"}
    ).json()

    assert data["rewritten_text"] == "<script>alert(1)</script>"


# --- 「確かめました」（FR-009） ---


def test_confirm_makes_the_memo_pending_and_keeps_the_time(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    response = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    memo = memo_row(session, memo_id)
    assert memo.status == "pending"
    assert memo.confirmed_at is not None
    # 確かめるだけでは、AI を呼ばない
    assert fake_llm.calls == []


def test_a_draft_is_not_shown_to_leaders_until_it_is_confirmed(
    client, make_staff, login_as, fake_llm, writer
):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    leader = make_staff(role="leader", display_name="リーダー")

    login_as(leader.user_id)
    before = client.get("/api/staff/memo-approvals").json()
    assert memo_id not in [item["id"] for item in before]

    login_as(writer["staff"].user_id)
    client.post(f"/api/staff/memos/{memo_id}/confirm")

    # 押したあとは、ほかのリーダーの承認待ちの一覧に出る。介護職員には承認の一覧は開けない
    login_as(leader.user_id)
    after = client.get("/api/staff/memo-approvals").json()
    assert memo_id in [item["id"] for item in after]
    login_as(writer["staff"].user_id)
    assert client.get("/api/staff/memo-approvals").status_code == 403


def test_confirm_needs_a_rewritten_text(client, writer):
    memo_id = create(client, writer["resident_id"])

    response = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"


def test_confirm_needs_the_back_translation_unless_japanese(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    # 整えた日本語を直したら、古い訳し戻しは消える。訳し戻し直すまで確かめられない
    client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED})

    blocked = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert blocked.status_code == 409
    assert error_code(blocked) == "invalid_state"
    assert memo_row(session, memo_id).status == "draft"
    fake_llm.add(text_response(BACK_EDITED))
    rewrite(client, memo_id, back_translate_only=True)
    assert client.post(f"/api/staff/memos/{memo_id}/confirm").status_code == 200


def test_a_returned_memo_can_be_fixed_and_confirmed_again(client, session, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, "returned")
    memo = session.get(CareMemo, memo_id)
    memo.return_reason = "ほかの方の名前が入っています"
    session.flush()

    shown = client.get(f"/api/staff/memos/{memo_id}").json()
    assert (shown["status"], shown["return_reason"]) == ("returned", "ほかの方の名前が入っています")
    response = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.parametrize("status", ["pending", "approved", "withdrawn"])
def test_only_draft_or_returned_can_be_confirmed(client, session, fake_llm, writer, status):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, status)

    response = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"
    assert memo_row(session, memo_id).status == status


def test_confirming_twice_is_refused_the_second_time(client, fake_llm, writer):
    memo_id = ready(client, fake_llm, writer["resident_id"])

    assert client.post(f"/api/staff/memos/{memo_id}/confirm").status_code == 200
    second = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert second.status_code == 409
    assert error_code(second) == "invalid_state"


# --- 取り下げ（FR-010） ---


@pytest.mark.parametrize("status", ["draft", "pending", "returned"])
def test_withdraw_before_it_is_public(client, session, fake_llm, writer, status):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, status)

    response = client.post(f"/api/staff/memos/{memo_id}/withdraw")

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert memo_row(session, memo_id).withdrawn_at is not None


@pytest.mark.parametrize("status", ["approved", "withdrawn"])
def test_an_approved_or_withdrawn_memo_cannot_be_withdrawn(
    client, session, fake_llm, writer, status
):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    set_status(session, memo_id, status)

    response = client.post(f"/api/staff/memos/{memo_id}/withdraw")

    assert response.status_code == 409
    assert error_code(response) == "invalid_state"
    assert memo_row(session, memo_id).status == status


def test_a_withdrawn_memo_leaves_the_approval_list_and_cannot_be_confirmed(
    client, make_staff, login_as, fake_llm, writer
):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    client.post(f"/api/staff/memos/{memo_id}/confirm")
    leader = make_staff(role="leader")
    login_as(leader.user_id)
    assert memo_id in [item["id"] for item in client.get("/api/staff/memo-approvals").json()]

    login_as(writer["staff"].user_id)
    assert client.post(f"/api/staff/memos/{memo_id}/withdraw").status_code == 200
    again = client.post(f"/api/staff/memos/{memo_id}/confirm")

    assert again.status_code == 409
    login_as(leader.user_id)
    assert memo_id not in [item["id"] for item in client.get("/api/staff/memo-approvals").json()]


def test_withdrawing_frees_a_slot_of_the_daily_limit(client, writer):
    ids = [create(client, writer["resident_id"]) for _ in range(3)]
    full = client.post(
        f"/api/staff/residents/{writer['resident_id']}/memos",
        json={"original_text": ORIGINAL, "source_lang": "id"},
    )
    assert full.status_code == 409

    client.post(f"/api/staff/memos/{ids[0]}/withdraw")

    assert (
        client.post(
            f"/api/staff/residents/{writer['resident_id']}/memos",
            json={"original_text": ORIGINAL, "source_lang": "id"},
        ).status_code
        == 201
    )


# --- 本人だけ・役割 ---


def test_other_staff_get_404_for_every_operation_even_leaders(
    client, session, make_staff, login_as, fake_llm, writer
):
    memo_id = ready(client, fake_llm, writer["resident_id"])
    client.post(f"/api/staff/memos/{memo_id}/confirm")

    for role in ("care_worker", "leader"):
        login_as(make_staff(role=role).user_id)
        responses = [
            client.get(f"/api/staff/memos/{memo_id}"),
            client.patch(f"/api/staff/memos/{memo_id}", json={"rewritten_text": EDITED}),
            rewrite(client, memo_id),
            rewrite(client, memo_id, back_translate_only=True),
            client.post(f"/api/staff/memos/{memo_id}/confirm"),
            client.post(f"/api/staff/memos/{memo_id}/withdraw"),
        ]
        assert [r.status_code for r in responses] == [404] * 6
        assert {error_code(r) for r in responses} == {"not_found"}
    assert fake_llm.calls == []
    memo = memo_row(session, memo_id)
    assert (memo.status, memo.rewritten_text) == ("pending", REWRITTEN)


def test_unknown_memo_is_404(client, writer):
    assert (
        client.patch("/api/staff/memos/999999999", json={"rewritten_text": EDITED}).status_code
        == 404
    )
    assert client.post("/api/staff/memos/999999999/confirm").status_code == 404
    assert client.post("/api/staff/memos/999999999/withdraw").status_code == 404


@pytest.mark.parametrize("role", ["clerk", "counselor", "director"])
def test_other_roles_are_forbidden(client, make_staff, login_as, role):
    login_as(make_staff(role=role).user_id)

    assert client.patch("/api/staff/memos/1", json={"rewritten_text": EDITED}).status_code == 403
    assert client.post("/api/staff/memos/1/confirm").status_code == 403
    assert client.post("/api/staff/memos/1/withdraw").status_code == 403


def test_family_is_forbidden_and_logged_out_is_401(client, make_family, login_as):
    family = make_family()

    assert client.post("/api/staff/memos/1/confirm").status_code == 401
    login_as(family.user_id)
    assert client.post("/api/staff/memos/1/confirm").status_code == 403
    assert client.post("/api/staff/memos/1/withdraw").status_code == 403
    assert client.patch("/api/staff/memos/1", json={"rewritten_text": EDITED}).status_code == 403


def test_a_leader_can_confirm_their_own_memo_but_not_approve_it(
    client, make_staff, make_family, login_as, fake_llm
):
    # 書いた本人がリーダーでも、確かめるまでは本人の操作。承認はほかのリーダーが行う（FR-011a）
    leader = make_staff(role="leader", language="id")
    resident = make_family()
    login_as(leader.user_id)
    memo_id = ready(client, fake_llm, resident.resident_id)

    assert client.post(f"/api/staff/memos/{memo_id}/confirm").status_code == 200
    approve = client.post(f"/api/staff/memo-approvals/{memo_id}/approve")

    assert approve.status_code == 403
    assert error_code(approve) == "self_approval"
