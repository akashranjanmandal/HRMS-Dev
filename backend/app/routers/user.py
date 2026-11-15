"""User accounts (RFP Section 9: admin manages logins and role
assignment). Creating a user issues a one-time temporary password by
email, in the same spirit as the sign-in flow's own OTP — the admin
never sets or sees anyone else's real password.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_can_grant_role, assert_can_manage_login, require_perm
from app.core.permissions import permission_code
from app.core.security import generate_temporary_password, hash_password
from app.models import Role, User
from app.schemas.user import UserActiveIn, UserCreatedOut, UserIn, UserOut, UserUpdateIn
from app.services import mailer

router = APIRouter(prefix="/api/users", tags=["Users"])

VIEW = require_perm(permission_code("user", "view"))
CREATE = require_perm(permission_code("user", "create"))
EDIT = require_perm(permission_code("user", "edit"))
DELETE = require_perm(permission_code("user", "delete"))


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, role_code=user.role.code, role_name=user.role.name,
        division_id=user.division_id, is_active=user.is_active, must_change_password=user.must_change_password,
        last_login_at=user.last_login_at, created_at=user.created_at,
    )


def _get_role_or_400(db: Session, role_code: str) -> Role:
    role = db.query(Role).filter_by(code=role_code).first()
    if role is None:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role_code}'")
    return role


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    rows = db.query(User).join(Role).filter(Role.is_hidden.is_(False)).order_by(User.email).all()
    return [_out(r) for r in rows]


@router.post("", response_model=UserCreatedOut, status_code=201)
def create_user(payload: UserIn, db: Session = Depends(get_db), actor: User = Depends(CREATE)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    role = _get_role_or_400(db, payload.role_code)
    assert_can_grant_role(actor, role)

    temp_password = generate_temporary_password()
    new_user = User(
        email=payload.email, hashed_password=hash_password(temp_password), role_id=role.id,
        division_id=payload.division_id, must_change_password=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    mailer.send_temporary_password_email(new_user.email, temp_password)
    return UserCreatedOut(**_out(new_user).model_dump(), temporary_password=temp_password)


def _get_user_or_404(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    return target


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdateIn, db: Session = Depends(get_db), actor: User = Depends(EDIT)):
    target = _get_user_or_404(db, user_id)
    assert_can_manage_login(actor, target)
    role = _get_role_or_400(db, payload.role_code)
    assert_can_grant_role(actor, role)

    target.role_id = role.id
    target.division_id = payload.division_id
    db.commit()
    db.refresh(target)
    return _out(target)


@router.put("/{user_id}/active", response_model=UserOut)
def set_user_active(user_id: int, payload: UserActiveIn, db: Session = Depends(get_db), actor: User = Depends(EDIT)):
    target = _get_user_or_404(db, user_id)
    assert_can_manage_login(actor, target)
    if target.id == actor.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return _out(target)


@router.post("/{user_id}/reset-password", response_model=UserCreatedOut)
def reset_password(user_id: int, db: Session = Depends(get_db), actor: User = Depends(EDIT)):
    target = _get_user_or_404(db, user_id)
    assert_can_manage_login(actor, target)

    temp_password = generate_temporary_password()
    target.hashed_password = hash_password(temp_password)
    target.must_change_password = True
    db.commit()
    db.refresh(target)

    mailer.send_temporary_password_email(target.email, temp_password)
    return UserCreatedOut(**_out(target).model_dump(), temporary_password=temp_password)


@router.delete("/{user_id}", status_code=204)
def deactivate_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(DELETE)):
    """Deletion is a deactivation, not a row delete — a user's past audit
    log, approval steps and authored records must keep pointing at someone."""
    target = _get_user_or_404(db, user_id)
    assert_can_manage_login(actor, target)
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    target.is_active = False
    db.commit()
