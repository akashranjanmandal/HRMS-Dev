"""Leave (RFP 4.6): configurable types, applications, balances, overlap
and eligibility checks, routed through the workflow engine.
"""
import pytest
from datetime import date, timedelta

from app.core.security import hash_password
from app.models import Division, Employee, EmploymentCategory, LeaveType, Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, division_id=None, email=None) -> User:
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


def _make_division(db, name="Rhino Research", code="RHN") -> Division:
    div = Division(name=name, code=code)
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


def _make_employee(db, division_id, user) -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name="Test Employee",
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
        user_id=user.id,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _make_leave_type(db, name="Casual Leave", days=12, requires_approval=True) -> LeaveType:
    lt = LeaveType(name=name, annual_entitlement_days=days, requires_approval=requires_approval)
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ------------------------------------------------------------------- types
def test_admin_creates_a_leave_type(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    r = client.post(
        "/api/leave/types",
        json={"name": "Maternity Leave", "annual_entitlement_days": 180, "carry_forward_allowed": False, "requires_approval": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["annual_entitlement_days"] == 180


def test_duplicate_leave_type_name_rejected(client, db):
    admin = _make_user(db, "admin")
    headers = _login(client, admin)
    client.post("/api/leave/types", json={"name": "Casual Leave", "annual_entitlement_days": 12}, headers=headers)
    r = client.post("/api/leave/types", json={"name": "Casual Leave", "annual_entitlement_days": 20}, headers=headers)
    assert r.status_code == 409


def test_field_staff_cannot_create_leave_types(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post("/api/leave/types", json={"name": "x", "annual_entitlement_days": 1}, headers=headers)
    assert r.status_code == 403


# --------------------------------------------------------------- application
def test_apply_for_leave_creates_pending_application_and_approval(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff", division_id=None)
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db)

    headers = _login(client, staff)
    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=1)
    r = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(end), "reason": "Family function"}, headers=headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["days"] == 2
    assert body["approval_request_id"] is not None


def test_leave_without_approval_requirement_is_auto_approved(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db, name="Casual Leave", requires_approval=False)

    headers = _login(client, staff)
    start = date.today() + timedelta(days=5)
    r = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=headers
    )
    assert r.json()["status"] == "approved"


def test_overlapping_application_rejected(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db)
    headers = _login(client, staff)

    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=2)
    client.post("/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(end)}, headers=headers)

    overlap_start = start + timedelta(days=1)
    overlap_end = overlap_start + timedelta(days=1)
    r = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(overlap_start), "end_date": str(overlap_end)}, headers=headers
    )
    assert r.status_code == 409


def test_insufficient_balance_rejected(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db, days=1)
    headers = _login(client, staff)

    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=5)  # 6 days requested, only 1 available
    r = client.post("/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(end)}, headers=headers)
    assert r.status_code == 422


def test_end_before_start_rejected(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db)
    headers = _login(client, staff)

    start = date.today() + timedelta(days=5)
    end = start - timedelta(days=1)
    r = client.post("/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(end)}, headers=headers)
    assert r.status_code == 422


def test_approval_deducts_balance(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db, days=12)

    headers = _login(client, staff)
    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=1)
    app_resp = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(end)}, headers=headers
    ).json()

    head_headers = _login(client, head)
    client.post(f"/api/approvals/{app_resp['approval_request_id']}/decide", json={"action": "approve"}, headers=head_headers)

    balances = client.get("/api/leave/balances", headers=headers).json()
    casual = next(b for b in balances if b["leave_type_id"] == lt.id)
    assert casual["available_days"] == 10


def test_cancel_own_pending_application(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db)
    headers = _login(client, staff)

    start = date.today() + timedelta(days=5)
    app_resp = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=headers
    ).json()
    r = client.post(f"/api/leave/{app_resp['id']}/cancel", headers=headers)
    assert r.json()["status"] == "cancelled"


def test_cannot_cancel_someone_elses_application(client, db):
    div = _make_division(db)
    staff1 = _make_user(db, "field_staff", email="one@aaranyak.org")
    staff2 = _make_user(db, "field_staff", email="two@aaranyak.org")
    emp1 = _make_employee(db, div.id, staff1)
    emp2 = _make_employee(db, div.id, staff2)
    lt = _make_leave_type(db)

    headers1 = _login(client, staff1)
    start = date.today() + timedelta(days=5)
    app_resp = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=headers1
    ).json()

    headers2 = _login(client, staff2)
    r = client.post(f"/api/leave/{app_resp['id']}/cancel", headers=headers2)
    assert r.status_code == 404


def test_division_head_sees_team_applications_scoped(client, db):
    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    head_a = _make_user(db, "division_head", division_id=div_a.id)
    staff_a = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff_b = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp_a = _make_employee(db, div_a.id, staff_a)
    emp_b = _make_employee(db, div_b.id, staff_b)
    lt = _make_leave_type(db)

    start = date.today() + timedelta(days=5)
    client.post("/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=_login(client, staff_a))
    client.post("/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=_login(client, staff_b))

    r = client.get("/api/leave", headers=_login(client, head_a))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_unauthenticated_is_401(client):
    assert client.get("/api/leave/mine").status_code == 401


def test_rejection_updates_application_status_without_deducting_balance(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    lt = _make_leave_type(db, days=12)

    headers = _login(client, staff)
    start = date.today() + timedelta(days=5)
    app_resp = client.post(
        "/api/leave", json={"leave_type_id": lt.id, "start_date": str(start), "end_date": str(start)}, headers=headers
    ).json()

    head_headers = _login(client, head)
    client.post(f"/api/approvals/{app_resp['approval_request_id']}/decide", json={"action": "reject"}, headers=head_headers)

    mine = client.get("/api/leave/mine", headers=headers).json()
    rejected = next(a for a in mine if a["id"] == app_resp["id"])
    assert rejected["status"] == "rejected"

    balances = client.get("/api/leave/balances", headers=headers).json()
    casual = next(b for b in balances if b["leave_type_id"] == lt.id)
    assert casual["available_days"] == 12  # untouched
