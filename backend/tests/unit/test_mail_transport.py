"""メールの組み立てと送り方（001-T057）のテスト。DB は使わない。SMTP も本物は呼ばない。"""

import pytest

from app.models.notifications import EmailOutbox
from app.services import mail
from app.services.mail import MailError, build_message, send_message


def _row(**kwargs) -> EmailOutbox:
    values = {"to_email": "family@example.com", "template": "reply", "params": {}}
    values.update(kwargs)
    return EmailOutbox(**values)


@pytest.fixture
def mail_env(monkeypatch):
    monkeypatch.setenv("MAIL_FROM", "no-reply@example.com")
    monkeypatch.setenv("APP_BASE_URL", "http://app.test")
    monkeypatch.setenv("MAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PORT", "1025")


def test_message_has_from_to_subject_and_body(mail_env):
    message = build_message(_row())
    assert message["From"] == "no-reply@example.com"
    assert message["To"] == "family@example.com"
    assert message["Subject"] == "知りたいことへの返事が届きました"
    assert "http://app.test" in message.get_content()


def test_message_needs_mail_from(mail_env, monkeypatch):
    monkeypatch.delenv("MAIL_FROM")
    with pytest.raises(MailError):
        build_message(_row())


def test_smtp_sends_to_the_configured_host(mail_env, monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, message):
            calls.append(message["To"])

    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    send_message(build_message(_row()))
    assert calls == [("mailpit", 1025, mail.SMTP_TIMEOUT_SECONDS), "family@example.com"]


def test_resend_is_not_supported_yet(mail_env, monkeypatch):
    # 本番の resend は Day 5 で足す。それまでは、送れない失敗として扱う
    monkeypatch.setenv("MAIL_TRANSPORT", "resend")
    with pytest.raises(MailError):
        send_message(build_message(_row()))


def test_smtp_needs_a_host(mail_env, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")
    with pytest.raises(MailError):
        send_message(build_message(_row()))


def test_send_email_now_never_raises(monkeypatch):
    # 返事の保存は済んでいるので、送れなくても API の応答には影響させない
    def broken(*args, **kwargs):
        raise RuntimeError("こわれた")

    monkeypatch.setattr(mail, "get_engine", lambda: None)
    monkeypatch.setattr(mail, "deliver_pending", broken)
    mail.send_email_now(1)
