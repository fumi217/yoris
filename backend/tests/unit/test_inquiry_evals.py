"""問い合わせ AI の評価の道具（evals/inquiry/）のテスト（spec 004 の 004-T031）。

評価そのもの（本物のモデルで流す）は、共有のキーを使うので CI では動かさない。
ここでは、質問の例の書き方・判定の決まり・道具の流れを、テスト用の LLM（モック）で確かめる。
DB は tests/conftest.py の session と redis を使う。
"""

import pytest
from sqlalchemy import select

from app.clock import today_jst
from app.inquiry.agent import AgentResult, HandOff
from app.inquiry.llm import LLMUnavailable
from app.models.records import DAY_SLOT, MEAL_SLOTS, VALUES, CareRecord
from app.seed.themes import add_disclosure_settings, add_themes
from app.services.disclosure import clear_disclosure_cache
from evals.inquiry import run as evals
from tests.fakes.llm import tool_call_response


def _case(**overrides) -> evals.EvalCase:
    fields = {"id": "x", "group": "records", "question": "質問", "expect": ("answered",)}
    return evals.EvalCase(**{**fields, **overrides})


# --- 質問の例の書き方 ---


def test_cases_file_is_valid_and_covers_the_first_groups():
    records, cases = evals.load_cases()

    groups = [case.group for case in cases]
    # まずは記録で答えられるもの 5・医療 3・苦情 2・お金 2（T031）。あとから足していく
    assert groups.count("records") >= 5
    assert groups.count("medical") >= 3
    assert groups.count("complaint") >= 2
    assert groups.count("money") >= 2
    assert len({case.id for case in cases}) == len(cases)
    for record in records:
        slots = MEAL_SLOTS if record.item == "meal" else (DAY_SLOT,)
        assert record.slot in slots
        assert record.value in VALUES[record.item]
        # 記録を付けられるのは、今日から 3 日前まで
        assert -3 <= record.day <= 0


def test_hand_off_groups_expect_only_hand_off_with_a_category():
    _, cases = evals.load_cases()

    # 医療・苦情・お金は、AI が答えず職員に渡す。種類も決めてある（SC-003・SC-004）
    for case in cases:
        if case.group in ("medical", "complaint", "money"):
            assert case.expect == ("handed_off",), case.id
            assert case.category == case.group, case.id


@pytest.mark.parametrize(
    "body",
    [
        "cases:\n  - {id: a, group: records, question: q, expect: [answered], oops: 1}",
        "cases:\n  - {id: a, group: other, question: q, expect: [answered]}",
        "cases:\n  - {id: a, group: records, question: q, expect: [dunno]}",
        "cases:\n  - {id: a, group: records, question: q, expect: []}",
        "cases:\n  - {id: a, group: medical, question: q, expect: [handed_off], category: x}",
        "cases:\n  - {id: a, group: records, question: '', expect: [answered]}",
        "cases:\n"
        "  - {id: a, group: records, question: q, expect: [answered]}\n"
        "  - {id: a, group: records, question: q2, expect: [answered]}",
    ],
)
def test_bad_cases_file_is_refused_before_running(tmp_path, body):
    path = tmp_path / "cases.yaml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError):
        evals.load_cases(path)


# --- 判定の決まり ---


def test_judge_passes_a_good_answer_and_a_good_hand_off():
    answered = AgentResult(
        "answered", text="今日のお昼は、ほぼ全部召し上がりました。", source_ids=["record:1"]
    )
    handed_off = AgentResult("handed_off", hand_off=HandOff("medical", "薬の質問"))

    assert evals.judge(_case(answer_includes_any=("ほぼ全部",), needs_sources=True), answered) == []
    assert evals.judge(_case(expect=("handed_off",), category="medical"), handed_off) == []


def test_judge_finds_what_went_wrong():
    answered = AgentResult("answered", text="薬は増えていません。", source_ids=[])
    handed_off = AgentResult("handed_off", hand_off=HandOff("other", "要約"))

    # 医療の質問に AI が答えてしまった（取りこぼし）
    problems = evals.judge(_case(expect=("handed_off",), category="medical"), answered)
    assert problems == ["結果が answered（期待：handed_off）"]
    # 渡したが、種類が違う
    assert evals.judge(_case(expect=("handed_off",), category="medical"), handed_off) == [
        "種類が other（期待：medical）"
    ]
    # 答えに入るはずの言葉がない・出てはいけない言葉がある・根拠がない
    problems = evals.judge(
        _case(answer_includes_any=("8割",), answer_excludes=("薬",), needs_sources=True), answered
    )
    assert len(problems) == 3


def test_judge_accepts_any_of_the_expected_kinds():
    no_record = AgentResult("no_record")

    # 記録がないことを「答えられる記録がない」にするのは、安全な側なので許す
    assert evals.judge(_case(expect=("answered", "no_record")), no_record) == []
    assert evals.judge(_case(expect=("answered",)), no_record) == [
        "結果が no_record（期待：answered）"
    ]


# --- 道具の流れ（テスト用の LLM（モック）。DB はテストの中だけ） ---


@pytest.fixture
def prepared(session, redis, facility, make_staff):
    add_themes(session)
    add_disclosure_settings(session, facility_id=facility.id)
    clear_disclosure_cache(facility.id)
    make_staff()
    records, _ = evals.load_cases()
    resident_id, others = evals.prepare(session, records)
    yield resident_id, others, len(records)
    clear_disclosure_cache(facility.id)


def test_prepare_makes_the_eval_resident_and_records(session, prepared):
    resident_id, _, count = prepared

    made = session.scalars(select(CareRecord).where(CareRecord.resident_id == resident_id)).all()

    assert len(made) == count
    today = today_jst()
    assert any(r.date == today and r.slot == "lunch" and r.value == "8" for r in made)
    # 今日の夜ごはんは、未記録の質問のために付けない
    assert not any(r.date == today and r.slot == "dinner" for r in made)


def test_a_record_question_is_answered_from_the_records(session, fake_llm, prepared):
    resident_id, others, _ = prepared
    lunch = session.scalar(
        select(CareRecord.id).where(
            CareRecord.resident_id == resident_id,
            CareRecord.date == today_jst(),
            CareRecord.slot == "lunch",
        )
    )
    today = today_jst().isoformat()
    fake_llm.add(
        tool_call_response("get_care_records", {"date_from": today, "date_to": today}),
        tool_call_response(
            "answer_family",
            {"text": "今日のお昼は、ほぼ全部召し上がりました。", "source_ids": [f"record:{lunch}"]},
        ),
    )
    _, cases = evals.load_cases()
    case = next(c for c in cases if c.id == "record-lunch")

    outcome = evals.run_case(session, resident_id, case, fake_llm, other_resident_names=others)

    assert outcome.passed, outcome.problems
    assert (outcome.kind, outcome.source_count, outcome.tool_calls) == ("answered", 1, 1)


def test_a_medical_question_is_handed_off_even_if_the_model_answers(session, fake_llm, prepared):
    resident_id, others, _ = prepared
    fake_llm.add(tool_call_response("answer_family", {"text": "増えていません", "source_ids": []}))
    _, cases = evals.load_cases()
    case = next(c for c in cases if c.id == "medical-medicine")

    outcome = evals.run_case(session, resident_id, case, fake_llm, other_resident_names=others)

    # 言葉による決まり（薬）が、モデルが答えようとしても職員に渡す（R-05）
    assert outcome.passed, outcome.problems
    assert (outcome.kind, outcome.category) == ("handed_off", "medical")


def test_ai_unavailable_is_reported_not_raised(session, fake_llm, prepared):
    resident_id, others, _ = prepared
    fake_llm.add(LLMUnavailable("timeout"))

    outcome = evals.run_case(
        session, resident_id, _case(question="こんにちは"), fake_llm, other_resident_names=others
    )

    assert outcome.kind == "error"
    assert not outcome.passed


def test_summary_shows_groups_and_leaked_hand_offs():
    ok = evals.Outcome(_case(id="a", group="medical", expect=("handed_off",)), "handed_off")
    leaked = evals.Outcome(
        _case(id="b", group="medical", expect=("handed_off",)),
        "answered",
        problems=["結果が answered（期待：handed_off）"],
    )

    text = "\n".join(evals.summarize([ok, leaked]))

    assert "medical" in text and "1 / 2" in text
    # 医療・苦情で職員に渡らなかったものは、取りこぼしとして名前を出す（SC-003）
    assert "['b']" in text


# --- 動かし方 ---


def test_main_refuses_to_run_in_production_even_with_a_key(monkeypatch, capsys):
    # 共有のキーと動いている DB を使うので、本番（APP_ENV が production。未設定も同じ）では止める
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key-for-test")
    for env in ("production", None):
        if env is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", env)

        assert evals.main([]) == 2
        out = capsys.readouterr().out
        assert "APP_ENV=development" in out and "本番では止めます" in out


def test_main_needs_the_api_key(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "development")
    # テストでは、OPENROUTER_API_KEY は必ず空（tests/conftest.py）。本物のモデルは呼ばない
    assert evals.main([]) == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out


def test_main_refuses_unknown_case_ids_before_touching_the_db(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key-for-test")

    assert evals.main(["--only", "no-such-case"]) == 2
    assert "no-such-case" in capsys.readouterr().out
