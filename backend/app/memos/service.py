"""様子のメモの保存と「日本語にする」（spec 007 の 007-T009・research.md R-05・R-09）。

- 下書きを先に保存する（`create_memo`）。「日本語にする」（`rewrite`）で AI を呼ぶ前に、
  原文は残っている。AI が止まったときは LLMUnavailable がそのまま出て、何も書かない
  （履歴も作らない。原文は残り、やり直しの回数にも数えない。R-09）
- 直す・整える・確かめる・取り下げるのは本人だけ。本人でないメモは、あることも分からないよう
  「ない」として扱う（NOT_FOUND）。承認待ち以降をリーダー・施設長が見られる条件は、
  007-T016・T018（作り込み）で足す
- 今は「整える」だけ。訳し戻し・機械の目の印・1 日 3 件・やり直しの上限は、作り込み
  （007-T008・T013・T014・T017）で足す

サービスの関数は commit しない（API の最後で 1 回 commit する。app/db.py）。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.errors import AppError, ErrorCode
from app.inquiry.llm import ChatClient
from app.memos.rewrite import rewrite_memo
from app.models.core import Resident, Staff
from app.models.memos import CareMemo, CareMemoRevision

# 直したり「日本語にする」をやり直したりできる状態（data-model.md の「状態の動き」）
EDITABLE_STATUSES = ("draft", "returned")


def create_memo(
    session: Session,
    user: CurrentUser,
    resident_id: int,
    original_text: str,
    source_lang: str,
) -> CareMemo:
    """下書きを作る。原文は、AI を呼ぶ前に、ここで保存する（R-09）。

    書いた職員は、ログイン中の職員から決める（送らせない）。日付は日本時間の今日。
    入居者は、書く職員と同じ施設のときだけ。ほかの施設の入居者は、ない入居者と同じ NOT_FOUND
    にする（承認の API と同じ作り。#326）。
    """
    assert user.staff_id is not None
    resident = session.get(Resident, resident_id)
    facility_id = session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()
    if resident is None or resident.facility_id != facility_id:
        raise AppError(ErrorCode.NOT_FOUND)
    memo = CareMemo(
        resident_id=resident_id,
        author_staff_id=user.staff_id,
        memo_date=today_jst(),
        source_lang=source_lang,
        original_text=original_text,
        status="draft",
    )
    session.add(memo)
    session.flush()
    return memo


def get_own_memo(
    session: Session, user: CurrentUser, memo_id: int, *, for_update: bool = False
) -> CareMemo:
    """本人のメモを返す。ないとき・本人でないときは NOT_FOUND（ほかの人の下書きを探られない）。"""
    query = select(CareMemo).where(
        CareMemo.id == memo_id, CareMemo.author_staff_id == user.staff_id
    )
    if for_update:
        query = query.with_for_update()
    memo = session.scalars(query).one_or_none()
    if memo is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return memo


def list_own_memos(
    session: Session,
    user: CurrentUser,
    *,
    resident_id: int | None = None,
    day: date | None = None,
) -> list[CareMemo]:
    """自分のメモの一覧（新しい順）。入居者・書いた日で絞れる。"""
    query = select(CareMemo).where(CareMemo.author_staff_id == user.staff_id)
    if resident_id is not None:
        query = query.where(CareMemo.resident_id == resident_id)
    if day is not None:
        query = query.where(CareMemo.memo_date == day)
    return list(session.scalars(query.order_by(CareMemo.id.desc())))


def rewrite(
    session: Session, user: CurrentUser, memo_id: int, *, llm: ChatClient | None = None
) -> CareMemo:
    """「日本語にする」：原文を整えた日本語にして、メモと履歴に保存する（FR-003・FR-004）。

    直せる状態（draft・returned）のときだけ（409 `invalid_state`）。メモの行を先に押さえて、
    同じメモの「日本語にする」が同時に走らないようにする。
    AI が止まったときは LLMUnavailable が出て、何も書かない。
    AI には、原文と原文の言語だけを渡す（入居者の呼び名・氏名は渡さない。FR-005）。
    """
    memo = get_own_memo(session, user, memo_id, for_update=True)
    if memo.status not in EDITABLE_STATUSES:
        raise AppError(ErrorCode.INVALID_STATE)
    result = rewrite_memo(
        memo.original_text, memo.source_lang, user.language, llm=llm, back_translate=False
    )
    memo.rewritten_text = result.rewritten_text
    memo.back_translation = None
    session.add(
        CareMemoRevision(
            memo_id=memo.id,
            original_text=memo.original_text,
            rewritten_text=result.rewritten_text,
            back_translation=None,
            model=result.model,
            latency_ms=result.latency_ms,
        )
    )
    session.flush()
    return memo
