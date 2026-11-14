"""Authentication and permission dependencies.

Every permission is enforced here, on the backend, regardless of what the
frontend chooses to render.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Role, Session as SessionModel, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise CRED_EXC
    payload = decode_token(token)
    if payload is None:
        raise CRED_EXC
    user_id = payload.get("sub")
    if user_id is None:
        raise CRED_EXC

    # A token logged out (revoked) is refused even though its JWT signature
    # and expiry are still valid — see app.models.Session. A token with no
    # session row at all (minted outside the login flow) is unaffected.
    jti = payload.get("jti")
    if jti is not None:
        session_row = db.query(SessionModel).filter(SessionModel.jti == jti).first()
        if session_row is not None and session_row.revoked_at is not None:
            raise CRED_EXC

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise CRED_EXC
    if user.role is None or not user.role.is_active:
        raise HTTPException(status_code=403, detail="Your role is not active")
    return user


def require_perm(*codes: str):
    """Require every listed permission code."""

    def checker(user: User = Depends(get_current_user)) -> User:
        missing = [c for c in codes if not user.has_permission(c)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission for this action ({', '.join(missing)})",
            )
        return user

    return checker


def require_any_perm(*codes: str):
    """Require at least one of the listed permission codes."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if not any(user.has_permission(c) for c in codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action",
            )
        return user

    return checker


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def assert_can_grant_role(actor: User, role: Role) -> None:
    """Guard every place a login is given a role: hidden roles are never
    assignable through the API, and nobody grants more than they hold."""
    if role.is_hidden:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role.code}'")
    missing = [c for c in role.permission_codes if not actor.has_permission(c)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant the {role.name} role — it has permissions you do not hold",
        )


def assert_can_manage_login(actor: User, target: User) -> None:
    """Guard every action on someone else's login (password reset,
    activation, role or scope change): the actor must hold every permission
    of the target's role, so nobody can take over a more powerful account."""
    role = target.role
    if role is None:
        return
    if role.is_hidden and not (actor.role and actor.role.is_hidden):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage this account")
    if any(not actor.has_permission(c) for c in role.permission_codes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot manage a {role.name} account — it has permissions you do not hold",
        )
