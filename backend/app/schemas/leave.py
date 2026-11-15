from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.leave import LeaveStatus


class LeaveTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    annual_entitlement_days: float = Field(ge=0)
    carry_forward_allowed: bool = False
    max_carry_forward_days: float = Field(default=0, ge=0)
    requires_approval: bool = True


class LeaveTypeOut(LeaveTypeIn):
    id: int
    is_active: bool


class LeaveApplicationIn(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=2000)


class LeaveApplicationOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    leave_type_id: int
    leave_type_name: str
    start_date: date
    end_date: date
    days: float
    reason: str
    status: LeaveStatus
    created_at: datetime
    approval_request_id: int | None = None


class LeaveBalanceOut(BaseModel):
    leave_type_id: int
    leave_type_name: str
    year: int
    opening_balance_days: float
    used_days: float
    available_days: float
