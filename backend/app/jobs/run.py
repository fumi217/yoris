"""決まった時刻の処理を、1 つの関数にまとめる（spec 001 の 001-T057。research.md R-09）。

本番は、外部のスケジューラー（cron-job.org）が 1 分ごとに POST /api/internal/jobs/run を呼ぶ。
開発は、worker（app/jobs/worker.py）が 1 分ごとに、同じ run_jobs() を呼ぶ。
呼ばれたときに、その時点でやることを全部やる（常に動き続けるものは要らない）。

今は、メールの送信・送り直しだけ。20 時のまとめ（001-T065）と前日の面会の知らせ（spec 003）は、
あとでここに足す。
"""

from sqlalchemy.orm import Session

from app.db import get_engine
from app.services.mail import deliver_pending


def run_jobs() -> None:
    # API のセッションは使えない（応答のあとに動く処理なので）。自分で開く
    with Session(get_engine()) as session:
        deliver_pending(session)
