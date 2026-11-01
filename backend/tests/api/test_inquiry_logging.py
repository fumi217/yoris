"""問い合わせ AI のログの確かめ（spec 004 の 004-T045。FR-029・research.md R-15）。

本番の設定（JSON・INFO 以上）でログを集め、次のことを確かめる。
- 発言の文・答え・要約・記録の値・氏名・メールアドレスが、ログに 1 つも出ない
- 出るのは、会話・発言の id・質問の種類・結果・ツールの回数・時間・モデル名だけ
- AI につながらなかったときは、理由の種類だけが出る

本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））に応答を足して使う。
"""

import io
import json
import logging

import pytest
import structlog

from app.clock import today_jst
from app.config import Settings
from app.inquiry.llm import LLMUnavailable
from app.logging import configure_logging
from app.models.records import CareRecord
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache
from tests.fakes.llm import look_up_response, tool_call_response

URL = "/api/family/inquiry/messages"

# ログに出てはいけない、架空の値（質問・答え・要約・記録の値・氏名）
QUESTION = "ひみつの質問：今日のお昼は食べましたか"
ANSWER = "ひみつの答え：ほぼ全部召し上がりました"
SUMMARY = "ひみつの要約：先月の請求書の金額について知りたい"
RECORD_NOTE = "ひみつの記録の値"
RESIDENT = "ひみつ入居者 花子"
STAFF = "ひみつ職員"


@pytest.fixture(autouse=True)
def restore_logging():
    """テストごとに変えた root のログの設定を、元に戻す。"""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level
    structlog.reset_defaults()


@pytest.fixture
def production_log(monkeypatch) -> io.StringIO:
    """本番の設定（JSON・INFO 以上）で、ログを文字列に集める。"""
    monkeypatch.setenv("APP_ENV", "production")
    stream = io.StringIO()
    configure_logging(Settings(), stream=stream)
    return stream


@pytest.fixture
def world(session, redis, facility, make_staff, make_family, login_as):
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    staff = make_staff(display_name=STAFF)
    family = make_family(name=RESIDENT)
    lunch = CareRecord(
        resident_id=family.resident_id,
        date=today_jst(),
        item="meal",
        slot="lunch",
        value="8",
        recorded_by=staff.id,
    )
    session.add(lunch)
    session.flush()
    login_as(family.user_id)
    yield {"family": family, "lunch": lunch}
    clear_disclosure_cache(facility.id)


def _lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _inquiry_lines(stream: io.StringIO) -> list[dict]:
    return [line for line in _lines(stream) if "inquiry" in line["logger"]]


def _assert_no_personal_values(stream: io.StringIO, *extra: str) -> None:
    text = stream.getvalue()
    for secret in (QUESTION, ANSWER, SUMMARY, RECORD_NOTE, RESIDENT, STAFF, *extra):
        assert secret not in text


def test_answer_logs_only_ids_result_and_numbers(client, fake_llm, production_log, world):
    today = today_jst().isoformat()
    lunch_id = world["lunch"].id
    fake_llm.add(
        look_up_response(today, today),
        tool_call_response("answer_family", {"text": ANSWER, "source_ids": [f"record:{lunch_id}"]}),
    )

    response = client.post(URL, json={"body": QUESTION})

    assert response.status_code == 201
    data = response.json()
    [line] = _inquiry_lines(production_log)
    # 出るのは、会話・発言の id・結果・ツールの回数・時間・モデル名だけ
    event = line["event"]
    assert f"family_message_id={data['family']['id']}" in event
    assert f"ai_message_id={data['ai']['id']}" in event
    assert "result=answered" in event
    assert "tool_calls=" in event
    assert "latency_ms=" in event
    assert "model=" in event
    assert line["level"] == "info"
    # 家族のメールアドレスも出ない
    _assert_no_personal_values(production_log, "@example.test")


def test_handoff_logs_the_category_but_not_the_summary(
    client, fake_llm, production_log, world, session
):
    fake_llm.add(tool_call_response("hand_off_to_staff", {"category": "money", "summary": SUMMARY}))

    response = client.post(URL, json={"body": QUESTION})

    assert response.status_code == 201
    [line] = _inquiry_lines(production_log)
    assert "result=handed_off" in line["event"]
    assert "category=money" in line["event"]
    _assert_no_personal_values(production_log)


def test_nothing_in_the_whole_log_has_personal_values(client, fake_llm, production_log, world):
    # このやり取りの間に出たログすべて（API・DB・外部のライブラリのものも含む）を見る
    today = today_jst().isoformat()
    lunch_id = world["lunch"].id
    fake_llm.add(
        look_up_response(today, today),
        tool_call_response("answer_family", {"text": ANSWER, "source_ids": [f"record:{lunch_id}"]}),
    )

    client.post(URL, json={"body": QUESTION})

    assert production_log.getvalue() != ""
    _assert_no_personal_values(production_log, "@example.test")


@pytest.mark.parametrize("reason", ["timeout", "status_429", "no_api_key"])
def test_unavailable_ai_logs_only_the_reason(client, fake_llm, production_log, world, reason):
    fake_llm.add(LLMUnavailable(reason))

    response = client.post(URL, json={"body": QUESTION})

    assert response.status_code == 503
    [line] = _inquiry_lines(production_log)
    assert line["level"] == "warning"
    assert f"reason={reason}" in line["event"]
    _assert_no_personal_values(production_log)


def test_the_log_uses_the_reason_not_the_text_of_the_exception(
    client, fake_llm, production_log, world
):
    # 将来、例外の文字列表現に、送った文や AI からの返事の本文が入っても、ログには出ない
    # （ログに出すのは reason だけ。AI チューターの指摘）
    class LeakyUnavailable(LLMUnavailable):
        def __str__(self) -> str:
            return f"{QUESTION} {ANSWER} {SUMMARY}"

    fake_llm.add(LeakyUnavailable("timeout"))

    response = client.post(URL, json={"body": QUESTION})

    assert response.status_code == 503
    [line] = _inquiry_lines(production_log)
    assert "reason=timeout" in line["event"]
    _assert_no_personal_values(production_log)


def test_nothing_is_logged_below_info_in_production(client, fake_llm, production_log, world):
    # 本番は INFO 以上。DEBUG のログは出ない
    fake_llm.add(tool_call_response("hand_off_to_staff", {"category": "money", "summary": SUMMARY}))

    client.post(URL, json={"body": QUESTION})

    assert all(line["level"] != "debug" for line in _lines(production_log))
