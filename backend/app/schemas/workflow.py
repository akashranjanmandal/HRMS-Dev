from datetime import datetime

from pydantic import BaseModel, Field

from app.models.workflow import ApprovalStatus, ApproverKind, RequestType, WorkflowAction


class WorkflowLevelIn(BaseModel):
    label: str = Field(default="", max_length=80)
    approver_kind: ApproverKind = ApproverKind.role
    approver_role_code: str | None = None
    approver_user_id: int | None = None


class WorkflowLevelOut(WorkflowLevelIn):
    id: int
    level_order: int


class WorkflowDefinitionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    levels: list[WorkflowLevelIn] = Field(min_length=1)


class WorkflowDefinitionOut(BaseModel):
    id: int
    request_type: RequestType
    name: str
    is_active: bool
    levels: list[WorkflowLevelOut]


class DecisionIn(BaseModel):
    action: WorkflowAction
    remark: str = Field(default="", max_length=2000)


class ApprovalStepOut(BaseModel):
    id: int
    level_order: int
    approver_id: int
    approver_name: str
    action: WorkflowAction
    remark: str
    created_at: datetime


class ApprovalRequestOut(BaseModel):
    id: int
    request_type: RequestType
    object_id: int
    requested_by_id: int | None
    requested_by_name: str | None
    division_id: int | None
    project_id: int | None
    status: ApprovalStatus
    current_level_order: int
    summary: str
    created_at: datetime
    updated_at: datetime
    steps: list[ApprovalStepOut]


class ApprovalCountOut(BaseModel):
    request_type: RequestType
    label: str
    pending_count: int
