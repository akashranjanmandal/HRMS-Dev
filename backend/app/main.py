from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auto_migrate import sync_enum_types, sync_missing_columns
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.rbac_sync import sync_rbac
from app.models import Base
from app.routers import (
    appraisal,
    asset,
    attendance,
    auth,
    employee,
    leave,
    notification,
    onboarding,
    organisation,
    payroll,
    report,
    role,
    user,
    workflow,
)
from app.services.workflow_seed import seed_default_workflows

Base.metadata.create_all(bind=engine)
sync_enum_types(engine, Base)
sync_missing_columns(engine, Base)
with SessionLocal() as _db:
    sync_rbac(_db)
    seed_default_workflows(_db)

app = FastAPI(title=f"{settings.ORG_NAME} HRMS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROUTERS = [
    appraisal.router,
    asset.router,
    attendance.router,
    auth.router,
    employee.router,
    leave.router,
    notification.router,
    onboarding.router,
    organisation.router,
    payroll.router,
    report.router,
    role.router,
    user.router,
    workflow.router,
]
for r in ROUTERS:
    app.include_router(r)


@app.get("/api/health", tags=["Meta"])
def health():
    return {"status": "ok"}
