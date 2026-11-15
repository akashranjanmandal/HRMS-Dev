"""Payroll calculation logic — pure helpers, no DB."""
import pytest

from app.services.payroll import _days_in_month

pytestmark = pytest.mark.unit


def test_days_in_month_handles_leap_february():
    assert _days_in_month(2028, 2) == 29


def test_days_in_month_normal_february():
    assert _days_in_month(2026, 2) == 28


def test_days_in_month_thirty_one():
    assert _days_in_month(2026, 1) == 31
