"""様子のメモの機械の目・1 日 3 件・やり直しの上限のテスト（spec 007 の 007-T015。FR-001・FR-016）。

機械の目は DB を使わない。1 日 3 件とやり直しの上限は、DB と fake_llm（モック）で確かめる。
"""

import pytest
from sqlalchemy import select

from app.memos.checks import check_memo
from app.models.memos import CareMemo, CareMemoRevision
from tests.fakes.llm import text_response


def check(original, rewritten, *, lang="ja", back=None, names=()):
    return check_memo(
        original_text=original,
        source_lang=lang,
        rewritten_text=rewritten,
        back_translation=back,
        other_resident_names=list(names),
    )


# --- 機械の目 ---


def test_plain_memo_has_no_warnings():
    warnings = check(
        "きょうはお昼ごはんを全部たべました", "今日はお昼ごはんを全部召し上がりました。"
    )

    assert warnings == []


def test_medical_word_added_by_the_rewrite():
    warnings = check("きょうは元気がなかった", "今日は元気がなく、体調が悪そうでした。")

    assert warnings == ["medical_added"]


def test_medical_word_in_japanese_original_is_not_added():
    warnings = check("きょうは薬をのんだ", "今日は薬を飲みました。")

    # 原文にもある言葉なので、足したことにはしない。原文にあることだけを知らせる
    assert warnings == ["medical_in_original"]


def test_medical_word_added_to_a_foreign_original_without_any_medical_word():
    warnings = check(
        "Hari ini Ibu kurang tersenyum.",
        "今日は笑顔が少なく、熱がありそうでした。",
        lang="id",
        back="Hari ini senyumnya sedikit dan sepertinya demam.",
    )

    assert "medical_added" in warnings
    assert "medical_in_original" not in warnings


def test_medical_word_in_a_foreign_original():
    warnings = check(
        "Ibu minum obat setelah makan siang.",
        "お昼ごはんのあとに薬を飲みました。",
        lang="id",
        back="Ibu minum obat setelah makan siang.",
    )

    assert warnings == ["medical_in_original"]


def test_english_original_with_medical_word():
    warnings = check(
        "He had a fever this morning.",
        "今朝は熱がありました。",
        lang="en",
        back="He had a fever this morning.",
    )

    assert warnings == ["medical_in_original"]


@pytest.mark.parametrize(
    ("rewritten_len", "expected"),
    [(9, True), (10, False), (40, False), (41, True)],
    ids=["under_half", "exactly_half", "exactly_double", "over_double"],
)
def test_length_changed_compares_with_the_original_when_japanese(rewritten_len, expected):
    warnings = check("あ" * 20, "い" * rewritten_len)

    assert ("length_changed" in warnings) is expected


def test_length_changed_uses_the_back_translation_for_a_foreign_original():
    original = "Ibu makan siang dengan lahap sekali hari ini."

    long_back = original * 3
    assert "length_changed" in check(original, "今日は食べました。", lang="id", back=long_back)
    assert "length_changed" not in check(original, "今日は食べました。", lang="id", back=original)
    # 訳し戻しがなければ、文字の種類が違うので比べない
    assert "length_changed" not in check(original, "今日は食べました。", lang="id", back=None)


def test_other_resident_name_in_the_rewrite():
    warnings = check(
        "さくらさんと散歩しました",
        "さくらさんの母と散歩しました。",
        names=["さくらさんの母", "ひまわりさん"],
    )

    assert "other_name" in warnings
    assert "other_name" not in check("散歩しました", "散歩しました。", names=["ひまわりさん"])


def test_blank_names_never_match():
    assert "other_name" not in check("散歩しました", "散歩しました。", names=[""])


@pytest.mark.parametrize(
    ("original", "lang"),
    [
        ("廊下でころんでいた", "ja"),
        ("Ibu jatuh di kamar mandi.", "id"),
        ("She collapsed in the hallway.", "en"),
    ],
)
def test_urgent_words_in_the_original(original, lang):
    assert "urgent_words" in check(original, "廊下で倒れていました。", lang=lang, back=original)


def test_warnings_come_in_a_fixed_order():
    warnings = check(
        "きょうは薬のあとにころんだ",
        "今日は薬のあとに転びました。さくらさんの母。",
        names=["さくらさんの母"],
    )

    assert warnings == ["medical_in_original", "other_name", "urgent_words"]


# --- 1 日 3 件・やり直しの上限（DB） ---


@pytest.fixture
def writer(client, make_staff, make_family, login_as):
    staff = make_staff(role="care_worker", display_name="シティ", language="id")
    resident = make_family(display_name="さくらさんの母")
    other = make_family(display_name="ひまわりさん")
    login_as(staff.user_id)
    return {"staff": staff, "resident_id": resident.resident_id, "other_id": other.resident_id}


def create(client, resident_id):
    return client.post(
        f"/api/staff/residents/{resident_id}/memos",
        json={"original_text": "今日は元気でした。", "source_lang": "ja"},
    )


def test_fourth_memo_of_the_day_is_refused(client, writer):
    for _ in range(3):
        assert create(client, writer["resident_id"]).status_code == 201

    response = create(client, writer["resident_id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "memo_limit"


def test_the_limit_is_per_resident(client, writer):
    for _ in range(3):
        create(client, writer["resident_id"])

    assert create(client, writer["other_id"]).status_code == 201


def test_withdrawn_memos_are_not_counted(client, session, writer):
    ids = [create(client, writer["resident_id"]).json()["id"] for _ in range(3)]
    session.get(CareMemo, ids[0]).status = "withdrawn"
    session.commit()

    assert create(client, writer["resident_id"]).status_code == 201


def test_rewrite_checks_warnings_against_other_residents(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(text_response("今日はひまわりさんと一緒に過ごしました。"))

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 200
    assert "other_name" in response.json()["warnings"]
    assert response.json()["warnings"] == session.get(CareMemo, memo_id).warnings


def test_sixth_rewrite_is_refused_without_calling_the_ai(client, session, fake_llm, writer):
    memo_id = create(client, writer["resident_id"]).json()["id"]
    fake_llm.add(*[text_response("今日は元気でした。") for _ in range(5)])
    for _ in range(5):
        assert client.post(f"/api/staff/memos/{memo_id}/rewrite").status_code == 200
    calls = len(fake_llm.calls)

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "rewrite_limit"
    assert len(fake_llm.calls) == calls
    count = len(
        session.scalars(select(CareMemoRevision).where(CareMemoRevision.memo_id == memo_id)).all()
    )
    assert count == 5
