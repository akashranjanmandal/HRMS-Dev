from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.organisation import SiteKind


# --------------------------------------------------------------- divisions
class DivisionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=20)


class DivisionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    head_user_id: int | None = None
    is_active: bool | None = None


class DivisionOut(BaseModel):
    id: int
    name: str
    code: str
    head_user_id: int | None
    is_active: bool


# ----------------------------------------------------------------- projects
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=20)
    division_id: int
    donor: str = Field(default="", max_length=160)
    lead_user_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    donor: str | None = None
    lead_user_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_active: bool | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    code: str
    division_id: int
    donor: str
    lead_user_id: int | None
    is_active: bool


# -------------------------------------------------------------------- sites
class CircleGeofence(BaseModel):
    shape: Literal["circle"]
    center_lat: float = Field(ge=-90, le=90)
    center_lng: float = Field(ge=-180, le=180)
    radius_m: float = Field(gt=0, le=50_000)


class PolygonGeofence(BaseModel):
    shape: Literal["polygon"]
    points: list[list[float]] = Field(min_length=3)

    @model_validator(mode="after")
    def _points_are_lat_lng_pairs(self):
        for p in self.points:
            if len(p) != 2:
                raise ValueError("Each polygon point must be [lat, lng]")
            lat, lng = p
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError(f"Point {p} is out of range for lat/lng")
        return self


GeofenceIn = CircleGeofence | PolygonGeofence


class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: SiteKind = SiteKind.office
    division_id: int | None = None
    address: str = Field(default="", max_length=2000)
    geofence: GeofenceIn | None = None


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    division_id: int | None = None
    address: str | None = None
    geofence: GeofenceIn | None = None
    is_active: bool | None = None


class GeofenceOut(BaseModel):
    shape: Literal["circle", "polygon"]
    center_lat: float | None = None
    center_lng: float | None = None
    radius_m: float | None = None
    points: list[list[float]] | None = None


class SiteOut(BaseModel):
    id: int
    name: str
    kind: SiteKind
    division_id: int | None
    address: str
    is_active: bool
    geofence: GeofenceOut | None


class CheckPointIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class CheckPointOut(BaseModel):
    inside: bool
    distance_m: float | None = None  # populated for circle fences only
