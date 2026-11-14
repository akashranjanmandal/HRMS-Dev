"""Sign-in (RFP 3.1, 3.7, 13): password login, an email one-time code for
roles that see confidential data, logout, and every sign-in/sign-out
audited.

Flow:
    POST /auth/login       email + password -> mfa_required flag, and an
                            access_token only when no OTP step is needed.
    POST /auth/verify-otp  email + code -> access_token (completes login
                            for a role with requires_mfa).
    POST /auth/logout      revokes the current session; the bearer token
                            is refused from then on even though its JWT
                            signature and expiry are still valid.
    GET  /auth/me          the signed-in user's own identity and permissions.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import audit
from app.core.database import get_db
from app.core.deps import client_ip, get_current_user
from app.core.security import (
    create_access_token,
    decode_token,
    generate_otp,
    hash_otp,
    otp_expiry,
    verify_otp,
    verify_password,
)
from app.models import Session as SessionModel, User
from app.schemas.auth import LoginIn, LoginOut, MeOut, VerifyOtpIn
from app.services import mailer

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# A separate bearer extractor for the logout endpoint, matching the one
# behind get_current_user, so logout can read the token's own jti after
# get_current_user has already confirmed it is valid and not yet revoked.
_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def _issue_session_token(db: Session, user: User) -> str:
    token = create_access_token({"sub": str(user.id)})
    payload = decode_token(token)
    db.add(SessionModel(jti=payload["jti"], user_id=user.id))
    user.last_login_at = datetime.now(timezone.utc)
    return token


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        audit.log(
            db,
            None,
            "auth.login_failed",
            actor_email=payload.email,
            summary=f"Failed sign-in attempt for {payload.email}",
            ip=client_ip(request),
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if user.role is not None and user.role.requires_mfa:
        code = generate_otp()
        user.otp_hash = hash_otp(code)
        user.otp_expires_at = otp_expiry()
        db.commit()
        mailer.send_otp_email(user.email, code)
        return LoginOut(mfa_required=True)

    token = _issue_session_token(db, user)
    audit.log(db, user, "auth.login", summary=f"{user.email} signed in", ip=client_ip(request))
    db.commit()
    return LoginOut(mfa_required=False, access_token=token)


@router.post("/verify-otp", response_model=LoginOut)
def verify_otp_route(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    bad_code = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect or expired code")

    if user is None or not user.otp_hash or user.otp_expires_at is None:
        raise bad_code
    if user.otp_expires_at < datetime.now(timezone.utc):
        raise bad_code
    if not verify_otp(payload.code, user.otp_hash):
        raise bad_code

    # One-time: clear immediately so the same code cannot be replayed.
    user.otp_hash = ""
    user.otp_expires_at = None

    token = _issue_session_token(db, user)
    audit.log(db, user, "auth.login", summary=f"{user.email} signed in (OTP verified)", ip=client_ip(request))
    db.commit()
    return LoginOut(mfa_required=False, access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    token: str | None = Depends(_bearer),
):
    payload = decode_token(token) if token else None
    jti = payload.get("jti") if payload else None
    if jti is not None:
        session_row = db.query(SessionModel).filter(SessionModel.jti == jti).first()
        if session_row is None:
            # A token minted without session tracking (see
            # create_access_token's docstring) — nothing to revoke, but the
            # logout attempt itself is still a real, auditable event.
            session_row = SessionModel(jti=jti, user_id=user.id)
            db.add(session_row)
        session_row.revoked_at = datetime.now(timezone.utc)

    audit.log(db, user, "auth.logout", summary=f"{user.email} signed out", ip=client_ip(request))
    db.commit()


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(
        id=user.id,
        email=user.email,
        role_code=user.role.code,
        role_name=user.role.name,
        permissions=user.role.permission_codes,
    )
