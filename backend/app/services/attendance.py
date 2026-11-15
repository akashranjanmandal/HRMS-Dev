"""Attendance check-in/out logic (RFP 4.1 §4.5).

A check-in supplies a GPS point (and, for a geofenced check-in, a selfie).
This module decides, from that point alone, which site (if any) the
employee is inside, and whether the check-in counts as a normal
geofenced attendance or needs to be raised as field duty for a
supervisor's approval.
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models import Attendance, AttendanceSource, AttendanceStatus, LeaveApplication, LeaveStatus, Site
from app.services.geofence import point_in_circle, point_in_polygon

# A check-in's reported GPS accuracy must be at least this good to be
# trusted as "inside the fence" at all — RFP 4.5's own "accuracy check".
# A reading worse than this is treated as inconclusive rather than
# silently accepted, so a low-accuracy phone fix can't be used to spoof
# a geofenced check-in from just outside the boundary.
MAX_TRUSTED_ACCURACY_M = 100.0


def find_containing_site(db: Session, lat: float, lng: float) -> Site | None:
    """The first active site (if any) whose geo-fence contains this
    point. Sites with no geo-fence drawn yet are never matched."""
    sites = db.query(Site).filter(Site.is_active.is_(True), Site.geofence_shape.isnot(None)).all()
    for site in sites:
        if site.geofence_shape.value == "circle":
            if point_in_circle(
                lat, lng, center_lat=float(site.geofence_center_lat), center_lng=float(site.geofence_center_lng), radius_m=float(site.geofence_radius_m)
            ):
                return site
        else:
            points = [tuple(float(x) for x in pair.split(",")) for pair in site.geofence_points_csv.split(";") if pair]
            if point_in_polygon(lat, lng, points):
                return site
    return None


def today_attendance(db: Session, employee_id: int, work_date: date | None = None) -> Attendance | None:
    work_date = work_date or datetime.now(timezone.utc).date()
    return db.query(Attendance).filter(Attendance.employee_id == employee_id, Attendance.work_date == work_date).first()


def is_on_approved_leave(db: Session, employee_id: int, on_date: date) -> bool:
    return (
        db.query(LeaveApplication)
        .filter(
            LeaveApplication.employee_id == employee_id,
            LeaveApplication.status == LeaveStatus.approved,
            LeaveApplication.start_date <= on_date,
            LeaveApplication.end_date >= on_date,
        )
        .first()
        is not None
    )


def check_in(
    db: Session,
    *,
    employee_id: int,
    lat: float,
    lng: float,
    accuracy_m: float | None,
    selfie_url: str,
    field_duty_reason: str = "",
) -> Attendance:
    today = datetime.now(timezone.utc).date()
    existing = today_attendance(db, employee_id, today)
    if existing is not None and existing.check_in_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Already checked in today")

    site = find_containing_site(db, lat, lng)
    trusted_accuracy = accuracy_m is not None and accuracy_m <= MAX_TRUSTED_ACCURACY_M
    within_fence = site is not None and trusted_accuracy

    if not within_fence and not field_duty_reason:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="You are outside every site's boundary (or location accuracy is too low) — "
            "give a field-duty reason to check in anyway, pending your supervisor's approval",
        )

    record = existing or Attendance(employee_id=employee_id, work_date=today)
    record.site_id = site.id if site else None
    record.check_in_at = datetime.now(timezone.utc)
    record.check_in_lat = lat
    record.check_in_lng = lng
    record.check_in_accuracy_m = accuracy_m
    record.check_in_selfie_url = selfie_url
    record.is_within_geofence = within_fence
    record.field_duty_reason = field_duty_reason

    if within_fence:
        record.source = AttendanceSource.geofence
        record.status = AttendanceStatus.present
    else:
        record.source = AttendanceSource.field_duty
        record.status = AttendanceStatus.pending_approval

    if existing is None:
        db.add(record)
    db.flush()
    return record


def check_out(db: Session, *, employee_id: int, lat: float, lng: float) -> Attendance:
    from fastapi import HTTPException

    today = datetime.now(timezone.utc).date()
    record = today_attendance(db, employee_id, today)
    if record is None or record.check_in_at is None:
        raise HTTPException(status_code=400, detail="You haven't checked in today")
    if record.check_out_at is not None:
        raise HTTPException(status_code=400, detail="Already checked out today")

    record.check_out_at = datetime.now(timezone.utc)
    record.check_out_lat = lat
    record.check_out_lng = lng
    db.flush()
    return record
