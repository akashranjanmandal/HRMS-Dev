"""Recruitment, onboarding, orientation (RFP 4.1 §4.2-4.4)."""
import pytest

from app.core.security import hash_password
from app.models import Division, Employee, EmploymentCategory, OnboardingTask, Role, User

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


def _make_division(db) -> Division:
    div = Division(name="Rhino Research", code="RHN")
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# -------------------------------------------------------------------- vacancy
def test_hr_creates_a_vacancy_as_draft(client, db):
    div = _make_division(db)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    r = client.post(
        "/api/vacancies",
        json={"title": "Research Officer", "division_id": div.id, "terms_of_reference": "Field research on rhino populations", "positions_open": 2},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "draft"


def test_submitting_vacancy_for_approval_creates_approval_request(client, db):
    div = _make_division(db)
    hr = _make_user(db, "hr_admin")
    headers = _login(client, hr)
    vac = client.post("/api/vacancies", json={"title": "Research Officer", "division_id": div.id}, headers=headers).json()
    r = client.post(f"/api/vacancies/{vac['id']}/submit", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_approval"
    assert r.json()["approval_request_id"] is not None


def test_approved_vacancy_is_published_and_visible_publicly(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vac = client.post("/api/vacancies", json={"title": "Research Officer", "division_id": div.id}, headers=hr_headers).json()
    client.post(f"/api/vacancies/{vac['id']}/submit", headers=hr_headers)
    vac_after_submit = client.get("/api/vacancies", headers=hr_headers).json()[0]

    head_headers = _login(client, head)
    client.post(f"/api/approvals/{vac_after_submit['approval_request_id']}/decide", json={"action": "approve"}, headers=head_headers)
    second_headers = _login(client, hr)
    client.post(f"/api/approvals/{vac_after_submit['approval_request_id']}/decide", json={"action": "approve"}, headers=second_headers)

    public = client.get("/api/public/vacancies").json()
    assert any(v["id"] == vac["id"] and v["status"] == "published" for v in public)


def test_rejected_vacancy_returns_to_draft(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vac = client.post("/api/vacancies", json={"title": "Research Officer", "division_id": div.id}, headers=hr_headers).json()
    client.post(f"/api/vacancies/{vac['id']}/submit", headers=hr_headers)
    vac_after_submit = client.get("/api/vacancies", headers=hr_headers).json()[0]

    head_headers = _login(client, head)
    client.post(f"/api/approvals/{vac_after_submit['approval_request_id']}/decide", json={"action": "reject"}, headers=head_headers)

    vac_now = client.get("/api/vacancies", headers=hr_headers).json()[0]
    assert vac_now["status"] == "draft"


def test_field_staff_cannot_create_vacancy(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    headers = _login(client, staff)
    r = client.post("/api/vacancies", json={"title": "x", "division_id": div.id}, headers=headers)
    assert r.status_code == 403


# ------------------------------------------------------------------ candidates
def _published_vacancy(client, db, hr_headers, head_headers, division_id):
    vac = client.post("/api/vacancies", json={"title": "Research Officer", "division_id": division_id}, headers=hr_headers).json()
    client.post(f"/api/vacancies/{vac['id']}/submit", headers=hr_headers)
    vac2 = client.get("/api/vacancies", headers=hr_headers).json()[0]
    client.post(f"/api/approvals/{vac2['approval_request_id']}/decide", json={"action": "approve"}, headers=head_headers)
    vac3 = [v for v in client.get("/api/vacancies", headers=hr_headers).json() if v["id"] == vac["id"]][0]
    client.post(f"/api/approvals/{vac3['approval_request_id']}/decide", json={"action": "approve"}, headers=hr_headers)
    return vac["id"]


def test_public_can_apply_to_published_vacancy(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    vacancy_id = _published_vacancy(client, db, _login(client, hr), _login(client, head), div.id)

    r = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply",
        json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com", "phone": "9864000000"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["stage"] == "applied"


def test_cannot_apply_to_unpublished_vacancy(client, db):
    div = _make_division(db)
    hr = _make_user(db, "hr_admin")
    vac = client.post("/api/vacancies", json={"title": "x", "division_id": div.id}, headers=_login(client, hr)).json()
    r = client.post(f"/api/public/vacancies/{vac['id']}/apply", json={"full_name": "x", "email": "x@y.com"})
    assert r.status_code == 404


def test_hr_moves_candidate_through_stages(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()

    r = client.put(f"/api/candidates/{candidate['id']}/stage", json={"stage": "shortlisted"}, headers=hr_headers)
    assert r.json()["stage"] == "shortlisted"


# ------------------------------------------------------------------ interviews
def test_schedule_and_evaluate_interview(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()

    interview = client.post(f"/api/candidates/{candidate['id']}/interviews", json={}, headers=hr_headers).json()
    r = client.put(
        f"/api/interviews/{interview['id']}/evaluate", json={"evaluation_notes": "Strong candidate", "recommendation": "select"}, headers=hr_headers
    )
    assert r.status_code == 200
    assert r.json()["recommendation"] == "select"


# -------------------------------------------------------------------- selection
def test_selecting_a_candidate_creates_employee_and_appointment_letter(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()

    r = client.post(
        f"/api/candidates/{candidate['id']}/select",
        json={"date_of_joining": "2026-04-01", "designation": "Research Officer", "employment_category": "project_contract"},
        headers=hr_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["employee_id"] is not None
    assert "Pallavi Kalita" in body["letter_text"]
    assert "AAR-RHN-" in body["letter_text"]


def test_selected_candidate_gets_default_onboarding_checklist(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()
    selection = client.post(f"/api/candidates/{candidate['id']}/select", json={}, headers=hr_headers).json()

    tasks = client.get(f"/api/employees/{selection['employee_id']}/onboarding-tasks", headers=hr_headers).json()
    assert len(tasks) == 8
    assert all(t["status"] == "pending" for t in tasks)


def test_cannot_select_the_same_candidate_twice(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()
    client.post(f"/api/candidates/{candidate['id']}/select", json={}, headers=hr_headers)
    r = client.post(f"/api/candidates/{candidate['id']}/select", json={}, headers=hr_headers)
    assert r.status_code == 400


# ----------------------------------------------------------------- onboarding
def test_complete_an_onboarding_task(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)
    candidate = client.post(
        f"/api/public/vacancies/{vacancy_id}/apply", json={"full_name": "Pallavi Kalita", "email": "pallavi.k@gmail.com"}
    ).json()
    selection = client.post(f"/api/candidates/{candidate['id']}/select", json={}, headers=hr_headers).json()
    tasks = client.get(f"/api/employees/{selection['employee_id']}/onboarding-tasks", headers=hr_headers).json()

    r = client.put(f"/api/onboarding-tasks/{tasks[0]['id']}", json={"status": "done", "notes": "Collected"}, headers=hr_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["completed_at"] is not None


# ----------------------------------------------------------------- orientation
def test_orientation_session_attendance_and_candidate_confirmation(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)
    vacancy_id = _published_vacancy(client, db, hr_headers, _login(client, head), div.id)

    new_user = _make_user(db, "field_staff", email="pallavi.k@aaranyak.org")
    emp = Employee(employee_code="AAR-RHN-9999", full_name="Pallavi Kalita", division_id=div.id, employment_category=EmploymentCategory.regular, user_id=new_user.id)
    db.add(emp)
    db.commit()
    db.refresh(emp)

    session = client.post("/api/orientation-sessions", json={"title": "New Joiner Orientation"}, headers=hr_headers).json()
    attendance = client.post(
        f"/api/orientation-sessions/{session['id']}/attendees", json={"employee_id": emp.id}, headers=hr_headers
    ).json()

    marked = client.put(f"/api/orientation-attendance/{attendance['id']}/mark-attended", headers=hr_headers)
    assert marked.json()["attended"] is True

    confirmed = client.put(f"/api/orientation-attendance/{attendance['id']}/confirm", headers=_login(client, new_user))
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_by_candidate"] is True


def test_cannot_confirm_someone_elses_orientation(client, db):
    div = _make_division(db)
    hr = _make_user(db, "hr_admin")
    hr_headers = _login(client, hr)

    new_user = _make_user(db, "field_staff", email="a@aaranyak.org")
    other_user = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp = Employee(employee_code="AAR-RHN-8888", full_name="Someone", division_id=div.id, employment_category=EmploymentCategory.regular, user_id=new_user.id)
    db.add(emp)
    db.commit()
    db.refresh(emp)

    session = client.post("/api/orientation-sessions", json={"title": "Orientation"}, headers=hr_headers).json()
    attendance = client.post(f"/api/orientation-sessions/{session['id']}/attendees", json={"employee_id": emp.id}, headers=hr_headers).json()

    r = client.put(f"/api/orientation-attendance/{attendance['id']}/confirm", headers=_login(client, other_user))
    assert r.status_code == 403
