"""家族の会話の保存と読み出し（spec 004 の 004-T018・data-model.md）。

- 会話は家族アカウントに 1 本。家族が初めて送ったときに作る
- 家族の発言と AI の発言は、AI の答えが決まってから一緒に保存する。
  AI につながらなかったとき（LLMUnavailable）は何も保存しない（送り直せる。FR-026）
- AI への指示の文・ツールの中身は保存しない。答えなかった AI の発言（handed_off・no_record）は
  本文を空にし、画面が辞書の決まった文を出す
- 「もとにした記録」は、読むたびに get_disclosed_records・get_active_replies を通して組み立てる
  （いま非開示になった記録・返事は出さない。FR-002）
- 根拠のうち 1 つでも非開示になった AI の答えは、本文も根拠も出さず（hidden）、AI にも渡さない
  （非開示になった中身を AI が新しい答えに書かないため。原則 IV・PR #205 ようこ）

職員に渡したときの職員へのメッセージ（staff_messages）は 004-T024 で作り、ここから呼ぶ。
サービスの関数は commit しない（API の最後で 1 回だけ commit する。app/db.py）。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.inquiry.agent import HISTORY_MESSAGES, run_agent
from app.inquiry.guard import detect_category
from app.inquiry.llm import ChatClient
from app.inquiry.tools import ToolContext
from app.models.core import FamilyAccount, Resident
from app.models.inquiry import InquiryConversation, InquiryMessage, StaffMessage
from app.models.records import CareRecord
from app.models.replies import Reply
from app.models.requests import Request
from app.services.disclosure import get_active_replies, get_disclosed_records

# AI に渡すときの、答えなかった AI の発言の書き方（本文が空のため）
_AI_RESULT_TEXT = {
    "handed_off": "（施設の職員にお伝えしました）",
    "no_record": "（お答えできる記録がありません）",
}
# 根拠が非開示になった答えの、AI への渡し方（中身は渡さない）
_HIDDEN_TEXT = "（この答えは、いまはお見せできません）"


@dataclass(frozen=True)
class SourceView:
    """AI の答えの「もとにした記録」（家族の画面に出す。FR-004）。"""

    source_id: str
    kind: str  # "record" / "reply"
    date: date
    item: str | None = None  # 記録の項目（"meal" など。辞書で引く）
    slot: str | None = None
    theme_code: str | None = None  # 返事のテーマ（"theme.meals" など。辞書で引く）


@dataclass(frozen=True)
class MessageView:
    id: int
    sender: str  # "family" / "ai" / "staff"
    body: str
    created_at: datetime
    ai_result: str | None = None
    sources: list[SourceView] = field(default_factory=list)
    # 根拠のうち 1 つでも非開示になった答え（本文・根拠は空。画面は inquiry.answer_hidden）
    hidden: bool = False


def _is_hidden(message: InquiryMessage, disclosed: dict[str, SourceView]) -> bool:
    """根拠のうち 1 つでも、いま家族に見せられない AI の答えか。"""
    return (
        message.sender == "ai"
        and message.ai_result == "answered"
        and any(s not in disclosed for s in (message.source_ids or []))
    )


def get_conversation(session: Session, user: CurrentUser) -> InquiryConversation | None:
    return session.scalars(
        select(InquiryConversation).where(
            InquiryConversation.family_account_id == get_family_account_id(session, user)
        )
    ).one_or_none()


def get_family_account_id(session: Session, user: CurrentUser) -> int:
    return session.scalars(
        select(FamilyAccount.id).where(FamilyAccount.user_id == user.user_id)
    ).one()


def _get_or_create_conversation(session: Session, user: CurrentUser) -> InquiryConversation:
    """会話を作る。初めての質問が同時に 2 つ届いても、2 本目は作らず同じ会話を使う。

    family_account_id は一意なので、ぶつかったら何もしない（ON CONFLICT DO NOTHING）で読み直す
    （一意の違反で 500 にしない。PR #205 ようこ）。
    """
    family_account_id = get_family_account_id(session, user)
    session.execute(
        insert(InquiryConversation)
        .values(family_account_id=family_account_id, resident_id=user.resident_id)
        .on_conflict_do_nothing(index_elements=["family_account_id"])
    )
    return session.scalars(
        select(InquiryConversation).where(
            InquiryConversation.family_account_id == family_account_id
        )
    ).one()


def _history(session: Session, resident_id: int, conversation_id: int) -> list[dict[str, Any]]:
    """AI に渡す直近のやりとり（6 往復。research.md R-06）。"""
    rows = session.scalars(
        select(InquiryMessage)
        .where(InquiryMessage.conversation_id == conversation_id)
        .order_by(InquiryMessage.id.desc())
        .limit(HISTORY_MESSAGES)
    ).all()
    disclosed = _disclosed_sources(
        session, resident_id, [s for m in rows for s in (m.source_ids or [])]
    )
    history = []
    for message in reversed(rows):
        if message.sender == "family":
            history.append({"role": "user", "content": message.body})
        elif message.sender == "ai":
            if _is_hidden(message, disclosed):
                # 根拠が非開示になった答えの中身は、AI にも渡さない（原則 IV）
                content = _HIDDEN_TEXT
            else:
                content = message.body or _AI_RESULT_TEXT.get(message.ai_result or "", "")
            history.append({"role": "assistant", "content": content})
        # 職員の返事は、004-T029（#87）で「施設の職員の返事」と分かる形で足す
    return history


def _waiting(session: Session, conversation_id: int) -> list[dict[str, Any]]:
    """この家族の対応待ちのメッセージ（同じ内容ならつなぐため。FR-016）。"""
    rows = session.scalars(
        select(StaffMessage)
        .where(StaffMessage.conversation_id == conversation_id, StaffMessage.status == "waiting")
        .order_by(StaffMessage.id)
    ).all()
    return [{"id": m.id, "category": m.category, "summary": m.summary} for m in rows]


def _other_resident_names(session: Session, resident_id: int) -> list[str]:
    """同じ施設のほかの入居者の呼び名（答えに入っていたら出さない。R-04 の 6）。"""
    facility_id = select(Resident.facility_id).where(Resident.id == resident_id).scalar_subquery()
    return list(
        session.scalars(
            select(Resident.display_name).where(
                Resident.facility_id == facility_id, Resident.id != resident_id
            )
        )
    )


def send_message(
    session: Session, user: CurrentUser, body: str, *, llm: ChatClient | None = None
) -> tuple[InquiryMessage, InquiryMessage]:
    """家族の発言を AI に渡し、家族の発言と AI の発言を保存して返す。

    入居者は user.resident_id から決める（FR-020）。AI が止まったら LLMUnavailable がそのまま出て、
    何も保存しない（呼ぶ側で 503 にする。FR-026）。
    """
    assert user.resident_id is not None
    # AI の答えが決まるまでは何も書かない（止まったときに取り消すものがないように）
    existing = get_conversation(session, user)
    result = run_agent(
        ToolContext(session=session, resident_id=user.resident_id, today=today_jst()),
        question=body,
        language=user.language,
        history=_history(session, user.resident_id, existing.id) if existing else [],
        waiting=_waiting(session, existing.id) if existing else [],
        other_resident_names=_other_resident_names(session, user.resident_id),
        forced_category=detect_category(body),
        llm=llm,
    )

    conversation = existing or _get_or_create_conversation(session, user)
    family_message = InquiryMessage(conversation_id=conversation.id, sender="family", body=body)
    session.add(family_message)
    session.flush()
    ai_message = InquiryMessage(
        conversation_id=conversation.id,
        sender="ai",
        body=result.text if result.kind == "answered" and result.text else "",
        ai_result=result.kind,
        source_ids=result.source_ids,
        model=result.model,
        tool_calls=result.tool_calls,
        latency_ms=result.latency_ms,
    )
    session.add(ai_message)
    session.flush()
    session.refresh(family_message)
    session.refresh(ai_message)
    return family_message, ai_message


def list_messages(
    session: Session, user: CurrentUser, *, before: int | None = None, limit: int = 30
) -> list[MessageView]:
    """会話の発言を新しい順に返す（FR-008）。会話がまだなければ空。"""
    conversation = get_conversation(session, user)
    if conversation is None:
        return []
    query = select(InquiryMessage).where(InquiryMessage.conversation_id == conversation.id)
    if before is not None:
        query = query.where(InquiryMessage.id < before)
    rows = session.scalars(query.order_by(InquiryMessage.id.desc()).limit(limit)).all()
    return to_views(session, user, rows)


def to_views(
    session: Session, user: CurrentUser, messages: list[InquiryMessage]
) -> list[MessageView]:
    assert user.resident_id is not None
    all_ids = [s for m in messages for s in (m.source_ids or [])]
    sources = _disclosed_sources(session, user.resident_id, all_ids)
    views = []
    for m in messages:
        if _is_hidden(m, sources):
            # 根拠のうち 1 つでも非開示になった答えは、本文も根拠も出さない（原則 IV）
            views.append(MessageView(m.id, m.sender, "", m.created_at, m.ai_result, hidden=True))
            continue
        views.append(
            MessageView(
                id=m.id,
                sender=m.sender,
                body=m.body,
                created_at=m.created_at,
                ai_result=m.ai_result,
                sources=[sources[s] for s in (m.source_ids or [])],
            )
        )
    return views


def _ids(source_ids: list[str], prefix: str) -> set[int]:
    ids = set()
    for source_id in source_ids:
        kind, _, number = source_id.partition(":")
        if kind == prefix and number.isdigit():
            ids.add(int(number))
    return ids


def _disclosed_sources(
    session: Session, resident_id: int, source_ids: list[str]
) -> dict[str, SourceView]:
    """source_id から「もとにした記録」を組み立てる。今も家族に見せてよいものだけを返す。

    共通の関数は期間で読むので、先に id から日付の幅を調べ、その幅で共通の関数を呼んで、
    返ってきたものの中から id で選ぶ（共通の関数が返さないものは出さない）。
    """
    views: dict[str, SourceView] = {}

    record_ids = _ids(source_ids, "record")
    if record_ids:
        dates = session.scalars(
            select(CareRecord.date).where(
                CareRecord.id.in_(record_ids), CareRecord.resident_id == resident_id
            )
        ).all()
        if dates:
            for record in get_disclosed_records(session, resident_id, min(dates), max(dates)):
                if record.id in record_ids:
                    views[f"record:{record.id}"] = SourceView(
                        f"record:{record.id}",
                        "record",
                        record.date,
                        item=record.item,
                        slot=record.slot,
                    )

    reply_ids = _ids(source_ids, "reply")
    if reply_ids:
        dates = session.scalars(
            select(Reply.contact_book_date)
            .join(Request, Request.id == Reply.request_id)
            .where(Reply.id.in_(reply_ids), Request.resident_id == resident_id)
        ).all()
        if dates:
            for reply in get_active_replies(session, resident_id, min(dates), max(dates)):
                if reply.id in reply_ids:
                    views[f"reply:{reply.id}"] = SourceView(
                        f"reply:{reply.id}",
                        "reply",
                        reply.contact_book_date,
                        theme_code=reply.theme_code,
                    )
    return views
