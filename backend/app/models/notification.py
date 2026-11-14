"""On-screen notifications (RFP 3.5), alongside email: a user's own feed
of alerts raised by other modules — pending approvals, deadlines,
contract expiry, system announcements — as they land in later phases.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # A short machine code (e.g. "leave.approved", "contract.expiring") so
    # the frontend can route to the right place or pick an icon; free text
    # for the actual message, since each module's wording differs.
    kind: Mapped[str] = mapped_column(String(60), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
