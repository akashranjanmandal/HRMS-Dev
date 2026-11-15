"""Roles and permissions (RFP Section 9). The 10 RFP roles are seeded as
system roles and cannot be deleted; an administrator may still adjust a
*non-system* role's permission set (custom roles created for case-by-case
access, e.g. a narrower "Other Authorised" variant) — see
app.core.rbac_sync for why system roles themselves are re-synced, not
hand-edited, at every startup.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perm
from app.core.permissions import PERMISSIONS, _ALL_CODES
from app.models import Role, User
from app.schemas.user import PermissionCatalogueItem, RoleOut, RolePermissionsIn

router = APIRouter(prefix="/api/roles", tags=["Roles"])

VIEW = require_perm("role:view")
ADMIN = require_perm("role:admin")


def _out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id, code=role.code, name=role.name, description=role.description,
        is_system=role.is_system, requires_mfa=role.requires_mfa, permissions=role.permission_codes,
    )


@router.get("", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    rows = db.query(Role).filter(Role.is_hidden.is_(False)).order_by(Role.name).all()
    return [_out(r) for r in rows]


@router.get("/permissions", response_model=list[PermissionCatalogueItem])
def list_permission_catalogue(user: User = Depends(VIEW)):
    return [PermissionCatalogueItem(code=code, group=group, description=desc) for code, group, desc in PERMISSIONS]


@router.put("/{role_id}/permissions", response_model=RoleOut)
def set_role_permissions(role_id: int, payload: RolePermissionsIn, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    from app.models import Permission

    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles are managed by the RFP's own role definitions, not edited here")

    unknown = [c for c in payload.permissions if c not in _ALL_CODES]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown permission code(s): {', '.join(unknown)}")

    role.permissions = db.query(Permission).filter(Permission.code.in_(payload.permissions)).all()
    db.commit()
    db.refresh(role)
    return _out(role)
