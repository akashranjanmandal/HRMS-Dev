"""Default approval chains per request type — a sensible starting
configuration the administrator can change at any time through the
workflow admin API (RFP: "approval levels per request type are set by the
administrator"). Run once at startup, idempotent like ``sync_rbac``: it
only creates a definition that doesn't exist yet, and never touches one
an administrator has already configured.
"""
from sqlalchemy.orm import Session

from app.models import ApproverKind, RequestType, WorkflowDefinition, WorkflowLevel

# (request_type, name, [(label, role_code), ...])
_DEFAULTS: list[tuple[RequestType, str, list[tuple[str, str]]]] = [
    (RequestType.leave, "Leave approval", [("Division Head", "division_head")]),
    (
        RequestType.attendance_regularisation,
        "Attendance regularisation",
        [("Division Head", "division_head"), ("HR", "hr_admin")],
    ),
    (RequestType.asset_issue, "Asset issue", [("Division Head", "division_head")]),
    (RequestType.asset_return, "Asset return", [("Division Head", "division_head")]),
    (
        RequestType.recruitment_vacancy,
        "Vacancy approval",
        [("Division Head", "division_head"), ("HR", "hr_admin")],
    ),
    (RequestType.recruitment_selection, "Selection approval", [("HR", "hr_admin")]),
    (RequestType.onboarding_step, "Onboarding sign-off", [("HR", "hr_admin")]),
    (
        RequestType.appraisal,
        "Appraisal sign-off",
        [("Supervisor", "division_head"), ("Division Head", "division_head")],
    ),
    (RequestType.document_approval, "Document approval", [("HR", "hr_admin")]),
]


def seed_default_workflows(db: Session) -> None:
    existing = {d.request_type for d in db.query(WorkflowDefinition).all()}
    for request_type, name, levels in _DEFAULTS:
        if request_type in existing:
            continue
        definition = WorkflowDefinition(request_type=request_type, name=name)
        db.add(definition)
        db.flush()
        for order, (label, role_code) in enumerate(levels, start=1):
            db.add(
                WorkflowLevel(
                    definition_id=definition.id,
                    level_order=order,
                    label=label,
                    approver_kind=ApproverKind.role,
                    approver_role_code=role_code,
                )
            )
    db.commit()
