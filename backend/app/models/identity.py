"""Logins, roles and permissions."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    group: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(String(200), default="")

    roles: Mapped[list["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Email one-time code required after password, on top of it (RFP 3.7,
    # 13: "optional two-step login"). A system policy, not a personal
    # choice — set true for roles that see confidential data.
    requires_mfa: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )
    users: Mapped[list["User"]] = relationship(back_populates="role")

    @property
    def permission_codes(self) -> list[str]:
        return sorted(p.code for p in self.permissions)


class User(Base):
    """A login. Passwords are stored only as bcrypt hashes."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_token_hash: Mapped[str] = mapped_column(String(255), default="")
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # One-time code (MFA), issued after a correct password for a role with
    # requires_mfa. Cleared once verified or once a fresh one is issued.
    otp_hash: Mapped[str] = mapped_column(String(255), default="")
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The one division this login is scoped to, when their role implies
    # Scope.division (a Division Head) — see app.core.scope.scope_for_role.
    # None for an organisation-scoped role, and also None for an
    # unassigned Division Head, who then sees nothing, never everything.
    # use_alter: divisions.head_user_id already points at users.id, so
    # this is a genuine circular FK between the two tables — without
    # use_alter, SQLAlchemy cannot pick a creation order for either table.
    division_id: Mapped[int | None] = mapped_column(
        ForeignKey("divisions.id", use_alter=True, name="fk_user_division"), nullable=True
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="selectin")

    def has_permission(self, code: str) -> bool:
        if not self.is_active or self.role is None or not self.role.is_active:
            return False
        return any(p.code == code for p in self.role.permissions)


class Session(Base):
    """A signed-in session, keyed by the JWT's own id (``jti``).

    JWTs are stateless by design, so "log out" needs a server-side record
    of which tokens are still valid — this table is it. ``get_current_user``
    checks a token's ``jti`` is present and not revoked here before trusting
    it; ``/auth/logout`` revokes it. Expired/old rows are left for the
    administrator to prune on a schedule — not needed for correctness, only
    for table size.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
