"""Workflow configuration (admin-only: how many levels, who approves at
each, per request type) and the Approvals Center (RFP 8, 11): pending
counts and the generic approve/reject/return action, usable against any
request type without that module needing its own approve-endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import ApprovalRequest, ApprovalStatus, RequestType, User, WorkflowDefinition, WorkflowLevel
from app.schemas.workflow import (
    ApprovalCountOut,
    ApprovalRequestOut,
    ApprovalStepOut,
    DecisionIn,
    WorkflowDefinitionIn,
    WorkflowDefinitionOut,
)
from app.services import workflow as workflow_service

router = APIRouter(tags=["Workflow"])

VIEW_WORKFLOW = require_perm(permission_code("workflow", "view"))
ADMIN_WORKFLOW = require_perm(permission_code("workflow", "admin"))


# ------------------------------------------------------- workflow configuration
@router.get("/api/workflows", response_model=list[WorkflowDefinitionOut])
def list_workflows(db: Session = Depends(get_db), user: User = Depends(VIEW_WORKFLOW)):
    return db.query(WorkflowDefinition).order_by(WorkflowDefinition.request_type).all()


@router.get("/api/workflows/{request_type}", response_model=WorkflowDefinitionOut)
def get_workflow(request_type: RequestType, db: Session = Depends(get_db), user: User = Depends(VIEW_WORKFLOW)):
    definition = db.query(WorkflowDefinition).filter_by(request_type=request_type).first()
    if definition is None:
        raise HTTPException(status_code=404, detail="No workflow configured for this request type")
    return definition


@router.put("/api/workflows/{request_type}", response_model=WorkflowDefinitionOut)
def set_workflow(
    request_type: RequestType,
    payload: WorkflowDefinitionIn,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN_WORKFLOW),
):
    for i, level in enumerate(payload.levels, start=1):
        if level.approver_kind.value == "role" and not level.approver_role_code:
            raise HTTPException(status_code=422, detail=f"Level {i}: approver_role_code is required for a role-based level")
        if level.approver_kind.value == "specific_user" and level.approver_user_id is None:
            raise HTTPException(status_code=422, detail=f"Level {i}: approver_user_id is required for a specific-user level")

    definition = db.query(WorkflowDefinition).filter_by(request_type=request_type).first()
    if definition is None:
        definition = WorkflowDefinition(request_type=request_type, name=payload.name)
        db.add(definition)
    else:
        definition.name = payload.name
        definition.levels.clear()
    db.flush()
    for order, level in enumerate(payload.levels, start=1):
        definition.levels.append(
            WorkflowLevel(
                level_order=order,
                label=level.label,
                approver_kind=level.approver_kind,
                approver_role_code=level.approver_role_code,
                approver_user_id=level.approver_user_id,
            )
        )
    db.commit()
    db.refresh(definition)
    return definition


# -------------------------------------------------------------- Approvals Center
def _out(request: ApprovalRequest) -> ApprovalRequestOut:
    return ApprovalRequestOut(
        id=request.id,
        request_type=request.request_type,
        object_id=request.object_id,
        requested_by_id=request.requested_by_id,
        requested_by_name=request.requested_by.full_name if request.requested_by else None,
        division_id=request.division_id,
        project_id=request.project_id,
        status=request.status,
        current_level_order=request.current_level_order,
        summary=request.summary,
        created_at=request.created_at,
        updated_at=request.updated_at,
        steps=[
            ApprovalStepOut(
                id=s.id,
                level_order=s.level_order,
                approver_id=s.approver_id,
                approver_name=s.approver.email,
                action=s.action,
                remark=s.remark,
                created_at=s.created_at,
            )
            for s in request.steps
        ],
    )


def _visible_pending_query(db: Session, user: User):
    """Every pending ApprovalRequest this user could plausibly decide
    *something* on right now — used both for the Approvals Center list and
    the per-type pending counts. Mirrors can_decide_at_current_level's own
    scope rule but as a bulk filter rather than a per-row check, since the
    Approvals Center lists many rows at once."""
    scope = scope_for_role(user.role.code)
    q = db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.pending)
    if scope == Scope.organisation:
        return q
    if scope == Scope.division:
        if user.division_id is None:
            return q.filter(False)
        return q.filter(ApprovalRequest.division_id == user.division_id)
    # Scope.project / Scope.own: only requests this user themselves raised
    # are visible via this bulk path (consistent with the project-scope
    # limitation documented in app/routers/employee.py).
    from app.models import Employee

    my_employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if my_employee is None:
        return q.filter(False)
    return q.filter(ApprovalRequest.requested_by_id == my_employee.id)


@router.get("/api/approvals", response_model=list[ApprovalRequestOut])
def list_pending_approvals(
    request_type: RequestType | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = _visible_pending_query(db, user)
    if request_type is not None:
        q = q.filter(ApprovalRequest.request_type == request_type)
    rows = q.order_by(ApprovalRequest.created_at).all()
    return [_out(r) for r in rows]


@router.get("/api/approvals/counts", response_model=list[ApprovalCountOut])
def pending_counts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = _visible_pending_query(db, user)
    counts: dict[RequestType, int] = {}
    for row in q.all():
        counts[row.request_type] = counts.get(row.request_type, 0) + 1
    return [
        ApprovalCountOut(request_type=rt, label=rt.value.replace("_", " ").title(), pending_count=n)
        for rt, n in counts.items()
    ]


@router.post("/api/approvals/{approval_id}/decide", response_model=ApprovalRequestOut)
def decide_approval(
    approval_id: int,
    payload: DecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request = db.get(ApprovalRequest, approval_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    workflow_service.decide(db, request, user, payload.action, payload.remark)
    db.commit()
    db.refresh(request)
    return _out(request)
