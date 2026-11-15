"""Leave application rules (RFP 4.6): the overlap and eligibility checks
run at submission time, and the balance a leave type's rules allow.
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import LeaveApplication, LeaveBalance, LeaveStatus, LeaveType


def working_days(start: date, end: date) -> float:
    """Calendar days inclusive of both ends. (Aaranyak has no fixed
    weekly-off pattern applied here yet — a future refinement could
    subtract weekends/holidays; for now every day in range counts, which
    matches how the demo data and the design mockups present "2 days".)"""
    if end < start:
        raise HTTPException(status_code=422, detail="End date must be on or after the start date")
    return float((end - start).days + 1)


def has_overlap(db: Session, employee_id: int, start: date, end: date, exclude_id: int | None = None) -> bool:
    q = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee_id,
        LeaveApplication.status.in_([LeaveStatus.pending, LeaveStatus.approved]),
        LeaveApplication.start_date <= end,
        LeaveApplication.end_date >= start,
    )
    if exclude_id is not None:
        q = q.filter(LeaveApplication.id != exclude_id)
    return q.first() is not None


def get_or_create_balance(db: Session, employee_id: int, leave_type: LeaveType, year: int) -> LeaveBalance:
    balance = (
        db.query(LeaveBalance)
        .filter(LeaveBalance.employee_id == employee_id, LeaveBalance.leave_type_id == leave_type.id, LeaveBalance.year == year)
        .first()
    )
    if balance is None:
        balance = LeaveBalance(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            year=year,
            opening_balance_days=float(leave_type.annual_entitlement_days),
            used_days=0,
        )
        db.add(balance)
        db.flush()
    return balance


def assert_eligible(db: Session, employee_id: int, leave_type: LeaveType, start: date, end: date, days: float) -> None:
    if has_overlap(db, employee_id, start, end):
        raise HTTPException(status_code=409, detail="This overlaps a leave application you already have pending or approved")
    balance = get_or_create_balance(db, employee_id, leave_type, start.year)
    if days > balance.available_days:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient balance: {balance.available_days:g} day(s) of {leave_type.name} available, {days:g} requested",
        )
