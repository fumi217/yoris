"""前日 20 時の面会の知らせ（spec 003 の 003-T034。research.md R-07）。

run_jobs()（app/jobs/run.py）が 1 分ごとに呼ばれ、日本時間で 20:00 を過ぎていたら、
翌日の「予約済み」ごとに、お知らせとメールの送る予定（visit_reminder）を作る。
spec 001 R-13 のまとめと同じ形で、時刻を見るのは作る側だけなので、開発（worker）と
本番（外から 1 分ごとに呼ぶ）で動きが同じ。

- 20:00〜24:00 のあいだだけ作る（24 時を過ぎると「翌日」が進むので、元の翌日の分は作らない）
- 20 時台に何度呼ばれても、同じ予約に 2 回は作らない（すでに知らせがある予約は探さない。
  同時に 2 つ動いても、DB の一意の決まりで片方は IntegrityError になる）
- 1 件ずつ savepoint で包む。1 件が失敗しても、同じ回のほかの予約の知らせは残す
  （ゆうさんの #224 レビューの提案）

手で動かすとき：
  docker compose exec worker python -m app.jobs.visit_reminder --at "2026-10-27T20:00:00+09:00"
"""

import argparse
import logging
from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from app.clock import now_jst
from app.models.notifications import Notification
from app.models.visits import VisitReservation
from app.services.notifications import create_visit_notice

logger = logging.getLogger(__name__)

# 日本時間で、この時刻を過ぎたら作る
REMINDER_HOUR = 20


def create_visit_reminders(session: Session, at: datetime | None = None) -> int:
    """翌日の「予約済み」ごとに、前日の知らせを作る。作った件数を返す。commit しない。

    at はテストと手で動かすとき用（タイムゾーン付きの日時）。
    """
    moment = now_jst(at)
    if moment.hour < REMINDER_HOUR:
        return 0
    tomorrow = moment.date() + timedelta(days=1)
    reservation_ids = session.scalars(
        select(VisitReservation.id)
        .where(
            VisitReservation.visit_date == tomorrow,
            VisitReservation.status == "booked",
            ~exists().where(
                Notification.visit_reservation_id == VisitReservation.id,
                Notification.kind == "visit_reminder",
            ),
        )
        .order_by(VisitReservation.id)
    ).all()
    created = 0
    for reservation_id in reservation_ids:
        try:
            with session.begin_nested():
                create_visit_notice(session, reservation_id, "visit_reminder")
        except IntegrityError:
            # ほかの呼び出しが先に作った。作ってあるので、何もしない
            continue
        except NoResultFound:
            # 入居者に家族アカウントがない（送り先がない）。ほかの予約は続ける
            logger.warning("前日の知らせの送り先がありません reservation_id=%s", reservation_id)
            continue
        created += 1
    return created


def main() -> None:
    from app.jobs.run import run_jobs
    from app.logging import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description="前日 20 時の面会の知らせを、時刻を指定して動かす")
    parser.add_argument(
        "--at",
        required=True,
        help='日本時間などの時刻（タイムゾーン付き）。例："2026-10-27T20:00:00+09:00"',
    )
    arguments = parser.parse_args()
    at = datetime.fromisoformat(arguments.at)
    if at.tzinfo is None:
        parser.error("--at には、+09:00 のようなタイムゾーンを付けてください")
    run_jobs(at)


if __name__ == "__main__":
    main()
