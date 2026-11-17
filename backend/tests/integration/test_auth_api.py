"""Sign-in flow (RFP 3.1, 3.7, 13): password login, email one-time code for
roles that see confidential data, logout, session expiry, and every
sign-in/sign-out audited.
"""
import pytest

from app.core.security import hash_password
from app.models import AuditLog, Role, User

pytestmark = pytest.mark.integration

PASSWORD = "Passw0rd!1"


def _make_user(db, role_code: str, email: str | None = None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(email=email or f"{role_code}@aaranyak.org", hashed_password=hash_password(PASSWORD), role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ------------------------------------------------------------------- login
def test_login_with_correct_password(client, db):
    user = _make_user(db, "field_staff")
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mfa_required"] is False
    assert body["access_token"]


def test_login_with_wrong_password_is_401(client, db):
    user = _make_user(db, "field_staff")
    r = client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    assert r.status_code == 401


def test_login_with_unknown_email_is_401_not_404(client, db):
    # Never reveal whether an email exists.
    r = client.post("/api/auth/login", json={"email": "nobody@aaranyak.org", "password": PASSWORD})
    assert r.status_code == 401


def test_login_for_inactive_user_is_401(client, db):
    user = _make_user(db, "field_staff")
    user.is_active = False
    db.commit()
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 401


def test_successful_login_is_audited(client, db):
    user = _make_user(db, "field_staff")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    entry = db.query(AuditLog).filter_by(action="auth.login").one()
    assert entry.actor_email == user.email


def test_failed_login_is_audited(client, db):
    user = _make_user(db, "field_staff")
    client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    entry = db.query(AuditLog).filter_by(action="auth.login_failed").one()
    assert entry.actor_email == user.email


# -------------------------------------------------------------- MFA gating
@pytest.mark.parametrize("role_code", ["admin", "hr_admin", "finance"])
def test_confidential_roles_require_otp_after_password(client, db, role_code):
    user = _make_user(db, role_code)
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["mfa_required"] is True
    assert "access_token" not in body or body.get("access_token") is None


@pytest.mark.parametrize("role_code", ["field_staff", "project_staff", "coordinator"])
def test_non_confidential_roles_skip_otp(client, db, role_code):
    user = _make_user(db, role_code)
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.json()["mfa_required"] is False
    assert r.json()["access_token"]


def test_otp_verify_completes_login(client, db, monkeypatch):
    from app.services import mailer

    user = _make_user(db, "admin")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    sent = mailer.OUTBOX[-1]
    assert sent["to"] == user.email
    code = sent["otp"]

    r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_otp_verify_with_wrong_code_is_401(client, db):
    user = _make_user(db, "admin")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "000000"})
    assert r.status_code == 401


def test_otp_cannot_be_reused(client, db):
    from app.services import mailer

    user = _make_user(db, "admin")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    code = mailer.OUTBOX[-1]["otp"]
    first = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
    assert first.status_code == 200
    second = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
    assert second.status_code == 401


def test_successful_otp_verification_is_audited(client, db):
    from app.services import mailer

    user = _make_user(db, "admin")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    code = mailer.OUTBOX[-1]["otp"]
    client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
    entry = db.query(AuditLog).filter_by(action="auth.login").one()
    assert entry.actor_email == user.email


# ------------------------------------------------------------------ logout
def test_logout_invalidates_the_token(client, db):
    user = _make_user(db, "field_staff")
    token = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).status_code == 200
    r = client.post("/api/auth/logout", headers=headers)
    assert r.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_logout_is_audited(client, db):
    user = _make_user(db, "field_staff")
    token = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()["access_token"]
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    entry = db.query(AuditLog).filter_by(action="auth.logout").one()
    assert entry.actor_email == user.email


def test_logout_without_a_token_is_401(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_using_a_logged_out_token_twice_is_still_401(client, db):
    user = _make_user(db, "field_staff")
    token = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/logout", headers=headers)
    assert client.post("/api/auth/logout", headers=headers).status_code == 401


# --------------------------------------------------------------------- /me
def test_me_returns_the_signed_in_user(client, db):
    user = _make_user(db, "field_staff")
    token = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == user.email
    assert r.json()["role_code"] == "field_staff"


def test_requesting_a_fresh_otp_invalidates_the_previous_one(client, db, monkeypatch):
    """A re-requested code must replace the old one — otherwise an
    intercepted first code stays usable even after the user re-requests."""
    import app.routers.auth as auth_router

    user = _make_user(db, "admin")
    codes = iter(["111111", "222222"])
    monkeypatch.setattr(auth_router, "generate_otp", lambda: next(codes))

    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})

    stale = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "111111"})
    assert stale.status_code == 401

    fresh = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "222222"})
    assert fresh.status_code == 200


# -------------------------------------------------------------- rate limiting
def test_login_is_rate_limited_after_repeated_failures(client, db):
    from app.routers.auth import LOGIN_MAX_ATTEMPTS

    user = _make_user(db, "field_staff")
    for _ in range(LOGIN_MAX_ATTEMPTS):
        r = client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    assert r.status_code == 429


def test_login_rate_limit_resets_on_success(client, db):
    from app.routers.auth import LOGIN_MAX_ATTEMPTS

    user = _make_user(db, "field_staff")
    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200

    r = client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    assert r.status_code == 401  # not 429 — the counter was reset by the successful login


def test_otp_verify_is_rate_limited_after_repeated_wrong_codes(client, db):
    from app.routers.auth import OTP_MAX_ATTEMPTS

    user = _make_user(db, "admin")
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    for _ in range(OTP_MAX_ATTEMPTS):
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "000000"})
        assert r.status_code == 401
    r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": "000000"})
    assert r.status_code == 429
