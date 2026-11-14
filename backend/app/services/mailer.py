"""Email sender — interface only; checklist 2.4 fills in a real provider
(SMTP, SES, etc.) behind this same function without changing any caller.

For now every "sent" email lands in ``OUTBOX``, an in-memory list, so
tests can read back an email's contents (the OTP code, the reset link)
without a real mail server. ``OUTBOX`` is per-process, not per-request —
fine for tests and for a single-worker deployment; checklist 2.4 should
either keep it for a local dev/test mode or replace it outright.
"""
OUTBOX: list[dict] = []


def send_otp_email(to: str, otp: str) -> None:
    OUTBOX.append({"to": to, "kind": "otp", "otp": otp})


def send_temporary_password_email(to: str, temporary_password: str) -> None:
    OUTBOX.append({"to": to, "kind": "temp_password", "temporary_password": temporary_password})
