"""The employee master (RFP 4.1): one permanent record per employee, every
RFP field group, bank/statutory fields restricted to a separate
permission, and reach scoped by role (RFP 3.1).
"""
import pytest

from app.core.security import hash_password
from app.models import Division, Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, division_id: int | None = None, email: str | None = None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(
        email=email or f"{role_code}@aaranyak.org",
        hashed_password=hash_password("Passw0rd!1"),
        role_id=role.id,
        division_id=division_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, user: User) -> dict:
    """Signs in, completing the email OTP step for roles that require it
    (admin, hr_admin, finance — see checklist 2.3)."""
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _make_division(db, name="Rhino Research", code="RHN") -> Division:
    div = Division(name=name, code=code)
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


BASE_PAYLOAD = {
    "full_name": "Pallavi Kalita",
    "gender": "female",
    "date_of_birth": "1992-04-10",
    "personal_email": "pallavi.k@gmail.com",
    "phone": "9864000000",
    "address": "Guwahati, Assam",
    "emergency_contact_name": "Bornali Kalita",
    "emergency_contact_phone": "9864000001",
    "date_of_joining": "2023-04-01",
    "designation": "Research Officer",
    "employment_category": "project_contract",
}


def _create_employee(client, headers, division_id, **overrides):
    payload = {**BASE_PAYLOAD, "division_id": division_id, **overrides}
    return client.post("/api/employees", json=payload, headers=headers)


# --------------------------------------------------------------------- create
def test_hr_creates_an_employee_with_a_permanent_code(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    r = _create_employee(client, headers, div.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["employee_code"].startswith("AAR-")
    assert body["full_name"] == "Pallavi Kalita"
    assert body["status"] == "active"


def test_employee_code_is_unique_and_permanent(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    first = _create_employee(client, headers, div.id).json()
    second = _create_employee(client, headers, div.id, full_name="Someone Else", personal_email="x@y.com").json()
    assert first["employee_code"] != second["employee_code"]


def test_create_requires_a_real_division(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    r = _create_employee(client, headers, division_id=999999)
    assert r.status_code == 400


def test_field_staff_cannot_create_employees(client, db):
    headers = _login(client, _make_user(db, "field_staff"))
    div = _make_division(db)
    assert _create_employee(client, headers, div.id).status_code == 403


# ---------------------------------------------------------- confidential data
def test_bank_and_statutory_fields_require_the_confidential_permission(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, hr_headers, div.id).json()

    r = client.put(
        f"/api/employees/{emp['id']}/confidential",
        json={"bank_account_number": "1234567890", "bank_ifsc": "SBIN0001234", "pan_number": "ABCDE1234F", "aadhaar_number": "123412341234"},
        headers=hr_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["bank_account_number"] == "1234567890"


def test_division_head_cannot_see_confidential_fields(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, hr_headers, div.id).json()
    client.put(
        f"/api/employees/{emp['id']}/confidential",
        json={"bank_account_number": "1234567890", "bank_ifsc": "SBIN0001234", "pan_number": "ABCDE1234F", "aadhaar_number": "123412341234"},
        headers=hr_headers,
    )

    head_headers = _login(client, _make_user(db, "division_head", division_id=div.id))
    r = client.get(f"/api/employees/{emp['id']}", headers=head_headers)
    assert r.status_code == 200
    assert "confidential" not in r.json()
    assert "bank_account_number" not in r.json()

    forbidden = client.get(f"/api/employees/{emp['id']}/confidential", headers=head_headers)
    assert forbidden.status_code == 403


def test_hr_sees_confidential_fields_when_requested(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, headers, div.id).json()
    client.put(
        f"/api/employees/{emp['id']}/confidential",
        json={"bank_account_number": "1234567890", "bank_ifsc": "SBIN0001234", "pan_number": "ABCDE1234F", "aadhaar_number": "123412341234"},
        headers=headers,
    )
    r = client.get(f"/api/employees/{emp['id']}/confidential", headers=headers)
    assert r.status_code == 200
    assert r.json()["pan_number"] == "ABCDE1234F"


def test_finance_can_view_but_not_edit_confidential_fields(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, hr_headers, div.id).json()

    finance_headers = _login(client, _make_user(db, "finance"))
    assert client.get(f"/api/employees/{emp['id']}/confidential", headers=finance_headers).status_code == 200
    r = client.put(
        f"/api/employees/{emp['id']}/confidential",
        json={"bank_account_number": "000", "bank_ifsc": "X", "pan_number": "Y", "aadhaar_number": "Z"},
        headers=finance_headers,
    )
    assert r.status_code == 403


# --------------------------------------------------------------------- scope
def test_division_head_sees_only_their_own_division(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    _create_employee(client, hr_headers, div_a.id, full_name="In Division A", personal_email="a@x.com")
    _create_employee(client, hr_headers, div_b.id, full_name="In Division B", personal_email="b@x.com")

    head_headers = _login(client, _make_user(db, "division_head", division_id=div_a.id))
    rows = client.get("/api/employees", headers=head_headers).json()
    assert [r["full_name"] for r in rows] == ["In Division A"]


def test_division_head_cannot_view_an_employee_outside_their_division(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    outsider = _create_employee(client, hr_headers, div_b.id).json()

    head_headers = _login(client, _make_user(db, "division_head", division_id=div_a.id))
    r = client.get(f"/api/employees/{outsider['id']}", headers=head_headers)
    assert r.status_code == 403


def test_unassigned_division_head_sees_nothing(client, db):
    """RFP: an unassigned scoped role sees nothing, never everything."""
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    _create_employee(client, hr_headers, div.id)

    head_headers = _login(client, _make_user(db, "division_head", division_id=None))
    rows = client.get("/api/employees", headers=head_headers).json()
    assert rows == []


def test_hr_sees_every_division(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    _create_employee(client, hr_headers, div_a.id, full_name="In Division A", personal_email="a@x.com")
    _create_employee(client, hr_headers, div_b.id, full_name="In Division B", personal_email="b@x.com")

    rows = client.get("/api/employees", headers=hr_headers).json()
    assert {r["full_name"] for r in rows} == {"In Division A", "In Division B"}


def test_field_staff_sees_only_their_own_record(client, db):
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    me_user = _make_user(db, "field_staff", email="me@aaranyak.org")
    other_user = _make_user(db, "field_staff", email="other@aaranyak.org")
    me_emp = _create_employee(client, hr_headers, div.id, full_name="Me", personal_email="me@x.com", user_id=me_user.id).json()
    _create_employee(client, hr_headers, div.id, full_name="Other", personal_email="other@x.com", user_id=other_user.id)

    me_headers = _login(client, me_user)
    rows = client.get("/api/employees", headers=me_headers).json()
    assert [r["full_name"] for r in rows] == ["Me"]

    assert client.get(f"/api/employees/{me_emp['id']}", headers=me_headers).status_code == 200


# --------------------------------------------------------------- edit/status
def test_hr_edits_an_employee_record(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, headers, div.id).json()
    r = client.put(f"/api/employees/{emp['id']}", json={"designation": "Senior Research Officer"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["designation"] == "Senior Research Officer"


def test_status_transition_to_separated_requires_exit_details(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, headers, div.id).json()
    bad = client.put(f"/api/employees/{emp['id']}/status", json={"status": "separated"}, headers=headers)
    assert bad.status_code == 422

    good = client.put(
        f"/api/employees/{emp['id']}/status",
        json={"status": "separated", "exit_reason": "Resignation", "exit_date": "2026-12-31"},
        headers=headers,
    )
    assert good.status_code == 200
    assert good.json()["status"] == "separated"


def test_contract_end_date_is_visible_on_the_record(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    emp = _create_employee(client, headers, div.id, contract_end_date="2026-12-31").json()
    assert emp["contract_end_date"] == "2026-12-31"


def test_reporting_officer_must_be_a_real_employee(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    r = _create_employee(client, headers, div.id, reporting_officer_id=999999)
    assert r.status_code == 400


def test_reporting_officer_chain(client, db):
    headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    manager = _create_employee(client, headers, div.id, full_name="Manager", personal_email="m@x.com").json()
    report = _create_employee(
        client, headers, div.id, full_name="Report", personal_email="r@x.com", reporting_officer_id=manager["id"]
    ).json()
    assert report["reporting_officer_id"] == manager["id"]


def test_unauthenticated_is_401(client):
    assert client.get("/api/employees").status_code == 401


def test_project_lead_scope_is_not_yet_enforceable_sees_only_own_record(client, db):
    """Known limitation, not a bug: Scope.project (project_lead,
    coordinator) has no employee<->project link to enforce against yet —
    it is added once the staffing/assignment module lands. Until then
    these roles fall through to 'own record only', the same as a
    self-service role, rather than silently seeing everyone."""
    hr_headers = _login(client, _make_user(db, "hr_admin"))
    div = _make_division(db)
    lead_user = _make_user(db, "project_lead")
    _create_employee(client, hr_headers, div.id, full_name="Team Member", personal_email="tm@x.com")

    lead_headers = _login(client, lead_user)
    rows = client.get("/api/employees", headers=lead_headers).json()
    assert rows == []
