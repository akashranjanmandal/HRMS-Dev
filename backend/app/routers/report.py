"""Dashboards and reports (RFP Section 7): a role-scoped dashboard summary
plus the core HR reports as downloadable Excel exports.
"""
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import User, require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import Asset, AssetStatus, Employee, EmployeeStatus, LeaveApplication, LeaveStatus
from app.services import reports as reports_service
from app.services.xlsx import xlsx_response

router = APIRouter(prefix="/api/reports", tags=["Reports"])

VIEW = require_perm(permission_code("report", "view"))
EXPORT = require_perm(permission_code("report", "export"))


@router.get("/dashboard")
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    scope = scope_for_role(user.role.code)
    emp_q = db.query(Employee).filter(Employee.status == EmployeeStatus.active)
    leave_q = db.query(LeaveApplication).filter(LeaveApplication.status == LeaveStatus.pending)
    asset_q = db.query(Asset).filter(Asset.status == AssetStatus.issued)
    if scope == Scope.division and user.division_id is not None:
        emp_q = emp_q.filter(Employee.division_id == user.division_id)
        leave_q = leave_q.join(Employee, LeaveApplication.employee_id == Employee.id).filter(Employee.division_id == user.division_id)
        asset_q = asset_q.filter(Asset.division_id == user.division_id)

    return {
        "active_employees": emp_q.count(),
        "pending_leave_applications": leave_q.count(),
        "assets_issued": asset_q.count(),
        "contracts_expiring_30_days": len(reports_service.contracts_expiring_within(db, 30)),
        "employee_strength_by_division": reports_service.employee_strength_by_division(db) if scope == Scope.organisation else [],
    }


@router.get("/employee-strength/export")
def export_employee_strength(db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    rows_data = reports_service.employee_strength_by_division(db)
    rows = [[r["division"], r["active_employees"]] for r in rows_data]
    return xlsx_response("Employee strength", ["Division", "Active employees"], rows, "employee_strength_by_division.xlsx")


@router.get("/contracts-expiring/export")
def export_contracts_expiring(days: int = 30, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    employees = reports_service.contracts_expiring_within(db, days)
    rows = [[e.employee_code, e.full_name, e.division.name, e.contract_end_date] for e in employees]
    return xlsx_response("Contracts expiring", ["Employee code", "Name", "Division", "Contract end date"], rows, "contracts_expiring.xlsx")


@router.get("/separations/export")
def export_separations(start: date, end: date, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    employees = reports_service.separations_between(db, start, end)
    rows = [[e.employee_code, e.full_name, e.division.name, e.exit_date, e.exit_reason] for e in employees]
    return xlsx_response("Separations", ["Employee code", "Name", "Division", "Exit date", "Reason"], rows, "separations.xlsx")


@router.get("/attendance-summary/export")
def export_attendance_summary(year: int, month: int, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    rows_data = reports_service.attendance_summary_for_month(db, year, month)
    rows = [[r["employee_code"], r["employee_name"], r["present_days"], r["absent_days"]] for r in rows_data]
    return xlsx_response(f"Attendance {month}-{year}", ["Employee code", "Name", "Present days", "Absent days"], rows, f"attendance_summary_{year}_{month:02d}.xlsx")


@router.get("/leave-register/export")
def export_leave_register(year: int, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    rows_data = reports_service.leave_register_for_year(db, year)
    rows = [[r["employee_code"], r["employee_name"], r["leave_type"], r["start_date"], r["end_date"], r["days"]] for r in rows_data]
    return xlsx_response(f"Leave register {year}", ["Employee code", "Name", "Leave type", "Start date", "End date", "Days"], rows, f"leave_register_{year}.xlsx")


@router.get("/asset-register/export")
def export_asset_register(db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    rows_data = reports_service.asset_register_summary(db)
    rows = [[r["status"], r["count"]] for r in rows_data]
    return xlsx_response("Asset register summary", ["Status", "Count"], rows, "asset_register_summary.xlsx")
