"""Performance appraisal (RFP 4.1 §4.8): an annual cycle, self-assessment,
supervisor assessment, Division Head review, routed through the workflow
engine for the sign-off chain.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class AppraisalStage(str, Enum):
    self_assessment = "self_assessment"
    supervisor_review = "supervisor_review"
    division_head_review = "division_head_review"
    completed = "completed"


class AppraisalCycle(Base):
    """One annual (or other period) appraisal cycle, admin-created."""

    __tablename__ = "appraisal_cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reviews: Mapped[list["AppraisalReview"]] = relationship(back_populates="cycle", cascade="all, delete-orphan")


class AppraisalReview(Base):
    """One employee's appraisal within one cycle — the record that moves
    through self -> supervisor -> Division Head."""

    __tablename__ = "appraisal_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    stage: Mapped[AppraisalStage] = mapped_column(SAEnum(AppraisalStage), default=AppraisalStage.self_assessment, index=True)

    self_assessment_text: Mapped[str] = mapped_column(Text, default="")
    self_rating: Mapped[int | None] = mapped_column(nullable=True)  # 1-5

    supervisor_comments: Mapped[str] = mapped_column(Text, default="")
    supervisor_rating: Mapped[int | None] = mapped_column(nullable=True)

    division_head_comments: Mapped[str] = mapped_column(Text, default="")
    division_head_rating: Mapped[int | None] = mapped_column(nullable=True)
    salary_revision_recommended: Mapped[bool] = mapped_column(default=False)
    recommendation_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    cycle: Mapped[AppraisalCycle] = relationship(back_populates="reviews")
    employee: Mapped["Employee"] = relationship(lazy="selectin")  # noqa: F821
    ratings: Mapped[list["AppraisalRating"]] = relationship(back_populates="review", cascade="all, delete-orphan")


class AppraisalRating(Base):
    """One KPI/parameter rated within a review. The parameter set itself
    is admin-configured (RFP: "performance parameters, KPIs, rating
    scales") — see app/services/appraisal_params.py for the default set,
    rather than hard-coded columns per parameter."""

    __tablename__ = "appraisal_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("appraisal_reviews.id", ondelete="CASCADE"), index=True)
    parameter: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column()  # 1-5
    comments: Mapped[str] = mapped_column(Text, default="")

    review: Mapped[AppraisalReview] = relationship(back_populates="ratings")
