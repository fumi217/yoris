"""家族の連絡帳の API（001-T055）のテスト。

DB と Redis を使う（conftest.py の client・session・redis・make_family・make_staff・login_as。
なければ手元では飛ばす）。ログインは、本物のセッション（Redis）を作って行う。
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today_jst
from app.models.core import Facility
from app.models.disclosure import DisclosureSetting, ReplyTemplate, Theme
from app.models.memos import CareMemo
from app.models.requests import Request
from app.seed.themes import add_themes
from app.services.disclosure import clear_disclosure_cache
from app.services.records import save_record
from app.services.replies import save_reply


def _show_items(session: Session, facility: Facility, hidden: tuple[str, ...] = ()) -> None:
    """記録の 3 項目を、見せる設定にする（hidden に入れたものは見せない）。"""
    for item in ("meal", "mood", "sleep"):
        setting = session.scalars(
            select(DisclosureSetting).where(
                DisclosureSetting.facility_id == facility.id,
                DisclosureSetting.target_type == "item",
                DisclosureSetting.target_code == item,
            )
        ).first()
        if setting is None:
            setting = DisclosureSetting(
                facility_id=facility.id, target_type="item", target_code=item, visible=True
            )
            session.add(setting)
        setting.visible = item not in hidden
    session.flush()
    session.commit()
    clear_disclosure_cache(facility.id)


@pytest.fixture
def world(
    session: Session, facility: Facility, make_family, make_staff, login_as, client, redis
) -> Iterator[dict]:
    """家族 2 組（ふだんは 1 組目でログイン）・職員・記録の 3 項目を見せる設定。"""
    _show_items(session, facility)
    add_themes(session)
    mine = make_family()
    other = make_family(name="べつの入居者")
    staff = make_staff()
    login_as(mine.user_id)
    yield {"client": client, "mine": mine, "other": other, "staff": staff, "facility": facility}
    # テストで変えた開示設定は、DB では取り消される。Redis のキャッシュ（5 分）に残さない
    clear_disclosure_cache(facility.id)


def _reply_to(session: Session, family, staff, theme_code="theme.daily_life", note=None):
    theme = session.scalars(select(Theme).where(Theme.code == theme_code)).one()
    request = Request(resident_id=family.resident_id, theme_id=theme.id)
    session.add(request)
    session.flush()
    template_id = session.scalars(
        select(ReplyTemplate.id).where(ReplyTemplate.theme_id == theme.id)
    ).first()
    return save_reply(
        session, request_id=request.id, staff_id=staff.id, template_ids=[template_id], note=note
    )


def _slots(body: dict, item: str) -> dict[str, dict]:
    section = next(section for section in body["sections"] if section["item"] == item)
    return {slot["slot"]: slot for slot in section["slots"]}


# --- ログイン・役割 ---


def test_not_logged_in_is_401(client):
    assert client.get("/api/family/contact-book").status_code == 401


def test_staff_cannot_use_the_family_api(client, make_staff, login_as):
    login_as(make_staff("care_worker").user_id)

    assert client.get("/api/family/contact-book").status_code == 403


# --- 記録と未記録の欄 ---


def test_records_and_not_recorded_slots(world, session):
    save_record(
        session,
        resident_id=world["mine"].resident_id,
        staff_id=world["staff"].id,
        record_date=today_jst(),
        item="meal",
        slot="lunch",
        value="8",
    )
    session.commit()

    body = world["client"].get("/api/family/contact-book").json()

    assert body["date"] == today_jst().isoformat()
    assert [section["item"] for section in body["sections"]] == ["meal", "mood", "sleep"]
    meal = _slots(body, "meal")
    # おやつは、記録があるときだけ欄が出る（毎日付けるとは限らないため）
    assert list(meal) == ["breakfast", "lunch", "dinner"]
    assert meal["lunch"]["record"]["value"] == "8"
    assert meal["lunch"]["message_key"] is None
    # まだ記録がない欄は、推測や空欄にせず、「まだ記録されていません」のキーを返す（FR-017）
    assert meal["breakfast"]["record"] is None
    assert meal["breakfast"]["message_key"] == "contact_book.not_recorded"
    assert _slots(body, "mood")["day"]["message_key"] == "contact_book.not_recorded"


def test_snack_slot_appears_only_when_recorded(world, session):
    save_record(
        session,
        resident_id=world["mine"].resident_id,
        staff_id=world["staff"].id,
        record_date=today_jst(),
        item="meal",
        slot="snack",
        value="5",
    )
    session.commit()

    meal = _slots(world["client"].get("/api/family/contact-book").json(), "meal")

    assert list(meal) == ["breakfast", "lunch", "dinner", "snack"]
    assert meal["snack"]["record"]["value"] == "5"
    assert meal["snack"]["message_key"] is None


def test_hidden_item_is_not_returned(world, session):
    save_record(
        session,
        resident_id=world["mine"].resident_id,
        staff_id=world["staff"].id,
        record_date=today_jst(),
        item="mood",
        slot="day",
        value="smile",
    )
    session.commit()
    _show_items(session, world["facility"], hidden=("mood",))

    body = world["client"].get("/api/family/contact-book").json()

    assert [section["item"] for section in body["sections"]] == ["meal", "sleep"]
    assert "smile" not in str(body)


def test_other_family_records_are_not_returned(world, session):
    save_record(
        session,
        resident_id=world["other"].resident_id,
        staff_id=world["staff"].id,
        record_date=today_jst(),
        item="sleep",
        slot="day",
        value="good",
    )
    session.commit()

    body = world["client"].get("/api/family/contact-book").json()

    assert _slots(body, "sleep")["day"]["record"] is None


def test_other_day_by_query(world, session):
    yesterday = today_jst() - timedelta(days=1)
    save_record(
        session,
        resident_id=world["mine"].resident_id,
        staff_id=world["staff"].id,
        record_date=yesterday,
        item="meal",
        slot="dinner",
        value="10",
    )
    session.commit()

    today_body = world["client"].get("/api/family/contact-book").json()
    past_body = world["client"].get(f"/api/family/contact-book?date={yesterday}").json()

    assert _slots(today_body, "meal")["dinner"]["record"] is None
    assert past_body["date"] == yesterday.isoformat()
    assert _slots(past_body, "meal")["dinner"]["record"]["value"] == "10"


# --- 返事 ---


def test_unread_replies_come_first_whatever_the_date(world, session):
    old = _reply_to(session, world["mine"], world["staff"], note="三日前の返事")
    old.contact_book_date = today_jst() - timedelta(days=3)
    new = _reply_to(session, world["mine"], world["staff"], "theme.meals", note="今日の返事")
    session.commit()

    body = world["client"].get("/api/family/contact-book").json()

    # 今日の連絡帳でも、三日前のまだ読んでいない返事が出る（FR-015）
    assert [reply["id"] for reply in body["unread_replies"]] == [old.id, new.id]
    assert body["day_replies"] == []
    first = body["unread_replies"][0]
    assert first["note"] == "三日前の返事"
    assert first["replied_by_name"] == world["staff"].display_name
    # 職種が空の職員は、空のまま返す（役割では補わない。画面は名前だけを出す。#263）
    assert first["replied_by_occupation"] is None
    assert first["read"] is False


def test_reply_has_the_occupation_not_the_role(world, session, make_staff):
    # 看護師も役割は care_worker。家族には役割ではなく職種を返す（#263。spec 004 の Clarifications）
    nurse = make_staff(display_name="西村", occupation="nurse")
    _reply_to(session, world["mine"], nurse)
    session.commit()

    body = world["client"].get("/api/family/contact-book").json()

    [reply] = body["unread_replies"]
    assert reply["replied_by_name"] == "西村"
    assert reply["replied_by_occupation"] == "nurse"


def test_read_replies_show_only_on_their_day(world, session):
    reply = _reply_to(session, world["mine"], world["staff"])
    reply.contact_book_date = today_jst() - timedelta(days=2)
    session.commit()
    assert world["client"].post(f"/api/family/replies/{reply.id}/read").status_code == 204

    today = world["client"].get("/api/family/contact-book").json()
    that_day = (
        world["client"].get(f"/api/family/contact-book?date={reply.contact_book_date}").json()
    )

    assert today["unread_replies"] == [] and today["day_replies"] == []
    assert that_day["unread_replies"] == []
    assert [item["id"] for item in that_day["day_replies"]] == [reply.id]
    assert that_day["day_replies"][0]["read"] is True


def test_other_family_replies_are_not_returned(world, session):
    _reply_to(session, world["other"], world["staff"], note="べつの家族への返事")
    session.commit()

    body = world["client"].get("/api/family/contact-book").json()

    assert body["unread_replies"] == []
    assert "べつの家族への返事" not in str(body)


# ---- 様子のメモ（007-T026・FR-012） ----


def _show_memo(session: Session, facility: Facility, visible: bool = True) -> None:
    setting = session.scalars(
        select(DisclosureSetting).where(
            DisclosureSetting.facility_id == facility.id,
            DisclosureSetting.target_type == "item",
            DisclosureSetting.target_code == "memo",
        )
    ).first()
    if setting is None:
        setting = DisclosureSetting(
            facility_id=facility.id, target_type="item", target_code="memo", visible=visible
        )
        session.add(setting)
    setting.visible = visible
    session.flush()
    session.commit()
    clear_disclosure_cache(facility.id)


def _memo(
    session: Session,
    world,
    who="mine",
    *,
    text="よく笑っていました",
    status="approved",
    day=None,
    hour=3,
):
    memo = CareMemo(
        resident_id=world[who].resident_id,
        author_staff_id=world["staff"].id,
        memo_date=day or today_jst(),
        written_at=datetime(2031, 3, 10, hour, 0, tzinfo=UTC),
        approved_at=datetime(2031, 3, 10, 12, 0, tzinfo=UTC) if status == "approved" else None,
        source_lang="id",
        original_text="ORIGINAL-TEXT",
        rewritten_text=text,
        back_translation="BACK-TRANSLATION",
        warnings=[],
        status=status,
    )
    session.add(memo)
    session.flush()
    return memo


def test_memos_are_returned_in_written_order_without_original_text(world, session):
    _show_memo(session, world["facility"])
    _memo(session, world, text="あとのメモ", hour=6)
    _memo(session, world, text="さきのメモ", hour=2)

    body = world["client"].get("/api/family/contact-book").json()

    assert [memo["text"] for memo in body["memos"]] == ["さきのメモ", "あとのメモ"]
    memo = body["memos"][0]
    assert set(memo) == {"id", "text", "author_name", "author_occupation", "written_at"}
    # 原文・訳し戻しは、家族に出さない（FR-012）
    assert "ORIGINAL-TEXT" not in str(body)
    assert "BACK-TRANSLATION" not in str(body)


def test_only_approved_memos_of_the_day_and_of_my_resident_are_returned(world, session):
    _show_memo(session, world["facility"])
    yesterday = today_jst() - timedelta(days=1)
    _memo(session, world, text="承認済み")
    for status in ("draft", "pending", "returned", "withdrawn"):
        _memo(session, world, text=f"{status}のメモ", status=status)
    _memo(session, world, text="きのうのメモ", day=yesterday)
    _memo(session, world, who="other", text="べつの入居者のメモ")

    body = world["client"].get("/api/family/contact-book").json()
    past = world["client"].get(f"/api/family/contact-book?date={yesterday}").json()

    assert [memo["text"] for memo in body["memos"]] == ["承認済み"]
    assert [memo["text"] for memo in past["memos"]] == ["きのうのメモ"]


def test_memos_are_empty_when_the_facility_hides_them(world, session):
    _show_memo(session, world["facility"], visible=False)
    _memo(session, world)

    assert world["client"].get("/api/family/contact-book").json()["memos"] == []


def test_a_script_in_a_memo_is_returned_as_plain_text(world, session):
    _show_memo(session, world["facility"])
    _memo(session, world, text="<script>alert(1)</script>")

    [memo] = world["client"].get("/api/family/contact-book").json()["memos"]

    assert memo["text"] == "<script>alert(1)</script>"
