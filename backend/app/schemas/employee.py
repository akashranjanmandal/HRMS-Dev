from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.employee import EmployeeStatus, EmploymentCategory


class EmployeeIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    gender: str = Field(default="", max_length=20)
    date_of_birth: date | None = None
    personal_email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=4000)
    emergency_contact_name: str = Field(default="", max_length=160)
    emergency_contact_phone: str = Field(default="", max_length=30)
    educational_qualifications: str = Field(default="", max_length=4000)
    professional_qualifications: str = Field(default="", max_length=4000)
    date_of_joining: date | None = None
    designation: str = Field(default="", max_length=160)
    division_id: int
    employment_category: EmploymentCategory = EmploymentCategory.regular
    employment_history: str = Field(default="", max_length=4000)
    reporting_officer_id: int | None = None
    contract_end_date: date | None = None
    engagement_details: str = Field(default="", max_length=4000)
    user_id: int | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    gender: str | None = None
    date_of_birth: date | None = None
    personal_email: str | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    educational_qualifications: str | None = None
    professional_qualifications: str | None = None
    designation: str | None = None
    division_id: int | None = None
    employment_category: EmploymentCategory | None = None
    employment_history: str | None = None
    reporting_officer_id: int | None = None
    contract_end_date: date | None = None
    engagement_details: str | None = None


class EmployeeStatusUpdate(BaseModel):
    status: EmployeeStatus
    exit_reason: str | None = Field(default=None, max_length=255)
    exit_date: date | None = None

    @model_validator(mode="after")
    def _separated_needs_exit_details(self):
        if self.status == EmployeeStatus.separated and not (self.exit_reason and self.exit_date):
            raise ValueError("exit_reason and exit_date are required when status is 'separated'")
        return self


class EmployeeOut(BaseModel):
    """Everything except bank/statutory details — see EmployeeConfidentialOut."""

    id: int
    employee_code: str
    full_name: str
    photo_url: str
    gender: str
    date_of_birth: date | None
    personal_email: str
    phone: str
    address: str
    emergency_contact_name: str
    emergency_contact_phone: str
    educational_qualifications: str
    professional_qualifications: str
    date_of_joining: date | None
    designation: str
    division_id: int
    employment_category: EmploymentCategory
    employment_history: str
    reporting_officer_id: int | None
    contract_end_date: date | None
    engagement_details: str
    status: EmployeeStatus
    exit_reason: str
    exit_date: date | None
    user_id: int | None
    created_at: datetime
    updated_at: datetime


class EmployeeConfidentialIn(BaseModel):
    bank_account_number: str = Field(default="", max_length=40)
    bank_ifsc: str = Field(default="", max_length=20)
    bank_name: str = Field(default="", max_length=160)
    pan_number: str = Field(default="", max_length=20)
    aadhaar_number: str = Field(default="", max_length=20)
    pf_number: str = Field(default="", max_length=40)
    esi_number: str = Field(default="", max_length=40)


class EmployeeConfidentialOut(EmployeeConfidentialIn):
    employee_id: int
    updated_at: datetime
