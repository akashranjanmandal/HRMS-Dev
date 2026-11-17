"""Dashboards and reports (RFP Section 7): role-scoped dashboard summary
and Excel exports for the core HR reports.
"""
from datetime import date

import pytest

from app.core.security import hash_password
from app.models import (
    Attendance,
    AttendanceSource,
    AttendanceStatus,
    Division,
    Employee,
    EmploymentCategory,
    EmployeeStatus,
    Role,
    User,
)

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


def test_dashboard_reports_checked_in_today_and_attendance_composition(client, db):
    div = _make_division(db)
    emp1 = _make_employee(db, div.id)
    emp2 = _make_employee(db, div.id)
    db.add(
        Attendance(
            employee_id=emp1.id,
            work_date=date.today(),
            status=AttendanceStatus.present,
            source=AttendanceSource.geofence,
        )
    )
    db.add(
        Attendance(
            employee_id=emp2.id,
            work_date=date.today(),
            status=AttendanceStatus.pending_approval,
            source=AttendanceSource.field_duty,
        )
    )
    db.commit()

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checked_in_today"] == 1

    comp = body["attendance_by_division"]
    assert len(comp) >= 1
    row = next(c for c in comp if c["division"] == div.name)
    assert row["present"] == 1
    assert row["field_duty"] == 1
    assert row["total_active"] == 2


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
    assert body["attendance_by_division"] == []


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


def test_preview_employee_strength_returns_json_rows(client, db):
    div = _make_division(db)
    _make_employee(db, div.id)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/employee-strength/preview", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(row["division"] == div.name and row["active_employees"] == 1 for row in rows)


def test_preview_does_not_require_export_permission(client, db):
    """Preview is view-only — report:view is enough; report:export is
    only required to download the Excel file."""
    staff = _make_user(db, "other_authorised")
    headers = _login(client, staff)
    r = client.get("/api/reports/employee-strength/preview", headers=headers)
    assert r.status_code == 200


def test_preview_asset_register_returns_json_rows(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/asset-register/preview", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert {row["status"] for row in rows} == {"in_store", "issued", "pending_return_approval", "disposed"}


def test_preview_attendance_summary_returns_json_rows(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/attendance-summary/preview?year=2026&month=3", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_preview_leave_register_returns_json_rows(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/leave-register/preview?year=2026", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_preview_contracts_expiring_returns_json_rows(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/contracts-expiring/preview?days=30", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_preview_separations_returns_json_rows(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/reports/separations/preview?start=2026-01-01&end=2026-12-31", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_payroll_cost_by_division_export_returns_xlsx(client, db):
    from app.models import PayrollRun

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    run = PayrollRun(month=3, year=2026, created_by_id=hr.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    r = client.get(f"/api/reports/payroll-cost-by-division/export?run_id={run.id}", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_payroll_cost_by_division_preview_returns_json_rows(client, db):
    from app.models import PayrollRun

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    run = PayrollRun(month=3, year=2026, created_by_id=hr.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    r = client.get(f"/api/reports/payroll-cost-by-division/preview?run_id={run.id}", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unauthenticated_is_401(client):
    assert client.get("/api/reports/dashboard").status_code == 401
