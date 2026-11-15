"""Recruitment, onboarding, orientation (RFP 4.1 §4.2-4.4).

    Vacancy (approved via the workflow) → Candidate (applies, is tracked
    through shortlisting/interviews/selection) → selection is itself
    routed through the workflow → an Employee record is created →
    OnboardingTask checklist items → OrientationSession + attendance.

Appointment letters are generated from the vacancy/candidate data at
selection time (see app/services/letters.py) rather than stored as a
separate editable entity — the letter is a rendered document, not
something with its own lifecycle.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class VacancyStatus(str, Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    published = "published"
    closed = "closed"


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    terms_of_reference: Mapped[str] = mapped_column(Text, default="")
    positions_open: Mapped[int] = mapped_column(default=1)
    status: Mapped[VacancyStatus] = mapped_column(SAEnum(VacancyStatus), default=VacancyStatus.draft, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    division: Mapped["Division"] = relationship(lazy="selectin")  # noqa: F821
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="vacancy")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(30), default="")
    resume_url: Mapped[str] = mapped_column(String(255), default="")
    cover_note: Mapped[str] = mapped_column(Text, default="")
    # Simple, HR-driven pipeline rather than a generic status enum, since
    # each stage genuinely means something different operationally:
    stage: Mapped[str] = mapped_column(
        String(30), default="applied"
    )  # applied -> shortlisted -> interviewed -> selected | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vacancy: Mapped[Vacancy] = relationship(back_populates="candidates", lazy="selectin")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    evaluation_notes: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(20), default="")  # select / reject / hold
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="interviews", lazy="selectin")


class OnboardingTaskStatus(str, Enum):
    pending = "pending"
    done = "done"
    not_applicable = "not_applicable"


class OnboardingTask(Base):
    """One checklist item for one new employee (RFP 4.3): document
    collection/verification, division/project allocation, reporting
    officer assignment, asset allocation, account setup, policy
    acknowledgement. The checklist's own item list is configurable — see
    app/services/onboarding_checklist.py for the default set."""

    __tablename__ = "onboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    sort_order: Mapped[int] = mapped_column(default=0)
    status: Mapped[OnboardingTaskStatus] = mapped_column(SAEnum(OnboardingTaskStatus), default=OnboardingTaskStatus.pending)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821


class OrientationSession(Base):
    __tablename__ = "orientation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    materials_url: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attendances: Mapped[list["OrientationAttendance"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class OrientationAttendance(Base):
    __tablename__ = "orientation_attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("orientation_sessions.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    attended: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by_candidate: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[OrientationSession] = relationship(back_populates="attendances")
    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821
