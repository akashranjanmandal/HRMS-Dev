"""Email sender.

``settings.SMTP_HOST`` empty (the default) is dev/test mode: every
"sent" email is recorded in ``OUTBOX``, an in-memory list, instead of
being sent — so local development and the test suite read back an
email's contents (the OTP code, a temporary password) without a real
mail server, and never touch the network. ``OUTBOX`` is per-process, not
per-request, and is never grown once a real SMTP host is configured —
it exists for dev/test only, not as a production audit trail (that is
what the audit log is for).

A send failure (bad credentials, host unreachable) raises rather than
being swallowed: a caller that thinks an OTP was delivered when it
wasn't is a worse failure mode than a 500.
"""
import smtplib
from email.message import EmailMessage

from app.core.config import settings

OUTBOX: list[dict] = []


def _send(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        return  # dev/test mode — caller already recorded the message in OUTBOX
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_otp_email(to: str, otp: str) -> None:
    if not settings.SMTP_HOST:
        OUTBOX.append({"to": to, "kind": "otp", "otp": otp})
        return
    _send(
        to,
        subject="Your Aaranyak HRMS sign-in code",
        body=f"Your one-time sign-in code is {otp}. It expires in 10 minutes.\n\n"
        "If you did not try to sign in, you can ignore this email.",
    )


def send_temporary_password_email(to: str, temporary_password: str) -> None:
    if not settings.SMTP_HOST:
        OUTBOX.append({"to": to, "kind": "temp_password", "temporary_password": temporary_password})
        return
    _send(
        to,
        subject="Your Aaranyak HRMS temporary password",
        body=f"Your temporary password is {temporary_password}. "
        "You will be asked to set a new one the first time you sign in.",
    )
