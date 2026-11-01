"""様子のメモの保存と「日本語にする」（spec 007 の 007-T009・research.md R-05・R-09）。

- 下書きを先に保存する（`create_memo`）。「日本語にする」（`rewrite`）で AI を呼ぶ前に、
  原文は残っている。AI が止まったときは LLMUnavailable がそのまま出て、何も書かない
  （履歴も作らない。原文は残り、やり直しの回数にも数えない。R-09）
- 直す・整える・確かめる・取り下げるのは本人だけ。本人でないメモは、あることも分からないよう
  「ない」として扱う（NOT_FOUND）。リーダー・施設長が承認待ちを見るのは、承認の API
  （approvals.py。007-T022）
- 「整える」のあとに訳し戻しと機械の目の印を付ける（checks.py）。1 日 3 件（409 `memo_limit`）と
  やり直しの上限（409 `rewrite_limit`）もここで守る
- 直す（`update_memo`）・確かめる（`confirm`）・取り下げる（`withdraw`）は、条件つきの
  1 回の更新で状態を進める（R-05）。進められなければ 409（`invalid_state`）

サービスの関数は commit しない（API の最後で 1 回 commit する。app/db.py）。
"""

import logging
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import clock
from app.auth.deps import CurrentUser
from app.clock import today_jst
from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.inquiry.llm import ChatClient, LLMUnavailable
from app.memos.checks import check_memo
from app.memos.rewrite import back_translate_memo, rewrite_memo
from app.models.core import Resident, Staff
from app.models.memos import CareMemo, CareMemoRevision
from app.services.resident_names import other_resident_names

# ログに出すのは、メモの id・状態・操作・印の名前・かかった時間・モデル名だけ。
# 原文・整えた日本語・訳し戻し・氏名・理由の文は出さない（FR-018・research.md R-11）
logger = logging.getLogger(__name__)

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
    # 職員の行を押さえてから数える（同時に押しても 4 件目が入らない。R-06）
    session.scalars(select(Staff.id).where(Staff.id == user.staff_id).with_for_update()).one()
    today = today_jst()
    written_today = session.scalar(
        select(func.count())
        .select_from(CareMemo)
        .where(
            CareMemo.author_staff_id == user.staff_id,
            CareMemo.resident_id == resident_id,
            CareMemo.memo_date == today,
            CareMemo.status != "withdrawn",
        )
    )
    if written_today >= get_settings().memo_daily_limit:
        raise AppError(ErrorCode.MEMO_LIMIT)
    memo = CareMemo(
        resident_id=resident_id,
        author_staff_id=user.staff_id,
        memo_date=today,
        source_lang=source_lang,
        original_text=original_text,
        status="draft",
    )
    session.add(memo)
    session.flush()
    logger.info("様子のメモの下書きを作った: memo=%s resident=%s", memo.id, resident_id)
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
    session: Session,
    user: CurrentUser,
    memo_id: int,
    *,
    back_translate_only: bool = False,
    llm: ChatClient | None = None,
) -> CareMemo:
    """「日本語にする」：整えた日本語にし、訳し戻して、メモと履歴に保存する（FR-003・FR-004・FR-007）。

    職員の表示言語が日本語のときは、訳し戻さない。`back_translate_only` のときは、整え直さず、
    職員が直した整えた日本語を訳し戻すだけにする
    （整えた日本語がない・表示言語が日本語のときは 409）。
    直せる状態（draft・returned）のときだけ（409 `invalid_state`）。メモの行を先に押さえて、
    同じメモの「日本語にする」が同時に走らないようにする。
    AI が止まったときは LLMUnavailable が出て、何も書かない
    （整えた直後に訳し戻しが止まったときも）。
    AI には、原文と原文の言語（訳し戻しには整えた日本語）だけを渡す。
    入居者の呼び名・氏名は渡さない（FR-005）。
    """
    memo = get_own_memo(session, user, memo_id, for_update=True)
    if memo.status not in EDITABLE_STATUSES:
        raise AppError(ErrorCode.INVALID_STATE)
    if back_translate_only and (memo.rewritten_text is None or user.language == "ja"):
        raise AppError(ErrorCode.INVALID_STATE)
    # 履歴の数で数える。AI が止まったときは履歴を作らないので、数えない（R-08・R-09）
    revisions = session.scalar(
        select(func.count())
        .select_from(CareMemoRevision)
        .where(CareMemoRevision.memo_id == memo.id)
    )
    if revisions >= get_settings().memo_rewrite_limit:
        raise AppError(ErrorCode.REWRITE_LIMIT)
    try:
        if back_translate_only:
            result = back_translate_memo(memo.rewritten_text, user.language, llm=llm)
        else:
            result = rewrite_memo(memo.original_text, memo.source_lang, user.language, llm=llm)
    except LLMUnavailable as error:
        # 理由の文（error の中身）は出さず、種類だけ出す
        logger.warning(
            "様子のメモを日本語にできなかった: memo=%s error=%s", memo.id, type(error).__name__
        )
        raise
    memo.rewritten_text = result.rewritten_text
    memo.back_translation = result.back_translation
    memo.warnings = _warnings_of(session, memo)
    session.add(
        CareMemoRevision(
            memo_id=memo.id,
            original_text=memo.original_text,
            rewritten_text=result.rewritten_text,
            back_translation=result.back_translation,
            model=result.model,
            latency_ms=result.latency_ms,
        )
    )
    session.flush()
    logger.info(
        "様子のメモを日本語にした: memo=%s warnings=%s model=%s latency_ms=%s",
        memo.id,
        memo.warnings,
        result.model,
        result.latency_ms,
    )
    return memo


def _warnings_of(session: Session, memo: CareMemo) -> list[str]:
    """いまのメモの中身から、機械の目の印を付け直す。"""
    return check_memo(
        original_text=memo.original_text,
        source_lang=memo.source_lang,
        rewritten_text=memo.rewritten_text,
        back_translation=memo.back_translation,
        # 同じ施設の、ほかの入居者の名前（機械の目の other_name に使う。R-03）
        other_resident_names=other_resident_names(session, memo.resident_id),
    )


def update_memo(
    session: Session,
    user: CurrentUser,
    memo_id: int,
    *,
    original_text: str | None = None,
    rewritten_text: str | None = None,
) -> CareMemo:
    """原文か整えた日本語を直す（FR-008）。直せる状態（draft・returned）のときだけ。

    - 原文を直すと、整えた日本語と訳し戻しは消える（その原文から作ったものではなくなる）。
      直した整えた日本語を一緒に送ったときは、それを使う
    - 整えた日本語を直すと、訳し戻しは消える（直した文で訳し戻し直す）
    - まだ整えていないメモの整えた日本語は直せない（409。AI が整えた文を元にするため。FR-004）
    印は、直した内容で付け直す。メモの行を押さえてから直すので、同時の確かめる・整えるとぶつからない。
    """
    memo = get_own_memo(session, user, memo_id, for_update=True)
    if memo.status not in EDITABLE_STATUSES:
        raise AppError(ErrorCode.INVALID_STATE)
    if rewritten_text is not None and memo.rewritten_text is None:
        raise AppError(ErrorCode.INVALID_STATE)
    if original_text is not None and original_text != memo.original_text:
        memo.original_text = original_text
        memo.back_translation = None
        if rewritten_text is None:
            memo.rewritten_text = None
    if rewritten_text is not None:
        if rewritten_text != memo.rewritten_text:
            memo.back_translation = None
        memo.rewritten_text = rewritten_text
    memo.warnings = _warnings_of(session, memo)
    session.flush()
    return memo


def _move_own(
    session: Session,
    user: CurrentUser,
    memo_id: int,
    *,
    from_statuses: tuple[str, ...],
    values: dict,
    conditions: tuple = (),
) -> CareMemo:
    """本人のメモを、条件つきの 1 回の更新で進める。進められなければ 409（R-05）。"""
    memo = get_own_memo(session, user, memo_id)
    result = session.execute(
        update(CareMemo)
        .where(
            CareMemo.id == memo_id,
            CareMemo.author_staff_id == user.staff_id,
            CareMemo.status.in_(from_statuses),
            *conditions,
        )
        .values(**values),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount == 0:
        raise AppError(ErrorCode.INVALID_STATE)
    session.refresh(memo)
    return memo


def confirm(session: Session, user: CurrentUser, memo_id: int) -> CareMemo:
    """「確かめました」（下書き・戻し → 承認待ち）。確かめた日時を残す（FR-009・FR-015）。

    訳し戻しを見たあとの操作なので、整えた日本語がないとき、表示言語が日本語でないのに
    訳し戻しがないときは押せない（409。R-05）。
    """
    conditions = [CareMemo.rewritten_text.is_not(None)]
    if user.language != "ja":
        conditions.append(CareMemo.back_translation.is_not(None))
    return _move_own(
        session,
        user,
        memo_id,
        from_statuses=EDITABLE_STATUSES,
        values={"status": "pending", "confirmed_at": clock.now()},
        conditions=tuple(conditions),
    )


def withdraw(session: Session, user: CurrentUser, memo_id: int) -> CareMemo:
    """取り下げる（下書き・承認待ち・戻し → 取り下げ）。家族に出ていないものだけ（FR-010）。"""
    return _move_own(
        session,
        user,
        memo_id,
        from_statuses=("draft", "pending", "returned"),
        values={"status": "withdrawn", "withdrawn_at": clock.now()},
    )
