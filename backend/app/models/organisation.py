"""Organisation structure: divisions, projects, sites.

Shape (RFP 3.2, 4.9, 7):

    Division (13, each with a Division Head)
      \\
       Project (donor-funded, cuts across divisions via staffing — not modelled here)
    Site (office or field location, optionally linked to one division, with
          an optional geo-fence used for attendance)

A Project belongs to one division for reporting (RFP: "division-wise salary
information", "project-wise staff"), but staff may work on several projects
at once — that assignment is a separate table, added with the employee
master (checklist 2.5).
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class SiteKind(str, Enum):
    office = "office"
    field = "field"


class GeofenceShape(str, Enum):
    circle = "circle"
    polygon = "polygon"


class Division(Base):
    __tablename__ = "divisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    head_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="division")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id"))
    donor: Mapped[str] = mapped_column(String(160), default="")
    lead_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    division: Mapped[Division] = relationship(back_populates="projects", lazy="selectin")


class Site(Base):
    """An office or field location. A field site may carry a geo-fence used
    to confirm a check-in happened at the right place (checklist 4.1)."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[SiteKind] = mapped_column(SAEnum(SiteKind), default=SiteKind.office)
    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True)
    address: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Geofence, flattened onto the site row rather than a separate table:
    # a site has at most one boundary, and this keeps "has this site got a
    # fence yet" a single null check instead of a join.
    geofence_shape: Mapped[GeofenceShape | None] = mapped_column(SAEnum(GeofenceShape), nullable=True)
    geofence_center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_radius_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Polygon points stored as "lat,lng;lat,lng;..." — simple, and the only
    # consumer is this module's own (de)serialisation in the schema layer.
    geofence_points_csv: Mapped[str] = mapped_column(Text, default="")

    division: Mapped[Division | None] = relationship(lazy="selectin")
