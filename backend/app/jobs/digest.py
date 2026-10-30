"""20 時のまとめ（spec 001 の 001-T065・FR-023。research.md R-13）。

run_jobs()（app/jobs/run.py）が 1 分ごとに呼ばれ、日本時間で 20:00 を過ぎていたら、
通知設定の頻度が「毎日」の家族（日曜は「毎週」の家族も）に、お知らせとメールの送る予定を作る。
前日 20 時の面会の知らせ（visit_reminder.py）と同じ形で、時刻を見るのは作る側だけなので、
開発（worker）と本番（外から 1 分ごとに呼ぶ）で動きが同じ。

- まとめの締めは、呼ばれた時刻ではなく、その日の 20:00。20:00 より後に記録されたものは、
  次のまとめに入る。24 時を過ぎたら、その日の分は作らない（その日のうちだけ取り戻す）
- 入れるのは、前回のまとめの締めより後に記録され（recorded_at）、開示されていて、家族が選んだ
  項目の記録。1 件もなければ、お知らせもメールも作らず、digest_runs にも残さない（仕様どおり、
  作ったまとめだけを残す。「前回のまとめ」は、作った最後のまとめ）。20 時〜24 時の毎分、記録の
  ない家族は探し直すが、家族の数が少ないうちは負担が小さい
- digest_runs（家族 × 種類 × 締め）が一意なので、20 時台に何度呼ばれても、手で動かすコマンドと
  重なっても、同じまとめは 1 回だけ。記録があれば digest_runs に書いて場所を取り、取れなければ
  何もしない
- 1 人ずつ savepoint で包む。1 人が想定外の失敗をしても、その家族の分だけ取り消し、ログ（家族の
  id・種類・エラーの種類だけ）に残して、同じ回のほかの家族のまとめは残す
- 直した記録（値の変更）は、新しい記録に数えない（recorded_at は、最初に記録した日時）
- お知らせ・メールに、記録の中身は入れない（SC-010）

手で動かすとき：
  docker compose exec worker python -m app.jobs.digest --at "2026-11-02T20:00:00+09:00"
"""

import argparse
import logging
from datetime import datetime, time, timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import JST, now_jst
from app.models.core import FamilyAccount
from app.models.notifications import (
    DEFAULT_FREQUENCY,
    DEFAULT_NOTIFY_ITEMS,
    DigestRun,
    NotificationSetting,
)
from app.services.disclosure import get_disclosed_records
from app.services.notifications import create_digest_notice

logger = logging.getLogger(__name__)

# 日本時間で、この時刻を過ぎたら作る（まとめの締めも、この時刻）
DIGEST_HOUR = 20
# 前回のまとめがないときの、期間の長さ
FIRST_PERIOD = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}
# 記録の日付が、前回の締めより前でも、あとから記録されたものを拾うために、日付の範囲を広げる日数
BACKDATE_DAYS = 7
SUNDAY = 6


def create_digests(session: Session, at: datetime | None = None) -> int:
    """20 時のまとめのお知らせを作る。作った件数を返す。commit しない。

    at はテストと手で動かすとき用（タイムゾーン付きの日時）。
    """
    moment = now_jst(at)
    if moment.hour < DIGEST_HOUR:
        return 0
    period_end = datetime.combine(moment.date(), time(DIGEST_HOUR), tzinfo=JST)
    kinds = ("daily", "weekly") if moment.weekday() == SUNDAY else ("daily",)
    return sum(_create_for_kind(session, kind, period_end) for kind in kinds)


def _create_for_kind(session: Session, kind: str, period_end: datetime) -> int:
    # 頻度がこの種類の家族（設定の行がなければ、初めの設定の「毎日」）のうち、
    # この締めのまとめを、まだ確かめていない家族だけ（毎分、同じ家族を探し直さない）
    frequency = func.coalesce(NotificationSetting.frequency, DEFAULT_FREQUENCY)
    families = session.execute(
        select(FamilyAccount.id, FamilyAccount.resident_id, NotificationSetting.notify_items)
        .outerjoin(NotificationSetting, NotificationSetting.family_account_id == FamilyAccount.id)
        .where(
            frequency == kind,
            ~exists().where(
                DigestRun.family_account_id == FamilyAccount.id,
                DigestRun.kind == kind,
                DigestRun.period_end == period_end,
            ),
        )
        .order_by(FamilyAccount.id)
    ).all()
    created = 0
    for family_account_id, resident_id, notify_items in families:
        items = list(DEFAULT_NOTIFY_ITEMS) if notify_items is None else notify_items
        try:
            with session.begin_nested():
                if _create_one(session, family_account_id, resident_id, items, kind, period_end):
                    created += 1
        except IntegrityError:
            # ほかの呼び出しが先に作った（digest_runs の一意の決まり）。作ってあるので、何もしない
            continue
        except Exception as error:
            # 想定外の失敗。この家族の分（savepoint）だけ取り消し、ログに残して、次の家族へ進む。
            # ログには、家族の id・種類・エラーの種類だけを出す（エラーの文面には、メールアドレス
            # などの値が入ることがあるので出さない）。次の呼び出しで、もう一度試す
            logger.error(
                "20 時のまとめを作れませんでした family_account_id=%s kind=%s error=%s",
                family_account_id,
                kind,
                type(error).__name__,
            )
            continue
    return created


def _create_one(
    session: Session,
    family_account_id: int,
    resident_id: int,
    items: list[str],
    kind: str,
    period_end: datetime,
) -> bool:
    previous_end = session.scalar(
        select(func.max(DigestRun.period_end)).where(
            DigestRun.family_account_id == family_account_id,
            DigestRun.kind == kind,
            DigestRun.period_end < period_end,
        )
    )
    period_start = previous_end or period_end - FIRST_PERIOD[kind]
    records = get_disclosed_records(
        session,
        resident_id,
        period_start.astimezone(JST).date() - timedelta(days=BACKDATE_DAYS),
        period_end.astimezone(JST).date(),
        items=items,
    )
    if not any(period_start < record.recorded_at <= period_end for record in records):
        return False
    # 記録があるときだけ、場所を取る（作ったまとめだけを残す）。同じまとめがすでにあれば、
    # ここで IntegrityError になり、何も作らない
    session.add(DigestRun(family_account_id=family_account_id, kind=kind, period_end=period_end))
    session.flush()
    create_digest_notice(session, family_account_id, kind, period_start, period_end)
    return True


def main() -> None:
    from app.jobs.run import run_jobs
    from app.logging import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description="20 時のまとめを、時刻を指定して動かす")
    parser.add_argument(
        "--at",
        required=True,
        help='日本時間などの時刻（タイムゾーン付き）。例："2026-11-02T20:00:00+09:00"',
    )
    arguments = parser.parse_args()
    at = datetime.fromisoformat(arguments.at)
    if at.tzinfo is None:
        parser.error("--at には、+09:00 のようなタイムゾーンを付けてください")
    run_jobs(at)


if __name__ == "__main__":
    main()
