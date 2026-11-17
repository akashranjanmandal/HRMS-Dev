"""In-process rate limiter used to throttle login/OTP attempts."""
import pytest
from fastapi import HTTPException

from app.core.rate_limit import check_and_record, reset

pytestmark = pytest.mark.unit


def test_allows_up_to_the_limit():
    key = "test:allow"
    for _ in range(3):
        check_and_record(key, max_attempts=3, window_seconds=60)


def test_blocks_once_over_the_limit():
    key = "test:block"
    for _ in range(3):
        check_and_record(key, max_attempts=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        check_and_record(key, max_attempts=3, window_seconds=60)
    assert exc.value.status_code == 429


def test_reset_clears_the_window():
    key = "test:reset"
    for _ in range(3):
        check_and_record(key, max_attempts=3, window_seconds=60)
    reset(key)
    check_and_record(key, max_attempts=3, window_seconds=60)  # does not raise


def test_old_attempts_outside_the_window_do_not_count():
    key = "test:expiry"
    check_and_record(key, max_attempts=1, window_seconds=0.05)
    import time

    time.sleep(0.1)
    check_and_record(key, max_attempts=1, window_seconds=0.05)  # does not raise
