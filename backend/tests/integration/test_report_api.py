"""Dashboards and reports (RFP Section 7): role-scoped dashboard summary
and Excel exports for the core HR reports.
"""
import pytest

from app.core.security import hash_password
from app.models import Division, Employee, EmploymentCategory, EmployeeStatus, Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, email=None, division_id=None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(
        email=email or f"{role_code}-{db.query(User).count()}@aaranyak.org",
        hashed_password=hash_password("Passw0rd!1"),
        role_id=role.id,
        division_id=division_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_division(db) -> Division:
    div = Division(name="Rhino Research", code="RHN")
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


def _make_employee(db, division_id, status=EmployeeStatus.active) -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name="Pallavi Kalita",
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
        status=status,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_hr_sees_org_wide_dashboard(client, db):
    div = _make_division(db)
    _make_employee(db, div.id)
    _make_employee(db, div.id)

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_employees"] == 2
    assert len(body["employee_strength_by_division"]) >= 1


def test_division_head_sees_only_own_division(client, db):
    div1 = _make_division(db)
    div2 = Division(name="Elephant Corridor", code="ELC")
    db.add(div2)
    db.commit()
    db.refresh(div2)
    _make_employee(db, div1.id)
    _make_employee(db, div2.id)

    division_head = _make_user(db, "division_head", division_id=div1.id)
    headers = _login(client, division_head)
    r = client.get("/api/reports/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_employees"] == 1
    assert body["employee_strength_by_division"] == []


def test_field_staff_cannot_view_dashboard(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.get("/api/reports/dashboard", headers=headers)
    assert r.status_code == 403


def test_export_employee_strength_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/employee-strength/export", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_export_contracts_expiring_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/contracts-expiring/export", headers=headers)
    assert r.status_code == 200


def test_export_separations_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/separations/export?start=2026-01-01&end=2026-12-31", headers=headers)
    assert r.status_code == 200


def test_export_attendance_summary_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/attendance-summary/export?year=2026&month=3", headers=headers)
    assert r.status_code == 200


def test_export_leave_register_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/leave-register/export?year=2026", headers=headers)
    assert r.status_code == 200


def test_export_asset_register_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/asset-register/export", headers=headers)
    assert r.status_code == 200


def test_field_staff_cannot_export(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.get("/api/reports/employee-strength/export", headers=headers)
    assert r.status_code == 403


def test_unauthenticated_is_401(client):
    assert client.get("/api/reports/dashboard").status_code == 401
