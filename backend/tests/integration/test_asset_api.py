"""Asset management (RFP 4.1 §4.9): register CRUD, issue/return via the
workflow engine, direct transfer, repair and disposal.
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


def _create_asset(client, headers, **overrides):
    payload = {"name": "GPS Unit", "category": "field_equipment", "purchase_value": 15000}
    payload.update(overrides)
    return client.post("/api/assets", json=payload, headers=headers).json()


def test_hr_creates_asset(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    asset = _create_asset(client, headers)
    assert asset["status"] == "in_store"
    assert asset["asset_code"].startswith("AST-")


def test_field_staff_cannot_create_asset(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post("/api/assets", json={"name": "GPS Unit", "category": "field_equipment"}, headers=headers)
    assert r.status_code == 403


def test_issue_requires_division_head_approval(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers)

    r = client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=hr_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_store"  # still not issued — pending approval

    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    r = client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/assets/{asset['id']}", headers=hr_headers)
    body = r.json()
    assert body["status"] == "issued"
    assert body["custodian_employee_id"] == emp.id


def test_cannot_issue_an_already_issued_asset(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=hr_headers)

    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    r = client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=hr_headers)
    assert r.status_code == 400


def test_return_flow_releases_asset_on_approval(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers, division_id=div.id)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=hr_headers)

    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    issue_request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{issue_request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    staff_headers = _login(client, staff)
    r = client.post(f"/api/assets/{asset['id']}/return", json={"notes": "done with fieldwork"}, headers=staff_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_return_approval"

    pending = client.get("/api/approvals", headers=dh_headers).json()
    return_request_id = next(p["id"] for p in pending if p["request_type"] == "asset_return")
    client.post(f"/api/approvals/{return_request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    r = client.get(f"/api/assets/{asset['id']}", headers=hr_headers)
    body = r.json()
    assert body["status"] == "in_store"
    assert body["custodian_employee_id"] is None


def test_employee_cannot_return_someone_elses_asset(client, db):
    div = _make_division(db)
    staff1 = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff2 = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp1 = _make_employee(db, div.id, user=staff1)
    _make_employee(db, div.id, user=staff2)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp1.id}, headers=hr_headers)
    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    staff2_headers = _login(client, staff2)
    r = client.post(f"/api/assets/{asset['id']}/return", json={}, headers=staff2_headers)
    assert r.status_code == 403


def test_transfer_asset_directly(client, db):
    div = _make_division(db)
    staff1 = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff2 = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp1 = _make_employee(db, div.id, user=staff1)
    emp2 = _make_employee(db, div.id, user=staff2)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp1.id}, headers=hr_headers)
    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    r = client.post(f"/api/assets/{asset['id']}/transfer", json={"to_employee_id": emp2.id}, headers=hr_headers)
    assert r.status_code == 200, r.text
    assert r.json()["custodian_employee_id"] == emp2.id


def test_repair_and_dispose(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    asset = _create_asset(client, headers)

    r = client.post(f"/api/assets/{asset['id']}/repair", json={"notes": "screen cracked"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["condition"] == "needs_repair"

    r = client.post(f"/api/assets/{asset['id']}/dispose", json={"notes": "beyond repair"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disposed"


def test_cannot_dispose_issued_asset(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    asset = _create_asset(client, headers)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=headers)
    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    r = client.post(f"/api/assets/{asset['id']}/dispose", json={"notes": "x"}, headers=headers)
    assert r.status_code == 400


def test_employee_can_view_own_assets(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    asset = _create_asset(client, hr_headers)
    client.post(f"/api/assets/{asset['id']}/issue", json={"employee_id": emp.id}, headers=hr_headers)
    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    pending = client.get("/api/approvals", headers=dh_headers).json()
    request_id = next(p["id"] for p in pending if p["request_type"] == "asset_issue")
    client.post(f"/api/approvals/{request_id}/decide", json={"action": "approve"}, headers=dh_headers)

    staff_headers = _login(client, staff)
    r = client.get(f"/api/assets/employees/{emp.id}", headers=staff_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_unauthenticated_is_401(client):
    assert client.get("/api/assets").status_code == 401
