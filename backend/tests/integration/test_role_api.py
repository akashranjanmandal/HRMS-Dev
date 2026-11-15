"""Roles and permissions (RFP Section 9): viewing the permission
catalogue, and editing a non-system role's permission set.
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


def test_admin_lists_roles(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    r = client.get("/api/roles", headers=headers)
    assert r.status_code == 200
    codes = [row["code"] for row in r.json()]
    assert "field_staff" in codes
    assert "admin" in codes


def test_permission_catalogue_is_visible(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    r = client.get("/api/roles/permissions", headers=headers)
    assert r.status_code == 200
    codes = [row["code"] for row in r.json()]
    assert "leave:approve" in codes


def test_cannot_edit_a_system_roles_permissions(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    field_staff = db.query(Role).filter_by(code="field_staff").one()
    r = client.put(f"/api/roles/{field_staff.id}/permissions", json={"permissions": ["employee:view"]}, headers=headers)
    assert r.status_code == 400


def test_field_staff_cannot_view_roles(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.get("/api/roles", headers=headers)
    assert r.status_code == 403


def test_unauthenticated_is_401(client):
    assert client.get("/api/roles").status_code == 401
