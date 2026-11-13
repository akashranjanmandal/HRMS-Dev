"""All tables. Import from here (``from app.models import User``) so every
model is registered on ``Base.metadata`` before the schema is built."""
from app.models.audit import AuditLog
from app.models.base import Base, utcnow
from app.models.identity import Permission, Role, User, role_permissions

__all__ = ["AuditLog", "Base", "Permission", "Role", "User", "role_permissions", "utcnow"]
