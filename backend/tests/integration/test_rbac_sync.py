"""sync_rbac populates the 10 RFP roles and the permission catalogue on a
fresh database, and only ever adds — it never strips an administrator's
own customisation to a role's permissions."""
import pytest

from app.core.permissions import DEFAULT_ROLES, PERMISSIONS
from app.core.rbac_sync import sync_rbac
from app.models import Permission, Role

pytestmark = pytest.mark.integration


def test_sync_creates_every_permission_and_role(db):
    sync_rbac(db)
    assert db.query(Permission).count() == len(PERMISSIONS)
    assert db.query(Role).count() == len(DEFAULT_ROLES)
    codes = {r.code for r in db.query(Role).all()}
    assert codes == {r[0] for r in DEFAULT_ROLES}


def test_sync_is_idempotent(db):
    sync_rbac(db)
    sync_rbac(db)
    assert db.query(Permission).count() == len(PERMISSIONS)
    assert db.query(Role).count() == len(DEFAULT_ROLES)


def test_sync_grants_the_rfp_bundle_to_each_role(db):
    sync_rbac(db)
    admin = db.query(Role).filter_by(code="admin").one()
    assert len(admin.permission_codes) == len(PERMISSIONS)

    field_staff = db.query(Role).filter_by(code="field_staff").one()
    assert len(field_staff.permission_codes) > 0
    assert len(field_staff.permission_codes) < len(PERMISSIONS)


def test_sync_never_removes_an_administrators_own_customisation(db):
    sync_rbac(db)
    hr = db.query(Role).filter_by(code="hr_admin").one()
    original_count = len(hr.permissions)
    # Admin manually strips one permission from HR's role.
    removed = hr.permissions[0]
    hr.permissions = hr.permissions[1:]
    db.commit()

    sync_rbac(db)  # re-run, as happens on every app startup
    db.refresh(hr)
    assert removed.code not in hr.permission_codes
    assert len(hr.permissions) == original_count - 1


def test_sync_sets_requires_mfa_for_confidential_roles(db):
    sync_rbac(db)
    admin = db.query(Role).filter_by(code="admin").one()
    hr = db.query(Role).filter_by(code="hr_admin").one()
    finance = db.query(Role).filter_by(code="finance").one()
    field_staff = db.query(Role).filter_by(code="field_staff").one()
    assert admin.requires_mfa is True
    assert hr.requires_mfa is True
    assert finance.requires_mfa is True
    assert field_staff.requires_mfa is False
