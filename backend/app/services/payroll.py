"""Payroll generation (RFP 4.1 §4.7).

A payroll run for one month creates one payslip per employee with an
active ``SalaryStructure``, deducting loss-of-pay days computed from
that month's attendance: any working day with no attendance record and
no approved leave covering it is a loss-of-pay day, proportionally
reducing gross pay. This is the "attendance and leave inputs" the RFP
asks payroll to take, kept intentionally simple (no weekly-off/holiday
calendar yet) rather than silently approximating something more complex.
"""
import calendar
from datetime import date

from sqlalchemy.orm import Session

from app.models import Attendance, AttendanceStatus, Employee, EmployeeStatus, LeaveApplication, LeaveStatus, Payslip, SalaryStructure


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def current_salary_structure(db: Session, employee_id: int, as_of: date) -> SalaryStructure | None:
    return (
        db.query(SalaryStructure)
        .filter(SalaryStructure.employee_id == employee_id, SalaryStructure.effective_from <= as_of)
        .order_by(SalaryStructure.effective_from.desc())
        .first()
    )


def loss_of_pay_days(db: Session, employee_id: int, year: int, month: int) -> float:
    total_days = _days_in_month(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, total_days)

    present_dates = {
        r.work_date
        for r in db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.work_date >= month_start,
            Attendance.work_date <= month_end,
            Attendance.status == AttendanceStatus.present,
        )
    }
    leave_rows = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee_id,
        LeaveApplication.status == LeaveStatus.approved,
        LeaveApplication.start_date <= month_end,
        LeaveApplication.end_date >= month_start,
    ).all()
    on_leave_dates: set[date] = set()
    for lr in leave_rows:
        d = max(lr.start_date, month_start)
        end = min(lr.end_date, month_end)
        while d <= end:
            on_leave_dates.add(d)
            d = date.fromordinal(d.toordinal() + 1)

    covered = len(present_dates | on_leave_dates)
    return float(max(0, total_days - covered))


def build_payslip(db: Session, run_id: int, employee: Employee, year: int, month: int) -> Payslip | None:
    structure = current_salary_structure(db, employee.id, date(year, month, _days_in_month(year, month)))
    if structure is None:
        return None

    total_days = _days_in_month(year, month)
    lop_days = loss_of_pay_days(db, employee.id, year, month)
    proration = max(0.0, (total_days - lop_days) / total_days)

    gross = structure.gross * proration
    deductions = structure.total_deductions  # statutory deductions are not prorated by LOP
    net = gross - deductions

    payslip = Payslip(
        run_id=run_id,
        employee_id=employee.id,
        division_id=employee.division_id,
        loss_of_pay_days=lop_days,
        gross=round(gross, 2),
        total_deductions=round(deductions, 2),
        net=round(net, 2),
        bank_account_number=structure.bank_account_number,
        bank_ifsc=structure.bank_ifsc,
    )
    db.add(payslip)
    return payslip


def generate_run_payslips(db: Session, run_id: int, year: int, month: int) -> list[Payslip]:
    employees = db.query(Employee).filter(Employee.status == EmployeeStatus.active).all()
    payslips = []
    for emp in employees:
        p = build_payslip(db, run_id, emp, year, month)
        if p is not None:
            payslips.append(p)
    db.flush()
    return payslips


def bank_export_rows(payslips: list[Payslip]) -> list[dict]:
    """Rows for a bank-format salary transfer file (RFP: 'payroll export,
    including a bank format salary file'). The exact column set a given
    bank wants varies; this is the common core — account number, IFSC,
    amount, narration — that app/services/xlsx.py's writer turns into a
    downloadable sheet."""
    return [
        {
            "employee_code": p.employee.employee_code,
            "employee_name": p.employee.full_name,
            "bank_account_number": p.bank_account_number,
            "bank_ifsc": p.bank_ifsc,
            "amount": float(p.net),
            "narration": f"Salary {p.run.month:02d}/{p.run.year}",
        }
        for p in payslips
    ]
