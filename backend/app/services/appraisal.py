"""Performance appraisal (RFP 4.1 §4.8) — pure helpers for creating one
review per employee in a cycle, kept separate from the router so the
"everyone active gets a review" rule is testable without HTTP.
"""
from sqlalchemy.orm import Session

from app.models import AppraisalCycle, AppraisalReview, Employee, EmployeeStatus


def create_reviews_for_cycle(db: Session, cycle: AppraisalCycle) -> list[AppraisalReview]:
    existing_employee_ids = {
        r.employee_id for r in db.query(AppraisalReview).filter(AppraisalReview.cycle_id == cycle.id)
    }
    employees = db.query(Employee).filter(Employee.status == EmployeeStatus.active).all()
    reviews = []
    for emp in employees:
        if emp.id in existing_employee_ids:
            continue
        review = AppraisalReview(cycle_id=cycle.id, employee_id=emp.id)
        db.add(review)
        reviews.append(review)
    db.flush()
    return reviews
