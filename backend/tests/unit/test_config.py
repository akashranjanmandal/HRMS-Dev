"""Settings safety: the dev-only fixed OTP must never be usable alongside
a real mail server, and must default off.
"""
import pytest

from app.core.config import Settings

pytestmark = pytest.mark.unit


def test_dev_fixed_otp_defaults_to_disabled():
    assert Settings(_env_file=None).DEV_FIXED_OTP == ""


def test_dev_fixed_otp_with_real_smtp_host_refuses_to_start():
    with pytest.raises(ValueError, match="DEV_FIXED_OTP"):
        Settings(_env_file=None, DEV_FIXED_OTP="000000", SMTP_HOST="smtp.example.com")


def test_dev_fixed_otp_alone_is_allowed():
    s = Settings(_env_file=None, DEV_FIXED_OTP="000000")
    assert s.DEV_FIXED_OTP == "000000"
