"""Recruitment, onboarding, orientation (RFP 4.1 §4.2-4.4).

    Vacancy (approved) -> published -> Candidates apply -> shortlist ->
    interview -> select (creates Employee + appointment letter + default
    onboarding checklist) -> orientation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_perm
from app.core.permissions import permission_code
from app.models import (
    Candidate,
    Employee,
    EmploymentCategory,
    Interview,
    OnboardingTask,
    OrientationAttendance,
    OrientationSession,
    RequestType,
    User,
    Vacancy,
    VacancyStatus,
)
from app.schemas.onboarding import (
    AppointmentLetterOut,
    CandidateIn,
    CandidateOut,
    CandidateStageUpdate,
    InterviewEvaluationIn,
    InterviewIn,
    InterviewOut,
    OnboardingTaskOut,
    OnboardingTaskUpdate,
    OrientationAttendanceIn,
    OrientationAttendanceOut,
    OrientationSessionIn,
    OrientationSessionOut,
    SelectionIn,
    VacancyIn,
    VacancyOut,
)
from app.services import letters
from app.services import workflow as workflow_service
from app.services.employee_code import generate_employee_code
from app.services.onboarding_checklist import create_default_tasks
from app.services.organisation import get_division_or_400

router = APIRouter(tags=["Recruitment & Onboarding"])

VIEW = require_perm(permission_code("recruitment", "view"))
CREATE = require_perm(permission_code("recruitment", "create"))
EDIT = require_perm(permission_code("recruitment", "edit"))
ONBOARD_VIEW = require_perm(permission_code("onboarding", "view"))
ONBOARD_EDIT = require_perm(permission_code("onboarding", "edit"))


# ------------------------------------------------------------------ vacancies
def _vacancy_out(db: Session, v: Vacancy) -> VacancyOut:
    req = workflow_service.find_approval_request(db, RequestType.recruitment_vacancy, v.id)
    return VacancyOut(
        id=v.id,
        title=v.title,
        division_id=v.division_id,
        project_id=v.project_id,
        terms_of_reference=v.terms_of_reference,
        positions_open=v.positions_open,
        status=v.status,
        created_at=v.created_at,
        published_at=v.published_at,
        closed_at=v.closed_at,
        approval_request_id=req.id if req else None,
    )


@router.get("/api/vacancies", response_model=list[VacancyOut])
def list_vacancies(db: Session = Depends(get_db), user: User = Depends(VIEW)):
    rows = db.query(Vacancy).order_by(Vacancy.created_at.desc()).all()
    return [_vacancy_out(db, v) for v in rows]


@router.get("/api/public/vacancies", response_model=list[VacancyOut])
def list_published_vacancies(db: Session = Depends(get_db)):
    """The public job page (RFP: 'vacancy publication') — no login needed."""
    rows = db.query(Vacancy).filter(Vacancy.status == VacancyStatus.published).order_by(Vacancy.published_at.desc()).all()
    return [_vacancy_out(db, v) for v in rows]


@router.post("/api/vacancies", response_model=VacancyOut, status_code=201)
def create_vacancy(payload: VacancyIn, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    get_division_or_400(db, payload.division_id)
    vacancy = Vacancy(**payload.model_dump(), created_by_id=user.id)
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return _vacancy_out(db, vacancy)


@router.post("/api/vacancies/{vacancy_id}/submit", response_model=VacancyOut)
def submit_vacancy_for_approval(vacancy_id: int, db: Session = Depends(get_db), user: User = Depends(CREATE)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if vacancy.status != VacancyStatus.draft:
        raise HTTPException(status_code=400, detail=f"Vacancy is already {vacancy.status.value}")
    vacancy.status = VacancyStatus.pending_approval
    workflow_service.submit_for_approval(
        db,
        request_type=RequestType.recruitment_vacancy,
        object_id=vacancy.id,
        requested_by_id=_requester_employee_id(db, user),
        division_id=vacancy.division_id,
        summary=f"Vacancy: {vacancy.title} ({vacancy.positions_open} position(s))",
    )
    db.commit()
    db.refresh(vacancy)
    return _vacancy_out(db, vacancy)


def _requester_employee_id(db: Session, user: User) -> int | None:
    """An Admin/HR user raising a vacancy or selection may have no
    Employee record of their own — ApprovalRequest.requested_by_id is
    nullable for exactly this case (see app/models/workflow.py)."""
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    return emp.id if emp else None


@router.post("/api/vacancies/{vacancy_id}/close", response_model=VacancyOut)
def close_vacancy(vacancy_id: int, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    from datetime import datetime, timezone

    vacancy.status = VacancyStatus.closed
    vacancy.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vacancy)
    return _vacancy_out(db, vacancy)


@workflow_service.on_outcome(RequestType.recruitment_vacancy)
def _on_vacancy_decided(db: Session, vacancy_id: int, outcome) -> None:
    from datetime import datetime, timezone

    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        return
    if outcome.value == "approved":
        vacancy.status = VacancyStatus.published
        vacancy.published_at = datetime.now(timezone.utc)
    else:
        vacancy.status = VacancyStatus.draft  # rejected/returned -> back to draft for correction


# ------------------------------------------------------------------ candidates
@router.get("/api/vacancies/{vacancy_id}/candidates", response_model=list[CandidateOut])
def list_candidates(vacancy_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    return db.query(Candidate).filter(Candidate.vacancy_id == vacancy_id).order_by(Candidate.created_at).all()


@router.post("/api/public/vacancies/{vacancy_id}/apply", response_model=CandidateOut, status_code=201)
def apply_to_vacancy(vacancy_id: int, payload: CandidateIn, db: Session = Depends(get_db)):
    """Public application — no login needed (RFP: candidates apply online)."""
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.status != VacancyStatus.published:
        raise HTTPException(status_code=404, detail="Vacancy not found or not currently open")
    candidate = Candidate(vacancy_id=vacancy_id, **payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.put("/api/candidates/{candidate_id}/stage", response_model=CandidateOut)
def update_candidate_stage(candidate_id: int, payload: CandidateStageUpdate, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.stage = payload.stage
    db.commit()
    db.refresh(candidate)
    return candidate


# ------------------------------------------------------------------ interviews
@router.post("/api/candidates/{candidate_id}/interviews", response_model=InterviewOut, status_code=201)
def schedule_interview(candidate_id: int, payload: InterviewIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    interview = Interview(candidate_id=candidate_id, **payload.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.put("/api/interviews/{interview_id}/evaluate", response_model=InterviewOut)
def evaluate_interview(interview_id: int, payload: InterviewEvaluationIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    interview.evaluation_notes = payload.evaluation_notes
    interview.recommendation = payload.recommendation
    db.commit()
    db.refresh(interview)
    return interview


# --------------------------------------------------------------------- selection
@router.post("/api/candidates/{candidate_id}/select", response_model=AppointmentLetterOut)
def select_candidate(candidate_id: int, payload: SelectionIn, db: Session = Depends(get_db), user: User = Depends(EDIT)):
    """Creates the Employee record immediately and routes the selection
    decision itself for approval (RFP: 'approval of selection') — the
    employee exists in the system from this point (so onboarding tasks
    can start), but the selection is marked pending until approved; a
    rejection at that stage is an exceptional HR correction path, not
    something this endpoint needs to undo automatically."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.stage == "selected":
        raise HTTPException(status_code=400, detail="This candidate has already been selected")

    vacancy = candidate.vacancy
    employee = Employee(
        employee_code=generate_employee_code(db, vacancy.division.code),
        full_name=candidate.full_name,
        personal_email=candidate.email,
        phone=candidate.phone,
        date_of_joining=payload.date_of_joining,
        designation=payload.designation or vacancy.title,
        division_id=vacancy.division_id,
        employment_category=EmploymentCategory(payload.employment_category),
    )
    db.add(employee)
    db.flush()

    candidate.stage = "selected"
    create_default_tasks(db, employee)

    requester_id = _requester_employee_id(db, user)
    workflow_service.submit_for_approval(
        db,
        request_type=RequestType.recruitment_selection,
        object_id=candidate.id,
        requested_by_id=requester_id or employee.id,
        division_id=vacancy.division_id,
        summary=f"Selection: {candidate.full_name} for {vacancy.title}",
    )

    letter_text = letters.appointment_letter_text(candidate, vacancy, employee)
    db.commit()
    return AppointmentLetterOut(candidate_id=candidate.id, employee_id=employee.id, letter_text=letter_text)


# ----------------------------------------------------------------- onboarding
@router.get("/api/employees/{employee_id}/onboarding-tasks", response_model=list[OnboardingTaskOut])
def list_onboarding_tasks(employee_id: int, db: Session = Depends(get_db), user: User = Depends(ONBOARD_VIEW)):
    return db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).order_by(OnboardingTask.sort_order).all()


@router.put("/api/onboarding-tasks/{task_id}", response_model=OnboardingTaskOut)
def update_onboarding_task(task_id: int, payload: OnboardingTaskUpdate, db: Session = Depends(get_db), user: User = Depends(ONBOARD_EDIT)):
    from datetime import datetime, timezone

    task = db.get(OnboardingTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Onboarding task not found")
    task.status = payload.status
    task.notes = payload.notes
    task.completed_at = datetime.now(timezone.utc) if payload.status == "done" else None
    task.completed_by_id = user.id if payload.status == "done" else None
    db.commit()
    db.refresh(task)
    return task


# ----------------------------------------------------------------- orientation
@router.get("/api/orientation-sessions", response_model=list[OrientationSessionOut])
def list_orientation_sessions(db: Session = Depends(get_db), user: User = Depends(ONBOARD_VIEW)):
    return db.query(OrientationSession).order_by(OrientationSession.scheduled_date).all()


@router.post("/api/orientation-sessions", response_model=OrientationSessionOut, status_code=201)
def create_orientation_session(payload: OrientationSessionIn, db: Session = Depends(get_db), user: User = Depends(ONBOARD_EDIT)):
    session = OrientationSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/api/orientation-sessions/{session_id}/attendees", response_model=OrientationAttendanceOut, status_code=201)
def add_orientation_attendee(session_id: int, payload: OrientationAttendanceIn, db: Session = Depends(get_db), user: User = Depends(ONBOARD_EDIT)):
    session = db.get(OrientationSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Orientation session not found")
    employee = db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=400, detail="Employee not found")
    row = OrientationAttendance(session_id=session_id, employee_id=payload.employee_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return OrientationAttendanceOut(
        id=row.id, session_id=row.session_id, employee_id=row.employee_id, employee_name=employee.full_name,
        attended=row.attended, confirmed_by_candidate=row.confirmed_by_candidate,
    )


@router.put("/api/orientation-attendance/{attendance_id}/mark-attended", response_model=OrientationAttendanceOut)
def mark_orientation_attended(attendance_id: int, db: Session = Depends(get_db), user: User = Depends(ONBOARD_EDIT)):
    row = db.get(OrientationAttendance, attendance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Orientation attendance record not found")
    row.attended = True
    db.commit()
    db.refresh(row)
    return OrientationAttendanceOut(
        id=row.id, session_id=row.session_id, employee_id=row.employee_id, employee_name=row.employee.full_name,
        attended=row.attended, confirmed_by_candidate=row.confirmed_by_candidate,
    )


@router.put("/api/orientation-attendance/{attendance_id}/confirm", response_model=OrientationAttendanceOut)
def confirm_orientation_completion(attendance_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The candidate themselves confirms completion (RFP: 'confirmation of
    completion from the candidate') — they must be the employee this row
    belongs to."""
    row = db.get(OrientationAttendance, attendance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Orientation attendance record not found")
    if row.employee.user_id != user.id:
        raise HTTPException(status_code=403, detail="This is not your own orientation record")
    row.confirmed_by_candidate = True
    db.commit()
    db.refresh(row)
    return OrientationAttendanceOut(
        id=row.id, session_id=row.session_id, employee_id=row.employee_id, employee_name=row.employee.full_name,
        attended=row.attended, confirmed_by_candidate=row.confirmed_by_candidate,
    )
