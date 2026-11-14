"""The permanent employee code: AAR-<division code>-#### (e.g.
AAR-RHN-0001), matching the design board's own mockups. The serial is
per-division and never reused, even if an earlier employee in that
division is separated — a code, once issued, is permanent (RFP 4.1).
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Employee

_PREFIX = "AAR"


def generate_employee_code(db: Session, division_code: str) -> str:
    division_code = division_code.upper()
    prefix = f"{_PREFIX}-{division_code}-"
    count = (
        db.query(func.count(Employee.id))
        .filter(Employee.employee_code.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    serial = count + 1
    code = f"{prefix}{serial:04d}"
    # A gap from a direct-SQL import or manual code could already occupy
    # this serial — keep advancing until a free one is found rather than
    # ever risk a collision on the unique constraint.
    while db.query(Employee).filter(Employee.employee_code == code).first() is not None:
        serial += 1
        code = f"{prefix}{serial:04d}"
    return code
