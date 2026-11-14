"""The employee master (RFP 4.1).

Ordinary fields (identity, personal, qualifications, career, reporting,
engagement, status) are gated by the ``employee:*`` permissions and
filtered by the caller's scope (RFP 3.1): organisation-scoped roles see
everyone, a Division Head sees only their division, a self-service role
sees only their own record. Bank/payment and statutory fields live under
``/confidential`` and need the separate ``employee_confidential:*``
permissions — see ``app/models/employee.py`` for why they are a distinct
table rather than columns on the same one.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core.database import get_db
from app.core.deps import require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_allows_division, scope_for_role
from app.models import Employee, EmployeeConfidential, User
from app.schemas.employee import (
    EmployeeConfidentialIn,
    EmployeeConfidentialOut,
    EmployeeIn,
    EmployeeOut,
    EmployeeStatusUpdate,
    EmployeeUpdate,
)
from app.services.employee_code import generate_employee_code
from app.services.organisation import get_division_or_400

router = APIRouter(prefix="/api/employees", tags=["Employees"])

VIEW = require_perm(permission_code("employee", "view"))
CREATE = require_perm(permission_code("employee", "create"))
EDIT = require_perm(permission_code("employee", "edit"))
VIEW_CONFIDENTIAL = require_perm(permission_code("employee_confidential", "view"))
EDIT_CONFIDENTIAL = require_perm(permission_code("employee_confidential", "edit"))


def _scope_query(user: User, q: Query) -> Query:
    """Restrict an employee query to what the caller's role may reach."""
    scope = scope_for_role(user.role.code)
    if scope == Scope.organisation:
        return q
    if scope == Scope.division:
        if user.division_id is None:
            return q.filter(False)  # unassigned: sees nothing, never everything
        return q.filter(Employee.division_id == user.division_id)
    # Scope.project is not yet enforceable here — no employee<->project
    # link exists until the staffing module lands; Scope.own falls through
    # to the same "my own record only" rule in the meantime.
    return q.filter(Employee.user_id == user.id)


def _assert_in_scope(user: User, employee: Employee) -> None:
    scope = scope_for_role(user.role.code)
    if scope == Scope.organisation:
        return
    if scope == Scope.division:
        if not scope_allows_division(scope, user_division_id=user.division_id, target_division_id=employee.division_id):
            raise HTTPException(status_code=403, detail="This employee is outside the division you manage")
        return
    if employee.user_id != user.id:
        raise HTTPException(status_code=403, detail="This is not your own record")


def _get_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.get("", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    q = _scope_query(user, db.query(Employee))
    return q.order_by(Employee.full_name).all()


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    division = get_division_or_400(db, payload.division_id)
    if payload.reporting_officer_id is not None and db.get(Employee, payload.reporting_officer_id) is None:
        raise HTTPException(status_code=400, detail="Reporting officer not found")

    employee = Employee(**payload.model_dump(), employee_code=generate_employee_code(db, division.code))
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    employee = _get_or_404(db, employee_id)
    _assert_in_scope(user, employee)
    return employee


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(EDIT),
):
    employee = _get_or_404(db, employee_id)
    _assert_in_scope(user, employee)
    data = payload.model_dump(exclude_unset=True)
    if "division_id" in data:
        get_division_or_400(db, data["division_id"])
    for k, v in data.items():
        setattr(employee, k, v)
    db.commit()
    db.refresh(employee)
    return employee


@router.put("/{employee_id}/status", response_model=EmployeeOut)
def update_employee_status(
    employee_id: int,
    payload: EmployeeStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(EDIT),
):
    employee = _get_or_404(db, employee_id)
    _assert_in_scope(user, employee)
    employee.status = payload.status
    employee.exit_reason = payload.exit_reason or ""
    employee.exit_date = payload.exit_date
    db.commit()
    db.refresh(employee)
    return employee


# ---------------------------------------------------------- confidential data
@router.get("/{employee_id}/confidential", response_model=EmployeeConfidentialOut)
def get_confidential(employee_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW_CONFIDENTIAL)):
    employee = _get_or_404(db, employee_id)
    row = employee.confidential
    if row is None:
        # Nothing recorded yet — every field defaults to blank rather than
        # 404ing, since "no bank details on file" is a normal state, not
        # an error.
        return EmployeeConfidentialOut(
            employee_id=employee.id, updated_at=employee.updated_at, **EmployeeConfidentialIn().model_dump()
        )
    return EmployeeConfidentialOut(
        employee_id=employee.id,
        updated_at=row.updated_at,
        **{f: getattr(row, f) for f in EmployeeConfidentialIn.model_fields},
    )


@router.put("/{employee_id}/confidential", response_model=EmployeeConfidentialOut)
def set_confidential(
    employee_id: int,
    payload: EmployeeConfidentialIn,
    db: Session = Depends(get_db),
    user: User = Depends(EDIT_CONFIDENTIAL),
):
    employee = _get_or_404(db, employee_id)
    row = employee.confidential
    if row is None:
        row = EmployeeConfidential(employee_id=employee.id)
        db.add(row)
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return EmployeeConfidentialOut(employee_id=employee.id, updated_at=row.updated_at, **payload.model_dump())
