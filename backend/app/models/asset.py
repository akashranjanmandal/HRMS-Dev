"""Asset management (RFP 4.1 §4.9): a register linked to employees,
projects and divisions, with issue/return/transfer routed through the
workflow engine, and repair/disposal tracking.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class AssetCondition(str, Enum):
    new = "new"
    good = "good"
    fair = "fair"
    needs_repair = "needs_repair"
    disposed = "disposed"


class AssetStatus(str, Enum):
    in_store = "in_store"  # not currently issued to anyone
    issued = "issued"
    pending_return_approval = "pending_return_approval"
    disposed = "disposed"


class AssetCategory(str, Enum):
    field_equipment = "field_equipment"
    it_equipment = "it_equipment"
    vehicle = "vehicle"
    furniture = "furniture"
    other = "other"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[AssetCategory] = mapped_column(SAEnum(AssetCategory), default=AssetCategory.other)
    serial_number: Mapped[str] = mapped_column(String(80), default="")
    specification: Mapped[str] = mapped_column(Text, default="")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(80), default="")
    purchase_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    custodian_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)

    condition: Mapped[AssetCondition] = mapped_column(SAEnum(AssetCondition), default=AssetCondition.new)
    status: Mapped[AssetStatus] = mapped_column(SAEnum(AssetStatus), default=AssetStatus.in_store, index=True)
    disposal_notes: Mapped[str] = mapped_column(Text, default="")
    disposed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    division: Mapped["Division | None"] = relationship(lazy="selectin")  # noqa: F821
    project: Mapped["Project | None"] = relationship(lazy="selectin")  # noqa: F821
    custodian: Mapped["Employee | None"] = relationship(lazy="selectin")  # noqa: F821
    movements: Mapped[list["AssetMovement"]] = relationship(
        back_populates="asset", order_by="AssetMovement.created_at", cascade="all, delete-orphan"
    )


class AssetMovement(Base):
    """One issue, return, transfer or repair event — the movement history
    RFP 4.9 asks for ("transfer history", "repair and maintenance
    records")."""

    __tablename__ = "asset_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # issue / return / transfer / repair
    from_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    to_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    asset: Mapped[Asset] = relationship(back_populates="movements")
