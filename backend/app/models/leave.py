"""Leave (RFP 4.6): configurable types and rules, applications routed
through the workflow engine, balances, and the overlap/eligibility checks
RFP 4.6 asks for at submission time.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class LeaveStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    returned = "returned"
    cancelled = "cancelled"


class LeaveType(Base):
    """Configurable by the administrator (RFP 4.6) — no code change needed
    to add "Maternity Leave" or change how many days "Casual Leave" carries
    forward. Seeded with Aaranyak's own common set; see
    app/services/demo_seed.py."""

    __tablename__ = "leave_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    annual_entitlement_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    carry_forward_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    max_carry_forward_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LeaveBalance(Base):
    """One row per employee, per leave type, per year — the running
    balance a new application is checked against."""

    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    opening_balance_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    used_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    leave_type: Mapped[LeaveType] = relationship(lazy="selectin")

    @property
    def available_days(self) -> float:
        return float(self.opening_balance_days) - float(self.used_days)


class LeaveApplication(Base):
    __tablename__ = "leave_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey("leave_types.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Numeric(6, 2))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LeaveStatus] = mapped_column(SAEnum(LeaveStatus), default=LeaveStatus.pending, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821
    leave_type: Mapped[LeaveType] = relationship(lazy="selectin")
