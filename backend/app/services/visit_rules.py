"""面会予約の判定（spec 003 の 003-T008。research.md R-02・R-04）。

DB を読まない純粋な関数だけを置く。時刻は日本時間で判断する（app.clock）。
DB を使う処理（予約を作る book_visit・選べるかどうかの get_availability）は
services/visits.py に置く。
"""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from app.clock import JST, now_jst

# 面会の長さ（FR-003）
VISIT_DURATION = timedelta(hours=1, minutes=30)
# 予約できるのは、翌日から 28 日先まで（FR-008）
BOOKING_DAYS_AHEAD = 28
# 予約・家族の取り消しの締め切りは、面会の前日のこの時刻（FR-007）
DEADLINE_TIME = time(17, 0)


class VisitRuleError(Exception):
    """決まりの外。code は spec 003 contracts のエラーのコード。"""

    code = "validation_error"


class VisitOutOfRange(VisitRuleError):
    """予約できる期間（翌日から 4 週間先まで）の外（422）。"""

    code = "visit_out_of_range"


class VisitDeadlinePassed(VisitRuleError):
    """面会の前日 17 時を過ぎている（409）。"""

    code = "visit_deadline_passed"


class VisitInvalidStartTime(VisitRuleError):
    """開始時刻が候補にない（422）。"""

    code = "validation_error"


def visit_range(visit_date: date, start_time: time) -> tuple[datetime, datetime]:
    """面会の時間（開始・終わり）。日本時間で組み立て、タイムゾーン付きで返す（R-02）。"""
    starts_at = datetime.combine(visit_date, start_time, tzinfo=JST)
    return starts_at, starts_at + VISIT_DURATION


def overlaps(visit_date: date, start_a: time, start_b: time) -> bool:
    """同じ日の 2 つの面会の時間が重なるか（終わりの時刻ちょうどに始まるのは重ならない）。"""
    a_start, a_end = visit_range(visit_date, start_a)
    b_start, b_end = visit_range(visit_date, start_b)
    return a_start < b_end and b_start < a_end


def deadline_of(visit_date: date) -> datetime:
    """その面会の締め切り（前日の 17 時、日本時間）。"""
    return datetime.combine(visit_date - timedelta(days=1), DEADLINE_TIME, tzinfo=JST)


def is_before_deadline(visit_date: date, at: datetime | None = None) -> bool:
    """締め切りより前か。at はテスト用（タイムゾーン付きの日時）。"""
    return now_jst(at) < deadline_of(visit_date)


def check_bookable_date(visit_date: date, at: datetime | None = None) -> None:
    """予約できる日か。できなければ VisitOutOfRange か VisitDeadlinePassed を出す。

    予約できる日：明日 ≦ 日付 ≦ 今日＋28 日。明日の予約は、今日の 17:00 より前だけ（R-04）。
    """
    today = now_jst(at).date()
    if not (today + timedelta(days=1) <= visit_date <= today + timedelta(days=BOOKING_DAYS_AHEAD)):
        raise VisitOutOfRange(f"visit_date: {visit_date}")
    if not is_before_deadline(visit_date, at):
        raise VisitDeadlinePassed(f"visit_date: {visit_date}")


def check_family_cancel(visit_date: date, at: datetime | None = None) -> None:
    """家族が取り消せるか（前日 17 時まで）。職員の取り消しには締め切りがない（FR-012）。"""
    if not is_before_deadline(visit_date, at):
        raise VisitDeadlinePassed(f"visit_date: {visit_date}")


def check_start_time(start_time: time, candidates: Iterable[time]) -> None:
    """開始時刻が、今の候補（active なもの）にあるか。"""
    if start_time not in set(candidates):
        raise VisitInvalidStartTime(f"start_time: {start_time}")
