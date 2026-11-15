from datetime import date, datetime

from pydantic import BaseModel, Field


class SalaryStructureIn(BaseModel):
    effective_from: date
    basic: float = Field(ge=0)
    hra: float = Field(default=0, ge=0)
    other_allowances: float = Field(default=0, ge=0)
    pf_deduction: float = Field(default=0, ge=0)
    esi_deduction: float = Field(default=0, ge=0)
    professional_tax: float = Field(default=0, ge=0)
    tds: float = Field(default=0, ge=0)
    bank_account_number: str = Field(default="", max_length=40)
    bank_ifsc: str = Field(default="", max_length=20)


class SalaryStructureOut(SalaryStructureIn):
    id: int
    employee_id: int
    gross: float
    total_deductions: float
    net: float
    created_at: datetime


class PayrollRunIn(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class PayslipOut(BaseModel):
    id: int
    run_id: int
    employee_id: int
    employee_name: str
    division_id: int | None
    division_name: str | None
    project_id: int | None
    loss_of_pay_days: float
    gross: float
    total_deductions: float
    net: float
    bank_account_number: str
    bank_ifsc: str


class PayrollRunOut(BaseModel):
    id: int
    month: int
    year: int
    status: str
    created_at: datetime
    finalised_at: datetime | None
    payslip_count: int
    total_net: float


class PayrollRunDetailOut(PayrollRunOut):
    payslips: list[PayslipOut]
