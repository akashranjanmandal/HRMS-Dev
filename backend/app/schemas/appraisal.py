from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.appraisal import AppraisalStage


class AppraisalCycleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    period_start: date
    period_end: date


class AppraisalCycleOut(AppraisalCycleIn):
    id: int
    is_active: bool
    created_at: datetime


class AppraisalRatingIn(BaseModel):
    parameter: str = Field(min_length=1, max_length=120)
    rating: int = Field(ge=1, le=5)
    comments: str = Field(default="", max_length=2000)


class AppraisalRatingOut(AppraisalRatingIn):
    model_config = {"from_attributes": True}

    id: int


class SelfAssessmentIn(BaseModel):
    self_assessment_text: str = Field(default="", max_length=5000)
    self_rating: int = Field(ge=1, le=5)
    ratings: list[AppraisalRatingIn] = Field(default_factory=list)


class SupervisorReviewIn(BaseModel):
    supervisor_comments: str = Field(default="", max_length=5000)
    supervisor_rating: int = Field(ge=1, le=5)


class DivisionHeadReviewIn(BaseModel):
    division_head_comments: str = Field(default="", max_length=5000)
    division_head_rating: int = Field(ge=1, le=5)
    salary_revision_recommended: bool = False
    recommendation_notes: str = Field(default="", max_length=2000)


class AppraisalReviewOut(BaseModel):
    id: int
    cycle_id: int
    cycle_name: str
    employee_id: int
    employee_name: str
    stage: AppraisalStage
    self_assessment_text: str
    self_rating: int | None
    supervisor_comments: str
    supervisor_rating: int | None
    division_head_comments: str
    division_head_rating: int | None
    salary_revision_recommended: bool
    recommendation_notes: str
    ratings: list[AppraisalRatingOut]
    created_at: datetime
    approval_request_id: int | None = None
