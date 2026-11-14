"""Bring an already-deployed database's permissions and roles up to date.

``seed.py`` builds RBAC from scratch, but a production database seeded
before a module existed never learns about that module's permissions. This
runs on every startup and only ever *adds*:

  * a permission code in ``PERMISSIONS`` that has no row yet is created and
    granted to every system role whose default set includes it;
  * a role in ``DEFAULT_ROLES`` that has no row yet is created with its
    full default permission set.

Permissions that already exist are left alone on every role, so anything
an Administrator removed from a role in the Roles screen stays removed.

``requires_mfa`` is different: it is a security policy, not a grantable
permission, so it is re-applied from ``DEFAULT_ROLES`` on every system
role every run — an Administrator cannot silently weaken MFA on a
confidential-data role by forgetting it was ever set. A non-system
(custom) role's ``requires_mfa`` is never touched here; the Administrator
who creates a custom role sets it explicitly.
"""
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_ROLES, PERMISSIONS
from app.models import Permission, Role


def sync_rbac(db: Session) -> None:
    existing = {p.code: p for p in db.query(Permission).all()}
    new_codes: set[str] = set()
    for code, group, description in PERMISSIONS:
        if code not in existing:
            perm = Permission(code=code, group=group, description=description)
            db.add(perm)
            existing[code] = perm
            new_codes.add(code)
    db.flush()

    for code, name, description, permission_codes, is_system, is_hidden, requires_mfa in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.code == code).first()
        if role is None:
            db.add(
                Role(
                    code=code,
                    name=name,
                    description=description,
                    is_system=is_system,
                    is_hidden=is_hidden,
                    requires_mfa=requires_mfa,
                    permissions=[existing[c] for c in permission_codes],
                )
            )
            continue
        if is_system:
            role.requires_mfa = requires_mfa
        held = {p.code for p in role.permissions}
        for c in permission_codes:
            if c in new_codes and c not in held:
                role.permissions.append(existing[c])
    db.commit()
