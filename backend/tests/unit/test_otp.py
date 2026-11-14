"""One-time code generation and verification — pure logic, no database."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import generate_otp, hash_otp, otp_expiry, verify_otp

pytestmark = pytest.mark.unit


def test_generated_otp_is_six_digits():
    code = generate_otp()
    assert len(code) == 6
    assert code.isdigit()


def test_otp_hash_roundtrip():
    code = "482917"
    h = hash_otp(code)
    assert h != code
    assert verify_otp(code, h)
    assert not verify_otp("000000", h)


def test_otp_expiry_is_in_the_future():
    assert otp_expiry() > datetime.now(timezone.utc)


def test_otp_expiry_is_within_fifteen_minutes():
    assert otp_expiry() <= datetime.now(timezone.utc) + timedelta(minutes=15)
