"""メールを送る（spec 001 の 001-T057。research.md R-09）。

- email_outbox の未送信の行を取り出して送り、送れたら sent_at を入れる。
  送れなければ回数を数える（5 回まで）
- 取り出すときは FOR UPDATE SKIP LOCKED で行を押さえる。run_jobs() と send_email_now が重なっても、
  手で動かしても、同じメールを 2 回送らない
- 1 件ごとに commit する（送ったあとで失敗しても、送った行を「未送信」に戻さないため）
- 送り方は MAIL_TRANSPORT で切り替える。今は smtp（開発の Mailpit）だけ。
  本番の resend は Day 5 で足す
"""

import logging
import smtplib
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.models.notifications import EmailOutbox
from app.templates.email import UnknownTemplate, render

logger = logging.getLogger(__name__)

# 失敗しても送り直すのは、この回数まで
MAX_ATTEMPTS = 5
# 1 回の呼び出しで送る、多くてもこの件数まで
BATCH_SIZE = 30
# 外部のスケジューラー（cron-job.org）の待ち時間が 30 秒なので、それより前に切り上げる
TIME_LIMIT_SECONDS = 25
# SMTP の応答を待つ長さ（1 件でこれ以上かかるなら、失敗として次の回に回す）
SMTP_TIMEOUT_SECONDS = 10


class MailError(Exception):
    """メールを送れなかった（設定が足りない、送り方が未対応など）。"""


def build_message(row: EmailOutbox) -> EmailMessage:
    settings = get_settings()
    if not settings.mail_from:
        raise MailError("MAIL_FROM が設定されていません")
    subject, body = render(row.template, row.params, settings.app_base_url)
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = row.to_email
    message["Subject"] = subject
    message.set_content(body)
    return message


def send_message(message: EmailMessage) -> None:
    """MAIL_TRANSPORT に合わせて送る。失敗したら例外を出す。"""
    settings = get_settings()
    if settings.mail_transport != "smtp":
        raise MailError(f"MAIL_TRANSPORT={settings.mail_transport} には、まだ対応していません")
    if not settings.smtp_host:
        raise MailError("SMTP_HOST が設定されていません")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        smtp.send_message(message)


def deliver_pending(
    session: Session,
    *,
    ids: list[int] | None = None,
    limit: int = BATCH_SIZE,
    time_limit: float = TIME_LIMIT_SECONDS,
    send: Callable[[EmailMessage], None] = send_message,
) -> int:
    """未送信のメールを送り、送れた件数を返す。1 件ごとに commit する。

    ids を渡すと、その行だけを対象にする。1 回の呼び出しで、同じ行を 2 回は試さない
    （失敗した行は、次の呼び出しで送り直す）。
    """
    started = time.monotonic()
    tried: list[int] = []
    sent = 0
    while len(tried) < limit and time.monotonic() - started < time_limit:
        query = (
            select(EmailOutbox)
            .where(EmailOutbox.sent_at.is_(None), EmailOutbox.attempts < MAX_ATTEMPTS)
            .order_by(EmailOutbox.id)
            .limit(1)
            # ほかが処理中の行は飛ばす（同じメールを 2 回送らない。R-09）
            .with_for_update(skip_locked=True)
        )
        if tried:
            query = query.where(EmailOutbox.id.not_in(tried))
        if ids is not None:
            query = query.where(EmailOutbox.id.in_(ids))
        row = session.scalars(query).one_or_none()
        if row is None:
            break
        tried.append(row.id)
        try:
            send(build_message(row))
        except (OSError, MailError, UnknownTemplate) as error:
            row.attempts += 1
            # 送り先のメールアドレスは、ログにも last_error にも入れない。SMTP が宛先を断ったとき
            # （SMTPRecipientsRefused）は例外の文に宛先が入るので、SMTP などの例外は種類だけ残す。
            # 自分で出した MailError・UnknownTemplate の文には、宛先は入らない
            if isinstance(error, MailError | UnknownTemplate):
                row.last_error = f"{type(error).__name__}: {error}"[:500]
            else:
                row.last_error = type(error).__name__
            logger.warning(
                "メールを送れませんでした outbox_id=%s attempts=%s", row.id, row.attempts
            )
        else:
            row.sent_at = datetime.now(UTC)
            row.last_error = None
            sent += 1
        session.commit()
    return sent


def send_email_now(outbox_id: int) -> None:
    """保存をコミットしたあとに、その行だけをその場で送る（BackgroundTasks から呼ぶ）。

    自分で DB のセッションを開く（API のセッションは、応答のあとには閉じているため）。
    送れなかったときも、すでに送られているときも、例外は出さない。送れなかった行は
    email_outbox に残り、次の run_jobs() が送り直す。
    """
    try:
        with Session(get_engine()) as session:
            deliver_pending(session, ids=[outbox_id], limit=1)
    except Exception:
        # BackgroundTasks の中で例外が出ても、返事の保存は済んでいる。送る予定は残るので、
        # ここでは記録だけして、応答には影響させない
        logger.exception("send_email_now に失敗しました outbox_id=%s", outbox_id)
