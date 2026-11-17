"""Global search (RFP's own design mockup: a persistent "Search people,
requests, assets" box on every screen). Cross-module, but every section
only searches what the caller's own permissions and scope already let
them see elsewhere — this endpoint grants no new visibility, it just
collects results from the same rules app/routers/employee.py,
app/routers/workflow.py and app/routers/asset.py already enforce.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import ApprovalRequest, ApprovalStatus, Asset, Employee, User
from app.schemas.search import SearchResultItem, SearchResultsOut

router = APIRouter(prefix="/api/search", tags=["Search"])

_MAX_PER_SECTION = 8


def _employee_results(db: Session, user: User, q: str) -> list[SearchResultItem]:
    if not user.has_permission(permission_code("employee", "view")):
        return []
    scope = scope_for_role(user.role.code)
    query = db.query(Employee).filter(
        or_(Employee.full_name.ilike(f"%{q}%"), Employee.employee_code.ilike(f"%{q}%"), Employee.designation.ilike(f"%{q}%"))
    )
    if scope == Scope.division:
        if user.division_id is None:
            return []
        query = query.filter(Employee.division_id == user.division_id)
    elif scope not in (Scope.organisation,):
        query = query.filter(Employee.user_id == user.id)
    rows = query.order_by(Employee.full_name).limit(_MAX_PER_SECTION).all()
    return [
        SearchResultItem(kind="employee", id=e.id, title=e.full_name, subtitle=f"{e.employee_code} · {e.designation or 'Employee'}", url=f"/employees?id={e.id}")
        for e in rows
    ]


def _approval_results(db: Session, user: User, q: str) -> list[SearchResultItem]:
    approve_codes = [
        permission_code(m, "approve")
        for m in ("recruitment", "onboarding", "attendance", "leave", "appraisal", "asset", "payroll")
    ]
    if not any(user.has_permission(c) for c in approve_codes):
        return []
    scope = scope_for_role(user.role.code)
    query = db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.pending, ApprovalRequest.summary.ilike(f"%{q}%"))
    if scope == Scope.division:
        if user.division_id is None:
            return []
        query = query.filter(ApprovalRequest.division_id == user.division_id)
    elif scope not in (Scope.organisation,):
        my_employee = db.query(Employee).filter(Employee.user_id == user.id).first()
        if my_employee is None:
            return []
        query = query.filter(ApprovalRequest.requested_by_id == my_employee.id)
    rows = query.order_by(ApprovalRequest.created_at.desc()).limit(_MAX_PER_SECTION).all()
    return [
        SearchResultItem(kind="approval_request", id=r.id, title=r.summary, subtitle=f"{r.request_type.value.replace('_', ' ')} · pending", url="/approvals")
        for r in rows
    ]


def _asset_results(db: Session, user: User, q: str) -> list[SearchResultItem]:
    if not user.has_permission(permission_code("asset", "view")):
        return []
    scope = scope_for_role(user.role.code)
    query = db.query(Asset).filter(or_(Asset.name.ilike(f"%{q}%"), Asset.asset_code.ilike(f"%{q}%")))
    if scope == Scope.division:
        if user.division_id is None:
            return []
        query = query.filter(or_(Asset.division_id == user.division_id, Asset.division_id.is_(None)))
    elif scope not in (Scope.organisation,):
        return []
    rows = query.order_by(Asset.asset_code).limit(_MAX_PER_SECTION).all()
    return [
        SearchResultItem(kind="asset", id=a.id, title=a.name, subtitle=f"{a.asset_code} · {a.status.value.replace('_', ' ')}", url="/assets")
        for a in rows
    ]


@router.get("", response_model=SearchResultsOut)
def search(q: str = Query(min_length=2), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = _employee_results(db, user, q) + _approval_results(db, user, q) + _asset_results(db, user, q)
    return SearchResultsOut(results=results)
