"""Attendance (RFP 4.1 §4.5): daily records, geo-fenced check-in/out with a
selfie, field duty outside a site's boundary, and regularisation routed
through the workflow engine.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class AttendanceSource(str, Enum):
    geofence = "geofence"  # inside a site's drawn boundary
    field_duty = "field_duty"  # outside every boundary, reason given,
    # counted once a supervisor approves (RFP 4.5)
    manual = "manual"  # HR/Admin entered it directly (e.g. backfilling)
    regularised = "regularised"  # corrected via the workflow after the fact


class AttendanceStatus(str, Enum):
    present = "present"
    absent = "absent"
    on_leave = "on_leave"
    pending_approval = "pending_approval"  # field duty / regularisation
    # awaiting the workflow's decision


class Attendance(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)

    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_in_lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_in_selfie_url: Mapped[str] = mapped_column(String(255), default="")
    check_in_accuracy_m: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_out_lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    source: Mapped[AttendanceSource] = mapped_column(SAEnum(AttendanceSource), default=AttendanceSource.geofence)
    status: Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus), default=AttendanceStatus.present)
    field_duty_reason: Mapped[str] = mapped_column(Text, default="")
    is_within_geofence: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821
    site: Mapped["Site | None"] = relationship(lazy="selectin")  # noqa: F821
