"""Performance appraisal (RFP 4.1 §4.8): admin-created cycles, one review
per active employee, moving through self-assessment -> supervisor review
-> Division Head review -> completed. Each stage is a structured,
multi-field hand-off (ratings, comments, a salary-revision recommendation)
rather than a single approve/reject, so it is modelled as its own stage
machine on the review itself rather than routed through the generic
workflow engine.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_perm
from app.core.permissions import permission_code
from app.core.scope import Scope, scope_for_role
from app.models import AppraisalCycle, AppraisalRating, AppraisalReview, AppraisalStage, Employee, User
from app.schemas.appraisal import (
    AppraisalCycleIn,
    AppraisalCycleOut,
    AppraisalReviewOut,
    DivisionHeadReviewIn,
    SelfAssessmentIn,
    SupervisorReviewIn,
)
from app.services import appraisal as appraisal_service

router = APIRouter(prefix="/api/appraisal", tags=["Appraisal"])

VIEW = require_perm(permission_code("appraisal", "view"))
CREATE = require_perm(permission_code("appraisal", "create"))
APPROVE = require_perm(permission_code("appraisal", "approve"))


def _my_employee(db: Session, user: User) -> Employee:
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="No employee record is linked to your account")
    return emp


def _out(review: AppraisalReview) -> AppraisalReviewOut:
    return AppraisalReviewOut(
        id=review.id,
        cycle_id=review.cycle_id,
        cycle_name=review.cycle.name,
        employee_id=review.employee_id,
        employee_name=review.employee.full_name,
        stage=review.stage,
        self_assessment_text=review.self_assessment_text,
        self_rating=review.self_rating,
        supervisor_comments=review.supervisor_comments,
        supervisor_rating=review.supervisor_rating,
        division_head_comments=review.division_head_comments,
        division_head_rating=review.division_head_rating,
        salary_revision_recommended=review.salary_revision_recommended,
        recommendation_notes=review.recommendation_notes,
        ratings=review.ratings,
        created_at=review.created_at,
    )


# ------------------------------------------------------------------- cycles
@router.get("/cycles", response_model=list[AppraisalCycleOut])
def list_cycles(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    return db.query(AppraisalCycle).order_by(AppraisalCycle.period_start.desc()).all()


@router.post("/cycles", response_model=AppraisalCycleOut, status_code=201)
def create_cycle(payload: AppraisalCycleIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    cycle = AppraisalCycle(**payload.model_dump())
    db.add(cycle)
    db.flush()
    appraisal_service.create_reviews_for_cycle(db, cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


# ------------------------------------------------------------------------ mine
@router.get("/mine", response_model=list[AppraisalReviewOut])
def my_reviews(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    emp = _my_employee(db, user)
    rows = db.query(AppraisalReview).filter(AppraisalReview.employee_id == emp.id).order_by(AppraisalReview.created_at.desc()).all()
    return [_out(r) for r in rows]


def _get_review_or_404(db: Session, review_id: int) -> AppraisalReview:
    review = db.get(AppraisalReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Appraisal review not found")
    return review


@router.post("/reviews/{review_id}/self-assessment", response_model=AppraisalReviewOut)
def submit_self_assessment(review_id: int, payload: SelfAssessmentIn, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    review = _get_review_or_404(db, review_id)
    emp = _my_employee(db, user)
    if review.employee_id != emp.id:
        raise HTTPException(status_code=403, detail="Not your appraisal review")
    if review.stage != AppraisalStage.self_assessment:
        raise HTTPException(status_code=400, detail=f"Review is already at stage {review.stage.value}")

    review.self_assessment_text = payload.self_assessment_text
    review.self_rating = payload.self_rating
    for r in payload.ratings:
        db.add(AppraisalRating(review_id=review.id, parameter=r.parameter, rating=r.rating, comments=r.comments))
    review.stage = AppraisalStage.supervisor_review
    db.commit()
    db.refresh(review)
    return _out(review)


@router.get("", response_model=list[AppraisalReviewOut])
def list_reviews(
    stage: AppraisalStage | None = None,
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(APPROVE),
):
    """For supervisors/Division Heads/HR to see reviews awaiting their
    action, scoped to their division like other approval-adjacent lists."""
    scope = scope_for_role(user.role.code)
    q = db.query(AppraisalReview).join(Employee, AppraisalReview.employee_id == Employee.id)
    if scope == Scope.division:
        if user.division_id is None:
            return []
        q = q.filter(Employee.division_id == user.division_id)
    if cycle_id is not None:
        q = q.filter(AppraisalReview.cycle_id == cycle_id)
    if stage is not None:
        q = q.filter(AppraisalReview.stage == stage)
    rows = q.order_by(AppraisalReview.created_at.desc()).all()
    return [_out(r) for r in rows]


@router.post("/reviews/{review_id}/supervisor-review", response_model=AppraisalReviewOut)
def submit_supervisor_review(review_id: int, payload: SupervisorReviewIn, db: Session = Depends(get_db), user: User = Depends(APPROVE)):
    review = _get_review_or_404(db, review_id)
    if review.stage != AppraisalStage.supervisor_review:
        raise HTTPException(status_code=400, detail=f"Review is at stage {review.stage.value}, not awaiting supervisor review")
    scope = scope_for_role(user.role.code)
    if scope == Scope.division and review.employee.division_id != user.division_id:
        raise HTTPException(status_code=403, detail="Not in your division")

    review.supervisor_comments = payload.supervisor_comments
    review.supervisor_rating = payload.supervisor_rating
    review.stage = AppraisalStage.division_head_review
    db.commit()
    db.refresh(review)
    return _out(review)


@router.post("/reviews/{review_id}/division-head-review", response_model=AppraisalReviewOut)
def submit_division_head_review(review_id: int, payload: DivisionHeadReviewIn, db: Session = Depends(get_db), user: User = Depends(APPROVE)):
    review = _get_review_or_404(db, review_id)
    if review.stage != AppraisalStage.division_head_review:
        raise HTTPException(status_code=400, detail=f"Review is at stage {review.stage.value}, not awaiting Division Head review")
    scope = scope_for_role(user.role.code)
    if scope == Scope.division and review.employee.division_id != user.division_id:
        raise HTTPException(status_code=403, detail="Not in your division")

    review.division_head_comments = payload.division_head_comments
    review.division_head_rating = payload.division_head_rating
    review.salary_revision_recommended = payload.salary_revision_recommended
    review.recommendation_notes = payload.recommendation_notes
    review.stage = AppraisalStage.completed
    db.commit()
    db.refresh(review)
    return _out(review)
