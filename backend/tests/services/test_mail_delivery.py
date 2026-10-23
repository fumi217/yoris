"""メールを送る処理（001-T057）のテスト。

DB を使うテストは、DATABASE_URL があるときだけ動く（CI に PostgreSQL が入るのは 001-T020）。
手元では `docker compose run --rm backend python -m pytest`（マイグレーションを当てた DB が要る）。
各テストは 1 つのトランザクションの中で動かし、最後に取り消すので、開発の DB のデータは残らない。
本物の SMTP は呼ばず、送る関数を差し替える。
"""

import smtplib
from collections.abc import Iterator
from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.notifications import EmailOutbox
from app.services.mail import MAX_ATTEMPTS, MailError, deliver_pending


@pytest.fixture
def session(monkeypatch) -> Iterator[Session]:
    url = get_settings().database_url
    if not url:
        pytest.skip("DATABASE_URL がない（CI に PostgreSQL が入るまで。001-T020）")
    monkeypatch.setenv("MAIL_FROM", "no-reply@example.com")
    monkeypatch.setenv("APP_BASE_URL", "http://app.test")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        # deliver_pending の commit が、外のトランザクションの中の SAVEPOINT になるように
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield db
        finally:
            db.close()
            transaction.rollback()
    engine.dispose()


def _add(session: Session, n: int = 1, **kwargs) -> list[EmailOutbox]:
    rows = [
        EmailOutbox(
            to_email=f"family{i}@example.com",
            template=kwargs.get("template", "reply"),
            params={"link": "http://app.test"},
        )
        for i in range(n)
    ]
    session.add_all(rows)
    session.flush()
    return rows


class Sender:
    """送る関数の代わり。送った宛先を覚える。fail_for の宛先は失敗させる。"""

    def __init__(self, fail_for: tuple[str, ...] = ()):
        self.sent: list[str] = []
        self.tried: list[str] = []
        self.fail_for = fail_for

    def __call__(self, message: EmailMessage) -> None:
        to = message["To"]
        self.tried.append(to)
        if to in self.fail_for:
            raise OSError("送れない")
        self.sent.append(to)


def test_unsent_rows_are_sent_and_marked(session):
    rows = _add(session, 2)
    sender = Sender()
    assert deliver_pending(session, send=sender) == 2
    assert sender.sent == ["family0@example.com", "family1@example.com"]
    for row in rows:
        session.refresh(row)
        assert row.sent_at is not None
        assert row.attempts == 0


def test_sent_rows_are_not_sent_again(session):
    _add(session)
    sender = Sender()
    deliver_pending(session, send=sender)
    assert deliver_pending(session, send=sender) == 0
    assert len(sender.tried) == 1


def test_failed_row_is_counted_and_kept(session):
    (row,) = _add(session)
    sender = Sender(fail_for=("family0@example.com",))
    assert deliver_pending(session, send=sender) == 0
    session.refresh(row)
    assert row.sent_at is None
    assert row.attempts == 1
    assert row.last_error is not None
    # 送り先のメールアドレスは、エラーの記録に残さない
    assert "family0@example.com" not in row.last_error


def test_refused_recipient_is_not_kept_in_last_error(session):
    # SMTP が宛先を断ったとき、例外の文に宛先が入る。last_error には種類だけを残す
    (row,) = _add(session)

    def refused(message: EmailMessage) -> None:
        raise smtplib.SMTPRecipientsRefused({message["To"]: (550, b"no such user")})

    deliver_pending(session, send=refused)
    session.refresh(row)
    assert row.last_error == "SMTPRecipientsRefused"
    assert "family0@example.com" not in row.last_error


def test_a_failed_row_is_tried_once_per_call(session):
    _add(session)
    sender = Sender(fail_for=("family0@example.com",))
    deliver_pending(session, send=sender)
    assert sender.tried == ["family0@example.com"]


def test_row_is_given_up_after_max_attempts(session):
    (row,) = _add(session)
    sender = Sender(fail_for=("family0@example.com",))
    for _ in range(MAX_ATTEMPTS + 2):
        deliver_pending(session, send=sender)
    session.refresh(row)
    assert row.attempts == MAX_ATTEMPTS
    assert len(sender.tried) == MAX_ATTEMPTS


def test_failed_row_is_sent_when_it_works_later(session):
    (row,) = _add(session)
    deliver_pending(session, send=Sender(fail_for=("family0@example.com",)))
    assert deliver_pending(session, send=Sender()) == 1
    session.refresh(row)
    assert row.sent_at is not None
    assert row.last_error is None


def test_one_failure_does_not_stop_the_others(session):
    _add(session, 3)
    sender = Sender(fail_for=("family1@example.com",))
    assert deliver_pending(session, send=sender) == 2
    assert sender.sent == ["family0@example.com", "family2@example.com"]


def test_only_the_given_ids_are_sent(session):
    rows = _add(session, 3)
    sender = Sender()
    assert deliver_pending(session, ids=[rows[1].id], send=sender) == 1
    assert sender.sent == ["family1@example.com"]


def test_limit_caps_one_call(session):
    _add(session, 5)
    sender = Sender()
    assert deliver_pending(session, limit=2, send=sender) == 2
    assert len(sender.sent) == 2


def test_template_without_text_is_a_failure_not_a_crash(session):
    # 招待のメールの文面は、ようこのタスクで足す。それまでは送れない失敗として数える
    (row,) = _add(session, template="invitation")
    assert deliver_pending(session, send=Sender()) == 0
    session.refresh(row)
    assert row.attempts == 1
    assert row.last_error is not None


def test_send_error_from_the_transport_is_recorded(session):
    (row,) = _add(session)

    def broken(message: EmailMessage) -> None:
        raise MailError("設定が足りない")

    deliver_pending(session, send=broken)
    session.refresh(row)
    assert row.attempts == 1
    assert "設定が足りない" in row.last_error
