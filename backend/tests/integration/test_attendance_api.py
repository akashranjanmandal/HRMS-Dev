"""Attendance (RFP 4.1 §4.5): geo-fenced check-in/out with selfie, field
duty outside every boundary, regularisation.
"""
import base64
import io

import pytest
from PIL import Image

from app.core.security import hash_password
from app.models import Division, Employee, EmploymentCategory, Role, Site, User

pytestmark = pytest.mark.integration

# Kaziranga Field Station (matches the design mockups): circle, 150 m.
SITE_LAT, SITE_LNG = 26.5775, 93.1711
INSIDE_LAT, INSIDE_LNG = 26.5775, 93.1711  # exact center, always inside
OUTSIDE_LAT, OUTSIDE_LNG = 26.60, 93.20  # several km away


def _fake_selfie_b64() -> str:
    img = Image.new("RGB", (1200, 1600), color=(100, 120, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode()


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


def _make_employee(db, division_id, user) -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name="Field Employee",
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
        user_id=user.id,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _make_site(db) -> Site:
    site = Site(
        name="Kaziranga Field Station",
        kind="field",
        geofence_shape="circle",
        geofence_center_lat=SITE_LAT,
        geofence_center_lng=SITE_LNG,
        geofence_radius_m=150,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ------------------------------------------------------------------ check-in
def test_check_in_inside_geofence_marks_present(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    site = _make_site(db)

    headers = _login(client, staff)
    r = client.post(
        "/api/attendance/check-in",
        json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "present"
    assert body["is_within_geofence"] is True
    assert body["site_id"] == site.id


def test_check_in_outside_every_fence_without_reason_is_rejected(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)

    headers = _login(client, staff)
    r = client.post(
        "/api/attendance/check-in",
        json={"lat": OUTSIDE_LAT, "lng": OUTSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()},
        headers=headers,
    )
    assert r.status_code == 422


def test_check_in_outside_fence_with_reason_becomes_field_duty_pending_approval(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)

    headers = _login(client, staff)
    r = client.post(
        "/api/attendance/check-in",
        json={
            "lat": OUTSIDE_LAT,
            "lng": OUTSIDE_LNG,
            "accuracy_m": 12,
            "selfie_base64": _fake_selfie_b64(),
            "field_duty_reason": "Camera-trap check, Bhuyanpara range",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending_approval"
    assert body["source"] == "field_duty"
    assert body["approval_request_id"] is not None


def test_poor_accuracy_reading_inside_fence_is_not_trusted(client, db):
    """RFP 4.5's 'accuracy check': a bad GPS fix must not silently count as
    inside the boundary even if the coordinates happen to match."""
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)

    headers = _login(client, staff)
    r = client.post(
        "/api/attendance/check-in",
        json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 500, "selfie_base64": _fake_selfie_b64()},
        headers=headers,
    )
    assert r.status_code == 422  # no field_duty_reason given, and accuracy is untrustworthy


def test_cannot_check_in_twice_same_day(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    r = client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    assert r.status_code == 400


def test_selfie_is_compressed_to_about_100kb(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    from app.core.config import settings

    today = client.get("/api/attendance/today", headers=headers).json()
    stored = settings.upload_path / "selfies" / str(emp.id)
    files = list(stored.glob("*.jpg"))
    assert len(files) == 1
    assert files[0].stat().st_size <= 150 * 1024  # well under the 100 KB target with headroom


def test_invalid_base64_selfie_rejected(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    r = client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": "not-an-image!!"}, headers=headers
    )
    assert r.status_code == 400


# ----------------------------------------------------------------- check-out
def test_check_out_after_check_in(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    r = client.post("/api/attendance/check-out", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG}, headers=headers)
    assert r.status_code == 200
    assert r.json()["check_out_at"] is not None


def test_cannot_check_out_without_checking_in(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    headers = _login(client, staff)
    r = client.post("/api/attendance/check-out", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG}, headers=headers)
    assert r.status_code == 400


def test_cannot_check_out_twice(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)
    client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    client.post("/api/attendance/check-out", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG}, headers=headers)
    r = client.post("/api/attendance/check-out", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG}, headers=headers)
    assert r.status_code == 400


# -------------------------------------------------------- field duty approval
def test_division_head_approves_field_duty(client, db):
    """The default attendance_regularisation workflow has two levels
    (Division Head, then HR — see app/services/workflow_seed.py), so the
    first approval advances rather than finalises."""
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)

    headers = _login(client, staff)
    r = client.post(
        "/api/attendance/check-in",
        json={"lat": OUTSIDE_LAT, "lng": OUTSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64(), "field_duty_reason": "Survey"},
        headers=headers,
    )
    approval_id = r.json()["approval_request_id"]

    head_headers = _login(client, head)
    resp = client.post(f"/api/approvals/{approval_id}/decide", json={"action": "approve"}, headers=head_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    assert resp.json()["current_level_order"] == 2

    hr_headers = _login(client, hr)
    final = client.post(f"/api/approvals/{approval_id}/decide", json={"action": "approve"}, headers=hr_headers)
    assert final.json()["status"] == "approved"


# --------------------------------------------------------------- regularise
def test_regularisation_submitted_for_approval(client, db):
    from datetime import date, timedelta

    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    headers = _login(client, staff)

    yesterday = date.today() - timedelta(days=1)
    r = client.post(
        "/api/attendance/regularise", json={"work_date": str(yesterday), "reason": "Forgot to check out; left 17:40"}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_approval"
    assert r.json()["approval_request_id"] is not None


# ---------------------------------------------------------------- my history
def test_my_history_and_today(client, db):
    div = _make_division(db)
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    assert client.get("/api/attendance/today", headers=headers).json() is None
    client.post(
        "/api/attendance/check-in", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()}, headers=headers
    )
    assert client.get("/api/attendance/today", headers=headers).json() is not None
    assert len(client.get("/api/attendance/mine", headers=headers).json()) == 1


# --------------------------------------------------------------------- register
def test_daily_register_scoped_to_division(client, db):
    div_a = Division(name="Rhino Research", code="RHN")
    div_b = Division(name="Elephant Research", code="ELE")
    db.add_all([div_a, div_b])
    db.commit()
    head_a = _make_user(db, "division_head", division_id=div_a.id)
    staff_a = _make_user(db, "field_staff", email="a@aaranyak.org")
    staff_b = _make_user(db, "field_staff", email="b@aaranyak.org")
    emp_a = _make_employee(db, div_a.id, staff_a)
    emp_b = _make_employee(db, div_b.id, staff_b)
    _make_site(db)

    client.post(
        "/api/attendance/check-in",
        json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()},
        headers=_login(client, staff_a),
    )
    client.post(
        "/api/attendance/check-in",
        json={"lat": INSIDE_LAT, "lng": INSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64()},
        headers=_login(client, staff_b),
    )

    r = client.get("/api/attendance/register", headers=_login(client, head_a))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["employee_id"] == emp_a.id


def test_unauthenticated_is_401(client):
    assert client.get("/api/attendance/today").status_code == 401


def test_approved_field_duty_updates_attendance_status(client, db):
    div = _make_division(db)
    head = _make_user(db, "division_head", division_id=div.id)
    hr = _make_user(db, "hr_admin")
    staff = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, staff)
    _make_site(db)
    headers = _login(client, staff)

    r = client.post(
        "/api/attendance/check-in",
        json={"lat": OUTSIDE_LAT, "lng": OUTSIDE_LNG, "accuracy_m": 12, "selfie_base64": _fake_selfie_b64(), "field_duty_reason": "Survey"},
        headers=headers,
    )
    approval_id = r.json()["approval_request_id"]

    client.post(f"/api/approvals/{approval_id}/decide", json={"action": "approve"}, headers=_login(client, head))
    client.post(f"/api/approvals/{approval_id}/decide", json={"action": "approve"}, headers=_login(client, hr))

    today = client.get("/api/attendance/today", headers=headers).json()
    assert today["status"] == "present"
