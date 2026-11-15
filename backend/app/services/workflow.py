"""The generic approval workflow engine (RFP Section 8).

Every module that needs approval calls exactly two functions here:

    submit_for_approval(db, request_type, object_id, requested_by=...,
                         division_id=..., project_id=..., summary=...)
        -> creates the ApprovalRequest at level 1 of that type's
           configured workflow. Raises if no WorkflowDefinition exists
           for the type (an administrator must configure it first).

    decide(db, approval_request, actor, action, remark="")
        -> records an ApprovalStep, then either advances to the next
           level (on approve, if one exists), finalises as approved (on
           approve, if that was the last level), or ends the chain
           (reject / return).

``can_decide_at_current_level`` is the permission/scope check: is this
actor allowed to decide at the request's *current* level, given the
level's configured approver (a role, scoped the normal way, or one named
user)? Routers call this before calling ``decide`` so a 403 is raised
before any state changes, not after.
"""
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.scope import Scope, scope_allows_division, scope_for_role
from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApproverKind,
    Employee,
    RequestType,
    User,
    WorkflowAction,
    WorkflowDefinition,
    WorkflowLevel,
)
from app.services import notify as notify_service


class NoWorkflowConfiguredError(Exception):
    """Raised when a module tries to submit a request type that has no
    active WorkflowDefinition yet — the administrator must configure
    approval levels before anyone can submit that type."""


# ---------------------------------------------------------------------------
# Outcome callbacks: a module registers what should happen to its own
# record when the generic engine finalises a request of its type. The
# engine stays ignorant of every module's internal shape (a leave
# application's balance, an asset's status, an appraisal's stage) — it
# only ever calls back with (db, object_id, final_status).
# ---------------------------------------------------------------------------
_OUTCOME_HANDLERS: dict[RequestType, Callable] = {}


def on_outcome(request_type: RequestType):
    """Decorator: register ``fn(db, object_id, status)`` to run whenever a
    request of this type reaches a final status (approved / rejected /
    returned). Call once at import time, e.g. in each router module."""

    def register(fn):
        _OUTCOME_HANDLERS[request_type] = fn
        return fn

    return register


def find_approval_request(db: Session, request_type: RequestType, object_id: int) -> ApprovalRequest | None:
    """The ApprovalRequest for one specific object, if any — used by a
    module's own read endpoints to show the current approval status/level
    alongside the record itself."""
    return (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.request_type == request_type, ApprovalRequest.object_id == object_id)
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )


def submit_for_approval(
    db: Session,
    *,
    request_type: RequestType,
    object_id: int,
    requested_by_id: int | None,
    division_id: int | None = None,
    project_id: int | None = None,
    summary: str = "",
) -> ApprovalRequest:
    definition = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.request_type == request_type, WorkflowDefinition.is_active.is_(True))
        .first()
    )
    if definition is None or not definition.levels:
        raise NoWorkflowConfiguredError(
            f"No active approval workflow is configured for '{request_type.value}' yet"
        )

    request = ApprovalRequest(
        request_type=request_type,
        object_id=object_id,
        requested_by_id=requested_by_id,
        division_id=division_id,
        project_id=project_id,
        summary=summary,
        current_level_order=definition.levels[0].level_order,
    )
    db.add(request)
    db.flush()
    _notify_approvers_at_current_level(db, request, definition)
    return request


def _level_at(definition: WorkflowDefinition, order: int) -> WorkflowLevel | None:
    return next((lv for lv in definition.levels if lv.level_order == order), None)


def _next_level(definition: WorkflowDefinition, order: int) -> WorkflowLevel | None:
    higher = sorted((lv for lv in definition.levels if lv.level_order > order), key=lambda lv: lv.level_order)
    return higher[0] if higher else None


def can_decide_at_current_level(db: Session, request: ApprovalRequest, actor: User) -> bool:
    """Is ``actor`` allowed to decide at this request's current level?"""
    definition = db.query(WorkflowDefinition).filter_by(request_type=request.request_type).one()
    level = _level_at(definition, request.current_level_order)
    if level is None:
        return False

    if level.approver_kind == ApproverKind.specific_user:
        return level.approver_user_id == actor.id

    # approver_kind == role: the actor's role must match, and the actor's
    # scope must actually reach this request's division/project — the same
    # rule Phase 2.5 established for the employee master, reused here
    # rather than re-derived per module.
    if actor.role.code != level.approver_role_code:
        return False
    scope = scope_for_role(actor.role.code)
    if scope == Scope.organisation:
        return True
    if scope == Scope.division:
        if request.division_id is None:
            return False
        return scope_allows_division(scope, user_division_id=actor.division_id, target_division_id=request.division_id)
    # Scope.project: not yet enforceable (see app/routers/employee.py's
    # own note) — a project-scoped approver can only decide requests
    # raised by their own record until the staffing link exists.
    if scope == Scope.project:
        requester = db.get(Employee, request.requested_by_id)
        return requester is not None and requester.user_id == actor.id
    # Scope.own: an approver role should never actually be Scope.own in
    # practice, but if it is, the only thing they could "approve" is
    # their own request — which decide() separately forbids anyway.
    return False


def decide(
    db: Session,
    request: ApprovalRequest,
    actor: User,
    action: WorkflowAction,
    remark: str = "",
) -> ApprovalRequest:
    if request.status != ApprovalStatus.pending:
        raise HTTPException(status_code=400, detail=f"This request is already {request.status.value}")

    requester = db.get(Employee, request.requested_by_id)
    if requester is not None and requester.user_id == actor.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own request")

    if not can_decide_at_current_level(db, request, actor):
        raise HTTPException(status_code=403, detail="You are not the approver for this request's current level")

    db.add(
        ApprovalStep(
            request_id=request.id,
            level_order=request.current_level_order,
            approver_id=actor.id,
            action=action,
            remark=remark,
        )
    )

    definition = db.query(WorkflowDefinition).filter_by(request_type=request.request_type).one()

    if action == WorkflowAction.reject:
        request.status = ApprovalStatus.rejected
    elif action == WorkflowAction.return_for_correction:
        request.status = ApprovalStatus.returned
    else:  # approve
        nxt = _next_level(definition, request.current_level_order)
        if nxt is None:
            request.status = ApprovalStatus.approved
        else:
            request.current_level_order = nxt.level_order

    db.flush()

    if request.status == ApprovalStatus.pending:
        _notify_approvers_at_current_level(db, request, definition)
    else:
        handler = _OUTCOME_HANDLERS.get(request.request_type)
        if handler is not None:
            handler(db, request.object_id, request.status)
        _notify_requester_of_outcome(db, request)

    return request


def _notify_approvers_at_current_level(db: Session, request: ApprovalRequest, definition: WorkflowDefinition) -> None:
    """Best-effort: notify anyone who could decide the request's new
    current level. For a role-based level this fans out to every user
    holding that role whose scope reaches the request — on a small
    organisation (RFP: up to 300 users) this is cheap and simple; it does
    not need to be exact for roles with no rows yet (e.g. nobody holds
    'coordinator' in a fresh deployment) — it then just notifies nobody."""
    level = _level_at(definition, request.current_level_order)
    if level is None:
        return
    if level.approver_kind == ApproverKind.specific_user:
        if level.approver_user_id is not None:
            notify_service.notify(
                db,
                user_id=level.approver_user_id,
                kind="approval.pending",
                message=f"Waiting for your decision: {request.summary or request.request_type.value}",
            )
        return

    candidates = db.query(User).filter(User.role.has(code=level.approver_role_code)).all()
    for user in candidates:
        scope = scope_for_role(user.role.code)
        if scope == Scope.division and request.division_id is not None:
            if not scope_allows_division(scope, user_division_id=user.division_id, target_division_id=request.division_id):
                continue
        notify_service.notify(
            db,
            user_id=user.id,
            kind="approval.pending",
            message=f"Waiting for your decision: {request.summary or request.request_type.value}",
        )


def _notify_requester_of_outcome(db: Session, request: ApprovalRequest) -> None:
    requester = db.get(Employee, request.requested_by_id)
    if requester is None or requester.user_id is None:
        return
    notify_service.notify(
        db,
        user_id=requester.user_id,
        kind=f"approval.{request.status.value}",
        message=f"Your request ({request.summary or request.request_type.value}) was {request.status.value}",
    )
