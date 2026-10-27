"""問い合わせ AI の 1 日の回数の制限のテスト（spec 004 の 004-T042）。FR-024・026・027・SC-009。

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
Redis は tests/conftest.py の redis（テスト用の 15 番）を使う。上限は環境変数で小さくして確かめる
（get_settings は呼んだときに読み直す）。
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.clock import today_jst
from app.inquiry.llm import LLMUnavailable
from app.inquiry.ratelimit import InquiryLimit, consume, release
from tests.fakes.llm import tool_call_response

URL = "/api/family/inquiry/messages"


@pytest.fixture
def world(redis, make_family, login_as):
    family = make_family()
    other = make_family(display_name="べつの入居者")
    login_as(family.user_id)
    return {"family": family, "other": other, "login_as": login_as}


def _day() -> str:
    return today_jst().strftime("%Y%m%d")


def _family_key(family) -> str:
    return f"ratelimit:inquiry:family:{family.id}:{_day()}"


def _facility_key() -> str:
    return f"ratelimit:inquiry:facility:{_day()}"


def _count(redis, key) -> int:
    return int(redis.get(key) or 0)


def _send(client, fake_llm, body="薬は増えましたか？"):
    # 言葉の決まり（薬）に当たる発言は、AI を 1 回呼んで職員に渡る（1 回の送信で呼び出しが 1 回）
    fake_llm.add(tool_call_response("answer_family", {"text": "はい", "source_ids": []}))
    return client.post(URL, json={"body": body})


def test_family_limit_blocks_the_next_one_without_calling_ai(
    client, redis, fake_llm, world, monkeypatch
):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "3")

    for _ in range(3):
        assert _send(client, fake_llm).status_code == 201
    response = client.post(URL, json={"body": "もう 1 つ"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "inquiry_limit"
    # 上限を超えた発言は、AI を呼ばない（SC-009）
    assert len(fake_llm.calls) == 3
    # 超えた分は戻す（4 ではなく 3 のまま）
    assert _count(redis, _family_key(world["family"])) == 3
    # 発言も残らない（家族 3・AI 3）
    assert len(client.get(URL).json()) == 6


def test_limit_is_per_family(client, redis, fake_llm, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "1")
    assert _send(client, fake_llm).status_code == 201
    assert client.post(URL, json={"body": "もう 1 つ"}).status_code == 429

    # ほかの家族は、まだ送れる
    world["login_as"](world["other"].user_id)

    assert _send(client, fake_llm).status_code == 201


def test_facility_limit_is_shared_by_all_families(client, redis, fake_llm, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FACILITY_DAILY_LIMIT", "2")
    assert _send(client, fake_llm).status_code == 201
    world["login_as"](world["other"].user_id)
    assert _send(client, fake_llm).status_code == 201

    # 施設全体で 2 回に達したので、どの家族も送れない（共有のキーを使い切らないため。FR-027）
    world["login_as"](world["family"].user_id)
    response = client.post(URL, json={"body": "もう 1 つ"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "inquiry_limit"
    assert len(fake_llm.calls) == 2
    # 数えた分は戻す（家族 1・施設 2 のまま）
    assert _count(redis, _facility_key()) == 2
    assert _count(redis, _family_key(world["family"])) == 1


def test_counting_starts_again_the_next_day(client, redis, fake_llm, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "1")
    assert _send(client, fake_llm).status_code == 201
    assert client.post(URL, json={"body": "もう 1 つ"}).status_code == 429

    # 日本時間で日付が変わった
    tomorrow = today_jst() + timedelta(days=1)
    monkeypatch.setattr("app.inquiry.ratelimit.today_jst", lambda: tomorrow)

    assert _send(client, fake_llm).status_code == 201
    assert _count(redis, _family_key(world["family"])) == 1
    assert _count(redis, f"ratelimit:inquiry:family:{world['family'].id}:{tomorrow:%Y%m%d}") == 1


def test_ai_unavailable_is_not_counted(client, redis, fake_llm, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "1")
    fake_llm.add(LLMUnavailable("timeout"))

    response = client.post(URL, json={"body": "薬は増えましたか？"})

    # AI が止まったときは、回数に数えない（FR-026）。家族・施設の両方を戻す
    assert response.status_code == 503
    assert _count(redis, _family_key(world["family"])) == 0
    assert _count(redis, _facility_key()) == 0
    # 上限が 1 でも、そのあと送れる
    assert _send(client, fake_llm).status_code == 201


def test_invalid_body_is_not_counted(client, redis, fake_llm, world):
    assert client.post(URL, json={"body": ""}).status_code == 422
    assert client.post(URL, json={"body": "   "}).status_code == 422
    assert client.post(URL, json={"body": "あ" * 501}).status_code == 422

    assert redis.get(_family_key(world["family"])) is None
    assert fake_llm.calls == []


def test_keys_have_a_ttl_of_two_days(client, redis, fake_llm, world):
    assert _send(client, fake_llm).status_code == 201

    # 期限のないキーを残さない（Redis の決まり。app/redis.py）
    for key in (_family_key(world["family"]), _facility_key()):
        assert 0 < redis.ttl(key) <= 2 * 24 * 60 * 60


def test_reading_the_conversation_is_not_limited(client, redis, fake_llm, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "1")
    assert _send(client, fake_llm).status_code == 201
    assert client.post(URL, json={"body": "もう 1 つ"}).status_code == 429

    # 上限に達しても、これまでのやりとりは見返せる
    assert client.get(URL).status_code == 200


def test_simultaneous_requests_never_exceed_the_limit(redis, world, monkeypatch):
    monkeypatch.setenv("INQUIRY_FAMILY_DAILY_LIMIT", "5")

    def attempt(_):
        try:
            consume(world["family"].id)
        except InquiryLimit:
            return False
        return True

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(40)))

    # 同時に送られても、Redis の INCR は 1 つずつ数えるので、通るのはちょうど 5 回
    assert results.count(True) == 5
    assert _count(redis, _family_key(world["family"])) == 5


def test_release_keeps_a_ttl_even_if_the_keys_were_lost(redis, world):
    ticket = consume(world["family"].id)
    # 数えたあと、途中でキーが消えた（Redis の再起動・flushdb など）
    redis.delete(ticket.family_key, ticket.facility_key)

    release(ticket)

    # DECR だけだと、期限のない -1 のキーができる（app/redis.py の「必ず期限を付ける」）
    for key in (ticket.family_key, ticket.facility_key):
        assert 0 < redis.ttl(key) <= 2 * 24 * 60 * 60
