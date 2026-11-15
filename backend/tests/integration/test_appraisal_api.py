"""Performance appraisal (RFP 4.1 §4.8): cycle creation, self-assessment,
supervisor review, Division Head review and sign-off.
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


def _create_cycle(client, headers):
    return client.post(
        "/api/appraisal/cycles",
        json={"name": "FY 2025-26", "period_start": "2025-04-01", "period_end": "2026-03-31"},
        headers=headers,
    ).json()


def test_hr_creates_cycle_and_reviews_are_generated_for_active_employees(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    _make_employee(db, div.id, user=staff)
    _make_employee(db, div.id, status=EmployeeStatus.separated)  # excluded

    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    cycle = _create_cycle(client, headers)
    assert cycle["name"] == "FY 2025-26"

    reviews = client.get(f"/api/appraisal?cycle_id={cycle['id']}", headers=headers).json()
    assert len(reviews) == 1
    assert reviews[0]["stage"] == "self_assessment"


def test_field_staff_cannot_create_cycle(client, db):
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post(
        "/api/appraisal/cycles",
        json={"name": "FY 2025-26", "period_start": "2025-04-01", "period_end": "2026-03-31"},
        headers=headers,
    )
    assert r.status_code == 403


def test_full_review_lifecycle(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    cycle = _create_cycle(client, hr_headers)
    reviews = client.get(f"/api/appraisal?cycle_id={cycle['id']}", headers=hr_headers).json()
    review_id = reviews[0]["id"]

    staff_headers = _login(client, staff)
    r = client.post(
        f"/api/appraisal/reviews/{review_id}/self-assessment",
        json={"self_assessment_text": "Met all field targets", "self_rating": 4, "ratings": [{"parameter": "Punctuality", "rating": 5}]},
        headers=staff_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "supervisor_review"
    assert len(body["ratings"]) == 1

    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    r = client.post(
        f"/api/appraisal/reviews/{review_id}/supervisor-review",
        json={"supervisor_comments": "Good field discipline", "supervisor_rating": 4},
        headers=dh_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["stage"] == "division_head_review"

    r = client.post(
        f"/api/appraisal/reviews/{review_id}/division-head-review",
        json={"division_head_comments": "Approved", "division_head_rating": 4, "salary_revision_recommended": True},
        headers=dh_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "completed"
    assert body["salary_revision_recommended"] is True


def test_employee_cannot_submit_self_assessment_for_someone_else(client, db):
    div = _make_division(db)
    staff1 = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff2 = _make_user(db, "field_staff", email="b@aaranyak.org")
    _make_employee(db, div.id, user=staff1)
    emp2 = _make_employee(db, div.id, user=staff2)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    cycle = _create_cycle(client, hr_headers)
    reviews = client.get(f"/api/appraisal?cycle_id={cycle['id']}", headers=hr_headers).json()
    review_for_emp2 = next(r for r in reviews if r["employee_id"] == emp2.id)

    staff1_headers = _login(client, staff1)
    r = client.post(
        f"/api/appraisal/reviews/{review_for_emp2['id']}/self-assessment",
        json={"self_assessment_text": "x", "self_rating": 3},
        headers=staff1_headers,
    )
    assert r.status_code == 403


def test_cannot_skip_stages(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    _make_employee(db, div.id, user=staff)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    cycle = _create_cycle(client, hr_headers)
    reviews = client.get(f"/api/appraisal?cycle_id={cycle['id']}", headers=hr_headers).json()
    review_id = reviews[0]["id"]

    division_head = _make_user(db, "division_head", division_id=div.id)
    dh_headers = _login(client, division_head)
    r = client.post(
        f"/api/appraisal/reviews/{review_id}/supervisor-review",
        json={"supervisor_comments": "x", "supervisor_rating": 3},
        headers=dh_headers,
    )
    assert r.status_code == 400


def test_division_head_outside_division_cannot_review(client, db):
    div1 = _make_division(db)
    div2 = Division(name="Elephant Corridor", code="ELC")
    db.add(div2)
    db.commit()
    db.refresh(div2)

    staff = _make_user(db, "field_staff")
    _make_employee(db, div1.id, user=staff)

    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    cycle = _create_cycle(client, hr_headers)
    reviews = client.get(f"/api/appraisal?cycle_id={cycle['id']}", headers=hr_headers).json()
    review_id = reviews[0]["id"]

    staff_headers = _login(client, staff)
    client.post(
        f"/api/appraisal/reviews/{review_id}/self-assessment",
        json={"self_assessment_text": "x", "self_rating": 3},
        headers=staff_headers,
    )

    other_division_head = _make_user(db, "division_head", email="other_dh@aaranyak.org", division_id=div2.id)
    headers = _login(client, other_division_head)
    r = client.post(
        f"/api/appraisal/reviews/{review_id}/supervisor-review",
        json={"supervisor_comments": "x", "supervisor_rating": 3},
        headers=headers,
    )
    assert r.status_code == 403


def test_unauthenticated_is_401(client):
    assert client.get("/api/appraisal/mine").status_code == 401
