"""決まった時刻の処理を、1 つの関数にまとめる（spec 001 の 001-T057。research.md R-09）。

本番は、外部のスケジューラー（cron-job.org）が 1 分ごとに POST /api/internal/jobs/run を呼ぶ。
開発は、worker（app/jobs/worker.py）が 1 分ごとに、同じ run_jobs() を呼ぶ。
呼ばれたときに、その時点でやることを全部やる（常に動き続けるものは要らない）。

前日 20 時の面会の知らせ（spec 003 の 003-T034）、20 時のまとめ（spec 001 の 001-T065）、
メールの送信・送り直し。
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import get_engine
from app.jobs.digest import create_digests
from app.jobs.visit_reminder import create_visit_reminders
from app.services.mail import deliver_pending

logger = logging.getLogger(__name__)


def run_jobs(at: datetime | None = None) -> None:
    """at は、手で動かすとき用の時刻（タイムゾーン付き）。省くと今。"""
    # API のセッションは使えない（応答のあとに動く処理なので）。自分で開く
    with Session(get_engine()) as session:
        # 知らせを先に作ってから送る（作った回に、そのまま送れる）。
        # 作る処理が失敗しても、メールの送信は止めない
        try:
            create_visit_reminders(session, at)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("前日の面会の知らせを作れませんでした")
        try:
            create_digests(session, at)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("20 時のまとめを作れませんでした")
        deliver_pending(session)
