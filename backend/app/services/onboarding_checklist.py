"""The default onboarding checklist (RFP 4.1 §4.3) created for every new
employee. Administrator-editable in principle (a future admin screen
could add/remove tasks per employee), but every employee starts from
this same sensible default so nothing gets forgotten.
"""
from sqlalchemy.orm import Session

from app.models import Employee, OnboardingTask

DEFAULT_TASKS = [
    "Collect identity documents (Aadhaar, PAN)",
    "Verify documents",
    "Confirm division / project allocation",
    "Assign reporting officer",
    "Allocate assets (laptop, field kit, etc.)",
    "Set up official email / system account",
    "Acknowledge HR policies",
    "Complete orientation session",
]


def create_default_tasks(db: Session, employee: Employee) -> list[OnboardingTask]:
    tasks = [
        OnboardingTask(employee_id=employee.id, label=label, sort_order=i)
        for i, label in enumerate(DEFAULT_TASKS)
    ]
    db.add_all(tasks)
    db.flush()
    return tasks
