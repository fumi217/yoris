"""リクエストのサンプル（spec 001 の 001-T058）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。
入居者とテーマを入れたあとに呼ぶこと。値は架空で、毎回同じになるように入居者・テーマの順番から決める（デモのたびに変わらないように）。
「返事あり」（answered）は、返事の保存（ゆう。001-T052）のテーブルができてから足す
（返事の中身がない answered を入れると、連絡帳の表示とずれるため）。
同じ入居者に、すでにリクエストがあれば足さない（何度流しても同じになるように）。
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.models.requests import Request


def add_sample_requests(
    session: Session, *, resident_ids: list[int], theme_ids: list[int], days_ago: int = 1
) -> int:
    """返事待ち 2 件と取り消し 1 件を、入居者ごとに足し、足した件数を返す。commit は呼んだ側が行う。

    3 日たった返事待ちも見せられるよう、返事待ちの 1 件は days_ago + 2 日前に送ったことにする。
    """
    if len(theme_ids) < 3:
        return 0
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
    session.flush()
    return count
