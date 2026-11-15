"""The approval workflow engine (RFP Section 8).

Generic across every request type that needs approval — leave, attendance
regularisation, asset issue/return, appraisal sign-off, recruitment
selection, onboarding steps, timesheets. Rather than bolting a bespoke
approval flow onto each of those tables, every one of them creates a single
``ApprovalRequest`` row that points back at its own record
(``request_type`` + ``object_id``), and the generic engine below drives it
through the levels the administrator configured for that request type.

Shape:

    WorkflowDefinition (one per request_type, admin-configured)
      └── WorkflowLevel (ordered: level_order 1, 2, 3...; each names the
            role, or a specific approver, that decides at that level)

    ApprovalRequest (one per actual thing awaiting approval)
      ├── current_level  (which WorkflowLevel is next)
      ├── status         (pending / approved / rejected / returned)
      └── ApprovalStep (one per decision made: level, approver, action,
            remark, timestamp) — the audit trail RFP 8 asks for.

A request moves to the next level only on an "approve" at the current one.
"reject" or "return" ends the pending chain immediately (return lets the
requester fix and resubmit, which creates a fresh ApprovalRequest rather
than resurrecting the old one — so the history of what was rejected and why
is never overwritten).
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class ApproverKind(str, Enum):
    """Who decides at a workflow level."""

    role = "role"  # anyone holding this role code (and in scope, e.g. the
    # employee's own Division Head) decides
    specific_user = "specific_user"  # one named login decides, regardless
    # of role (e.g. "the Executive Director" for a specific high-value case)


class RequestType(str, Enum):
    """Every kind of request the workflow engine can route. Extend this as
    new modules land — each new value needs a WorkflowDefinition seeded
    (see app/services/workflow_seed.py) before anyone can submit that type."""

    leave = "leave"
    attendance_regularisation = "attendance_regularisation"
    asset_issue = "asset_issue"
    asset_return = "asset_return"
    recruitment_vacancy = "recruitment_vacancy"
    recruitment_selection = "recruitment_selection"
    onboarding_step = "onboarding_step"
    appraisal = "appraisal"
    document_approval = "document_approval"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    returned = "returned"  # sent back for correction; not a final state in
    # the sense of "resubmittable", but the chain itself is dead — the
    # requester creates a new ApprovalRequest to try again.


class WorkflowAction(str, Enum):
    approve = "approve"
    reject = "reject"
    return_for_correction = "return_for_correction"


class WorkflowDefinition(Base):
    """One per request type. ``is_active`` lets the administrator disable a
    workflow (e.g. while reconfiguring levels) without deleting its history."""

    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_type: Mapped[RequestType] = mapped_column(
        SAEnum(RequestType), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    levels: Mapped[list["WorkflowLevel"]] = relationship(
        back_populates="definition",
        order_by="WorkflowLevel.level_order",
        cascade="all, delete-orphan",
    )


class WorkflowLevel(Base):
    """One approval level within a definition. ``level_order`` starts at 1.

    ``approver_kind='role'``: ``approver_role_code`` names the role; the
    *scope* that role already carries (RFP 3.1 — a Division Head only sees
    their own division) is what narrows this down to "the right person",
    not an extra field here. ``approver_kind='specific_user'``:
    ``approver_user_id`` names exactly one login, bypassing scope entirely.
    """

    __tablename__ = "workflow_levels"
    __table_args__ = (UniqueConstraint("definition_id", "level_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    definition_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), index=True
    )
    level_order: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80), default="")
    approver_kind: Mapped[ApproverKind] = mapped_column(SAEnum(ApproverKind), default=ApproverKind.role)
    approver_role_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    definition: Mapped[WorkflowDefinition] = relationship(back_populates="levels")


class ApprovalRequest(Base):
    """One actual thing awaiting approval. ``request_type`` + ``object_id``
    point back at the record this approval is for — the engine itself
    never needs to know what a "leave request" or "asset issue" looks
    like beyond that pointer; the owning module reads the pointer back to
    show its own detail."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_type: Mapped[RequestType] = mapped_column(SAEnum(RequestType), index=True)
    object_id: Mapped[int] = mapped_column(Integer, index=True)
    # Nullable: a vacancy or selection decision may be raised by an
    # Admin/HR login that has no Employee record of its own (RFP's
    # administrative users are not always modelled as staff). "Who is
    # the requester" is then simply unknown for self-approval and
    # notification purposes, rather than forced onto an unrelated row.
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    # Snapshot of the division/project the request was raised in, so a
    # Division-Head-scoped approver's "is this mine?" check never needs to
    # join back through the (possibly already-changed) source record.
    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    status: Mapped[ApprovalStatus] = mapped_column(SAEnum(ApprovalStatus), default=ApprovalStatus.pending, index=True)
    current_level_order: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(String(255), default="")  # one line for the Approvals Center list

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    steps: Mapped[list["ApprovalStep"]] = relationship(
        back_populates="request", order_by="ApprovalStep.created_at", cascade="all, delete-orphan"
    )
    requested_by: Mapped["Employee | None"] = relationship(lazy="selectin")  # noqa: F821


class ApprovalStep(Base):
    """One decision made on an ApprovalRequest — the audit trail RFP 8
    asks for: "the approver's name, time and remark are saved with each
    decision"."""

    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True)
    level_order: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[WorkflowAction] = mapped_column(SAEnum(WorkflowAction))
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    request: Mapped[ApprovalRequest] = relationship(back_populates="steps")
    approver: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
