"""変化の決まり（spec 006 の 006-T002）。記録の値だけで決まる関数で、DB に触らない。

決まりは 3 つ（コードで持ち、条件は変えられない。FR-012）。

- `meal_low`：朝ごはん・昼ごはん・夜ごはんのうち、2 食続けて「少し」以下（おやつは数えない）
- `mood_low`：機嫌・様子が、2 日続けて「元気がない」
- `sleep_poor`：眠りが、2 日続けて「あまり眠れなかった」

「続けて」の数え方は research.md R-02：
いちばん新しい記録のある枠から古いほうへさかのぼり、当てはまる値を数える。
未記録・取り消した記録・「食事なし」は「すきま」で、当てはまる値としては数えない。
すきまが 2 枠続いたら、当てはまらない値が来たら、そこでやめる。
まだ記録のない「これからの枠」は、いちばん新しい記録より新しいので、数えない。

AI は使わない。様子のメモなどの文は読まない（原則 III）。
入力は、取り消していない記録だけを渡す（取り消した記録は、渡さないことですきまになる）。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

# さかのぼる日数（いちばん新しい記録の日を含めて 7 日。1 回に読む記録を少なくするため）。
# 7 日より長く続いても、目印は付いたまま（続いた数と記録が 7 日分になるだけ）
LOOKBACK_DAYS = 7
# すきまがこれだけ続いたら数えるのをやめる（食事は 2 食、機嫌・眠りは 2 日）
MAX_GAP = 2


@dataclass(frozen=True)
class RuleSpec:
    """1 つの決まりの条件。"""

    code: str
    item: str
    # 時間の順に並べた枠。食事は朝・昼・夜（おやつは入れない）、機嫌・眠りは 1 日 1 枠
    slots: tuple[str, ...]
    # 当てはまる値
    matching_values: frozenset[str]
    # すきまとして扱う値（未記録と同じ。「食事なし」）
    gap_values: frozenset[str]
    # 何枠続けば当てはまるか
    required: int


RULES: dict[str, RuleSpec] = {
    "meal_low": RuleSpec(
        code="meal_low",
        item="meal",
        slots=("breakfast", "lunch", "dinner"),
        matching_values=frozenset({"2", "0"}),
        gap_values=frozenset({"none"}),
        required=2,
    ),
    "mood_low": RuleSpec(
        code="mood_low",
        item="mood",
        slots=("day",),
        matching_values=frozenset({"low"}),
        gap_values=frozenset(),
        required=2,
    ),
    "sleep_poor": RuleSpec(
        code="sleep_poor",
        item="sleep",
        slots=("day",),
        matching_values=frozenset({"poor"}),
        gap_values=frozenset(),
        required=2,
    ),
}
RULE_CODES = tuple(RULES)


@dataclass(frozen=True)
class RuleRecord:
    """決まりに渡す記録 1 件（`care_records` の取り消していない行）。"""

    record_id: int
    date: date
    item: str
    slot: str
    value: str


@dataclass(frozen=True)
class Evidence:
    """当てはまったもとの記録。すきまは含まない。"""

    record_id: int
    date: date
    slot: str
    value: str

    def as_json(self) -> dict[str, Any]:
        """`change_flags.evidence`（jsonb）に入れる形。日付は文字にする。"""
        return {
            "record_id": self.record_id,
            "date": self.date.isoformat(),
            "slot": self.slot,
            "value": self.value,
        }


@dataclass(frozen=True)
class RuleResult:
    """決まりを調べた結果。当てはまらないときも、数えた分の続いた数と記録を返す。"""

    matches: bool
    streak: int
    # 古い順
    evidence: tuple[Evidence, ...]


def evaluate_rule(code: str, records: Sequence[RuleRecord]) -> RuleResult:
    """1 人の入居者の記録の並びに、決まり `code` が当てはまるかを調べる。

    records の順番は問わない。決まりに関係ない項目・区分（おやつなど）は読み飛ばす。
    """
    rule = RULES[code]
    per_day = len(rule.slots)
    slot_index = {slot: i for i, slot in enumerate(rule.slots)}

    # 時間の順に 1 つずつ増える番号（日 × 1 日の枠の数 ＋ 枠の位置）で、枠を並べる
    by_position: dict[int, RuleRecord] = {}
    for record in records:
        if record.item == rule.item and record.slot in slot_index:
            by_position[record.date.toordinal() * per_day + slot_index[record.slot]] = record
    if not by_position:
        return RuleResult(matches=False, streak=0, evidence=())

    newest = max(by_position)
    newest_date = date.fromordinal(newest // per_day)
    oldest = (newest_date - timedelta(days=LOOKBACK_DAYS - 1)).toordinal() * per_day

    found: list[Evidence] = []
    gaps = 0
    for position in range(newest, oldest - 1, -1):
        record = by_position.get(position)
        if record is None or record.value in rule.gap_values:
            gaps += 1
            if gaps >= MAX_GAP:
                break
        elif record.value in rule.matching_values:
            gaps = 0
            found.append(Evidence(record.record_id, record.date, record.slot, record.value))
        else:
            break

    found.reverse()
    return RuleResult(matches=len(found) >= rule.required, streak=len(found), evidence=tuple(found))
