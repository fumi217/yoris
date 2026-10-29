"""様子のメモの承認（spec 007 の 007-T022・research.md R-05）。

- 承認する・戻す・公開を取り下げるのは、リーダー・施設長だけ。同じ施設のメモだけを扱う
- 書いた職員本人は、承認も戻すもできない（FR-011a。リーダーでも）。公開の取り下げは本人でもよい
- どの操作も、条件つきの 1 回の更新で状態を進める。ほぼ同時に押されても、先の 1 つだけが通り、
  あとの人には 409（`invalid_state`）を返す
- 一度も「確かめました」を押していない下書きは、リーダーにも見せない（FR-009）。
  ほかの施設のものと同じく、あることも分からないよう「ない」として扱う（NOT_FOUND）

サービスの関数は commit しない（API の最後で 1 回 commit する。app/db.py）。
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, aliased

from app import clock
from app.auth.deps import CurrentUser
from app.errors import AppError, ErrorCode
from app.models.core import Resident, Staff
from app.models.memos import CareMemo

# 承認する・戻す・公開を取り下げられる役割（FR-011）
APPROVER_ROLES = ("leader", "director")
# 確かめてからこれだけ待っているものは目立たせる（FR-015「1 日以上待っています」）
OVERDUE_AFTER = timedelta(hours=24)

# 一覧で選べる状態：承認待ち、公開を取り下げる対象を探すための承認済み
LIST_STATUSES = ("pending", "approved")


@dataclass(frozen=True)
class ApprovalRow:
    memo: CareMemo
    resident_name: str
    author_name: str


def waiting_minutes(memo: CareMemo) -> int | None:
    """確かめてからの経過時間（分）。承認待ちのときだけ（FR-015）。"""
    if memo.status != "pending" or memo.confirmed_at is None:
        return None
    return max(0, int((clock.now() - memo.confirmed_at).total_seconds() // 60))


def is_overdue(memo: CareMemo) -> bool:
    waited = waiting_minutes(memo)
    return waited is not None and timedelta(minutes=waited) >= OVERDUE_AFTER


def _facility_id(session: Session, user: CurrentUser) -> int:
    return session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()


def _rows_query(facility_id: int):
    """同じ施設の、一度でも「確かめました」を押されたメモ（入居者の呼び名・書いた職員つき）。"""
    author = aliased(Staff)
    return (
        select(CareMemo, Resident.display_name, author.display_name)
        .join(Resident, Resident.id == CareMemo.resident_id)
        .join(author, author.id == CareMemo.author_staff_id)
        .where(Resident.facility_id == facility_id, CareMemo.confirmed_at.is_not(None))
    )


def list_approvals(session: Session, user: CurrentUser, status: str) -> list[ApprovalRow]:
    """承認待ち（確かめてから長く待っている順）か、承認済み（新しく承認した順）の一覧。"""
    assert status in LIST_STATUSES
    query = _rows_query(_facility_id(session, user)).where(CareMemo.status == status)
    if status == "pending":
        query = query.order_by(CareMemo.confirmed_at, CareMemo.id)
    else:
        query = query.order_by(CareMemo.approved_at.desc(), CareMemo.id.desc())
    return [
        ApprovalRow(memo, resident, author) for memo, resident, author in session.execute(query)
    ]


def count_pending_memos(session: Session, user: CurrentUser) -> int | None:
    """承認待ちの件数（施設全体。本人が書いたものも数える）。承認できない役割は None（FR-015）。"""
    if user.role not in APPROVER_ROLES:
        return None
    return session.scalar(
        select(func.count())
        .select_from(CareMemo)
        .join(Resident, Resident.id == CareMemo.resident_id)
        .where(Resident.facility_id == _facility_id(session, user), CareMemo.status == "pending")
    )


def get_approval(session: Session, user: CurrentUser, memo_id: int) -> ApprovalRow:
    """メモ 1 つ。同じ施設で、確かめられたことがあるものだけ。ないときは NOT_FOUND。"""
    query = _rows_query(_facility_id(session, user)).where(CareMemo.id == memo_id)
    row = session.execute(query).one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    memo, resident, author = row
    return ApprovalRow(memo, resident, author)


def _move(
    session: Session,
    user: CurrentUser,
    memo_id: int,
    *,
    from_status: str,
    values: dict,
    author_may: bool,
) -> ApprovalRow:
    """from_status のメモを、条件つきの 1 回の更新で進める。進められなければ 409。"""
    row = get_approval(session, user, memo_id)
    own = row.memo.author_staff_id == user.staff_id
    if own and not author_may:
        raise AppError(ErrorCode.SELF_APPROVAL)

    statement = update(CareMemo).where(CareMemo.id == memo_id, CareMemo.status == from_status)
    if not author_may:
        statement = statement.where(CareMemo.author_staff_id != user.staff_id)
    result = session.execute(
        statement.values(**values), execution_options={"synchronize_session": False}
    )
    if result.rowcount == 0:
        # ほかの人が先に承認した・戻した、本人が取り下げた、など
        raise AppError(ErrorCode.INVALID_STATE)

    session.refresh(row.memo)
    return row


def approve(session: Session, user: CurrentUser, memo_id: int) -> ApprovalRow:
    """承認する（承認待ち → 承認済み）。承認した職員・日時を残す（FR-014）。"""
    return _move(
        session,
        user,
        memo_id,
        from_status="pending",
        values={"status": "approved", "approved_by": user.staff_id, "approved_at": clock.now()},
        author_may=False,
    )


def return_memo(session: Session, user: CurrentUser, memo_id: int, reason: str) -> ApprovalRow:
    """戻す（承認待ち → 戻し）。戻した職員・日時・理由を残す（FR-013・FR-014）。"""
    return _move(
        session,
        user,
        memo_id,
        from_status="pending",
        values={
            "status": "returned",
            "returned_by": user.staff_id,
            "returned_at": clock.now(),
            "return_reason": reason,
        },
        author_may=False,
    )


def unpublish(session: Session, user: CurrentUser, memo_id: int, reason: str) -> ApprovalRow:
    """公開を取り下げる（承認済み → 戻し）。家族から見えなくなる（FR-013a・FR-014）。

    承認の列は消さずに残す。書いた職員本人が取り下げてもよい（承認と違い、公開を止める操作のため）。
    """
    return _move(
        session,
        user,
        memo_id,
        from_status="approved",
        values={
            "status": "returned",
            "unpublished_by": user.staff_id,
            "unpublished_at": clock.now(),
            "unpublish_reason": reason,
        },
        author_may=True,
    )
