"""Attendance (RFP 4.1 §4.5): geo-fenced check-in/out with a compressed
selfie, field duty outside every boundary (approved via the workflow as
an "attendance_regularisation" of sorts — see note below), and
regularisation for a missed/incorrect check-in.
"""
import base64
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import Attendance, AttendanceSource, AttendanceStatus, Employee, RequestType, User
from app.schemas.attendance import AttendanceOut, CheckInIn, CheckOutIn, RegularisationIn
from app.services import attendance as attendance_service
from app.services import workflow as workflow_service
from app.services.selfie import compress_selfie

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])

VIEW = require_perm(permission_code("attendance", "view"))
CREATE = require_perm(permission_code("attendance", "create"))


def _my_employee(db: Session, user: User) -> Employee:
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="No employee record is linked to your account")
    return emp


def _out(record: Attendance, db: Session) -> AttendanceOut:
    req = None
    if record.status == AttendanceStatus.pending_approval:
        req = workflow_service.find_approval_request(db, RequestType.attendance_regularisation, record.id)
    return AttendanceOut(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=record.employee.full_name,
        work_date=record.work_date,
        site_id=record.site_id,
        site_name=record.site.name if record.site else None,
        check_in_at=record.check_in_at,
        check_out_at=record.check_out_at,
        source=record.source,
        status=record.status,
        field_duty_reason=record.field_duty_reason,
        is_within_geofence=record.is_within_geofence,
        approval_request_id=req.id if req else None,
    )


def _save_selfie(employee_id: int, selfie_base64: str) -> str:
    try:
        raw = base64.b64decode(selfie_base64.split(",")[-1], validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="selfie_base64 is not valid base64 image data")
    compressed = compress_selfie(raw)
    folder = settings.upload_path / "selfies" / str(employee_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (folder / name).write_bytes(compressed)
    return f"selfies/{employee_id}/{name}"


@router.post("/check-in", response_model=AttendanceOut)
def check_in(payload: CheckInIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    emp = _my_employee(db, user)
    selfie_url = _save_selfie(emp.id, payload.selfie_base64)
    record = attendance_service.check_in(
        db,
        employee_id=emp.id,
        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,
        selfie_url=selfie_url,
        field_duty_reason=payload.field_duty_reason,
    )

    if record.status == AttendanceStatus.pending_approval:
        workflow_service.submit_for_approval(
            db,
            request_type=RequestType.attendance_regularisation,
            object_id=record.id,
            requested_by_id=emp.id,
            division_id=emp.division_id,
            summary=f"Field duty, {record.work_date}: {payload.field_duty_reason}",
        )

    db.commit()
    db.refresh(record)
    return _out(record, db)


@router.post("/check-out", response_model=AttendanceOut)
def check_out(payload: CheckOutIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    emp = _my_employee(db, user)
    record = attendance_service.check_out(db, employee_id=emp.id, lat=payload.lat, lng=payload.lng)
    db.commit()
    db.refresh(record)
    return _out(record, db)


@router.get("/today", response_model=AttendanceOut | None)
def today(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    record = attendance_service.today_attendance(db, emp.id)
    return _out(record, db) if record else None


@router.get("/mine", response_model=list[AttendanceOut])
def my_history(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    rows = db.query(Attendance).filter(Attendance.employee_id == emp.id).order_by(Attendance.work_date.desc()).limit(90).all()
    return [_out(r, db) for r in rows]


@router.post("/regularise", response_model=AttendanceOut)
def request_regularisation(payload: RegularisationIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    emp = _my_employee(db, user)
    record = db.query(Attendance).filter(Attendance.employee_id == emp.id, Attendance.work_date == payload.work_date).first()
    if record is None:
        record = Attendance(employee_id=emp.id, work_date=payload.work_date, status=AttendanceStatus.pending_approval)
        db.add(record)
        db.flush()
    else:
        record.status = AttendanceStatus.pending_approval
    record.field_duty_reason = payload.reason

    workflow_service.submit_for_approval(
        db,
        request_type=RequestType.attendance_regularisation,
        object_id=record.id,
        requested_by_id=emp.id,
        division_id=emp.division_id,
        summary=f"Regularisation for {payload.work_date}: {payload.reason}",
    )
    db.commit()
    db.refresh(record)
    return _out(record, db)


# ----------------------------------------------------------------- register
@workflow_service.on_outcome(RequestType.attendance_regularisation)
def _on_attendance_decided(db: Session, attendance_id: int, outcome) -> None:
    """Field duty / regularisation reaching a final decision: present on
    approval, stays absent-like (never counted) otherwise."""
    record = db.get(Attendance, attendance_id)
    if record is None:
        return
    if outcome.value == "approved":
        record.status = AttendanceStatus.present
        if record.check_in_at is None:
            record.source = AttendanceSource.regularised
    else:
        record.status = AttendanceStatus.absent


@router.get("/register", response_model=list[AttendanceOut])
def daily_register(
    for_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm(permission_code("attendance", "approve"))),
):
    """The daily attendance register (RFP 4.5): who's in, scoped the same
    way the rest of the system is."""
    for_date = for_date or date.today()
    scope = scope_for_role(user.role.code)
    q = db.query(Attendance).join(Employee, Attendance.employee_id == Employee.id).filter(Attendance.work_date == for_date)
    if scope == Scope.division:
        if user.division_id is None:
            return []
        q = q.filter(Employee.division_id == user.division_id)
    elif scope not in (Scope.organisation,):
        q = q.filter(Employee.user_id == user.id)
    rows = q.all()
    return [_out(r, db) for r in rows]
