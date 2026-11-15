"""Payroll (RFP 4.1 §4.7): configurable salary structure, monthly runs
with loss-of-pay from attendance/leave, payslips, division/project-wise
reports, and a bank-format export. Statutory amounts are entered as
values, never computed — see app/models/payroll.py's own note; filing
returns stays with Aaranyak.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_perm
from app.core.permissions import permission_code
from app.models import Employee, PayrollRun, Payslip, SalaryStructure, User
from app.schemas.payroll import (
    PayrollRunDetailOut,
    PayrollRunIn,
    PayrollRunOut,
    PayslipOut,
    SalaryStructureIn,
    SalaryStructureOut,
)
from app.services import payroll as payroll_service
from app.services.xlsx import xlsx_response

router = APIRouter(prefix="/api/payroll", tags=["Payroll"])

VIEW = require_perm(permission_code("payroll", "view"))
CREATE = require_perm(permission_code("payroll", "create"))
EDIT = require_perm(permission_code("payroll", "edit"))
APPROVE = require_perm(permission_code("payroll", "approve"))
EXPORT = require_perm(permission_code("payroll", "export"))


def _structure_out(s: SalaryStructure) -> SalaryStructureOut:
    return SalaryStructureOut(
        id=s.id, employee_id=s.employee_id, effective_from=s.effective_from, basic=float(s.basic), hra=float(s.hra),
        other_allowances=float(s.other_allowances), pf_deduction=float(s.pf_deduction), esi_deduction=float(s.esi_deduction),
        professional_tax=float(s.professional_tax), tds=float(s.tds), bank_account_number=s.bank_account_number,
        bank_ifsc=s.bank_ifsc, gross=round(s.gross, 2), total_deductions=round(s.total_deductions, 2), net=round(s.net, 2),
        created_at=s.created_at,
    )


def _payslip_out(p: Payslip) -> PayslipOut:
    return PayslipOut(
        id=p.id, run_id=p.run_id, employee_id=p.employee_id, employee_name=p.employee.full_name,
        division_id=p.division_id, division_name=p.division.name if p.division else None,
        project_id=p.project_id, loss_of_pay_days=float(p.loss_of_pay_days), gross=float(p.gross),
        total_deductions=float(p.total_deductions), net=float(p.net), bank_account_number=p.bank_account_number,
        bank_ifsc=p.bank_ifsc,
    )


def _run_out(run: PayrollRun, with_payslips: bool = False):
    base = dict(
        id=run.id, month=run.month, year=run.year, status=run.status, created_at=run.created_at,
        finalised_at=run.finalised_at, payslip_count=len(run.payslips), total_net=round(sum(float(p.net) for p in run.payslips), 2),
    )
    if with_payslips:
        return PayrollRunDetailOut(**base, payslips=[_payslip_out(p) for p in run.payslips])
    return PayrollRunOut(**base)


# -------------------------------------------------------------- salary structure
@router.get("/employees/{employee_id}/structure", response_model=list[SalaryStructureOut])
def list_salary_structures(employee_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    rows = db.query(SalaryStructure).filter(SalaryStructure.employee_id == employee_id).order_by(SalaryStructure.effective_from.desc()).all()
    return [_structure_out(r) for r in rows]


@router.post("/employees/{employee_id}/structure", response_model=SalaryStructureOut, status_code=201)
def set_salary_structure(employee_id: int, payload: SalaryStructureIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    structure = SalaryStructure(employee_id=employee_id, **payload.model_dump())
    db.add(structure)
    db.commit()
    db.refresh(structure)
    return _structure_out(structure)


# -------------------------------------------------------------------- payroll runs
@router.get("", response_model=list[PayrollRunOut])
def list_payroll_runs(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    rows = db.query(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).all()
    return [_run_out(r) for r in rows]


@router.post("", response_model=PayrollRunDetailOut, status_code=201)
def create_payroll_run(payload: PayrollRunIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    existing = db.query(PayrollRun).filter(PayrollRun.month == payload.month, PayrollRun.year == payload.year).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A payroll run for {payload.month}/{payload.year} already exists")
    run = PayrollRun(month=payload.month, year=payload.year, created_by_id=user.id)
    db.add(run)
    db.flush()
    payroll_service.generate_run_payslips(db, run.id, payload.year, payload.month)
    db.commit()
    db.refresh(run)
    return _run_out(run, with_payslips=True)


@router.get("/{run_id}", response_model=PayrollRunDetailOut)
def get_payroll_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    run = db.get(PayrollRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return _run_out(run, with_payslips=True)


@router.post("/{run_id}/finalise", response_model=PayrollRunOut)
def finalise_payroll_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(APPROVE)):
    from datetime import datetime, timezone

    run = db.get(PayrollRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "draft":
        raise HTTPException(status_code=400, detail=f"Run is already {run.status}")
    run.status = "finalised"
    run.finalised_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _run_out(run)


@router.get("/employees/{employee_id}/payslips", response_model=list[PayslipOut])
def my_payslips(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if employee.user_id != user.id and not user.has_permission(permission_code("payroll", "view")):
        raise HTTPException(status_code=403, detail="Not permitted")
    rows = db.query(Payslip).filter(Payslip.employee_id == employee_id).order_by(Payslip.id.desc()).all()
    return [_payslip_out(r) for r in rows]


# ----------------------------------------------------------------------- export
@router.get("/{run_id}/export/bank-file")
def export_bank_file(run_id: int, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    run = db.get(PayrollRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    rows_data = payroll_service.bank_export_rows(run.payslips)
    columns = ["employee_code", "employee_name", "bank_account_number", "bank_ifsc", "amount", "narration"]
    rows = [[r[c] for c in columns] for r in rows_data]
    return xlsx_response(f"Bank file {run.month}-{run.year}", columns, rows, f"salary_bank_file_{run.year}_{run.month:02d}.xlsx")


@router.get("/{run_id}/export/payroll-report")
def export_payroll_report(run_id: int, db: Session = Depends(get_db), user: User = Depends(EXPORT)) -> StreamingResponse:
    """Division/project-wise payroll report (RFP: 'payroll reports...
    division wise, project wise salary information')."""
    run = db.get(PayrollRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    columns = ["employee_code", "employee_name", "division", "gross", "deductions", "net", "loss_of_pay_days"]
    rows = [
        [
            p.employee.employee_code, p.employee.full_name, p.division.name if p.division else "",
            float(p.gross), float(p.total_deductions), float(p.net), float(p.loss_of_pay_days),
        ]
        for p in run.payslips
    ]
    return xlsx_response(f"Payroll {run.month}-{run.year}", columns, rows, f"payroll_report_{run.year}_{run.month:02d}.xlsx")
