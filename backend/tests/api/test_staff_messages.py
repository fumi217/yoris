"""職員の「家族からのメッセージ」の一覧・件数・詳細の API（004-T025）のテスト（004-T023 の一部）。

「自分が対応する」・返事の 409（already_assigned・already_answered）のテストは、
その API（004-T026・004-T027）と一緒に足す。

手元の DB には開発の初期データがあるので、一覧は resident_id でテストの入居者に絞って確かめる。
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.inquiry import (
    InquiryConversation,
    InquiryMessage,
    StaffMessage,
    StaffMessageTemplate,
)
from app.models.notifications import EmailOutbox, Notification

NOW = datetime(2026, 10, 26, 3, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    monkeypatch.setattr("app.clock.now", lambda: NOW)


@pytest.fixture
def conversation_of(session):
    """家族の会話を返す（なければ作る）。"""

    def get(family) -> InquiryConversation:
        conversation = session.scalar(
            select(InquiryConversation).where(InquiryConversation.family_account_id == family.id)
        )
        if conversation is None:
            conversation = InquiryConversation(
                family_account_id=family.id, resident_id=family.resident_id
            )
            session.add(conversation)
            session.flush()
        return conversation

    return get


@pytest.fixture
def say(session, conversation_of):
    """家族の会話に発言を 1 つ足す。"""

    def add(family, sender: str, body: str, **fields) -> InquiryMessage:
        message = InquiryMessage(
            conversation_id=conversation_of(family).id, sender=sender, body=body, **fields
        )
        session.add(message)
        session.flush()
        return message

    return add


@pytest.fixture
def add_message(session, say):
    """家族の質問と、それを渡した職員へのメッセージを足す。"""

    def add(
        family,
        category: str = "medical",
        *,
        status: str = "waiting",
        assignee=None,
        handed_at: datetime = NOW - timedelta(hours=1),
        reopened_at: datetime | None = None,
        body: str = "質問",
        summary: str = "要約",
    ) -> StaffMessage:
        origin = say(family, "family", body)
        message = StaffMessage(
            conversation_id=origin.conversation_id,
            resident_id=family.resident_id,
            origin_message_id=origin.id,
            category=category,
            summary=summary,
            status=status,
            assignee_id=assignee.id if assignee else None,
            handed_at=handed_at,
            reopened_at=reopened_at,
        )
        session.add(message)
        session.flush()
        return message

    return add


@pytest.fixture
def staff_client(client, make_staff, login_as):
    """職員としてログインしたクライアントを作る（返すのは (client, staff)）。"""

    def login(role: str = "care_worker"):
        staff = make_staff(role=role, display_name=f"テスト{role}")
        login_as(staff.user_id)
        return client, staff

    return login


def ids(response) -> list[int]:
    return [m["id"] for m in response.json()["messages"]]


# --- ログイン・役割 ---


def test_not_logged_in_is_401(client):
    assert client.get("/api/staff/messages").status_code == 401
    assert client.get("/api/staff/messages/count").status_code == 401
    assert client.get("/api/staff/messages/1").status_code == 401


def test_family_is_403(client, make_family, login_as, add_message):
    family = make_family()
    message = add_message(family)
    login_as(family.user_id)

    assert client.get("/api/staff/messages").status_code == 403
    assert client.get("/api/staff/messages/count").status_code == 403
    response = client.get(f"/api/staff/messages/{message.id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_clerk_can_read_messages(staff_client, make_family, add_message):
    # 役割の略号 S には事務員も入る（contracts/api.md）
    client, _ = staff_client("clerk")
    family = make_family()
    message = add_message(family, "money")

    assert client.get(f"/api/staff/messages/{message.id}").status_code == 200


def test_unknown_message_is_404(staff_client):
    client, _ = staff_client()

    response = client.get("/api/staff/messages/999999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- 苦情の見え方 ---


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_complaint_is_hidden_from_other_roles(staff_client, make_family, add_message, role):
    client, _ = staff_client(role)
    family = make_family()
    medical = add_message(family, "medical")
    complaint = add_message(family, "complaint")
    params = {"resident_id": family.resident_id}

    assert ids(client.get("/api/staff/messages", params=params)) == [medical.id]
    assert client.get("/api/staff/messages/count", params=params).json() == {"count": 1}
    response = client.get(f"/api/staff/messages/{complaint.id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("role", ["counselor", "director"])
def test_complaint_is_visible_to_counselor_and_director(
    staff_client, make_family, add_message, role
):
    client, _ = staff_client(role)
    family = make_family()
    add_message(family, "medical")
    complaint = add_message(family, "complaint")
    params = {"resident_id": family.resident_id}

    assert complaint.id in ids(client.get("/api/staff/messages", params=params))
    assert client.get("/api/staff/messages/count", params=params).json() == {"count": 2}
    response = client.get(f"/api/staff/messages/{complaint.id}")
    assert response.status_code == 200
    assert response.json()["category"] == "complaint"
    # 苦情には定型文を用意しない（電話で対応する。FR-014）
    assert response.json()["templates"] == []


# --- 一覧 ---


def test_list_order(staff_client, make_staff, make_family, add_message):
    client, me = staff_client()
    other = make_staff(display_name="ほかの職員")
    family = make_family()
    answered = add_message(family, status="answered", handed_at=NOW - timedelta(days=5))
    others = add_message(family, assignee=other, handed_at=NOW - timedelta(days=4))
    mine = add_message(family, assignee=me, handed_at=NOW - timedelta(days=3))
    empty = add_message(family, handed_at=NOW - timedelta(days=2))

    response = client.get("/api/staff/messages", params={"resident_id": family.resident_id})

    # 対応待ち → 担当が自分か空 → 古い順
    assert ids(response) == [mine.id, empty.id, others.id, answered.id]


def test_list_filters_by_status(staff_client, make_family, add_message):
    client, _ = staff_client()
    family = make_family()
    waiting = add_message(family)
    answered = add_message(family, status="answered")
    params = {"resident_id": family.resident_id}

    assert ids(client.get("/api/staff/messages", params={**params, "status": "waiting"})) == [
        waiting.id
    ]
    assert ids(client.get("/api/staff/messages", params={**params, "status": "answered"})) == [
        answered.id
    ]
    assert client.get("/api/staff/messages", params={"status": "done"}).status_code == 422


def test_list_row(staff_client, make_staff, make_family, add_message):
    client, _ = staff_client()
    assignee = make_staff(display_name="担当の職員")
    family = make_family(display_name="テストさん")
    message = add_message(family, "care_request", assignee=assignee)

    row = client.get("/api/staff/messages", params={"resident_id": family.resident_id}).json()[
        "messages"
    ][0]

    assert row["id"] == message.id
    assert row["resident_display_name"] == "テストさん"
    assert row["category"] == "care_request"
    assert row["assignee"] == {"id": assignee.id, "display_name": "担当の職員"}
    assert row["summary"] == "要約"
    assert row["status"] == "waiting"


def test_summary_and_origin_come_with_readings_without_changing_the_saved_text(
    staff_client, make_family, add_message
):
    client, _ = staff_client()
    family = make_family()
    message = add_message(family, body="父が転倒しました", summary="体調の相談です")

    row = client.get("/api/staff/messages", params={"resident_id": family.resident_id}).json()[
        "messages"
    ][0]
    detail = client.get(f"/api/staff/messages/{message.id}").json()

    # 保存している文は、そのまま。読みを付けたものは、別の項目（FR-028a）
    assert row["summary"] == "体調の相談です"
    assert row["summary_ruby"] == "{体調|たいちょう}の{相談|そうだん}です"
    assert detail["origin"]["body"] == "父が転倒しました"
    assert detail["origin_ruby"] == "{父|ちち}が{転倒|てんとう}しました"
    assert detail["summary_ruby"] == row["summary_ruby"]


def test_elapsed_days_and_waiting_over_a_day(staff_client, make_family, add_message):
    client, _ = staff_client()
    family = make_family()
    fresh = add_message(family, handed_at=NOW - timedelta(hours=23))
    old = add_message(family, handed_at=NOW - timedelta(hours=49))
    # 家族の続きで対応待ちに戻ったものは、戻った日時から数える（data-model.md）
    reopened = add_message(
        family, handed_at=NOW - timedelta(days=5), reopened_at=NOW - timedelta(hours=2)
    )
    answered = add_message(family, status="answered", handed_at=NOW - timedelta(days=3))

    rows = {
        m["id"]: m
        for m in client.get(
            "/api/staff/messages", params={"resident_id": family.resident_id}
        ).json()["messages"]
    }

    assert (rows[fresh.id]["elapsed_days"], rows[fresh.id]["waiting_over_a_day"]) == (0, False)
    assert (rows[old.id]["elapsed_days"], rows[old.id]["waiting_over_a_day"]) == (2, True)
    assert (rows[reopened.id]["elapsed_days"], rows[reopened.id]["waiting_over_a_day"]) == (
        0,
        False,
    )
    # 対応済みは目立たせない
    assert rows[answered.id]["waiting_over_a_day"] is False


# --- 件数 ---


def test_count_is_waiting_only(staff_client, make_family, add_message):
    client, _ = staff_client()
    family = make_family()
    add_message(family)
    add_message(family, "money")
    add_message(family, status="answered")

    response = client.get("/api/staff/messages/count", params={"resident_id": family.resident_id})

    assert response.json() == {"count": 2}


# --- 詳細 ---


def test_detail_shows_only_the_previous_three_turns(staff_client, make_family, say, add_message):
    client, _ = staff_client()
    family = make_family()
    for n in range(1, 5):
        say(family, "family", f"家族{n}")
        say(family, "ai", f"AI{n}")
    message = add_message(family, body="原文")
    say(family, "ai", "職員にお伝えしました", ai_result="handed_off", staff_message_id=message.id)
    say(family, "family", "追加の書き込み", staff_message_id=message.id)

    detail = client.get(f"/api/staff/messages/{message.id}").json()

    assert detail["origin"]["body"] == "原文"
    # 原文の直前の 6 件（家族 3・AI 3）だけ。それより前（家族1・AI1）は出さない
    assert [m["body"] for m in detail["previous"]] == [
        "家族2",
        "AI2",
        "家族3",
        "AI3",
        "家族4",
        "AI4",
    ]
    assert [m["body"] for m in detail["follow_ups"]] == ["追加の書き込み"]


@pytest.fixture
def complaint_then_medical(make_family, say, add_message):
    """苦情を送ったあと、同じ会話で医療の質問をした家族（PR #209 のレビューの場面）。

    医療の原文の前の 7 件：古い1・古い2・家族1・AI1・苦情の原文・苦情を渡した AI・苦情の続き。
    """
    family = make_family()
    say(family, "family", "古い1")
    say(family, "family", "古い2")
    say(family, "family", "家族1")
    say(family, "ai", "AI1")
    complaint = add_message(family, "complaint", body="苦情の原文")
    say(family, "ai", "", ai_result="handed_off", staff_message_id=complaint.id)
    say(family, "family", "苦情の続き", staff_message_id=complaint.id)
    medical = add_message(family, "medical", body="医療の原文")
    return medical


@pytest.mark.parametrize("role", ["care_worker", "leader", "clerk"])
def test_previous_hides_complaint_from_other_roles(staff_client, complaint_then_medical, role):
    client, _ = staff_client(role)

    detail = client.get(f"/api/staff/messages/{complaint_then_medical.id}").json()

    # 直前の 6 件から苦情の発言（原文・渡した AI・続き）を除く。印も出さない（FR-012・R-12）。
    # 除いた分、さらに前（古い1）は取りに行かない
    assert [m["body"] for m in detail["previous"]] == ["古い2", "家族1", "AI1"]
    # 苦情の続きは、苦情のメッセージに結びついているので、医療の続きには出ない
    assert detail["follow_ups"] == []


@pytest.mark.parametrize("role", ["counselor", "director"])
def test_previous_shows_complaint_to_counselor_and_director(
    staff_client, complaint_then_medical, role
):
    client, _ = staff_client(role)

    detail = client.get(f"/api/staff/messages/{complaint_then_medical.id}").json()

    assert [m["body"] for m in detail["previous"]] == [
        "古い2",
        "家族1",
        "AI1",
        "苦情の原文",
        "",
        "苦情の続き",
    ]


def test_detail_shows_staff_reply_templates_in_previous(
    session, staff_client, make_family, say, add_message
):
    client, me = staff_client()
    template = StaffMessageTemplate(
        category="money", code="staff_template.test.prev", sort_order=99
    )
    session.add(template)
    session.flush()
    family = make_family()
    say(family, "family", "前の質問")
    say(
        family,
        "staff",
        "",
        staff_id=me.id,
        template_ids=[template.id],
        note="書き足し",
        response_type="app",
    )
    message = add_message(family, "money")

    previous = client.get(f"/api/staff/messages/{message.id}").json()["previous"]

    assert previous[-1]["template_codes"] == ["staff_template.test.prev"]
    assert previous[-1]["note"] == "書き足し"


def test_detail_has_templates_of_the_category(session, staff_client, make_family, add_message):
    client, _ = staff_client()
    session.add_all(
        [
            StaffMessageTemplate(category="money", code="staff_template.test.b", sort_order=92),
            StaffMessageTemplate(category="money", code="staff_template.test.a", sort_order=91),
            StaffMessageTemplate(category="medical", code="staff_template.test.c", sort_order=91),
        ]
    )
    session.flush()
    family = make_family()
    message = add_message(family, "money")

    codes = [t["code"] for t in client.get(f"/api/staff/messages/{message.id}").json()["templates"]]

    # その種類の定型文だけを、並び順で（初期データの定型文の後ろに並ぶ）
    assert [c for c in codes if c.startswith("staff_template.test.")] == [
        "staff_template.test.a",
        "staff_template.test.b",
    ]


# --- 通知・音 ---


def test_reading_messages_sends_no_notifications(session, staff_client, make_family, add_message):
    # 職員への通知・音は出さない（SC-008）。開いても家族へのお知らせ・メールは作らない
    client, _ = staff_client("counselor")
    family = make_family()
    message = add_message(family)
    before = (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    )

    client.get("/api/staff/messages")
    client.get("/api/staff/messages/count")
    client.get(f"/api/staff/messages/{message.id}")

    assert (
        session.scalar(select(func.count()).select_from(Notification)),
        session.scalar(select(func.count()).select_from(EmailOutbox)),
    ) == before
