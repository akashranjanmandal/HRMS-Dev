"""Dashboards and reports (RFP Section 7). Most reports are computed
on-the-fly from the other modules' own tables (see
app/services/reports.py) — there is nothing to persist for "employee
strength" or "division-wise staff". ``SavedReport`` exists only for the
handful of exports worth remembering were generated (contract-expiry,
separation lists) for audit purposes; it is not the reporting engine
itself.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_key: Mapped[str] = mapped_column(String(80), index=True)
    format: Mapped[str] = mapped_column(String(10))  # pdf / xlsx / docx
    generated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    file_path: Mapped[str] = mapped_column(String(255), default="")
