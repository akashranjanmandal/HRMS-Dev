"""Appointment letters, generated from a template at selection time (RFP
4.1 §4.2) — plain text for now; checklist 9 adds proper PDF/Word
rendering (WeasyPrint / python-docx) once the reporting module needs
those libraries anyway, and this same template string is what feeds
them.
"""
from datetime import date

from app.models import Candidate, Employee, Vacancy


def appointment_letter_text(candidate: Candidate, vacancy: Vacancy, employee: Employee) -> str:
    return (
        f"Dear {candidate.full_name},\n\n"
        f"We are pleased to offer you the position of {employee.designation or vacancy.title} "
        f"with Aaranyak, in the {vacancy.division.name} division, "
        f"effective from {employee.date_of_joining or date.today()}.\n\n"
        f"Your employee code is {employee.employee_code}.\n\n"
        "Please contact HR for details of your terms of engagement, reporting officer, "
        "and the onboarding checklist to be completed before your first day.\n\n"
        "Congratulations, and welcome to Aaranyak.\n\n"
        "Human Resources\nAaranyak"
    )
