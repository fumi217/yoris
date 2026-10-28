"""問い合わせ AI に渡すツール（spec 004 の 004-T016・contracts/agent-tools.md・research.md R-02）。

どのツールも、入居者の id を引数に持たない。入居者はサーバーがログイン中の家族から決めて、
ToolContext に入れて渡す（FR-020）。AI ができるのは、読み取りと「答える」「渡す」だけで、
データを書き換えるツールは渡さない（FR-022）。

answer_family と hand_off_to_staff はループを終えるツールなので、agent.py が扱う。
ここでは、読むツール（get_care_records・get_staff_replies）を実行する。
"""

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.inquiry.labels import TEMPLATE_LABELS, THEME_LABELS
from app.models.records import DAY_SLOT
from app.services.disclosure import get_active_replies, get_disclosed_records, is_item_disclosed

# 調べられる期間（今日を含めて 7 日。agent-tools.md）
LOOKBACK_DAYS = 7
READ_ITEMS = ("meal", "mood", "sleep")
# 未記録として返す食事の区分（おやつは毎日あるとは限らないので入れない）
MISSING_MEAL_SLOTS = ("breakfast", "lunch", "dinner")

# AI が読むための値の意味（日本語）。家族の画面の文言は辞書（ja.json）で引く
VALUE_LABELS = {
    "meal": {
        "10": "全部",
        "8": "ほぼ全部（8割）",
        "5": "半分",
        "2": "少し",
        "0": "食べていない",
        "none": "食事なし（外泊・入院など）",
    },
    "mood": {"smile": "笑顔が多い", "normal": "いつもどおり", "low": "元気がない"},
    "sleep": {"good": "よく眠れた", "normal": "いつもどおり", "poor": "あまり眠れなかった"},
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_care_records",
            "description": (
                "この入居者の、家族に見せてよい連絡帳の記録（食事量・機嫌・様子・眠り）を調べる。"
                "今日を含めて 7 日まで。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
                    "items": {"type": "array", "items": {"enum": list(READ_ITEMS)}},
                },
                "required": ["date_from", "date_to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_replies",
            "description": (
                "家族の「知りたいこと」への、施設の職員の返事を調べる。今日を含めて 7 日まで。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
                },
                "required": ["date_from", "date_to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_family",
            "description": (
                "家族に答える。記録・返事にもとづく内容だけを書き、"
                "もとにした source_id を必ず入れる。"
                "記録がなければ、ないと伝える。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "家族の表示言語で。やさしい日本語。500 文字まで",
                    },
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "source_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hand_off_to_staff",
            "description": (
                "答えずに施設の職員に渡す。医療・服薬・体調の解釈・苦情・お金・緊急・記録にないことで"
                "人の確認が要るもの。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "enum": ["medical", "complaint", "money", "care_request", "urgent", "other"]
                    },
                    "summary": {
                        "type": "string",
                        "description": (
                            "職員向けの要約。やさしい日本語（短い文）。500 文字まで。"
                            "開示されていない記録の内容は書かない"
                        ),
                    },
                    "existing_message_id": {
                        "type": ["integer", "null"],
                        "description": "同じ内容の対応待ちのメッセージがあれば、その id",
                    },
                },
                "required": ["category", "summary"],
            },
        },
    },
]


@dataclass(frozen=True)
class ToolContext:
    """ツールを実行するときの前提。入居者はサーバーが決める（AI には選ばせない）。"""

    session: Session
    resident_id: int
    today: date


@dataclass(frozen=True)
class ToolOutcome:
    # AI に返す結果（JSON の文字列）
    content: str
    # この結果で AI に見せた根拠の id（answer_family の source_ids はこの中だけを残す。R-03）
    source_ids: list[str] = field(default_factory=list)


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _clamp(ctx: ToolContext, args: dict[str, Any]) -> tuple[date, date, bool] | None:
    """期間を、今日を含めて 7 日に切り詰める。日付が読めなければ None。"""
    try:
        date_from = date.fromisoformat(str(args.get("date_from")))
        date_to = date.fromisoformat(str(args.get("date_to")))
    except ValueError:
        return None
    earliest = ctx.today - timedelta(days=LOOKBACK_DAYS - 1)
    clamped_from = min(max(date_from, earliest), ctx.today)
    clamped_to = min(max(date_to, earliest), ctx.today)
    if clamped_from > clamped_to:
        clamped_from, clamped_to = clamped_to, clamped_from
    clamped = (clamped_from, clamped_to) != (date_from, date_to)
    return clamped_from, clamped_to, clamped


def get_care_records(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    period = _clamp(ctx, args)
    if period is None:
        return ToolOutcome(_json({"error": "invalid_date"}))
    date_from, date_to, clamped = period
    requested = args.get("items")
    items = [i for i in READ_ITEMS if not isinstance(requested, list) or i in requested]
    # 非開示の項目は、records にも missing にも出さない
    disclosed = [item for item in items if is_item_disclosed(ctx.session, item)]

    records = get_disclosed_records(ctx.session, ctx.resident_id, date_from, date_to, disclosed)
    filled = {(r.date, r.item, r.slot) for r in records}
    missing = []
    day = date_from
    while day <= date_to:
        for item in disclosed:
            slots = MISSING_MEAL_SLOTS if item == "meal" else (DAY_SLOT,)
            for slot in slots:
                if (day, item, slot) not in filled:
                    missing.append({"date": day.isoformat(), "item": item, "slot": slot})
        day += timedelta(days=1)

    rows = [
        {
            "source_id": f"record:{r.id}",
            "date": r.date.isoformat(),
            "item": r.item,
            "slot": r.slot,
            "value": r.value,
            "label": VALUE_LABELS.get(r.item, {}).get(r.value, r.value),
        }
        for r in records
    ]
    return ToolOutcome(
        _json({"records": rows, "missing": missing, "clamped": clamped}),
        [row["source_id"] for row in rows],
    )


def get_staff_replies(ctx: ToolContext, args: dict[str, Any]) -> ToolOutcome:
    period = _clamp(ctx, args)
    if period is None:
        return ToolOutcome(_json({"error": "invalid_date"}))
    date_from, date_to, clamped = period
    replies = [
        {
            "source_id": f"reply:{reply.id}",
            "date": reply.contact_book_date.isoformat(),
            # テーマと定型文はコードで返ってくるので、AI が読む日本語にする（labels.py）
            "theme": THEME_LABELS.get(reply.theme_code, reply.theme_code),
            "text": "。".join(TEMPLATE_LABELS.get(code, code) for code in reply.template_codes),
            # 職員が書き足した文（指示のような文が入っていても、データとして渡す。R-04）
            "note": reply.note,
        }
        for reply in get_active_replies(ctx.session, ctx.resident_id, date_from, date_to)
    ]
    return ToolOutcome(
        _json({"replies": replies, "clamped": clamped}),
        [reply["source_id"] for reply in replies],
    )


READ_TOOLS = {"get_care_records": get_care_records, "get_staff_replies": get_staff_replies}


def run_read_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> ToolOutcome:
    """読むツールを実行する。知らない名前なら、エラーを AI に返す（止めない）。"""
    tool = READ_TOOLS.get(name)
    if tool is None:
        return ToolOutcome(_json({"error": "unknown_tool"}))
    return tool(ctx, args)
