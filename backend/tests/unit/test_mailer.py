"""Email sender: in dev/test mode (no SMTP host configured) every message
lands in the in-memory OUTBOX and nothing touches the network; with an
SMTP host configured, it sends for real and never grows OUTBOX."""
import smtplib

import pytest

from app.services import mailer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_outbox():
    mailer.OUTBOX.clear()
    yield
    mailer.OUTBOX.clear()


class _FakeSMTP:
    """Records what would have been sent, instead of opening a socket."""

    sent: list[dict] = []

    def __init__(self, host, port, timeout=10):
        self.host, self.port = host, port
        _FakeSMTP.sent.append({"host": host, "port": port})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        _FakeSMTP.sent[-1]["starttls"] = True

    def login(self, user, password):
        _FakeSMTP.sent[-1]["login"] = user

    def send_message(self, msg):
        _FakeSMTP.sent[-1]["to"] = msg["To"]
        _FakeSMTP.sent[-1]["subject"] = msg["Subject"]
        _FakeSMTP.sent[-1]["body"] = msg.get_content()


def test_dev_mode_with_no_smtp_host_uses_the_outbox(monkeypatch):
    monkeypatch.setattr(mailer.settings, "SMTP_HOST", "")
    mailer.send_otp_email("field@aaranyak.org", "482917")
    assert mailer.OUTBOX == [{"to": "field@aaranyak.org", "kind": "otp", "otp": "482917"}]


def test_configured_smtp_host_sends_for_real_and_skips_the_outbox(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(mailer.settings, "SMTP_HOST", "smtp.aaranyak.org")
    monkeypatch.setattr(mailer.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(mailer.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(mailer.settings, "SMTP_USERNAME", "noreply@aaranyak.org")
    monkeypatch.setattr(mailer.settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(mailer.settings, "SMTP_FROM", "Aaranyak HRMS <noreply@aaranyak.org>")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    mailer.send_otp_email("hr@aaranyak.org", "111222")

    assert mailer.OUTBOX == []  # production path never grows the in-memory outbox
    sent = _FakeSMTP.sent[0]
    assert sent["host"] == "smtp.aaranyak.org" and sent["port"] == 587
    assert sent["starttls"] is True
    assert sent["login"] == "noreply@aaranyak.org"
    assert sent["to"] == "hr@aaranyak.org"
    assert "111222" in sent["body"]


def test_smtp_without_tls_skips_starttls(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(mailer.settings, "SMTP_HOST", "smtp.aaranyak.org")
    monkeypatch.setattr(mailer.settings, "SMTP_USE_TLS", False)
    monkeypatch.setattr(mailer.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mailer.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    mailer.send_otp_email("hr@aaranyak.org", "333444")
    assert "starttls" not in _FakeSMTP.sent[0]
    assert "login" not in _FakeSMTP.sent[0]


def test_send_failure_is_not_swallowed(monkeypatch):
    """A real send failure (bad credentials, network error) must surface,
    not disappear silently — an OTP that was never actually delivered must
    not look like a success to the caller."""

    class _BrokenSMTP(_FakeSMTP):
        def send_message(self, msg):
            raise smtplib.SMTPException("535 authentication failed")

    monkeypatch.setattr(mailer.settings, "SMTP_HOST", "smtp.aaranyak.org")
    monkeypatch.setattr(mailer.settings, "SMTP_USE_TLS", False)
    monkeypatch.setattr(mailer.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mailer.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(smtplib, "SMTP", _BrokenSMTP)

    with pytest.raises(smtplib.SMTPException):
        mailer.send_otp_email("hr@aaranyak.org", "555666")


def test_temporary_password_email_dev_mode(monkeypatch):
    monkeypatch.setattr(mailer.settings, "SMTP_HOST", "")
    mailer.send_temporary_password_email("new.joiner@aaranyak.org", "Xk9#mPq2")
    assert mailer.OUTBOX == [
        {"to": "new.joiner@aaranyak.org", "kind": "temp_password", "temporary_password": "Xk9#mPq2"}
    ]
