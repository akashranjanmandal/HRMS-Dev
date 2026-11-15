from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.asset import AssetCategory, AssetCondition, AssetStatus


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: AssetCategory = AssetCategory.other
    serial_number: str = Field(default="", max_length=80)
    specification: str = Field(default="", max_length=2000)
    purchase_date: date | None = None
    invoice_number: str = Field(default="", max_length=80)
    purchase_value: float = Field(default=0, ge=0)
    division_id: int | None = None
    project_id: int | None = None


class AssetOut(BaseModel):
    id: int
    asset_code: str
    name: str
    category: AssetCategory
    serial_number: str
    specification: str
    purchase_date: date | None
    invoice_number: str
    purchase_value: float
    division_id: int | None
    project_id: int | None
    custodian_employee_id: int | None
    custodian_name: str | None
    condition: AssetCondition
    status: AssetStatus
    disposal_notes: str
    disposed_at: date | None
    created_at: datetime


class AssetIssueIn(BaseModel):
    employee_id: int
    notes: str = Field(default="", max_length=2000)


class AssetReturnIn(BaseModel):
    notes: str = Field(default="", max_length=2000)
    condition: AssetCondition = AssetCondition.good


class AssetTransferIn(BaseModel):
    to_employee_id: int
    notes: str = Field(default="", max_length=2000)


class AssetRepairIn(BaseModel):
    notes: str = Field(min_length=1, max_length=2000)
    condition: AssetCondition = AssetCondition.needs_repair


class AssetDisposeIn(BaseModel):
    notes: str = Field(default="", max_length=2000)


class AssetMovementOut(BaseModel):
    id: int
    kind: str
    from_employee_id: int | None
    to_employee_id: int | None
    notes: str
    created_at: datetime
