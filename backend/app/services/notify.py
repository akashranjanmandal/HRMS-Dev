"""Raise an on-screen notification for one user.

Every module that needs to tell a user something happened (their leave
was approved, a contract is expiring, a deadline is near) calls this
instead of writing to the ``notifications`` table directly — one place to
change if the shape of a notification ever needs to grow (a link target,
a priority, grouping).

Callers commit alongside their own transaction (this only ``add``s, like
``app.core.audit.log``), so a notification and the action that caused it
land together or not at all.
"""
from sqlalchemy.orm import Session

from app.models import Notification


def notify(db: Session, *, user_id: int, kind: str, message: str) -> Notification:
    row = Notification(user_id=user_id, kind=kind, message=message)
    db.add(row)
    return row
