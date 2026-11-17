"""Global search (design mockup: "Search people, requests, assets" in the
top bar on every screen) — cross-module, but scoped exactly the way each
owning module already scopes its own listing.
"""
import pytest

from app.core.security import hash_password
from app.models import Asset, AssetCategory, Division, Employee, EmploymentCategory, RequestType, Role, User
from app.services import workflow as workflow_service

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


def _make_division(db, name="Rhino Research", code="RHN") -> Division:
    div = Division(name=name, code=code)
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


def _make_employee(db, division_id, full_name="Pallavi Kalita") -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name=full_name,
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
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


def test_hr_finds_employee_by_name(client, db):
    div = _make_division(db)
    _make_employee(db, div.id, full_name="Pallavi Kalita")
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/search?q=Pallavi", headers=headers)
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert any(res["kind"] == "employee" and "Pallavi" in res["title"] for res in results)


def test_division_head_only_finds_own_divisions_employee(client, db):
    div1 = _make_division(db, "Rhino Research", "RHN")
    div2 = _make_division(db, "Elephant Corridor", "ELC")
    _make_employee(db, div1.id, full_name="Pallavi Kalita")
    _make_employee(db, div2.id, full_name="Pallavi Sharma")

    division_head = _make_user(db, "division_head", division_id=div1.id)
    headers = _login(client, division_head)
    r = client.get("/api/search?q=Pallavi", headers=headers)
    assert r.status_code == 200
    names = [res["title"] for res in r.json()["results"] if res["kind"] == "employee"]
    assert names == ["Pallavi Kalita"]


def test_field_staff_cannot_find_employees_outside_their_own_record(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    _make_employee(db, div.id, full_name="Someone Else")
    headers = _login(client, staff)
    r = client.get("/api/search?q=Someone", headers=headers)
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_finds_pending_approval_request_by_summary(client, db):
    div = _make_division(db)
    emp = _make_employee(db, div.id)
    workflow_service.submit_for_approval(
        db, request_type=RequestType.asset_issue, object_id=1, requested_by_id=emp.id, division_id=div.id, summary="Issue Camera Trap to Pallavi"
    )
    db.commit()

    division_head = _make_user(db, "division_head", division_id=div.id)
    headers = _login(client, division_head)
    r = client.get("/api/search?q=Camera", headers=headers)
    assert r.status_code == 200
    assert any(res["kind"] == "approval_request" for res in r.json()["results"])


def test_finds_asset_by_name(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    db.add(Asset(asset_code="AST-00001", name="Camera Trap Bushnell", category=AssetCategory.field_equipment, purchase_value=18000))
    db.commit()

    r = client.get("/api/search?q=Camera", headers=headers)
    assert r.status_code == 200
    assert any(res["kind"] == "asset" and res["title"] == "Camera Trap Bushnell" for res in r.json()["results"])


def test_division_head_does_not_find_another_divisions_asset(client, db):
    div1 = _make_division(db, "Rhino Research", "RHN")
    div2 = _make_division(db, "Elephant Corridor", "ELC")
    db.add(Asset(asset_code="AST-00001", name="Camera Trap Bushnell", category=AssetCategory.field_equipment, division_id=div2.id))
    db.commit()

    division_head = _make_user(db, "division_head", division_id=div1.id)
    headers = _login(client, division_head)
    r = client.get("/api/search?q=Camera", headers=headers)
    assert r.json()["results"] == []


def test_query_too_short_is_422(client, db):
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.get("/api/search?q=a", headers=headers)
    assert r.status_code == 422


def test_unauthenticated_is_401(client):
    assert client.get("/api/search?q=test").status_code == 401
