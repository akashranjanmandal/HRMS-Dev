"""Leave (RFP 4.6): configurable types (admin), application with the
overlap/balance checks run at submission, routed through the workflow
engine for approval.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import Employee, LeaveApplication, LeaveStatus, LeaveType, RequestType, User
from app.schemas.leave import LeaveApplicationIn, LeaveApplicationOut, LeaveBalanceOut, LeaveTypeIn, LeaveTypeOut
from app.services import leave as leave_service
from app.services import workflow as workflow_service

router = APIRouter(prefix="/api/leave", tags=["Leave"])

VIEW = require_perm(permission_code("leave", "view"))
CREATE = require_perm(permission_code("leave", "create"))
ADMIN_TYPES = require_perm(permission_code("leave", "edit"))


def _my_employee(db: Session, user: User) -> Employee:
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="No employee record is linked to your account")
    return emp


def _out(app: LeaveApplication, db: Session) -> LeaveApplicationOut:
    req = workflow_service.find_approval_request(db, RequestType.leave, app.id)
    return LeaveApplicationOut(
        id=app.id,
        employee_id=app.employee_id,
        employee_name=app.employee.full_name,
        leave_type_id=app.leave_type_id,
        leave_type_name=app.leave_type.name,
        start_date=app.start_date,
        end_date=app.end_date,
        days=float(app.days),
        reason=app.reason,
        status=app.status,
        created_at=app.created_at,
        approval_request_id=req.id if req else None,
    )


# ---------------------------------------------------------------- leave types
@router.get("/types", response_model=list[LeaveTypeOut])
def list_leave_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(LeaveType).filter(LeaveType.is_active.is_(True)).order_by(LeaveType.name).all()


@router.post("/types", response_model=LeaveTypeOut, status_code=201)
def create_leave_type(payload: LeaveTypeIn, db: Session = Depends(get_db), user: User = Depends(ADMIN_TYPES)):
    if db.query(LeaveType).filter(LeaveType.name == payload.name).first():
        raise HTTPException(status_code=409, detail="A leave type with this name already exists")
    lt = LeaveType(**payload.model_dump())
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


@router.put("/types/{type_id}", response_model=LeaveTypeOut)
def update_leave_type(type_id: int, payload: LeaveTypeIn, db: Session = Depends(get_db), user: User = Depends(ADMIN_TYPES)):
    lt = db.get(LeaveType, type_id)
    if lt is None:
        raise HTTPException(status_code=404, detail="Leave type not found")
    for k, v in payload.model_dump().items():
        setattr(lt, k, v)
    db.commit()
    db.refresh(lt)
    return lt


# ----------------------------------------------------------------------- mine
@router.get("/mine", response_model=list[LeaveApplicationOut])
def my_applications(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    rows = db.query(LeaveApplication).filter(LeaveApplication.employee_id == emp.id).order_by(LeaveApplication.created_at.desc()).all()
    return [_out(r, db) for r in rows]


@router.get("/balances", response_model=list[LeaveBalanceOut])
def my_balances(year: int | None = None, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    year = year or date.today().year
    types = db.query(LeaveType).filter(LeaveType.is_active.is_(True)).all()
    out = []
    for lt in types:
        bal = leave_service.get_or_create_balance(db, emp.id, lt, year)
        out.append(
            LeaveBalanceOut(
                leave_type_id=lt.id,
                leave_type_name=lt.name,
                year=year,
                opening_balance_days=float(bal.opening_balance_days),
                used_days=float(bal.used_days),
                available_days=bal.available_days,
            )
        )
    db.commit()
    return out


@router.post("", response_model=LeaveApplicationOut, status_code=201)
def apply_for_leave(payload: LeaveApplicationIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    emp = _my_employee(db, user)
    leave_type = db.get(LeaveType, payload.leave_type_id)
    if leave_type is None:
        raise HTTPException(status_code=400, detail="Leave type not found")

    days = leave_service.working_days(payload.start_date, payload.end_date)
    leave_service.assert_eligible(db, emp.id, leave_type, payload.start_date, payload.end_date, days)

    application = LeaveApplication(
        employee_id=emp.id,
        leave_type_id=leave_type.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        days=days,
        reason=payload.reason,
    )
    db.add(application)
    db.flush()

    if leave_type.requires_approval:
        workflow_service.submit_for_approval(
            db,
            request_type=RequestType.leave,
            object_id=application.id,
            requested_by_id=emp.id,
            division_id=emp.division_id,
            summary=f"{leave_type.name}: {days:g} day(s), {payload.start_date} to {payload.end_date}",
        )
    else:
        application.status = LeaveStatus.approved
        _apply_balance(db, application, leave_type)

    db.commit()
    db.refresh(application)
    return _out(application, db)


def _apply_balance(db: Session, application: LeaveApplication, leave_type: LeaveType) -> None:
    balance = leave_service.get_or_create_balance(db, application.employee_id, leave_type, application.start_date.year)
    balance.used_days = float(balance.used_days) + float(application.days)


@workflow_service.on_outcome(RequestType.leave)
def _on_leave_decided(db: Session, application_id: int, outcome) -> None:
    """The generic workflow engine has no idea what a leave application
    is — this is how it tells the leave module "your request #N reached a
    final decision", so the balance deduction (on approval) actually
    happens. Registered once, at import time."""
    application = db.get(LeaveApplication, application_id)
    if application is None:
        return
    application.status = LeaveStatus(outcome.value)
    if application.status == LeaveStatus.approved:
        leave_type = db.get(LeaveType, application.leave_type_id)
        if leave_type is not None:
            _apply_balance(db, application, leave_type)


@router.post("/{application_id}/cancel", response_model=LeaveApplicationOut)
def cancel_my_application(application_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    application = db.get(LeaveApplication, application_id)
    if application is None or application.employee_id != emp.id:
        raise HTTPException(status_code=404, detail="Leave application not found")
    if application.status not in (LeaveStatus.pending,):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {application.status.value} application")
    application.status = LeaveStatus.cancelled
    db.commit()
    db.refresh(application)
    return _out(application, db)


# ------------------------------------------------------------- team visibility
@router.get("", response_model=list[LeaveApplicationOut])
def list_team_applications(
    status: LeaveStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm(permission_code("leave", "approve"))),
):
    """For Division Heads / HR to see applications in their scope — not
    the approval action itself (that's the generic Approvals Center), but
    a browsable list, e.g. for the leave register / monthly reports."""
    scope = scope_for_role(user.role.code)
    q = db.query(LeaveApplication).join(Employee, LeaveApplication.employee_id == Employee.id)
    if scope == Scope.division:
        if user.division_id is None:
            return []
        q = q.filter(Employee.division_id == user.division_id)
    elif scope not in (Scope.organisation,):
        q = q.filter(Employee.user_id == user.id)
    if status is not None:
        q = q.filter(LeaveApplication.status == status)
    rows = q.order_by(LeaveApplication.created_at.desc()).all()
    return [_out(r, db) for r in rows]
