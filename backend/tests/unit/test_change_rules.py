"""変化の決まりの判定（006-T001）。DB を使わないので CI でも動く。

SC-002：当てはまる 10 件・当てはまらない 10 件で、付け間違い・付け忘れが 0 件。
記録は「取り消していないもの」だけを渡す（取り消した記録は、渡さないことですきまになる）。
日付は、水曜の 2026-10-28 を「今日」にして、何日前かで書く。
"""

from datetime import date, timedelta

import pytest

from app.services.change_rules import LOOKBACK_DAYS, RULE_CODES, RuleRecord, evaluate_rule

TODAY = date(2026, 10, 28)
ITEM_OF = {"meal_low": "meal", "mood_low": "mood", "sleep_poor": "sleep"}


def records(code: str, rows: list[tuple[int, str, str]]) -> list[RuleRecord]:
    """(何日前, 区分, 値) の並びから記録を作る。id は 1 から順に振る。"""
    item = ITEM_OF[code]
    return [
        RuleRecord(i, TODAY - timedelta(days=days_ago), item, slot, value)
        for i, (days_ago, slot, value) in enumerate(rows, start=1)
    ]


def mood(rows: list[tuple[int, str]]) -> list[tuple[int, str, str]]:
    return [(days_ago, "day", value) for days_ago, value in rows]


# --- 当てはまる 10 件 ---

MATCHING = {
    # 食事
    "前の日の夜「少し」→ 朝「食べていない」（US1 シナリオ 1）": (
        "meal_low",
        [(1, "dinner", "2"), (0, "breakfast", "0")],
    ),
    "同じ日の朝「少し」・昼「少し」": ("meal_low", [(0, "breakfast", "2"), (0, "lunch", "2")]),
    "昼「少し」・夜「食べていない」（朝は前の日）": (
        "meal_low",
        [(0, "lunch", "2"), (0, "dinner", "0")],
    ),
    "3 食続けて": (
        "meal_low",
        [(1, "dinner", "2"), (0, "breakfast", "0"), (0, "lunch", "2")],
    ),
    "間に 1 食の未記録（朝「少し」・昼なし・夜「少し」）": (
        "meal_low",
        [(0, "breakfast", "2"), (0, "dinner", "2")],
    ),
    "間に「食事なし」が 1 食（外泊の前後）": (
        "meal_low",
        [(1, "dinner", "2"), (0, "breakfast", "none"), (0, "lunch", "0")],
    ),
    "おやつは数えず、朝・昼で当てはまる": (
        "meal_low",
        [(0, "breakfast", "2"), (0, "lunch", "2"), (0, "snack", "10")],
    ),
    # 機嫌
    "機嫌 月・水「元気がない」・火は未記録（Edge Cases）": (
        "mood_low",
        mood([(2, "low"), (0, "low")]),
    ),
    # 眠り
    "眠り 2 日続けて「あまり眠れなかった」": (
        "sleep_poor",
        [(1, "day", "poor"), (0, "day", "poor")],
    ),
    "眠り 間に 1 日の未記録": ("sleep_poor", [(2, "day", "poor"), (0, "day", "poor")]),
}

# --- 当てはまらない 10 件 ---

NOT_MATCHING = {
    "昼「少し」→ おやつ「食べていない」（おやつは数えない。US1 シナリオ 3a）": (
        "meal_low",
        [(0, "lunch", "2"), (0, "snack", "0")],
    ),
    "夜「食事なし」→ 朝「食事なし」（すきまが 2 食続く）": (
        "meal_low",
        [(2, "dinner", "2"), (1, "dinner", "none"), (0, "breakfast", "none")],
    ),
    "最新が「ほぼ全部」（その前に「少し」が 2 食あっても数えない）": (
        "meal_low",
        [(1, "dinner", "2"), (0, "breakfast", "2"), (0, "lunch", "8")],
    ),
    "「少し」が 1 食だけ": ("meal_low", [(0, "breakfast", "2")]),
    "間の未記録が 2 食（昼・朝がない）": (
        "meal_low",
        [(1, "dinner", "2"), (0, "dinner", "0")],
    ),
    "間に「ほぼ全部」": (
        "meal_low",
        [(0, "breakfast", "2"), (0, "lunch", "10"), (0, "dinner", "2")],
    ),
    "機嫌 月「元気がない」・火〜木は未記録・金「元気がない」（Edge Cases）": (
        "mood_low",
        mood([(4, "low"), (0, "low")]),
    ),
    "機嫌 最新が「いつもどおり」": ("mood_low", mood([(1, "low"), (0, "normal")])),
    "眠り 「あまり眠れなかった」が 1 日だけ（前の日は「よく眠れた」）": (
        "sleep_poor",
        [(1, "day", "good"), (0, "day", "poor")],
    ),
    "機嫌 火「元気がない」は取り消された（記録の並びにない）・月の 1 日だけ": (
        "mood_low",
        mood([(2, "low")]),
    ),
}


@pytest.mark.parametrize(("code", "rows"), MATCHING.values(), ids=MATCHING.keys())
def test_matching(code, rows):
    result = evaluate_rule(code, records(code, rows))
    assert result.matches, "付け忘れ"


@pytest.mark.parametrize(("code", "rows"), NOT_MATCHING.values(), ids=NOT_MATCHING.keys())
def test_not_matching(code, rows):
    result = evaluate_rule(code, records(code, rows))
    assert not result.matches, "付け間違い"


def test_every_rule_has_cases():
    assert set(RULE_CODES) == {"meal_low", "mood_low", "sleep_poor"}
    assert len(MATCHING) == 10
    assert len(NOT_MATCHING) == 10
    for cases in (MATCHING, NOT_MATCHING):
        assert {code for code, _ in cases.values()} == set(RULE_CODES)


# --- 続いた数と、返す記録（research.md R-02） ---


def test_evidence_is_oldest_first_and_has_no_gap():
    # 前の日の夜「少し」・朝「食事なし」・昼「食べていない」：朝はすきまなので含めない
    rows = [(1, "dinner", "2"), (0, "breakfast", "none"), (0, "lunch", "0")]
    result = evaluate_rule("meal_low", records("meal_low", rows))
    assert result.matches
    assert result.streak == 2
    assert [(e.record_id, e.date, e.slot, e.value) for e in result.evidence] == [
        (1, TODAY - timedelta(days=1), "dinner", "2"),
        (3, TODAY, "lunch", "0"),
    ]


def test_evidence_as_json_for_jsonb():
    result = evaluate_rule("meal_low", records("meal_low", [(1, "dinner", "2"), (0, "lunch", "0")]))
    # 朝がすきま 1 食（記録なし）。日付は文字にする
    assert [e.as_json() for e in result.evidence] == [
        {"record_id": 1, "date": "2026-10-27", "slot": "dinner", "value": "2"},
        {"record_id": 2, "date": "2026-10-28", "slot": "lunch", "value": "0"},
    ]


def test_order_of_input_does_not_matter():
    rows = [(1, "dinner", "2"), (0, "breakfast", "0"), (0, "lunch", "2")]
    forward = evaluate_rule("meal_low", records("meal_low", rows))
    backward = evaluate_rule("meal_low", records("meal_low", rows)[::-1])
    assert forward == backward


def test_future_slots_are_not_counted_as_gaps():
    # 昼の時点で、夜ごはんはまだ記録がない。朝「少し」・昼「少し」は当てはまる
    result = evaluate_rule(
        "meal_low", records("meal_low", [(0, "breakfast", "2"), (0, "lunch", "2")])
    )
    assert result.matches
    assert result.streak == 2


def test_snack_is_not_the_newest_slot():
    # おやつが最新でも、その前の 2 食を数える（おやつで途切れない）
    rows = [(0, "breakfast", "2"), (0, "lunch", "0"), (0, "snack", "10")]
    assert evaluate_rule("meal_low", records("meal_low", rows)).streak == 2


def test_none_only_is_not_matching():
    # 入院などで何日も「食事なし」が続いても、目印は付けない
    rows = [(d, slot, "none") for d in range(3) for slot in ("breakfast", "lunch", "dinner")]
    result = evaluate_rule("meal_low", records("meal_low", rows))
    assert not result.matches
    assert result.streak == 0
    assert result.evidence == ()


def test_no_records():
    result = evaluate_rule("meal_low", [])
    assert not result.matches
    assert result.streak == 0


def test_other_items_are_ignored():
    # 機嫌の記録だけがある入居者に、食事の決まりは当てはまらない
    rows = records("mood_low", mood([(1, "low"), (0, "low")]))
    assert not evaluate_rule("meal_low", rows).matches
    assert evaluate_rule("mood_low", rows).matches


def test_not_matching_value_stops_counting_even_after_a_gap():
    # 夜「少し」・昼なし・朝「ほぼ全部」：1 食あけても、「ほぼ全部」で数えるのをやめる
    rows = [(0, "breakfast", "8"), (0, "dinner", "2")]
    result = evaluate_rule("meal_low", records("meal_low", rows))
    assert result.streak == 1
    assert not result.matches


def test_lookback_is_limited_to_seven_days():
    # 10 日続けて「元気がない」でも、読むのは新しい記録から 7 日分
    rows = mood([(d, "low") for d in range(10)])
    result = evaluate_rule("mood_low", records("mood_low", rows))
    assert result.matches
    assert result.streak == LOOKBACK_DAYS
    assert result.evidence[0].date == TODAY - timedelta(days=LOOKBACK_DAYS - 1)
    assert result.evidence[-1].date == TODAY


def test_meal_gap_across_days_counts_slots_not_days():
    # 夜「少し」→（翌日の朝はなし）→ 昼「少し」：すきま 1 食なので当てはまる
    rows = [(1, "dinner", "2"), (0, "lunch", "2")]
    assert evaluate_rule("meal_low", records("meal_low", rows)).matches
    # 夜「少し」→（翌日の朝・昼がなし）→ 夜「少し」：すきま 2 食なので数え直し
    rows = [(1, "dinner", "2"), (0, "dinner", "2")]
    assert not evaluate_rule("meal_low", records("meal_low", rows)).matches
