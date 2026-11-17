"""Dashboards and reports (RFP Section 7): on-the-fly aggregates computed
from each module's own tables — nothing here is persisted, since the
underlying data is always the current source of truth. ``SavedReport``
(app/models/report.py) records that an export happened; it does not hold
the numbers themselves.
"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetStatus,
    Attendance,
    AttendanceStatus,
    Division,
    Employee,
    EmployeeStatus,
    LeaveApplication,
    LeaveStatus,
    Payslip,
)


def attendance_by_division_for_date(db: Session, for_date: date) -> list[dict]:
    """Per-division attendance composition for one day (dashboard's
    stacked bar): how many active employees are present, out on field
    duty (still awaiting approval), or on leave, against that division's
    total active headcount. Organisation-scoped only — same visibility
    rule as ``employee_strength_by_division``."""
    rows = (
        db.query(Division.name, Attendance.status, func.count(Attendance.id))
        .join(Employee, Employee.division_id == Division.id)
        .join(Attendance, (Attendance.employee_id == Employee.id) & (Attendance.work_date == for_date))
        .filter(Employee.status == EmployeeStatus.active)
        .group_by(Division.name, Attendance.status)
        .order_by(Division.name)
        .all()
    )
    totals = dict(
        db.query(Division.name, func.count(Employee.id))
        .outerjoin(Employee, (Employee.division_id == Division.id) & (Employee.status == EmployeeStatus.active))
        .group_by(Division.name)
        .all()
    )
    by_division: dict[str, dict] = {
        name: {"division": name, "present": 0, "field_duty": 0, "on_leave": 0, "total_active": total}
        for name, total in totals.items()
    }
    for name, status, count in rows:
        entry = by_division.setdefault(
            name, {"division": name, "present": 0, "field_duty": 0, "on_leave": 0, "total_active": totals.get(name, 0)}
        )
        if status == AttendanceStatus.present:
            entry["present"] += count
        elif status == AttendanceStatus.pending_approval:
            entry["field_duty"] += count
        elif status == AttendanceStatus.on_leave:
            entry["on_leave"] += count
    return [by_division[name] for name in sorted(by_division)]


def employee_strength_by_division(db: Session) -> list[dict]:
    rows = (
        db.query(Division.name, func.count(Employee.id))
        .outerjoin(Employee, (Employee.division_id == Division.id) & (Employee.status == EmployeeStatus.active))
        .group_by(Division.name)
        .order_by(Division.name)
        .all()
    )
    return [{"division": name, "active_employees": count} for name, count in rows]


def employee_strength_by_category(db: Session) -> list[dict]:
    rows = (
        db.query(Employee.employment_category, func.count(Employee.id))
        .filter(Employee.status == EmployeeStatus.active)
        .group_by(Employee.employment_category)
        .all()
    )
    return [{"category": cat.value, "count": count} for cat, count in rows]


def contracts_expiring_within(db: Session, days: int) -> list[Employee]:
    cutoff = date.today() + timedelta(days=days)
    return (
        db.query(Employee)
        .filter(
            Employee.status == EmployeeStatus.active,
            Employee.contract_end_date.is_not(None),
            Employee.contract_end_date <= cutoff,
        )
        .order_by(Employee.contract_end_date)
        .all()
    )


def separations_between(db: Session, start: date, end: date) -> list[Employee]:
    return (
        db.query(Employee)
        .filter(Employee.status == EmployeeStatus.separated, Employee.exit_date >= start, Employee.exit_date <= end)
        .order_by(Employee.exit_date)
        .all()
    )


def attendance_summary_for_month(db: Session, year: int, month: int) -> list[dict]:
    rows = (
        db.query(Employee.id, Employee.full_name, Employee.employee_code, Attendance.status, func.count(Attendance.id))
        .join(Attendance, Attendance.employee_id == Employee.id)
        .filter(func.extract("year", Attendance.work_date) == year, func.extract("month", Attendance.work_date) == month)
        .group_by(Employee.id, Employee.full_name, Employee.employee_code, Attendance.status)
        .all()
    )
    by_employee: dict[int, dict] = {}
    for emp_id, name, code, status, count in rows:
        entry = by_employee.setdefault(emp_id, {"employee_code": code, "employee_name": name, "present_days": 0, "absent_days": 0})
        if status == AttendanceStatus.present:
            entry["present_days"] = count
        elif status == AttendanceStatus.absent:
            entry["absent_days"] = count
    return list(by_employee.values())


def leave_register_for_year(db: Session, year: int) -> list[dict]:
    rows = (
        db.query(LeaveApplication)
        .filter(LeaveApplication.status == LeaveStatus.approved, func.extract("year", LeaveApplication.start_date) == year)
        .order_by(LeaveApplication.start_date)
        .all()
    )
    return [
        {
            "employee_code": r.employee.employee_code,
            "employee_name": r.employee.full_name,
            "leave_type": r.leave_type.name,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "days": float(r.days),
        }
        for r in rows
    ]


def asset_register_summary(db: Session) -> list[dict]:
    rows = db.query(Asset.status, func.count(Asset.id)).group_by(Asset.status).all()
    counts = {status.value: 0 for status in AssetStatus}
    for status, count in rows:
        counts[status.value] = count
    return [{"status": k, "count": v} for k, v in counts.items()]


def payroll_cost_by_division_for_run(db: Session, run_id: int) -> list[dict]:
    rows = (
        db.query(Division.name, func.sum(Payslip.net))
        .join(Payslip, Payslip.division_id == Division.id)
        .filter(Payslip.run_id == run_id)
        .group_by(Division.name)
        .all()
    )
    return [{"division": name, "total_net": float(total or 0)} for name, total in rows]
