"""Demo/dev data for manual testing — one login per RFP role, a small
organisation structure, and a handful of records in every module so the
UI has something to show immediately after a fresh clone.

Not run automatically at startup (unlike app.core.rbac_sync and
app.services.workflow_seed): this is sample data, not system
configuration, so it is only ever invoked deliberately via
``scripts/seed_demo.py``. Idempotent — safe to run again on a database
that already has this data; it skips anything it finds already created
by email/code rather than erroring or duplicating it.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Asset,
    AssetCategory,
    AppraisalCycle,
    Attendance,
    AttendanceStatus,
    Division,
    Employee,
    EmploymentCategory,
    LeaveApplication,
    LeaveStatus,
    LeaveType,
    Project,
    Role,
    SalaryStructure,
    Site,
    SiteKind,
    User,
)
from app.services import appraisal as appraisal_service

DEMO_PASSWORD = "Demo@1234"
# Not aaranyak.org itself (so these can't be mistaken for real staff
# emails) and not a reserved TLD like .test/.example/.invalid — pydantic's
# EmailStr validator rejects those as special-use, non-routable domains.
DEMO_EMAIL_DOMAIN = "aaranyak-demo.org"

# (role_code, email_local_part, full_name, division_code)
_DEMO_USERS: list[tuple[str, str, str, str | None]] = [
    ("admin", "admin", "Admin User", None),
    ("hr_admin", "hr", "Hira Das (HR)", None),
    ("finance", "finance", "Farid Ahmed (Finance)", None),
    ("executive", "executive", "Ekta Bordoloi (Executive)", None),
    ("division_head", "divisionhead", "Deepjyoti Saikia (Division Head)", "RHN"),
    ("project_lead", "projectlead", "Pranab Gogoi (Project Lead)", "RHN"),
    ("coordinator", "coordinator", "Chandana Phukan (Coordinator)", "RHN"),
    ("project_staff", "projectstaff", "Projit Kalita (Project Staff)", "RHN"),
    ("field_staff", "fieldstaff", "Farhana Begum (Field Staff)", "RHN"),
    ("other_authorised", "auditor", "Other Authorised (Auditor)", None),
]

_DIVISIONS = [
    ("Rhino Research", "RHN"),
    ("Elephant Corridor", "ELC"),
]

_LEAVE_TYPES = [
    ("Casual Leave", 12, True, 6, True),
    ("Earned Leave", 15, True, 15, True),
    ("Sick Leave", 10, False, 0, True),
    ("Maternity Leave", 180, False, 0, True),
]


def _get_or_create_division(db: Session, name: str, code: str) -> Division:
    div = db.query(Division).filter_by(code=code).first()
    if div is None:
        div = Division(name=name, code=code)
        db.add(div)
        db.flush()
    return div


def _get_or_create_user(db: Session, role_code: str, email: str, full_name: str, division_id: int | None) -> User:
    user = db.query(User).filter_by(email=email).first()
    if user is not None:
        return user
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        role_id=role.id,
        division_id=division_id,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    if not db.query(Employee).filter_by(user_id=user.id).first() and division_id is not None:
        db.add(
            Employee(
                employee_code=f"AAR-{user.id:04d}",
                full_name=full_name,
                division_id=division_id,
                employment_category=EmploymentCategory.regular,
                designation=role_code.replace("_", " ").title(),
                date_of_joining=date.today() - timedelta(days=365),
                user_id=user.id,
            )
        )
        db.flush()
    return user


def seed_demo_data(db: Session) -> dict:
    created: dict = {"users": [], "divisions": [], "leave_types": []}

    divisions = {code: _get_or_create_division(db, name, code) for name, code in _DIVISIONS}
    created["divisions"] = list(divisions.keys())

    if not db.query(Project).filter_by(code="RHN-CAM").first():
        db.add(Project(name="Camera Trap Survey", code="RHN-CAM", division_id=divisions["RHN"].id, donor="WWF"))
    if not db.query(Site).filter_by(name="Guwahati Office").first():
        db.add(Site(name="Guwahati Office", kind=SiteKind.office, division_id=divisions["RHN"].id, address="Guwahati, Assam"))
    if not db.query(Site).filter_by(name="Kaziranga Field Camp").first():
        db.add(
            Site(
                name="Kaziranga Field Camp",
                kind=SiteKind.field,
                division_id=divisions["RHN"].id,
                address="Kaziranga, Assam",
                geofence_shape="circle",
                geofence_center_lat=26.5775,
                geofence_center_lng=93.1714,
                geofence_radius_m=500,
            )
        )
    db.flush()

    for name, days, carry, max_carry, requires_approval in _LEAVE_TYPES:
        if not db.query(LeaveType).filter_by(name=name).first():
            db.add(
                LeaveType(
                    name=name,
                    annual_entitlement_days=days,
                    carry_forward_allowed=carry,
                    max_carry_forward_days=max_carry,
                    requires_approval=requires_approval,
                )
            )
            created["leave_types"].append(name)
    db.flush()

    for role_code, local_part, full_name, division_code in _DEMO_USERS:
        email = f"{local_part}@{DEMO_EMAIL_DOMAIN}"
        division_id = divisions[division_code].id if division_code else None
        _get_or_create_user(db, role_code, email, full_name, division_id)
        created["users"].append({"email": email, "role": role_code, "password": DEMO_PASSWORD})
    db.commit()

    _seed_sample_records(db, divisions)
    db.commit()
    return created


def _seed_sample_records(db: Session, divisions: dict[str, Division]) -> None:
    field_staff = db.query(Employee).join(User, Employee.user_id == User.id).filter(User.email == f"fieldstaff@{DEMO_EMAIL_DOMAIN}").first()
    project_staff = db.query(Employee).join(User, Employee.user_id == User.id).filter(User.email == f"projectstaff@{DEMO_EMAIL_DOMAIN}").first()
    if field_staff is None or project_staff is None:
        return

    # Salary structures, so a payroll run has something to generate.
    for emp in (field_staff, project_staff):
        if not db.query(SalaryStructure).filter_by(employee_id=emp.id).first():
            db.add(
                SalaryStructure(
                    employee_id=emp.id,
                    effective_from=date.today() - timedelta(days=180),
                    basic=30000,
                    hra=12000,
                    other_allowances=3000,
                    pf_deduction=3600,
                    professional_tax=200,
                    bank_account_number="123456789012",
                    bank_ifsc="SBIN0001234",
                )
            )

    # A week of attendance for the field staff this month.
    today = date.today()
    for offset in range(1, 6):
        work_date = today - timedelta(days=offset)
        if not db.query(Attendance).filter_by(employee_id=field_staff.id, work_date=work_date).first():
            db.add(Attendance(employee_id=field_staff.id, work_date=work_date, status=AttendanceStatus.present))

    # One pending leave application for the project staff.
    casual = db.query(LeaveType).filter_by(name="Casual Leave").first()
    if casual is not None and not db.query(LeaveApplication).filter_by(employee_id=project_staff.id).first():
        db.add(
            LeaveApplication(
                employee_id=project_staff.id,
                leave_type_id=casual.id,
                start_date=today + timedelta(days=7),
                end_date=today + timedelta(days=8),
                days=2,
                reason="Family function",
                status=LeaveStatus.pending,
            )
        )

    # One asset in the register.
    if not db.query(Asset).filter_by(asset_code="AST-00001").first():
        db.add(
            Asset(
                asset_code="AST-00001",
                name="Camera Trap (Bushnell)",
                category=AssetCategory.field_equipment,
                purchase_value=18000,
                division_id=divisions["RHN"].id,
            )
        )

    db.flush()

    # One open appraisal cycle with reviews generated for active employees.
    if not db.query(AppraisalCycle).filter_by(name="FY 2025-26").first():
        cycle = AppraisalCycle(name="FY 2025-26", period_start=date(2025, 4, 1), period_end=date(2026, 3, 31))
        db.add(cycle)
        db.flush()
        appraisal_service.create_reviews_for_cycle(db, cycle)
