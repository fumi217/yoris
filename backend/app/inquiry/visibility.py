"""職員へのメッセージの見え方と件数（spec 004 の 004-T006・research.md R-12・data-model.md）。

苦情（category = 'complaint'）は、生活相談員・施設長だけが読める。
一覧・件数・詳細・操作のすべてが visible_staff_messages(user) を通り、
ほかの役割では苦情を最初から除く（あとから画面で隠すのではない）。

件数の関数は、ゆうの入居者一覧（004-T030）からも呼ぶ。中では commit しない。
"""

from sqlalchemy import ColumnElement, Select, false, func, select, true
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.models.inquiry import StaffMessage

# 苦情を読める役割（FR-012）
COMPLAINT_ROLES = ("counselor", "director")


def _visible(user: CurrentUser) -> ColumnElement[bool]:
    """その人が読める職員へのメッセージの条件。"""
    if user.kind != "staff":
        # 家族は職員へのメッセージを読まない（家族の画面は自分の会話の発言だけを出す）
        return false()
    if user.role in COMPLAINT_ROLES:
        return true()
    return StaffMessage.category != "complaint"


def visible_staff_messages(user: CurrentUser) -> Select[tuple[StaffMessage]]:
    """その人が読める職員へのメッセージを選ぶ問い合わせ。並び順や条件は、呼ぶ側で足す。"""
    return select(StaffMessage).where(_visible(user))


def count_waiting_staff_messages(
    session: Session, user: CurrentUser, resident_id: int | None = None
) -> int:
    """対応待ちの件数。resident_id を渡すとその入居者の分だけ、渡さないと施設全体を数える。"""
    query = (
        select(func.count())
        .select_from(StaffMessage)
        .where(_visible(user), StaffMessage.status == "waiting")
    )
    if resident_id is not None:
        query = query.where(StaffMessage.resident_id == resident_id)
    return session.scalar(query) or 0


def count_waiting_staff_messages_by_resident(session: Session, user: CurrentUser) -> dict[int, int]:
    """入居者ごとの対応待ちの件数を、1 回の問い合わせで返す（入居者 id → 件数。0 件は入れない）。

    入居者一覧で 1 人ずつ数えると、問い合わせが人数分になるため（PR #42 のゆうのコメント）。
    """
    rows = session.execute(
        select(StaffMessage.resident_id, func.count())
        .where(_visible(user), StaffMessage.status == "waiting")
        .group_by(StaffMessage.resident_id)
    )
    return {resident_id: count for resident_id, count in rows}
