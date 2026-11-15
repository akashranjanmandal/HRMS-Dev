"""Asset register helpers (RFP 4.1 §4.9) — pure state transitions kept out
of the router so "can this asset be issued/returned right now" is
testable without HTTP.
"""
from sqlalchemy.orm import Session

from app.models import Asset, AssetMovement, AssetStatus


def record_movement(db: Session, asset: Asset, kind: str, *, from_employee_id: int | None = None, to_employee_id: int | None = None, notes: str = "") -> AssetMovement:
    movement = AssetMovement(
        asset_id=asset.id, kind=kind, from_employee_id=from_employee_id, to_employee_id=to_employee_id, notes=notes,
    )
    db.add(movement)
    return movement


def assert_available_for_issue(asset: Asset) -> None:
    if asset.status != AssetStatus.in_store:
        raise ValueError(f"Asset is {asset.status.value}, not available to issue")


def assert_issued_to(asset: Asset, employee_id: int) -> None:
    if asset.status != AssetStatus.issued or asset.custodian_employee_id != employee_id:
        raise ValueError("Asset is not currently issued to this employee")
