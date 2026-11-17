"""Asset management (RFP 4.1 §4.9): register, issue/return routed through
the workflow engine (an employee can't just take an asset off the
register without their Division Head's sign-off), direct transfer/repair/
disposal tracking for the people who administer the register.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import User, get_current_user, require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import Asset, AssetCondition, AssetStatus, Employee, RequestType
from app.schemas.asset import (
    AssetDisposeIn,
    AssetIn,
    AssetIssueIn,
    AssetOut,
    AssetRepairIn,
    AssetReturnIn,
    AssetTransferIn,
)
from app.services import asset as asset_service
from app.services import workflow as workflow_service

router = APIRouter(prefix="/api/assets", tags=["Assets"])

VIEW = require_perm(permission_code("asset", "view"))
CREATE = require_perm(permission_code("asset", "create"))
EDIT = require_perm(permission_code("asset", "edit"))
DELETE = require_perm(permission_code("asset", "delete"))


def _out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id, asset_code=asset.asset_code, name=asset.name, category=asset.category,
        serial_number=asset.serial_number, specification=asset.specification, purchase_date=asset.purchase_date,
        invoice_number=asset.invoice_number, purchase_value=float(asset.purchase_value), division_id=asset.division_id,
        project_id=asset.project_id, custodian_employee_id=asset.custodian_employee_id,
        custodian_name=asset.custodian.full_name if asset.custodian else None,
        condition=asset.condition, status=asset.status, disposal_notes=asset.disposal_notes,
        disposed_at=asset.disposed_at, created_at=asset.created_at,
    )


def _next_asset_code(db: Session) -> str:
    n = db.query(Asset).count() + 1
    return f"AST-{n:05d}"


def _assert_in_scope(user: User, asset: Asset) -> None:
    """A division-scoped role (e.g. Division Head) sees/acts on its own
    division's assets and org-wide ones (division_id is None), never
    another division's — mirrors the filter in _scoped_query below, but
    as a single-row check for the by-id endpoints."""
    scope = scope_for_role(user.role.code)
    if scope in (Scope.organisation,):
        return
    if scope == Scope.division:
        if asset.division_id is not None and asset.division_id != user.division_id:
            raise HTTPException(status_code=403, detail="Not in your division")
        return
    raise HTTPException(status_code=403, detail="Not permitted")


def _scoped_query(db: Session, user: User):
    from sqlalchemy import or_

    scope = scope_for_role(user.role.code)
    q = db.query(Asset)
    if scope == Scope.organisation:
        return q
    if scope == Scope.division:
        if user.division_id is None:
            return q.filter(False)
        return q.filter(or_(Asset.division_id == user.division_id, Asset.division_id.is_(None)))
    return q.filter(False)


@router.get("", response_model=list[AssetOut])
def list_assets(status: AssetStatus | None = None, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    q = _scoped_query(db, user)
    if status is not None:
        q = q.filter(Asset.status == status)
    return [_out(a) for a in q.order_by(Asset.asset_code).all()]


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(payload: AssetIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    asset = Asset(asset_code=_next_asset_code(db), **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _out(asset)


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    _assert_in_scope(user, asset)
    return _out(asset)


@router.get("/employees/{employee_id}", response_model=list[AssetOut])
def list_employee_assets(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.user_id != user.id and not user.has_permission(permission_code("asset", "view")):
        raise HTTPException(status_code=403, detail="Not permitted")
    rows = db.query(Asset).filter(Asset.custodian_employee_id == employee_id).order_by(Asset.asset_code).all()
    return [_out(a) for a in rows]


def _get_asset_or_404(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/{asset_id}/issue", response_model=AssetOut)
def issue_asset(asset_id: int, payload: AssetIssueIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    asset = _get_asset_or_404(db, asset_id)
    _assert_in_scope(user, asset)
    try:
        asset_service.assert_available_for_issue(asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    employee = db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    asset_service.record_movement(db, asset, "issue", to_employee_id=employee.id, notes=payload.notes)
    workflow_service.submit_for_approval(
        db,
        request_type=RequestType.asset_issue,
        object_id=asset.id,
        requested_by_id=employee.id,
        division_id=employee.division_id,
        summary=f"Issue {asset.name} ({asset.asset_code}) to {employee.full_name}",
    )
    db.commit()
    db.refresh(asset)
    return _out(asset)


@router.post("/{asset_id}/return", response_model=AssetOut)
def return_asset(asset_id: int, payload: AssetReturnIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    asset = _get_asset_or_404(db, asset_id)
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    is_self = emp is not None and asset.custodian_employee_id == emp.id
    if not is_self and not user.has_permission(permission_code("asset", "edit")):
        raise HTTPException(status_code=403, detail="Not permitted")
    if not is_self:
        _assert_in_scope(user, asset)
    if asset.status != AssetStatus.issued:
        raise HTTPException(status_code=400, detail=f"Asset is {asset.status.value}, not currently issued")

    requester_id = emp.id if emp is not None else asset.custodian_employee_id
    asset.status = AssetStatus.pending_return_approval
    asset_service.record_movement(db, asset, "return", from_employee_id=asset.custodian_employee_id, notes=payload.notes)
    workflow_service.submit_for_approval(
        db,
        request_type=RequestType.asset_return,
        object_id=asset.id,
        requested_by_id=requester_id,
        division_id=asset.division_id,
        summary=f"Return {asset.name} ({asset.asset_code})",
    )
    db.commit()
    db.refresh(asset)
    return _out(asset)


@workflow_service.on_outcome(RequestType.asset_issue)
def _on_issue_decided(db: Session, asset_id: int, outcome) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return
    if outcome.value == "approved":
        last_issue = next((m for m in reversed(asset.movements) if m.kind == "issue"), None)
        if last_issue is not None:
            asset.custodian_employee_id = last_issue.to_employee_id
            asset.status = AssetStatus.issued


@workflow_service.on_outcome(RequestType.asset_return)
def _on_return_decided(db: Session, asset_id: int, outcome) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return
    if outcome.value == "approved":
        asset.custodian_employee_id = None
        asset.status = AssetStatus.in_store
    else:
        asset.status = AssetStatus.issued


@router.post("/{asset_id}/transfer", response_model=AssetOut)
def transfer_asset(asset_id: int, payload: AssetTransferIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    asset = _get_asset_or_404(db, asset_id)
    _assert_in_scope(user, asset)
    if asset.status != AssetStatus.issued:
        raise HTTPException(status_code=400, detail=f"Asset is {asset.status.value}, not currently issued")
    to_employee = db.get(Employee, payload.to_employee_id)
    if to_employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    asset_service.record_movement(db, asset, "transfer", from_employee_id=asset.custodian_employee_id, to_employee_id=to_employee.id, notes=payload.notes)
    asset.custodian_employee_id = to_employee.id
    db.commit()
    db.refresh(asset)
    return _out(asset)


@router.post("/{asset_id}/repair", response_model=AssetOut)
def log_repair(asset_id: int, payload: AssetRepairIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    asset = _get_asset_or_404(db, asset_id)
    _assert_in_scope(user, asset)
    asset_service.record_movement(db, asset, "repair", notes=payload.notes)
    asset.condition = payload.condition
    db.commit()
    db.refresh(asset)
    return _out(asset)


@router.post("/{asset_id}/dispose", response_model=AssetOut)
def dispose_asset(asset_id: int, payload: AssetDisposeIn, db: Session = Depends(get_db), user: User = Depends(DELETE)):
    from datetime import date as date_cls

    asset = _get_asset_or_404(db, asset_id)
    _assert_in_scope(user, asset)
    if asset.status == AssetStatus.issued:
        raise HTTPException(status_code=400, detail="Cannot dispose an asset that is currently issued")
    asset.status = AssetStatus.disposed
    asset.condition = AssetCondition.disposed
    asset.disposal_notes = payload.notes
    asset.disposed_at = date_cls.today()
    db.commit()
    db.refresh(asset)
    return _out(asset)
