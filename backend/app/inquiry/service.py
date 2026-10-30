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

- AI が職員に渡したら、職員へのメッセージ（staff_messages）を作る（担当は空。004-T024）。
  その家族の対応待ちにつなぐときは新しく作らず、家族の発言をそのメッセージの続きの書き込みにする（FR-016）
  （言葉による決まりに当たった発言の種類は、AI のループ（agent.py）で決まった種類に直してある）

サービスの関数は commit しない（API の最後で 1 回だけ commit する。app/db.py）。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import now, today_jst
from app.errors import AppError, ErrorCode
from app.inquiry.agent import HISTORY_MESSAGES, HandOff, run_agent
from app.inquiry.guard import detect_category
from app.inquiry.llm import ChatClient
from app.inquiry.staff_replies import load_staff_reply_details
from app.inquiry.tools import ToolContext
from app.models.core import FamilyAccount, Resident
from app.models.inquiry import InquiryConversation, InquiryMessage, StaffMessage
from app.models.notifications import Notification
from app.models.records import CareRecord
from app.models.replies import Reply
from app.models.requests import Request
from app.services.disclosure import get_active_replies, get_disclosed_records

logger = logging.getLogger(__name__)

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
class HandoffView:
    """職員に渡した AI の発言の、家族の画面に出す状態（質問の種類そのものは出さない）。"""

    status: str  # "waiting" / "answered"
    # 緊急なら、画面は「お急ぎのときは、施設にお電話ください」も出す（Edge Cases）
    urgent: bool
    # 同じ内容の対応待ちにつないだなら、画面は「すでに施設の職員にお伝えしています」（FR-016）
    already: bool


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
    # 職員の発言だけ：返事をした職員の表示名・選んだ定型文のコード・書き足した文・
    # 返し方（app／phone）
    staff_name: str | None = None
    staff_occupation: str | None = None
    template_codes: list[str] | None = None
    note: str | None = None
    response_type: str | None = None
    # 職員に渡した AI の発言だけ
    handoff: HandoffView | None = None


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


def mark_staff_reply_read(session: Session, user: CurrentUser, message_id: int) -> None:
    """職員の返事の発言を見たとき、その発言のお知らせを読んだことにする（Issue #244）。

    読んだことにするのは、その発言と同じ staff_message_id で、その発言の日時までに作られた、
    同じ家族の未読のお知らせ。返事の発言とお知らせは同じトランザクションで作る（reply_in_app）
    ので、時刻が同じになる。同じメッセージに返事が 2 回付いたときは、後の返事を見れば前の分も、
    前の返事だけなら前の分だけが読んだことになる。
    ほかの家族の発言・職員の返事でない発言（電話で対応した発言を含む）は 404。何度呼んでも同じ。
    commit しない。
    """
    family_account_id = get_family_account_id(session, user)
    message = session.execute(
        select(InquiryMessage)
        .join(InquiryConversation, InquiryConversation.id == InquiryMessage.conversation_id)
        .where(
            InquiryMessage.id == message_id,
            InquiryConversation.family_account_id == family_account_id,
            InquiryMessage.sender == "staff",
            InquiryMessage.response_type == "app",
        )
    ).scalar_one_or_none()
    if message is None or message.staff_message_id is None:
        raise AppError(ErrorCode.NOT_FOUND)
    session.execute(
        update(Notification)
        .where(
            Notification.family_account_id == family_account_id,
            Notification.kind == "staff_message_reply",
            Notification.staff_message_id == message.staff_message_id,
            Notification.read_at.is_(None),
            Notification.created_at <= message.created_at,
        )
        .values(read_at=now())
    )


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
        # 職員の返事は、次の PR で「施設の職員の返事」と分かる形で足す（R-06）
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
    staff_message_id = None
    if result.kind == "handed_off":
        # 渡したのに中身がないと、黙って職員に届かなくなるので、ここで止める（PR #215 ようこ）
        assert result.hand_off is not None
        staff_message_id = _hand_off(session, conversation, family_message, result.hand_off)
    ai_message = InquiryMessage(
        conversation_id=conversation.id,
        sender="ai",
        body=result.text if result.kind == "answered" and result.text else "",
        ai_result=result.kind,
        source_ids=result.source_ids,
        model=result.model,
        tool_calls=result.tool_calls,
        latency_ms=result.latency_ms,
        staff_message_id=staff_message_id,
    )
    session.add(ai_message)
    session.flush()
    session.refresh(family_message)
    session.refresh(ai_message)
    # 1 回のやり取りの記録。出すのは id・種類・結果・ツールの回数・時間・モデル名だけ。
    # 発言の文・答え・要約・記録の値・氏名は出さない（FR-029・research.md R-15）。
    # 値は %s で埋める（名前つきの引数は、標準の logging では使えない）
    logger.info(
        "問い合わせの AI が答えを決めた conversation_id=%s family_message_id=%s"
        " ai_message_id=%s result=%s category=%s tool_calls=%s latency_ms=%s model=%s",
        conversation.id,
        family_message.id,
        ai_message.id,
        result.kind,
        result.hand_off.category if result.hand_off else None,
        result.tool_calls,
        result.latency_ms,
        result.model,
    )
    return family_message, ai_message


def _hand_off(
    session: Session,
    conversation: InquiryConversation,
    family_message: InquiryMessage,
    hand_off: HandOff,
) -> int:
    """職員へのメッセージを作り（またはつなぎ）、その id を返す（004-T024）。

    AI が existing_message_id を付け、それがこの家族の対応待ちで、種類も同じなら、新しく作らずに
    つなぐ（FR-016）。種類が違えば新しく作る（緊急がほかの種類に埋もれない・苦情がほかの種類の
    続きとして見えないように。PR #215 のレビュー）。対応済みになっていたときも新しく作る。
    担当は空で作る（FR-012b）。
    """
    if hand_off.existing_message_id is not None:
        existing = session.scalars(
            select(StaffMessage)
            .where(
                StaffMessage.id == hand_off.existing_message_id,
                StaffMessage.conversation_id == conversation.id,
                StaffMessage.status == "waiting",
                StaffMessage.category == hand_off.category,
            )
            .with_for_update()
        ).one_or_none()
        if existing is not None:
            # 職員の詳細の「追加された家族の書き込み」に出る
            family_message.staff_message_id = existing.id
            return existing.id
    staff_message = StaffMessage(
        conversation_id=conversation.id,
        resident_id=conversation.resident_id,
        origin_message_id=family_message.id,
        category=hand_off.category,
        summary=hand_off.summary,
    )
    session.add(staff_message)
    session.flush()
    return staff_message.id


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
    staff_replies = load_staff_reply_details(session, messages)
    handoffs = _handoffs(session, messages)
    views = []
    for m in messages:
        if m.id in staff_replies:
            reply = staff_replies[m.id]
            views.append(
                MessageView(
                    id=m.id,
                    sender=m.sender,
                    body=m.body,
                    created_at=m.created_at,
                    staff_name=reply.staff_name,
                    staff_occupation=reply.staff_occupation,
                    template_codes=reply.template_codes,
                    note=reply.note,
                    response_type=reply.response_type,
                )
            )
            continue
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
                handoff=handoffs.get(m.id),
            )
        )
    return views


def _handoffs(session: Session, messages: list[InquiryMessage]) -> dict[int, HandoffView]:
    """職員に渡した AI の発言ごとの状態（AI の発言の id → 状態）。

    「すでにお伝えしています」は、その AI の発言より前に、同じメッセージへの家族の続きの書き込みが
    あるかで決める（最初に渡したときの家族の発言は、メッセージの原文で、続きの書き込みではない）。
    """
    handed = {
        m.id: m.staff_message_id
        for m in messages
        if m.sender == "ai" and m.ai_result == "handed_off" and m.staff_message_id is not None
    }
    if not handed:
        return {}
    staff_ids = set(handed.values())
    states = {
        row.id: row
        for row in session.execute(
            select(StaffMessage.id, StaffMessage.status, StaffMessage.category).where(
                StaffMessage.id.in_(staff_ids)
            )
        )
    }
    first_follow_up = dict(
        session.execute(
            select(InquiryMessage.staff_message_id, func.min(InquiryMessage.id))
            .where(
                InquiryMessage.sender == "family", InquiryMessage.staff_message_id.in_(staff_ids)
            )
            .group_by(InquiryMessage.staff_message_id)
        ).all()
    )
    views = {}
    for ai_id, staff_id in handed.items():
        state = states.get(staff_id)
        if state is None:
            continue
        follow_up = first_follow_up.get(staff_id)
        views[ai_id] = HandoffView(
            status=state.status,
            urgent=state.category == "urgent",
            already=follow_up is not None and follow_up < ai_id,
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
