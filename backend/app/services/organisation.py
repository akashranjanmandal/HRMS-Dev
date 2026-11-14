"""Small lookups shared by the organisation router and anything else
(the employee master, eventually payroll/asset modules) that needs to
confirm a division/project/site actually exists before attaching
something to it.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Division


def get_division_or_400(db: Session, division_id: int) -> Division:
    division = db.get(Division, division_id)
    if division is None:
        raise HTTPException(status_code=400, detail="Division not found")
    return division
