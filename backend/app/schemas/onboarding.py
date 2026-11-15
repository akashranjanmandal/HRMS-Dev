from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.onboarding import VacancyStatus


class VacancyIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    division_id: int
    project_id: int | None = None
    terms_of_reference: str = Field(default="", max_length=8000)
    positions_open: int = Field(default=1, ge=1)


class VacancyOut(BaseModel):
    id: int
    title: str
    division_id: int
    project_id: int | None
    terms_of_reference: str
    positions_open: int
    status: VacancyStatus
    created_at: datetime
    published_at: datetime | None
    closed_at: datetime | None
    approval_request_id: int | None = None


class CandidateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=160)
    phone: str = Field(default="", max_length=30)
    resume_url: str = Field(default="", max_length=255)
    cover_note: str = Field(default="", max_length=4000)


class CandidateStageUpdate(BaseModel):
    stage: str = Field(pattern="^(applied|shortlisted|interviewed|selected|rejected)$")


class CandidateOut(BaseModel):
    id: int
    vacancy_id: int
    full_name: str
    email: str
    phone: str
    resume_url: str
    cover_note: str
    stage: str
    created_at: datetime


class InterviewIn(BaseModel):
    scheduled_at: datetime | None = None
    interviewer_id: int | None = None


class InterviewEvaluationIn(BaseModel):
    evaluation_notes: str = Field(default="", max_length=8000)
    recommendation: str = Field(pattern="^(select|reject|hold)$")


class InterviewOut(BaseModel):
    id: int
    candidate_id: int
    scheduled_at: datetime | None
    interviewer_id: int | None
    evaluation_notes: str
    recommendation: str
    created_at: datetime


class SelectionIn(BaseModel):
    """Selecting a candidate creates the Employee record and, through the
    workflow, routes the selection decision itself for approval (RFP:
    'approval of selection')."""

    date_of_joining: date | None = None
    designation: str = Field(default="", max_length=160)
    employment_category: str = Field(default="regular")


class AppointmentLetterOut(BaseModel):
    candidate_id: int
    employee_id: int | None
    letter_text: str


class OnboardingTaskOut(BaseModel):
    id: int
    employee_id: int
    label: str
    sort_order: int
    status: str
    completed_at: datetime | None
    notes: str


class OnboardingTaskUpdate(BaseModel):
    status: str = Field(pattern="^(pending|done|not_applicable)$")
    notes: str = Field(default="", max_length=2000)


class OrientationSessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    scheduled_date: date | None = None
    materials_url: str = Field(default="", max_length=255)


class OrientationSessionOut(OrientationSessionIn):
    id: int
    created_at: datetime


class OrientationAttendanceIn(BaseModel):
    employee_id: int


class OrientationAttendanceOut(BaseModel):
    id: int
    session_id: int
    employee_id: int
    employee_name: str
    attended: bool
    confirmed_by_candidate: bool
