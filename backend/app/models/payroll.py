"""Payroll integration (RFP 4.1 §4.7) — the scope the proposal actually
commits to: configurable salary structures, attendance/leave as pay
inputs, payslip generation, division/project-wise reports, a bank-format
export file. Statutory calculation (PF/ESI/PT/TDS) is entered or imported
as a value, never computed here — that stays an optional, separately
priced module per the proposal, and filing returns stays with Aaranyak.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class SalaryStructure(Base):
    """One per employee: the current pay components. A later revision
    creates a new row (effective_from) rather than overwriting the old
    one, so "what was this employee's salary structure in March" stays
    answerable."""

    __tablename__ = "salary_structures"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    basic: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    hra: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    other_allowances: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    pf_deduction: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    esi_deduction: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    professional_tax: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tds: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    bank_account_number: Mapped[str] = mapped_column(String(40), default="")
    bank_ifsc: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821

    @property
    def gross(self) -> float:
        return float(self.basic) + float(self.hra) + float(self.other_allowances)

    @property
    def total_deductions(self) -> float:
        return float(self.pf_deduction) + float(self.esi_deduction) + float(self.professional_tax) + float(self.tds)

    @property
    def net(self) -> float:
        return self.gross - self.total_deductions


class PayrollRun(Base):
    """One monthly payroll cycle. Payslips are generated for every active
    employee's current salary structure, adjusted by that month's
    attendance/leave (loss-of-pay days)."""

    __tablename__ = "payroll_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft -> finalised -> exported
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payslips: Mapped[list["Payslip"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Payslip(Base):
    __tablename__ = "payslips"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    loss_of_pay_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    gross: Mapped[float] = mapped_column(Numeric(10, 2))
    total_deductions: Mapped[float] = mapped_column(Numeric(10, 2))
    net: Mapped[float] = mapped_column(Numeric(10, 2))
    bank_account_number: Mapped[str] = mapped_column(String(40), default="")
    bank_ifsc: Mapped[str] = mapped_column(String(20), default="")

    run: Mapped[PayrollRun] = relationship(back_populates="payslips")
    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821
    division: Mapped["Division | None"] = relationship(lazy="selectin")  # noqa: F821
