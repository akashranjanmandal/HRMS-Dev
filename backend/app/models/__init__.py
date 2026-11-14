"""All tables. Import from here (``from app.models import User``) so every
model is registered on ``Base.metadata`` before the schema is built."""
from app.models.audit import AuditLog
from app.models.base import Base, utcnow
from app.models.employee import Employee, EmployeeConfidential, EmploymentCategory, EmployeeStatus
from app.models.identity import Permission, Role, Session, User, role_permissions
from app.models.notification import Notification
from app.models.organisation import Division, GeofenceShape, Project, Site, SiteKind

__all__ = [
    "AuditLog",
    "Base",
    "Division",
    "Employee",
    "EmployeeConfidential",
    "EmploymentCategory",
    "EmployeeStatus",
    "GeofenceShape",
    "Notification",
    "Permission",
    "Project",
    "Role",
    "Session",
    "Site",
    "SiteKind",
    "User",
    "role_permissions",
    "utcnow",
]
