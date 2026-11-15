"""All tables. Import from here (``from app.models import User``) so every
model is registered on ``Base.metadata`` before the schema is built."""
from app.models.appraisal import (
    AppraisalCycle,
    AppraisalRating,
    AppraisalReview,
    AppraisalStage,
)
from app.models.asset import Asset, AssetCategory, AssetCondition, AssetMovement, AssetStatus
from app.models.attendance import Attendance, AttendanceSource, AttendanceStatus
from app.models.audit import AuditLog
from app.models.base import Base, utcnow
from app.models.employee import Employee, EmployeeConfidential, EmploymentCategory, EmployeeStatus
from app.models.identity import Permission, Role, Session, User, role_permissions
from app.models.leave import LeaveApplication, LeaveBalance, LeaveStatus, LeaveType
from app.models.notification import Notification
from app.models.onboarding import (
    Candidate,
    Interview,
    OnboardingTask,
    OnboardingTaskStatus,
    OrientationAttendance,
    OrientationSession,
    Vacancy,
    VacancyStatus,
)
from app.models.organisation import Division, GeofenceShape, Project, Site, SiteKind
from app.models.payroll import PayrollRun, Payslip, SalaryStructure
from app.models.report import SavedReport
from app.models.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApproverKind,
    RequestType,
    WorkflowAction,
    WorkflowDefinition,
    WorkflowLevel,
)

__all__ = [
    "Asset",
    "AssetCategory",
    "AssetCondition",
    "AssetMovement",
    "AssetStatus",
    "Attendance",
    "AttendanceSource",
    "AttendanceStatus",
    "AppraisalCycle",
    "AppraisalRating",
    "AppraisalReview",
    "AppraisalStage",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStep",
    "ApproverKind",
    "AuditLog",
    "Base",
    "Candidate",
    "Division",
    "Employee",
    "EmployeeConfidential",
    "EmploymentCategory",
    "EmployeeStatus",
    "GeofenceShape",
    "Interview",
    "LeaveApplication",
    "LeaveBalance",
    "LeaveStatus",
    "LeaveType",
    "Notification",
    "OnboardingTask",
    "OnboardingTaskStatus",
    "OrientationAttendance",
    "OrientationSession",
    "PayrollRun",
    "Payslip",
    "Permission",
    "Project",
    "RequestType",
    "Role",
    "SalaryStructure",
    "SavedReport",
    "Session",
    "Site",
    "SiteKind",
    "User",
    "Vacancy",
    "VacancyStatus",
    "WorkflowAction",
    "WorkflowDefinition",
    "WorkflowLevel",
    "role_permissions",
    "utcnow",
]
