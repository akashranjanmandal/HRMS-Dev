"""Shared fixtures.

Integration tests run against a real Postgres database (``aaranyak_hrms_test``,
override with ``TEST_DATABASE_URL``). The schema is rebuilt once per session;
each test runs in a transaction that is rolled back afterwards.
"""
import os
import tempfile

import psycopg
import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/aaranyak_hrms_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="aaranyak-test-uploads-")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# The dev-only fixed OTP (app.core.config.Settings.DEV_FIXED_OTP) must not
# leak into the test suite, which exercises real random-OTP behaviour
# (e.g. that a wrong code is rejected).
os.environ["DEV_FIXED_OTP"] = ""


def _reset_test_database() -> None:
    dsn = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    base, name = dsn.rsplit("/", 1)
    with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


_reset_test_database()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_rate_limit_state():
    """The login/OTP rate limiter (app.core.rate_limit) keeps in-process
    state that DB transaction rollback never touches — clear it between
    tests so one test's attempts can't trip another's assertions."""
    from app.core.rate_limit import _attempts

    _attempts.clear()
    yield
    _attempts.clear()


@pytest.fixture()
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
