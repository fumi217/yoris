"""開発用の worker。1 分ごとに run_jobs() を呼ぶ（spec 001 の 001-T057。research.md R-09）。

本番は、外部のスケジューラー（cron-job.org）が API を呼ぶので、worker は動かさない。
開発と本番で、run_jobs() の中身は同じ。
"""

import logging
import signal
import threading
import time

from app.jobs.run import run_jobs
from app.logging import configure_logging

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60


def main() -> None:
    configure_logging()
    stop = threading.Event()
    # docker compose stop / restart で、きれいに止まれるように
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger.info("worker を始めます（%s 秒ごとに run_jobs()）", INTERVAL_SECONDS)
    while not stop.is_set():
        started = time.monotonic()
        try:
            run_jobs()
        except Exception:
            # 1 回失敗しても、worker は止めずに、次の回でやり直す
            logger.exception("run_jobs() に失敗しました")
        stop.wait(max(0.0, INTERVAL_SECONDS - (time.monotonic() - started)))
    logger.info("worker を止めます")


if __name__ == "__main__":
    main()
