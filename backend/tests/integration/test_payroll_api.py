"""Payroll (RFP 4.1 §4.7): salary structure, monthly runs, loss-of-pay
from attendance, payslips, bank export.
"""
import pytest
from datetime import date

from app.core.security import hash_password
from app.models import Attendance, AttendanceStatus, Division, Employee, EmploymentCategory, EmployeeStatus, Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, email=None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(email=email or f"{role_code}-{db.query(User).count()}@aaranyak.org", hashed_password=hash_password("Passw0rd!1"), role_id=role.id)
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


def _make_employee(db, division_id, user=None, status=EmployeeStatus.active) -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name="Pallavi Kalita",
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
        user_id=user.id if user else None,
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


# ---------------------------------------------------------- salary structure
def test_hr_sets_salary_structure(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.post(
        f"/api/payroll/employees/{emp.id}/structure",
        json={"effective_from": "2026-01-01", "basic": 56100, "hra": 22440, "other_allowances": 5000, "pf_deduction": 6732, "professional_tax": 200},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["gross"] == 83540
    assert body["total_deductions"] == 6932
    assert body["net"] == 76608


def test_field_staff_cannot_set_salary_structure(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id)
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post(f"/api/payroll/employees/{emp.id}/structure", json={"effective_from": "2026-01-01", "basic": 10000}, headers=headers)
    assert r.status_code == 403


# ----------------------------------------------------------------- payroll runs
def test_create_payroll_run_generates_payslips_for_employees_with_structure(client, db):
    div = _make_division(db)
    emp_with_structure = _make_employee(db, div.id)
    emp_without_structure = _make_employee(db, div.id)
    db.add(Attendance(employee_id=emp_with_structure.id, work_date=date(2026, 3, 1), status=AttendanceStatus.present))
    db.commit()

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    client.post(
        f"/api/payroll/employees/{emp_with_structure.id}/structure",
        json={"effective_from": "2026-01-01", "basic": 50000},
        headers=headers,
    )

    r = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["payslip_count"] == 1  # only the employee with a salary structure


def test_cannot_create_duplicate_run_for_same_month(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers)
    r = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers)
    assert r.status_code == 409


def test_separated_employee_excluded_from_payroll(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id, status=EmployeeStatus.separated)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    client.post(f"/api/payroll/employees/{emp.id}/structure", json={"effective_from": "2026-01-01", "basic": 50000}, headers=headers)
    r = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers)
    assert r.json()["payslip_count"] == 0


def test_loss_of_pay_reduces_gross_proportionally(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id)
    # Present on only 10 of March's 31 days, no leave covering the rest.
    for day in range(1, 11):
        db.add(Attendance(employee_id=emp.id, work_date=date(2026, 3, day), status=AttendanceStatus.present))
    db.commit()

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    client.post(f"/api/payroll/employees/{emp.id}/structure", json={"effective_from": "2026-01-01", "basic": 31000}, headers=headers)
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()

    payslip = run["payslips"][0]
    assert payslip["loss_of_pay_days"] == 21  # 31 - 10
    assert round(payslip["gross"]) == round(31000 * 10 / 31)


def test_finalise_run(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()
    r = client.post(f"/api/payroll/{run['id']}/finalise", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "finalised"


def test_cannot_finalise_twice(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()
    client.post(f"/api/payroll/{run['id']}/finalise", headers=headers)
    r = client.post(f"/api/payroll/{run['id']}/finalise", headers=headers)
    assert r.status_code == 400


def test_employee_views_own_payslips(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    client.post(f"/api/payroll/employees/{emp.id}/structure", json={"effective_from": "2026-01-01", "basic": 50000}, headers=hr_headers)
    client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=hr_headers)

    staff_headers = _login(client, staff)
    r = client.get(f"/api/payroll/employees/{emp.id}/payslips", headers=staff_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_employee_cannot_view_someone_elses_payslips(client, db):
    div = _make_division(db)
    staff1 = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff2 = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp1 = _make_employee(db, div.id, user=staff1)
    r = client.get(f"/api/payroll/employees/{emp1.id}/payslips", headers=_login(client, staff2))
    assert r.status_code == 403


def test_export_bank_file_returns_xlsx(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    client.post(
        f"/api/payroll/employees/{emp.id}/structure",
        json={"effective_from": "2026-01-01", "basic": 50000, "bank_account_number": "1234567890", "bank_ifsc": "SBIN0001234"},
        headers=headers,
    )
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()

    r = client.get(f"/api/payroll/{run['id']}/export/bank-file", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_export_payroll_report_returns_xlsx(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()
    r = client.get(f"/api/payroll/{run['id']}/export/payroll-report", headers=headers)
    assert r.status_code == 200


def test_finance_can_create_and_export_payroll(client, db):
    finance = _make_user(db, "finance")
    headers = _login(client, finance)
    run = client.post("/api/payroll", json={"month": 3, "year": 2026}, headers=headers).json()
    assert run["month"] == 3
    r = client.get(f"/api/payroll/{run['id']}/export/bank-file", headers=headers)
    assert r.status_code == 200


def test_unauthenticated_is_401(client):
    assert client.get("/api/payroll").status_code == 401
