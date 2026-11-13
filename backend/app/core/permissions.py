"""Permission catalogue and the 10 default RFP roles (RFP Section 9).

Every permission is ``<module>:<action>``. Seven action types, per module,
mirror the RFP's own wording exactly: view, create, edit, delete, approve
(approve/reject), export, admin (module configuration).

Not every module needs every action (there is nothing to "approve" about
the asset register's catalogue, say) — each module declares only the
actions that make sense for it. A role's reach within those permissions
("my division only", "my own records") is a separate axis, handled by
``app.core.scope``, not baked into the permission code.
"""
from dataclasses import dataclass


def permission_code(module: str, action: str) -> str:
    return f"{module}:{action}"


@dataclass(frozen=True)
class ModuleDef:
    key: str
    group: str
    label: str
    actions: tuple[str, ...] = ("view", "create", "edit", "delete", "export")


# Modules a permission can apply to, grouped the way the RFP groups them.
# (key, group, label, actions)
MODULE_DEFS: list[ModuleDef] = [
    ModuleDef("employee", "People", "Employee records", ("view", "create", "edit", "delete", "export")),
    ModuleDef("organisation", "People", "Divisions, projects, sites", ("view", "create", "edit", "delete")),
    ModuleDef("recruitment", "People", "Recruitment and hiring", ("view", "create", "edit", "delete", "approve")),
    ModuleDef("onboarding", "People", "Onboarding and orientation", ("view", "create", "edit", "approve")),
    ModuleDef("attendance", "Time", "Attendance", ("view", "create", "edit", "approve", "export")),
    ModuleDef("leave", "Time", "Leave", ("view", "create", "edit", "approve", "export")),
    ModuleDef("appraisal", "Performance", "Performance appraisal", ("view", "create", "edit", "approve", "export")),
    ModuleDef("asset", "Assets", "Asset register", ("view", "create", "edit", "delete", "approve", "export")),
    ModuleDef("payroll", "Finance", "Payroll", ("view", "create", "edit", "approve", "export")),
    ModuleDef("report", "Reports", "Dashboards and reports", ("view", "export")),
    ModuleDef("document", "Documents", "Document management", ("view", "create", "edit", "delete")),
    ModuleDef("user", "Admin", "User accounts", ("view", "create", "edit", "delete")),
    ModuleDef("role", "Admin", "Roles and permissions", ("view", "edit", "admin")),
    ModuleDef("workflow", "Admin", "Approval workflow configuration", ("view", "admin")),
    ModuleDef("settings", "Admin", "System settings", ("view", "admin")),
    ModuleDef("audit", "Admin", "Audit trail", ("view", "export")),
]

MODULES: tuple[str, ...] = tuple(m.key for m in MODULE_DEFS)

ACTION_LABELS = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve / reject",
    "export": "Export",
    "admin": "Administer",
}

PERMISSIONS: list[tuple[str, str, str]] = [
    (permission_code(m.key, action), m.group, f"{ACTION_LABELS[action]} — {m.label}")
    for m in MODULE_DEFS
    for action in m.actions
]

_ALL_CODES: list[str] = [p[0] for p in PERMISSIONS]


def _codes(*, modules: tuple[str, ...] = MODULES, actions: tuple[str, ...] | None = None) -> list[str]:
    """Every registered code for the given modules, optionally filtered to
    a subset of actions (codes that don't exist for a module are skipped)."""
    wanted = set(actions) if actions is not None else None
    return [
        permission_code(m.key, a)
        for m in MODULE_DEFS
        if m.key in modules
        for a in m.actions
        if wanted is None or a in wanted
    ]


# ---------------------------------------------------------------------------
# The 10 RFP roles (Section 9). Each tuple: (code, name, description,
# permission codes, is_system, is_hidden).
# ---------------------------------------------------------------------------
_VIEW_ALL = _codes(actions=("view",))

_HR_ADMIN_PERMS = [c for c in _ALL_CODES if c not in _codes(modules=("role",), actions=("admin",))]

_DIVISION_HEAD_PERMS = _codes(
    modules=("employee", "organisation", "attendance", "leave", "appraisal", "asset", "report", "document"),
    actions=("view", "edit", "approve", "export"),
) + _codes(modules=("employee",), actions=("create",))

_PROJECT_LEAD_PERMS = _codes(
    modules=("employee", "attendance", "leave", "asset", "report", "document"),
    actions=("view", "approve", "export"),
)

_COORDINATOR_PERMS = _codes(
    modules=("attendance", "leave", "document"), actions=("view", "create", "edit")
) + _codes(modules=("employee", "asset", "report"), actions=("view",))

_PROJECT_STAFF_PERMS = _codes(
    modules=("attendance", "leave", "asset", "document"), actions=("view", "create")
)

_FIELD_STAFF_PERMS = _codes(modules=("attendance", "leave"), actions=("view", "create"))

_FINANCE_PERMS = _codes(
    modules=("payroll", "report"), actions=("view", "create", "edit", "approve", "export")
) + _codes(modules=("employee", "asset"), actions=("view",))

_EXECUTIVE_PERMS = _VIEW_ALL + _codes(modules=("report",), actions=("export",))

DEFAULT_ROLES: list[tuple[str, str, str, list[str], bool, bool]] = [
    (
        "admin",
        "System Administrator",
        "Full system access: configuration, roles, users, every module.",
        list(_ALL_CODES),
        True,
        False,
    ),
    (
        "hr_admin",
        "HR / Admin",
        "Full operational access to every HR module; does not manage roles.",
        _HR_ADMIN_PERMS,
        True,
        False,
    ),
    (
        "finance",
        "Finance and Accounts",
        "Payroll, financial reports, read-only view of staff and assets for costing.",
        _FINANCE_PERMS,
        True,
        False,
    ),
    (
        "executive",
        "Executive Management",
        "Organisation-wide read access and exportable reports; no editing rights.",
        _EXECUTIVE_PERMS,
        True,
        False,
    ),
    (
        "division_head",
        "Division Head",
        "Manages one division: its staff, attendance, leave, appraisal and assets.",
        _DIVISION_HEAD_PERMS,
        True,
        False,
    ),
    (
        "project_lead",
        "Project Lead / PI",
        "Approves for their own project(s): attendance, leave, assets, reports.",
        _PROJECT_LEAD_PERMS,
        True,
        False,
    ),
    (
        "coordinator",
        "Project Coordinator",
        "Day-to-day project administration: attendance, leave and documents.",
        _COORDINATOR_PERMS,
        True,
        False,
    ),
    (
        "project_staff",
        "Project Staff",
        "Self-service: own attendance, leave, assets and documents.",
        _PROJECT_STAFF_PERMS,
        True,
        False,
    ),
    (
        "field_staff",
        "Field Staff",
        "Self-service from the field: own attendance (geo-fenced) and leave.",
        _FIELD_STAFF_PERMS,
        True,
        False,
    ),
    (
        "other_authorised",
        "Other Authorised User",
        "View-only access granted case by case (e.g. auditors, donors).",
        _VIEW_ALL,
        True,
        False,
    ),
]
