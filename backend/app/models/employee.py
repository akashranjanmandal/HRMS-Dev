"""The employee master (RFP 4.1): one permanent record per employee.

Bank/payment and statutory (PAN, Aadhaar, PF, ESI) details live on a
separate, one-to-one ``EmployeeConfidential`` row rather than as columns
on ``Employee`` itself — "access controls are required for confidential
employee information" (RFP 4.1) is enforced structurally this way: a
query that never joins that table can never leak those fields, instead of
relying on every caller to remember to strip a handful of columns.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class EmploymentCategory(str, Enum):
    """RFP 4.1: "employment category" — Aaranyak's own staff are a mix of
    regular and donor-project-linked contract roles."""

    regular = "regular"
    project_contract = "project_contract"
    consultant = "consultant"
    intern = "intern"


class EmployeeStatus(str, Enum):
    active = "active"
    on_notice = "on_notice"
    separated = "separated"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Identity (RFP 4.1) ---
    employee_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    photo_url: Mapped[str] = mapped_column(String(255), default="")
    gender: Mapped[str] = mapped_column(String(20), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Personal and contact ---
    personal_email: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    emergency_contact_name: Mapped[str] = mapped_column(String(160), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(String(30), default="")

    # --- Qualifications (free text for now; checklist 2.x may split this
    # into its own table once onboarding/recruitment need to query it) ---
    educational_qualifications: Mapped[str] = mapped_column(Text, default="")
    professional_qualifications: Mapped[str] = mapped_column(Text, default="")

    # --- Career ---
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)
    designation: Mapped[str] = mapped_column(String(160), default="")
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id"), index=True)
    employment_category: Mapped[EmploymentCategory] = mapped_column(
        SAEnum(EmploymentCategory), default=EmploymentCategory.regular
    )
    employment_history: Mapped[str] = mapped_column(Text, default="")

    # --- Reporting ---
    reporting_officer_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)

    # --- Engagement / contract ---
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    engagement_details: Mapped[str] = mapped_column(Text, default="")

    # --- Status ---
    status: Mapped[EmployeeStatus] = mapped_column(SAEnum(EmployeeStatus), default=EmployeeStatus.active)
    exit_reason: Mapped[str] = mapped_column(String(255), default="")
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Login link (optional: not every employee has a login, e.g. a
    # consultant onboarded before their account is issued) ---
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    division: Mapped["Division"] = relationship(lazy="selectin")  # noqa: F821
    reporting_officer: Mapped["Employee | None"] = relationship(
        remote_side=[id], lazy="selectin", foreign_keys=[reporting_officer_id]
    )
    confidential: Mapped["EmployeeConfidential | None"] = relationship(
        back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )


class EmployeeConfidential(Base):
    """Bank/payment and statutory details (RFP 4.1), restricted to the
    ``employee_confidential:view``/``:edit`` permissions — see
    ``app/routers/employee.py``, never returned on the ordinary employee
    read/list endpoints."""

    __tablename__ = "employee_confidential"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)

    bank_account_number: Mapped[str] = mapped_column(String(40), default="")
    bank_ifsc: Mapped[str] = mapped_column(String(20), default="")
    bank_name: Mapped[str] = mapped_column(String(160), default="")
    pan_number: Mapped[str] = mapped_column(String(20), default="")
    aadhaar_number: Mapped[str] = mapped_column(String(20), default="")
    pf_number: Mapped[str] = mapped_column(String(40), default="")
    esi_number: Mapped[str] = mapped_column(String(40), default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    employee: Mapped[Employee] = relationship(back_populates="confidential")
