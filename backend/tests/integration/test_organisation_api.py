"""Divisions, projects and sites — the organisation structure.

Masters are managed by an administrator, with no code change needed
(RFP 3.2), and sites carry an optional geo-fence used for attendance.
"""
import pytest

pytestmark = pytest.mark.integration


def _admin_role(db):
    from app.models import Permission, Role
    role = Role(code="admin", name="System Administrator", is_system=True)
    role.permissions = db.query(Permission).all()
    db.add(role)
    db.flush()
    return role


def _login(db, client, role_code="admin"):
    from app.core.security import create_access_token, hash_password
    from app.models import Role, User

    role = db.query(Role).filter_by(code=role_code).first()
    if role is None:
        role = _admin_role(db) if role_code == "admin" else None
    user = User(email=f"{role_code}@aaranyak.org", hashed_password=hash_password("Passw0rd!1"), role_id=role.id)
    db.add(user)
    db.commit()
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}, user


# --------------------------------------------------------------- divisions
def test_create_and_list_divisions(client, db):
    headers, _ = _login(db, client)
    r = client.post("/api/divisions", json={"name": "Rhino Research", "code": "RHN"}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Rhino Research"
    assert body["code"] == "RHN"

    rows = client.get("/api/divisions", headers=headers).json()
    assert [d["name"] for d in rows] == ["Rhino Research"]


def test_division_code_must_be_unique(client, db):
    headers, _ = _login(db, client)
    client.post("/api/divisions", json={"name": "Rhino Research", "code": "RHN"}, headers=headers)
    r = client.post("/api/divisions", json={"name": "Rhino Again", "code": "RHN"}, headers=headers)
    assert r.status_code == 409


def test_division_head_assignment(client, db):
    headers, admin_user = _login(db, client)
    div = client.post("/api/divisions", json={"name": "Elephant Research", "code": "ELE"}, headers=headers).json()
    r = client.put(f"/api/divisions/{div['id']}", json={"head_user_id": admin_user.id}, headers=headers)
    assert r.status_code == 200
    assert r.json()["head_user_id"] == admin_user.id


def test_deactivate_division_keeps_it_but_hides_from_default_list(client, db):
    headers, _ = _login(db, client)
    div = client.post("/api/divisions", json={"name": "Legal & Advocacy", "code": "LEG"}, headers=headers).json()
    client.put(f"/api/divisions/{div['id']}", json={"is_active": False}, headers=headers)
    assert client.get("/api/divisions", headers=headers).json() == []
    assert len(client.get("/api/divisions", params={"include_inactive": True}, headers=headers).json()) == 1


def test_unauthenticated_request_is_401(client):
    assert client.get("/api/divisions").status_code == 401


# ----------------------------------------------------------------- projects
def test_create_project_linked_to_a_division(client, db):
    headers, _ = _login(db, client)
    div = client.post("/api/divisions", json={"name": "Rhino Research", "code": "RHN"}, headers=headers).json()
    r = client.post(
        "/api/projects",
        json={"name": "Rhino Count 2026", "code": "RC26", "division_id": div["id"], "donor": "WWF"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["division_id"] == div["id"]


def test_project_requires_a_real_division(client, db):
    headers, _ = _login(db, client)
    r = client.post("/api/projects", json={"name": "Orphan Project", "code": "ORP", "division_id": 999}, headers=headers)
    assert r.status_code == 400


def test_list_projects_filtered_by_division(client, db):
    headers, _ = _login(db, client)
    div_a = client.post("/api/divisions", json={"name": "Rhino Research", "code": "RHN"}, headers=headers).json()
    div_b = client.post("/api/divisions", json={"name": "Elephant Research", "code": "ELE"}, headers=headers).json()
    client.post("/api/projects", json={"name": "Rhino Count 2026", "code": "RC26", "division_id": div_a["id"]}, headers=headers)
    client.post("/api/projects", json={"name": "Elephant Corridor", "code": "ECR", "division_id": div_b["id"]}, headers=headers)

    rows = client.get("/api/projects", params={"division_id": div_a["id"]}, headers=headers).json()
    assert [p["name"] for p in rows] == ["Rhino Count 2026"]


# -------------------------------------------------------------------- sites
def test_create_office_site_without_geofence(client, db):
    headers, _ = _login(db, client)
    r = client.post("/api/sites", json={"name": "Guwahati Head Office", "kind": "office"}, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["geofence"] is None


def test_create_field_site_with_circle_geofence(client, db):
    headers, _ = _login(db, client)
    r = client.post(
        "/api/sites",
        json={
            "name": "Kaziranga Field Station",
            "kind": "field",
            "geofence": {"shape": "circle", "center_lat": 26.5775, "center_lng": 93.1711, "radius_m": 150},
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["geofence"]["shape"] == "circle"


def test_create_field_site_with_polygon_geofence(client, db):
    headers, _ = _login(db, client)
    points = [[26.57, 93.17], [26.58, 93.17], [26.58, 93.18], [26.57, 93.18]]
    r = client.post(
        "/api/sites",
        json={"name": "Manas Range Office", "kind": "field", "geofence": {"shape": "polygon", "points": points}},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["geofence"]["points"] == points


def test_polygon_geofence_needs_at_least_three_points(client, db):
    headers, _ = _login(db, client)
    r = client.post(
        "/api/sites",
        json={"name": "Bad Site", "kind": "field", "geofence": {"shape": "polygon", "points": [[0, 0], [1, 1]]}},
        headers=headers,
    )
    assert r.status_code == 422


def test_circle_geofence_needs_positive_radius(client, db):
    headers, _ = _login(db, client)
    r = client.post(
        "/api/sites",
        json={"name": "Bad Site", "kind": "field", "geofence": {"shape": "circle", "center_lat": 1, "center_lng": 1, "radius_m": 0}},
        headers=headers,
    )
    assert r.status_code == 422


def test_check_point_endpoint_reports_inside_or_outside(client, db):
    headers, _ = _login(db, client)
    site = client.post(
        "/api/sites",
        json={
            "name": "Kaziranga Field Station",
            "kind": "field",
            "geofence": {"shape": "circle", "center_lat": 26.5775, "center_lng": 93.1711, "radius_m": 150},
        },
        headers=headers,
    ).json()

    inside = client.post(f"/api/sites/{site['id']}/check-point", json={"lat": 26.5775, "lng": 93.1711}, headers=headers)
    assert inside.status_code == 200 and inside.json()["inside"] is True

    outside = client.post(f"/api/sites/{site['id']}/check-point", json={"lat": 26.60, "lng": 93.20}, headers=headers)
    assert outside.status_code == 200 and outside.json()["inside"] is False


def test_check_point_on_site_without_geofence_is_404(client, db):
    headers, _ = _login(db, client)
    site = client.post("/api/sites", json={"name": "Guwahati Head Office", "kind": "office"}, headers=headers).json()
    r = client.post(f"/api/sites/{site['id']}/check-point", json={"lat": 1, "lng": 1}, headers=headers)
    assert r.status_code == 404


def test_site_can_be_linked_to_a_division(client, db):
    headers, _ = _login(db, client)
    div = client.post("/api/divisions", json={"name": "Rhino Research", "code": "RHN"}, headers=headers).json()
    r = client.post("/api/sites", json={"name": "Kaziranga Field Station", "kind": "field", "division_id": div["id"]}, headers=headers)
    assert r.status_code == 201
    assert r.json()["division_id"] == div["id"]
