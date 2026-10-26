"""リクエストのサンプル（spec 001 の 001-T058）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。
入居者とテーマを入れたあとに呼ぶこと。値は架空で、毎回同じになるように入居者・テーマの順番から決める（デモのたびに変わらないように）。
「返事あり」（answered）は、返事（replies）と一緒に足す（返事の中身がない answered を入れると、
連絡帳の表示とずれるため）。返事をした職員（staff_id）を渡したときだけ足す。
返事は、リクエストを送った日の連絡帳に入り、まだ読んでいない（家族が今日の連絡帳を開くと、
日付に関わらず一番上に出る。FR-015）。家族のお知らせ（アプリ内）も未読で足す。
メール（email_outbox）は足さない（開発で、入居者の数だけメールが出ないように）。
同じ入居者に、すでにリクエストがあれば足さない（何度流しても同じになるように）。
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import JST, now, today_jst
from app.models.core import FamilyAccount
from app.models.disclosure import ReplyTemplate
from app.models.notifications import Notification
from app.models.replies import Reply
from app.models.requests import Request

# 返事の書き足し（架空）。1 人おきに付ける
SAMPLE_NOTE = "今日は、おやつを楽しそうに食べていました"


def add_sample_requests(
    session: Session,
    *,
    resident_ids: list[int],
    theme_ids: list[int],
    days_ago: int = 1,
    staff_id: int | None = None,
) -> int:
    """返事待ち 2 件と取り消し 1 件を、入居者ごとに足し、足した件数を返す。commit は呼んだ側が行う。

    3 日たった返事待ちも見せられるよう、返事待ちの 1 件は days_ago + 2 日前に送ったことにする。
    staff_id（返事をした職員）を渡したときは、返事あり 1 件と、その返事も足す
    （そのテーマに定型文があり、テーマが 4 つ以上あるときだけ）。
    """
    if len(theme_ids) < 3:
        return 0
    templates = _templates_by_theme(session, theme_ids) if staff_id is not None else {}
    count = 0
    for n, resident_id in enumerate(resident_ids):
        if session.scalars(select(Request.id).where(Request.resident_id == resident_id)).first():
            continue
        themes = [theme_ids[(n + k) % len(theme_ids)] for k in range(3)]
        sent_at = now()
        rows = [
            (themes[0], "waiting", sent_at - timedelta(days=days_ago), None),
            (themes[1], "waiting", sent_at - timedelta(days=days_ago + 2), None),
            (themes[2], "cancelled", sent_at - timedelta(days=days_ago + 1), sent_at),
        ]
        for theme_id, status, created_at, cancelled_at in rows:
            session.add(
                Request(
                    resident_id=resident_id,
                    theme_id=theme_id,
                    status=status,
                    created_at=created_at,
                    cancelled_at=cancelled_at,
                )
            )
            count += 1
        answered_theme = theme_ids[(n + 3) % len(theme_ids)]
        if staff_id is not None and len(theme_ids) >= 4 and templates.get(answered_theme):
            _add_answered(
                session,
                resident_id=resident_id,
                theme_id=answered_theme,
                template_ids=templates[answered_theme][:2],
                staff_id=staff_id,
                sent_at=sent_at - timedelta(days=days_ago + 1),
                note=SAMPLE_NOTE if n % 2 == 0 else None,
            )
            count += 1
    session.flush()
    return count


def _templates_by_theme(session: Session, theme_ids: list[int]) -> dict[int, list[int]]:
    """テーマごとの定型文の id（並べ順）。"""
    rows = session.execute(
        select(ReplyTemplate.theme_id, ReplyTemplate.id)
        .where(ReplyTemplate.theme_id.in_(theme_ids))
        .order_by(ReplyTemplate.theme_id, ReplyTemplate.sort_order, ReplyTemplate.id)
    )
    result: dict[int, list[int]] = {}
    for theme_id, template_id in rows:
        result.setdefault(theme_id, []).append(template_id)
    return result


def _add_answered(
    session: Session,
    *,
    resident_id: int,
    theme_id: int,
    template_ids: list[int],
    staff_id: int,
    sent_at: datetime,
    note: str | None,
) -> None:
    """返事あり 1 件。返事は送った 3 時間後、その日の連絡帳に入り、まだ読んでいない。

    3 時間後が日本時間の翌日になるとき（21 時以降に流したとき）は、送った日の終わり（23:59）にする。
    返事の日付が、流す時刻によってずれないように（返事の日付は、返事をした日）。
    """
    request = Request(
        resident_id=resident_id, theme_id=theme_id, status="answered", created_at=sent_at
    )
    session.add(request)
    session.flush()
    end_of_day = datetime.combine(today_jst(sent_at), time(23, 59), tzinfo=JST)
    replied_at = min(sent_at + timedelta(hours=3), end_of_day)
    reply = Reply(
        request_id=request.id,
        template_ids=template_ids,
        note=note,
        replied_by=staff_id,
        replied_at=replied_at,
        contact_book_date=today_jst(replied_at),
    )
    session.add(reply)
    session.flush()
    family_account_id = session.scalar(
        select(FamilyAccount.id).where(FamilyAccount.resident_id == resident_id)
    )
    if family_account_id is not None:
        session.add(
            Notification(
                family_account_id=family_account_id,
                kind="reply",
                reply_id=reply.id,
                created_at=replied_at,
            )
        )
