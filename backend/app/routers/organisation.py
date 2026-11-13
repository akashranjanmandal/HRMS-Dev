"""Divisions, projects and sites — the organisation structure (RFP 3.2).

Masters are managed by an administrator with no code change needed:
``organisation:view/create/edit/delete``. A site's geo-fence is checked
against a point with ``/sites/{id}/check-point``, which the attendance
check-in flow (checklist 4.1) calls on every check-in — it needs only
``attendance:create`` (the same permission that lets someone mark their
own attendance at all), not organisation-admin rights.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_perm
from app.core.permissions import permission_code
from app.models import Division, Project, Site, User
from app.schemas.organisation import (
    CheckPointIn,
    CheckPointOut,
    DivisionIn,
    DivisionOut,
    DivisionUpdate,
    GeofenceOut,
    ProjectIn,
    ProjectOut,
    ProjectUpdate,
    SiteIn,
    SiteOut,
    SiteUpdate,
)
from app.services.geofence import haversine_m, point_in_circle, point_in_polygon

router = APIRouter(tags=["Organisation"])

VIEW = require_perm(permission_code("organisation", "view"))
CREATE = require_perm(permission_code("organisation", "create"))
EDIT = require_perm(permission_code("organisation", "edit"))
MARK_ATTENDANCE = require_perm(permission_code("attendance", "create"))


# --------------------------------------------------------------- divisions
@router.get("/api/divisions", response_model=list[DivisionOut])
def list_divisions(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(VIEW),
):
    q = db.query(Division)
    if not include_inactive:
        q = q.filter(Division.is_active.is_(True))
    return q.order_by(Division.name).all()


@router.post("/api/divisions", response_model=DivisionOut, status_code=status.HTTP_201_CREATED)
def create_division(payload: DivisionIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    if db.query(Division).filter(Division.code == payload.code).first():
        raise HTTPException(status_code=409, detail=f"Division code '{payload.code}' is already in use")
    division = Division(**payload.model_dump())
    db.add(division)
    db.commit()
    db.refresh(division)
    return division


@router.put("/api/divisions/{division_id}", response_model=DivisionOut)
def update_division(
    division_id: int,
    payload: DivisionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(EDIT),
):
    division = db.get(Division, division_id)
    if division is None:
        raise HTTPException(status_code=404, detail="Division not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(division, k, v)
    db.commit()
    db.refresh(division)
    return division


# ----------------------------------------------------------------- projects
@router.get("/api/projects", response_model=list[ProjectOut])
def list_projects(
    division_id: int | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(VIEW),
):
    q = db.query(Project)
    if division_id is not None:
        q = q.filter(Project.division_id == division_id)
    if not include_inactive:
        q = q.filter(Project.is_active.is_(True))
    return q.order_by(Project.name).all()


@router.post("/api/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    if db.get(Division, payload.division_id) is None:
        raise HTTPException(status_code=400, detail="Division not found")
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.put("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(EDIT),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return project


# -------------------------------------------------------------------- sites
def _geofence_out(site: Site) -> GeofenceOut | None:
    if site.geofence_shape is None:
        return None
    if site.geofence_shape.value == "circle":
        return GeofenceOut(
            shape="circle",
            center_lat=site.geofence_center_lat,
            center_lng=site.geofence_center_lng,
            radius_m=site.geofence_radius_m,
        )
    points = [
        [float(x) for x in pair.split(",")]
        for pair in site.geofence_points_csv.split(";")
        if pair
    ]
    return GeofenceOut(shape="polygon", points=points)


def _apply_geofence(site: Site, geofence) -> None:
    if geofence is None:
        site.geofence_shape = None
        site.geofence_center_lat = site.geofence_center_lng = site.geofence_radius_m = None
        site.geofence_points_csv = ""
        return
    if geofence.shape == "circle":
        site.geofence_shape = "circle"
        site.geofence_center_lat = geofence.center_lat
        site.geofence_center_lng = geofence.center_lng
        site.geofence_radius_m = geofence.radius_m
        site.geofence_points_csv = ""
    else:
        site.geofence_shape = "polygon"
        site.geofence_center_lat = site.geofence_center_lng = site.geofence_radius_m = None
        site.geofence_points_csv = ";".join(f"{lat},{lng}" for lat, lng in geofence.points)


def _site_out(site: Site) -> SiteOut:
    return SiteOut(
        id=site.id,
        name=site.name,
        kind=site.kind,
        division_id=site.division_id,
        address=site.address,
        is_active=site.is_active,
        geofence=_geofence_out(site),
    )


@router.get("/api/sites", response_model=list[SiteOut])
def list_sites(
    division_id: int | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(VIEW),
):
    q = db.query(Site)
    if division_id is not None:
        q = q.filter(Site.division_id == division_id)
    if not include_inactive:
        q = q.filter(Site.is_active.is_(True))
    return [_site_out(s) for s in q.order_by(Site.name).all()]


@router.post("/api/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(payload: SiteIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    if payload.division_id is not None and db.get(Division, payload.division_id) is None:
        raise HTTPException(status_code=400, detail="Division not found")
    site = Site(name=payload.name, kind=payload.kind, division_id=payload.division_id, address=payload.address)
    _apply_geofence(site, payload.geofence)
    db.add(site)
    db.commit()
    db.refresh(site)
    return _site_out(site)


@router.put("/api/sites/{site_id}", response_model=SiteOut)
def update_site(site_id: int, payload: SiteUpdate, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    data = payload.model_dump(exclude_unset=True)
    if "geofence" in data:
        _apply_geofence(site, payload.geofence)
        data.pop("geofence")
    for k, v in data.items():
        setattr(site, k, v)
    db.commit()
    db.refresh(site)
    return _site_out(site)


@router.post("/api/sites/{site_id}/check-point", response_model=CheckPointOut)
def check_point(
    site_id: int,
    payload: CheckPointIn,
    db: Session = Depends(get_db),
    user: User = Depends(MARK_ATTENDANCE),
):
    """Is (lat, lng) inside this site's geo-fence? Used by attendance
    check-in to confirm the staff member is really where they say."""
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    if site.geofence_shape is None:
        raise HTTPException(status_code=404, detail="This site has no geo-fence drawn yet")

    if site.geofence_shape.value == "circle":
        distance = haversine_m(payload.lat, payload.lng, site.geofence_center_lat, site.geofence_center_lng)
        return CheckPointOut(inside=distance <= site.geofence_radius_m, distance_m=round(distance, 1))

    points = [tuple(float(x) for x in pair.split(",")) for pair in site.geofence_points_csv.split(";") if pair]
    return CheckPointOut(inside=point_in_polygon(payload.lat, payload.lng, points))
