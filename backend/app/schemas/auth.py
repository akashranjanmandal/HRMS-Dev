from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    mfa_required: bool
    access_token: str | None = None
    token_type: str = "bearer"


class VerifyOtpIn(BaseModel):
    email: EmailStr
    code: str


class MeOut(BaseModel):
    id: int
    email: str
    role_code: str
    role_name: str
    permissions: list[str]
