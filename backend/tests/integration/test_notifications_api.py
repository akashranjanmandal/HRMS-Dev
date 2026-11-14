"""On-screen notifications (RFP 3.5, alongside email): a user's own feed of
alerts — pending approvals, deadlines, contract expiry, system
announcements — created by other modules as they land, read by the user
who owns them.
"""
import pytest

from app.core.security import hash_password
from app.models import Notification, Role, User

pytestmark = pytest.mark.integration


def _make_user(db, role_code="field_staff") -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(email=f"{role_code}@aaranyak.org", hashed_password=hash_password("Passw0rd!1"), role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, user: User) -> dict:
    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_notify_creates_a_row_for_the_right_user(db):
    from app.services.notify import notify

    user = _make_user(db)
    notify(db, user_id=user.id, kind="leave.approved", message="Your leave request was approved")
    db.commit()
    row = db.query(Notification).filter_by(user_id=user.id).one()
    assert row.kind == "leave.approved"
    assert row.message == "Your leave request was approved"
    assert row.read_at is None


def test_list_my_notifications_newest_first(client, db):
    from app.services.notify import notify

    user = _make_user(db)
    headers = _login(client, user)
    notify(db, user_id=user.id, kind="system", message="First")
    notify(db, user_id=user.id, kind="system", message="Second")
    db.commit()

    rows = client.get("/api/notifications", headers=headers).json()
    assert [r["message"] for r in rows] == ["Second", "First"]


def test_only_sees_own_notifications(client, db):
    from app.services.notify import notify

    me = _make_user(db, "field_staff")
    someone_else = _make_user(db, "project_staff")
    headers = _login(client, me)
    notify(db, user_id=someone_else.id, kind="system", message="Not yours")
    db.commit()

    rows = client.get("/api/notifications", headers=headers).json()
    assert rows == []


def test_unread_count(client, db):
    from app.services.notify import notify

    user = _make_user(db)
    headers = _login(client, user)
    notify(db, user_id=user.id, kind="system", message="One")
    notify(db, user_id=user.id, kind="system", message="Two")
    db.commit()

    assert client.get("/api/notifications/unread-count", headers=headers).json() == {"count": 2}


def test_mark_one_as_read(client, db):
    from app.services.notify import notify

    user = _make_user(db)
    headers = _login(client, user)
    notify(db, user_id=user.id, kind="system", message="One")
    db.commit()
    note_id = client.get("/api/notifications", headers=headers).json()[0]["id"]

    r = client.post(f"/api/notifications/{note_id}/read", headers=headers)
    assert r.status_code == 200
    assert r.json()["read_at"] is not None
    assert client.get("/api/notifications/unread-count", headers=headers).json() == {"count": 0}


def test_cannot_mark_someone_elses_notification_as_read(client, db):
    from app.services.notify import notify

    me = _make_user(db, "field_staff")
    someone_else = _make_user(db, "project_staff")
    headers = _login(client, me)
    note = notify(db, user_id=someone_else.id, kind="system", message="Not yours")
    db.commit()

    r = client.post(f"/api/notifications/{note.id}/read", headers=headers)
    assert r.status_code == 404


def test_mark_all_as_read(client, db):
    from app.services.notify import notify

    user = _make_user(db)
    headers = _login(client, user)
    notify(db, user_id=user.id, kind="system", message="One")
    notify(db, user_id=user.id, kind="system", message="Two")
    db.commit()

    r = client.post("/api/notifications/read-all", headers=headers)
    assert r.status_code == 204
    assert client.get("/api/notifications/unread-count", headers=headers).json() == {"count": 0}


def test_unauthenticated_is_401(client):
    assert client.get("/api/notifications").status_code == 401
