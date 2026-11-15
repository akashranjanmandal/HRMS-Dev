"""User accounts (RFP Section 9): admin creates logins, assigns roles,
resets passwords, deactivates accounts — all gated so nobody can grant or
manage an account more powerful than their own.
"""
import pytest

from app.core.security import hash_password
from app.models import Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, email=None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(email=email or f"{role_code}-{db.query(User).count()}@aaranyak.org", hashed_password=hash_password("Passw0rd!1"), role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_admin_creates_user_and_gets_temp_password(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    r = client.post("/api/users", json={"email": "newhire@aaranyak.org", "role_code": "field_staff"}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["temporary_password"]
    assert body["must_change_password"] is True


def test_hr_admin_cannot_grant_role_management_permission(client, db):
    """hr_admin lacks role:admin, so it cannot create an admin account —
    nobody can grant permissions they do not themselves hold."""
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.post("/api/users", json={"email": "wannabe-admin@aaranyak.org", "role_code": "admin"}, headers=headers)
    assert r.status_code == 403


def test_field_staff_cannot_create_users(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post("/api/users", json={"email": "x@aaranyak.org", "role_code": "field_staff"}, headers=headers)
    assert r.status_code == 403


def test_cannot_create_duplicate_email(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    client.post("/api/users", json={"email": "dup@aaranyak.org", "role_code": "field_staff"}, headers=headers)
    r = client.post("/api/users", json={"email": "dup@aaranyak.org", "role_code": "field_staff"}, headers=headers)
    assert r.status_code == 409


def test_admin_deactivates_and_reactivates_user(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    staff = _make_user(db, "field_staff")

    r = client.put(f"/api/users/{staff.id}/active", json={"is_active": False}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    r = client.put(f"/api/users/{staff.id}/active", json={"is_active": True}, headers=headers)
    assert r.json()["is_active"] is True


def test_cannot_deactivate_own_account(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    r = client.put(f"/api/users/{admin.id}/active", json={"is_active": False}, headers=headers)
    assert r.status_code == 400


def test_admin_resets_password(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    staff = _make_user(db, "field_staff")
    r = client.post(f"/api/users/{staff.id}/reset-password", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["temporary_password"]


def test_hr_admin_cannot_manage_an_admin_account(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    admin = _make_user(db, "admin")
    r = client.put(f"/api/users/{admin.id}/active", json={"is_active": False}, headers=headers)
    assert r.status_code == 403


def test_list_users_excludes_nothing_hidden(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    _make_user(db, "field_staff", email="a@aaranyak.org")
    r = client.get("/api/users", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_unauthenticated_is_401(client):
    assert client.get("/api/users").status_code == 401
