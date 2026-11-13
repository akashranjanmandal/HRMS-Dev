import pytest

from app.core import audit
from app.core.security import (
    create_access_token,
    decode_token,
    generate_temporary_password,
    hash_password,
    password_strength_error,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_password_hash_roundtrip():
    h = hash_password("Secret123")
    assert h != "Secret123"
    assert verify_password("Secret123", h)
    assert not verify_password("secret123", h)


def test_token_roundtrip_and_tamper():
    token = create_access_token({"sub": "7"})
    assert decode_token(token)["sub"] == "7"
    assert decode_token(token + "x") is None


@pytest.mark.parametrize("pw, ok", [("Short1", False), ("allletters", False), ("12345678", False), ("Good1234", True)])
def test_password_strength(pw, ok):
    assert (password_strength_error(pw) is None) is ok


def test_password_min_length_override():
    assert password_strength_error("Good1234", min_length=10) is not None


def test_temporary_password_always_passes_policy():
    assert all(password_strength_error(generate_temporary_password()) is None for _ in range(2000))


def test_audit_diff_only_changed_fields():
    assert audit.diff({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": {"old": 2, "new": 3}}
