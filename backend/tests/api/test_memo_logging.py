"""様子のメモのログのテスト（spec 007 の 007-T030。FR-018・research.md R-11）。

本番の設定（JSON・INFO 以上）で、書く・「日本語にする」・承認する・戻すを一通り流し、
ログに、原文・整えた日本語・訳し戻し・氏名・理由の文が出ないこと、
メモの id・状態・操作・印・時間・モデル名だけが出ることを確かめる。
本物の AI は呼ばず、fake_llm（テスト用の LLM（モック））を使う。
このアプリはデプロイ・公開しないので、実際の本番では確かめない（本番の設定をテストの中で再現する）。
"""

import io
import json
import logging
from datetime import UTC, datetime

import pytest
import structlog

from app.config import Settings
from app.inquiry.llm import LLMUnavailable
from app.logging import configure_logging
from app.models.memos import CareMemo
from tests.fakes.llm import text_response

NOW = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
ORIGINAL = "Hari ini Ibu makan siang sampai habis, tapi kurang bersemangat."
REWRITTEN = "今日はお昼ごはんを全部召し上がりましたが、あまり元気がありませんでした。"
BACK_TRANSLATION = "Hari ini beliau menghabiskan makan siang, tetapi kurang bersemangat."
RETURN_REASON = "ご飯の量の書き方を、もう少しくわしく直してください"
# ログに出てはいけない文字（氏名・呼び名・原文・整えた日本語・訳し戻し・理由の文）
FORBIDDEN = (
    ORIGINAL,
    REWRITTEN,
    BACK_TRANSLATION,
    RETURN_REASON,
    "シティ",
    "リーダーA",
    "さくらさんの母",
    "Hari ini",
    "お昼ごはん",
)


@pytest.fixture(autouse=True)
def restore_logging():
    """テストごとに変えた root のログの設定を、元に戻す。"""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level
    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr("app.clock.now", lambda: NOW)


@pytest.fixture
def production_log(monkeypatch) -> io.StringIO:
    """本番の設定（JSON・INFO 以上）にして、出たログを受ける。"""
    monkeypatch.setenv("APP_ENV", "production")
    stream = io.StringIO()
    configure_logging(Settings(), stream=stream)
    return stream


@pytest.fixture
def world(client, make_staff, make_family, login_as):
    """書く介護職員（インドネシア語）、リーダー、入居者 1 人。ログインは書く職員。"""
    writer = make_staff(role="care_worker", display_name="シティ", language="id")
    leader = make_staff(role="leader", display_name="リーダーA")
    resident = make_family(display_name="さくらさんの母")
    login_as(writer.user_id)
    return {"writer": writer, "leader": leader, "resident_id": resident.resident_id}


def memo_lines(stream: io.StringIO) -> list[dict]:
    """メモのログだけを、JSON の行として取り出す。"""
    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    return [line for line in lines if line["logger"].startswith("app.memos")]


def write_and_rewrite(client, fake_llm, world) -> int:
    """下書きを作って「日本語にする」まで進め、メモの id を返す。"""
    # 職員の表示言語が日本語でないときは、整えたあとに訳し戻すので、AI が 2 回呼ばれる
    fake_llm.add(text_response(REWRITTEN))
    fake_llm.add(text_response(BACK_TRANSLATION))
    created = client.post(
        f"/api/staff/residents/{world['resident_id']}/memos",
        json={"original_text": ORIGINAL, "source_lang": "id"},
    )
    assert created.status_code == 201
    memo_id = created.json()["id"]
    assert client.post(f"/api/staff/memos/{memo_id}/rewrite").status_code == 200
    return memo_id


def make_pending(session, memo_id: int) -> None:
    """「確かめました」を押したあとの承認待ちにする（確かめる API は作り込みで足す）。"""
    memo = session.get(CareMemo, memo_id)
    memo.status = "pending"
    memo.confirmed_at = NOW
    memo.back_translation = BACK_TRANSLATION
    session.flush()


def test_write_and_rewrite_log_only_ids_model_and_time(client, fake_llm, world, production_log):
    memo_id = write_and_rewrite(client, fake_llm, world)

    lines = memo_lines(production_log)
    assert [line["event"] for line in lines] == [
        f"様子のメモの下書きを作った: memo={memo_id} resident={world['resident_id']}",
        lines[1]["event"],
    ]
    rewritten = lines[1]["event"]
    assert rewritten.startswith(f"様子のメモを日本語にした: memo={memo_id} warnings=")
    # 使ったモデルと、かかった時間は出る（FR-018）
    assert "model=fake" in rewritten
    assert "latency_ms=" in rewritten
    assert all(line["level"] == "info" for line in lines)
    for secret in FORBIDDEN:
        assert secret not in production_log.getvalue()


def test_a_stopped_ai_logs_the_kind_of_error_but_not_its_message(
    client, fake_llm, world, production_log
):
    created = client.post(
        f"/api/staff/residents/{world['resident_id']}/memos",
        json={"original_text": ORIGINAL, "source_lang": "id"},
    )
    memo_id = created.json()["id"]
    # エラーの中身に原文が混ざっても、ログには出ない
    fake_llm.add(LLMUnavailable("timeout: " + ORIGINAL))

    response = client.post(f"/api/staff/memos/{memo_id}/rewrite")

    assert response.status_code == 503
    warnings = [line for line in memo_lines(production_log) if line["level"] == "warning"]
    assert [line["event"] for line in warnings] == [
        f"様子のメモを日本語にできなかった: memo={memo_id} error=LLMUnavailable"
    ]
    for secret in FORBIDDEN:
        assert secret not in production_log.getvalue()


def test_approve_and_return_log_the_state_change_but_not_the_reason(
    client, session, fake_llm, world, login_as, production_log
):
    first = write_and_rewrite(client, fake_llm, world)
    second = write_and_rewrite(client, fake_llm, world)
    make_pending(session, first)
    make_pending(session, second)
    login_as(world["leader"].user_id)

    approved = client.post(f"/api/staff/memo-approvals/{first}/approve")
    returned = client.post(
        f"/api/staff/memo-approvals/{second}/return", json={"reason": RETURN_REASON}
    )

    assert approved.status_code == 200
    assert returned.status_code == 200
    events = [line["event"] for line in memo_lines(production_log)]
    staff_id = world["leader"].id
    assert f"様子のメモの状態を変えた: memo={first} pending->approved staff={staff_id}" in events
    assert f"様子のメモの状態を変えた: memo={second} pending->returned staff={staff_id}" in events
    for secret in FORBIDDEN:
        assert secret not in production_log.getvalue()


def test_a_failed_approval_logs_nothing_about_the_memo(
    client, session, fake_llm, world, login_as, production_log
):
    memo_id = write_and_rewrite(client, fake_llm, world)
    make_pending(session, memo_id)
    production_log.truncate(0)
    production_log.seek(0)

    # 本人は承認できない（FR-011a）。状態は変わらないので、状態の変更のログは出ない
    response = client.post(f"/api/staff/memo-approvals/{memo_id}/approve")

    assert response.status_code == 403
    assert not any("状態を変えた" in line["event"] for line in memo_lines(production_log))
