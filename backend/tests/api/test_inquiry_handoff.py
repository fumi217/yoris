"""AI から職員に渡す処理のテスト（spec 004 の 004-T022。FR-009〜011・FR-016・research.md R-05）。

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.inquiry import InquiryConversation, InquiryMessage, StaffMessage
from tests.fakes.llm import tool_call_response

URL = "/api/family/inquiry/messages"


@pytest.fixture
def family(client, make_family, login_as):
    family = make_family()
    login_as(family.user_id)
    return family


def staff_messages(session, family) -> list[StaffMessage]:
    return list(
        session.scalars(
            select(StaffMessage)
            .where(StaffMessage.resident_id == family.resident_id)
            .order_by(StaffMessage.id)
        )
    )


def hand_off(fake_llm, category: str, summary: str, existing: int | None = None) -> None:
    args = {"category": category, "summary": summary}
    if existing is not None:
        args["existing_message_id"] = existing
    fake_llm.add(tool_call_response("hand_off_to_staff", args))


def test_hand_off_creates_staff_message_with_empty_assignee(client, session, fake_llm, family):
    hand_off(fake_llm, "money", "先月の請求書の金額について知りたい")

    response = client.post(URL, json={"body": "先月の請求書の金額を教えてください"})

    assert response.status_code == 201
    data = response.json()
    assert data["ai"]["ai_result"] == "handed_off"
    # 家族の画面は「施設の職員にお伝えしました」（辞書の文。本文は空）
    assert data["ai"]["body"] == ""
    assert data["ai"]["handoff"] == {
        "status": "waiting",
        "urgent": False,
        "already": False,
        "over_three_days": False,
    }
    assert data["family"]["handoff"] is None
    [message] = staff_messages(session, family)
    # 原文（渡すきっかけの家族の発言）・要約・種類が残り、担当は空（FR-011・FR-012b）
    assert message.origin_message_id == data["family"]["id"]
    assert session.get(InquiryMessage, message.origin_message_id).body == (
        "先月の請求書の金額を教えてください"
    )
    assert message.summary == "先月の請求書の金額について知りたい"
    assert message.category == "money"
    assert message.status == "waiting"
    assert message.assignee_id is None
    assert message.handed_at is not None
    # AI の発言は、どのメッセージに渡したかを持つ
    assert session.get(InquiryMessage, data["ai"]["id"]).staff_message_id == message.id


def test_guarded_words_are_handed_off_even_if_ai_answers(client, session, fake_llm, family):
    # 言葉による決まり（「薬」）に当たった発言で AI が答えようとしても受け付けない（R-05）
    fake_llm.add(
        tool_call_response("answer_family", {"text": "お薬は飲んでいます", "source_ids": []})
    )

    response = client.post(URL, json={"body": "母は薬をちゃんと飲んでいますか？"})

    data = response.json()
    assert data["ai"]["ai_result"] == "handed_off"
    assert data["ai"]["body"] == ""
    [message] = staff_messages(session, family)
    assert message.category == "medical"
    # AI の答えの文は、どこにも残さない
    assert "お薬は飲んでいます" not in message.summary


def test_guarded_category_wins_over_ai_category(client, session, fake_llm, family):
    hand_off(fake_llm, "other", "母について")

    client.post(URL, json={"body": "母が倒れたと聞きました"})

    assert [m.category for m in staff_messages(session, family)] == ["urgent"]


def test_urgent_tells_family_to_call(client, fake_llm, family):
    hand_off(fake_llm, "urgent", "倒れたと聞いた")

    data = client.post(URL, json={"body": "母が倒れたと聞きました"}).json()

    # 画面は「お急ぎのときは、施設にお電話ください」も出す（Edge Cases）
    assert data["ai"]["handoff"]["urgent"] is True


def test_same_waiting_message_is_joined_not_created(client, session, fake_llm, family):
    hand_off(fake_llm, "care_request", "冬物の上着を持ってきてほしい")
    first = client.post(URL, json={"body": "冬物の上着を持って行ってもいいですか"}).json()
    [message] = staff_messages(session, family)

    hand_off(fake_llm, "care_request", "冬物の上着", existing=message.id)
    second = client.post(URL, json={"body": "上着の件、どうなりましたか"}).json()

    # 新しく渡さずに「すでに施設の職員にお伝えしています」（FR-016）
    assert [m.id for m in staff_messages(session, family)] == [message.id]
    assert second["ai"]["handoff"] == {
        "status": "waiting",
        "urgent": False,
        "already": True,
        "over_three_days": False,
    }
    # 家族の発言は、そのメッセージの続きの書き込みになる（職員の詳細に出る）
    assert session.get(InquiryMessage, second["family"]["id"]).staff_message_id == message.id
    # 最初に渡した発言は、読み直しても「お伝えしました」のまま
    listed = {m["id"]: m for m in client.get(URL).json()}
    assert listed[first["ai"]["id"]]["handoff"]["already"] is False
    assert listed[second["ai"]["id"]]["handoff"]["already"] is True


def test_urgent_is_not_joined_to_other_category(client, session, fake_llm, family):
    hand_off(fake_llm, "money", "請求書について")
    client.post(URL, json={"body": "請求書について教えてください"})
    [money] = staff_messages(session, family)

    # AI がお金のメッセージにつなごうとしても、言葉の決まりで緊急になるので、つながない（FR-016）
    hand_off(fake_llm, "money", "請求書について", existing=money.id)
    data = client.post(URL, json={"body": "母が倒れたと聞きました"}).json()

    messages = staff_messages(session, family)
    assert [m.category for m in messages] == ["money", "urgent"]
    assert messages[1].origin_message_id == data["family"]["id"]
    assert session.get(InquiryMessage, data["family"]["id"]).staff_message_id is None
    # 家族の画面には「お急ぎのときは、施設にお電話ください」が出る
    assert data["ai"]["handoff"] == {
        "status": "waiting",
        "urgent": True,
        "already": False,
        "over_three_days": False,
    }


def test_complaint_is_not_joined_to_medical(
    client, session, fake_llm, family, make_staff, login_as
):
    hand_off(fake_llm, "medical", "熱について")
    client.post(URL, json={"body": "母の熱は下がりましたか"})
    [medical] = staff_messages(session, family)

    # 苦情を医療のメッセージにつなぐと、医療の続きの書き込みとして苦情の中身が見えてしまう
    hand_off(fake_llm, "medical", "熱について", existing=medical.id)
    data = client.post(URL, json={"body": "夜勤の職員の対応がひどいです"}).json()

    assert [m.category for m in staff_messages(session, family)] == ["medical", "complaint"]
    # 苦情の家族の発言は、医療のメッセージにつながっていない（緊急のテストとそろえる）
    assert session.get(InquiryMessage, data["family"]["id"]).staff_message_id is None
    # 介護職員が医療のメッセージを開いても、苦情は続きの書き込みに出ない（R-12・#209）
    login_as(make_staff(role="care_worker").user_id)
    detail = client.get(f"/api/staff/messages/{medical.id}").json()
    assert detail["follow_ups"] == []


def test_answered_message_is_not_joined(client, session, fake_llm, family):
    hand_off(fake_llm, "money", "請求書")
    client.post(URL, json={"body": "請求書について"})
    [message] = staff_messages(session, family)
    message.status = "answered"
    session.flush()

    # AI に見せるのは対応待ちだけなので、対応済みの id を付けてきても新しく渡す
    hand_off(fake_llm, "money", "請求書", existing=message.id)
    data = client.post(URL, json={"body": "もう一度、請求書について"}).json()

    assert len(staff_messages(session, family)) == 2
    assert data["ai"]["handoff"]["already"] is False


def test_other_familys_message_is_not_joined(client, session, fake_llm, make_family, family):
    # ほかの家族の対応待ちのメッセージを 1 つ作っておく
    other = make_family()
    conversation = InquiryConversation(family_account_id=other.id, resident_id=other.resident_id)
    session.add(conversation)
    session.flush()
    origin = InquiryMessage(conversation_id=conversation.id, sender="family", body="質問")
    session.add(origin)
    session.flush()
    other_message = StaffMessage(
        conversation_id=conversation.id,
        resident_id=other.resident_id,
        origin_message_id=origin.id,
        category="money",
        summary="ほかの家族",
    )
    session.add(other_message)
    session.flush()

    hand_off(fake_llm, "money", "請求書", existing=other_message.id)
    client.post(URL, json={"body": "請求書について"})

    # ほかの家族のメッセージにはつながず、自分の家族の分を新しく作る
    assert len(staff_messages(session, family)) == 1
    assert (
        session.scalars(
            select(InquiryMessage).where(
                InquiryMessage.staff_message_id == other_message.id,
                InquiryMessage.sender == "family",
            )
        ).all()
        == []
    )


# --- 3 日たっても対応待ちのとき（FR-016b・R-13） ---

NOW = datetime(2026, 10, 30, 3, 0, tzinfo=UTC)


@pytest.fixture
def fixed_now(monkeypatch):
    """家族の会話の「3 日たったか」は、service が読む今の時刻で決まる。"""
    monkeypatch.setattr("app.inquiry.service.now", lambda: NOW)


def handoff_state(client) -> dict:
    """会話の中の、職員に渡した AI の発言（新しい順の先頭）の handoff。"""
    listed = client.get(URL).json()
    return next(m["handoff"] for m in listed if m["ai_result"] == "handed_off")


@pytest.mark.parametrize(
    ("waited", "expected"),
    [
        (timedelta(days=3) - timedelta(seconds=1), False),
        (timedelta(days=3), True),
        (timedelta(days=10), True),
    ],
    ids=["just_under_3_days", "exactly_3_days", "10_days"],
)
def test_waiting_for_3_days_adds_the_call_hint(
    client, session, fake_llm, family, fixed_now, waited, expected
):
    hand_off(fake_llm, "care_request", "上着")
    client.post(URL, json={"body": "冬物の上着を持って行ってもいいですか"})
    [message] = staff_messages(session, family)
    message.handed_at = NOW - waited
    session.flush()

    assert handoff_state(client)["over_three_days"] is expected
    # 状態は変えない（種類・担当・対応待ちのまま。催促もしない）
    session.refresh(message)
    assert (message.status, message.category, message.assignee_id) == (
        "waiting",
        "care_request",
        None,
    )


def test_3_days_are_counted_from_the_time_it_was_put_back_to_waiting(
    client, session, fake_llm, family, fixed_now
):
    hand_off(fake_llm, "care_request", "上着")
    client.post(URL, json={"body": "冬物の上着を持って行ってもいいですか"})
    [message] = staff_messages(session, family)
    # 渡したのは 5 日前だが、家族の続きで対応待ちに戻ったのは 1 日前
    message.handed_at = NOW - timedelta(days=5)
    message.reopened_at = NOW - timedelta(days=1)
    session.flush()

    assert handoff_state(client)["over_three_days"] is False


def test_answered_message_has_no_call_hint_even_after_3_days(
    client, session, fake_llm, family, fixed_now
):
    hand_off(fake_llm, "care_request", "上着")
    client.post(URL, json={"body": "冬物の上着を持って行ってもいいですか"})
    [message] = staff_messages(session, family)
    message.handed_at = NOW - timedelta(days=10)
    message.status = "answered"
    session.flush()

    state = handoff_state(client)
    assert (state["status"], state["over_three_days"]) == ("answered", False)
