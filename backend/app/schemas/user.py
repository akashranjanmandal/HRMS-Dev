from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserIn(BaseModel):
    email: EmailStr
    role_code: str
    division_id: int | None = None


class UserOut(BaseModel):
    id: int
    email: str
    role_code: str
    role_name: str
    division_id: int | None
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


class UserCreatedOut(UserOut):
    temporary_password: str


class UserUpdateIn(BaseModel):
    role_code: str
    division_id: int | None = None


class UserActiveIn(BaseModel):
    is_active: bool


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    is_system: bool
    requires_mfa: bool
    permissions: list[str]


class RolePermissionsIn(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class PermissionCatalogueItem(BaseModel):
    code: str
    group: str
    description: str
