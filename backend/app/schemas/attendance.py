from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceSource, AttendanceStatus


class CheckInIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    selfie_base64: str = Field(min_length=1)
    field_duty_reason: str = Field(default="", max_length=2000)


class CheckOutIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    work_date: date
    site_id: int | None
    site_name: str | None
    check_in_at: datetime | None
    check_out_at: datetime | None
    source: AttendanceSource
    status: AttendanceStatus
    field_duty_reason: str
    is_within_geofence: bool
    approval_request_id: int | None = None


class RegularisationIn(BaseModel):
    work_date: date
    reason: str = Field(min_length=1, max_length=2000)
