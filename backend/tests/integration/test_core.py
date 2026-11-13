import pytest
from sqlalchemy import inspect

from app.core import audit
from app.core.database import engine
from app.models import AuditLog

pytestmark = pytest.mark.integration


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_schema_built():
    assert {"users", "roles", "permissions", "role_permissions", "audit_logs"} <= set(inspect(engine).get_table_names())


def test_audit_log_without_actor(db):
    audit.log(db, None, "system.test", summary="hello")
    db.commit()
    assert db.query(AuditLog).filter_by(action="system.test").one().summary == "hello"
