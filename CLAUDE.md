# Aaranyak HRMS — project context

Read this file fully before doing anything else in this folder. It exists so a
new Claude session never has to re-derive what's already been decided.

## What this is

A Human Resource Management System for **Aaranyak**, a biodiversity
conservation non-profit in Guwahati, Assam, built against a specific client
RFP (Ref. AA/GCA/42C/26-27/4243, dated 23.10.2026) and the Xeta Labs technical
proposal responding to it. Full requirements are in `RFP.md` if present in
this folder, or ask the user — do not guess at scope.

**This is a completely separate project from `../` (the AVFU HRMS).** They
share no code, no database, no git history, and no deployment target. AVFU's
structure is University → College → Office → Section; Aaranyak's is
Organisation → Division → Project → Site. Never copy AVFU-specific names,
branding, or org-structure assumptions into this project. The backend's
*infrastructure* (auth plumbing, audit log, file storage, Excel export
helpers) was adapted from AVFU's build at project start — see Phase 0 in
`CHECKLIST.md` — but has been re-pointed at Aaranyak's own config, database,
and domain model since. There is no ongoing code-sharing between the two.

## The one rule that overrides everything else

**`CHECKLIST.md` is the source of truth for what's done and what's left.**
Before starting any new work, read it. After finishing a checklist item —
tests passing, not before — tick it and commit. Never tick an item that
isn't actually done; a previous session caught itself doing this once (see
git history around "Phase 2.4") and reverted the tick until the real work
was finished. Follow that same discipline.

Work test-first: write the failing test, confirm it fails for the right
reason, implement, confirm it passes, then move to the next item. Don't batch
multiple checklist items into one untested push of code.

## Design status — READ BEFORE TOUCHING THE FRONTEND

`frontend/` now exists and is a working Next.js app wired to the real
backend (see Codebase map below) — built without waiting for formal client
sign-off, per the user's explicit instruction. Seven key screens were
designed and published to the user for client review first (see
`design/index.html` + `design/tokens.css` for the source — these remain the
canonical visual language: colour tokens, type, spacing, component shapes).
`frontend/src/app/globals.css` mirrors `design/tokens.css` 1:1 — keep them in
sync if the palette ever changes, don't invent a new one.

- Check with the user whether formal client sign-off has since happened.
- The mobile screens are deliberately shown inside a **phone browser frame**
  (URL bar, lock icon, browser toolbar) in `design/index.html` — this is RFP
  compliance, not decoration (RFP requires "web application only, no
  Android or iOS app"). The real app's own `(app)/layout.tsx` runs as an
  ordinary responsive website — a bottom tab bar on mobile is just a layout
  choice — don't try to reintroduce native-app framing.

## Stack (fixed, from the proposal — do not substitute)

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.x |
| Database | PostgreSQL 16, via `psycopg` v3 |
| Frontend | Next.js 15, React 19, Tailwind CSS 4 — scaffolded and built out |
| Maps / geo-fence | Leaflet + OpenStreetMap (geo-fence math is backend-only pure functions; no map UI built yet for drawing fences — only for check-in, which reads the browser's own geolocation) |
| Reports | openpyxl (Excel) only. WeasyPrint (PDF) and python-docx (Word) were never added — no blocking RFP requirement found for them; all reports/exports ship as .xlsx. Revisit only if the client specifically asks for PDF/Word. |
| Auth | JWT (jose), bcrypt, email one-time code for confidential-data roles |

## Database

- **Dev/local database:** `aaranyak_hrms` (Postgres, must exist locally —
  `createdb -U postgres aaranyak_hrms` if missing). Connection string default
  lives in `backend/app/core/config.py`; override via `backend/.env` (copy
  from `.env.example`).
- **Test database:** `aaranyak_hrms_test`, created and torn down
  automatically by `backend/tests/conftest.py` on every test run. Never
  shares data with the dev database. Each test runs inside a transaction
  that's rolled back afterward — tests never leave rows behind.
- Schema is created by `Base.metadata.create_all()` at app startup
  (`app/main.py`), plus `sync_rbac()` which seeds/updates the permission
  catalogue and the 10 RFP roles idempotently on every boot. There is no
  Alembic/migrations tool yet — schema changes land as new model fields that
  `create_all` picks up (it won't alter or drop existing columns; a destructive
  schema change needs a manual migration or a dropped dev database).
- **Demo/seed data**: `backend/app/services/demo_seed.py` + runner
  `backend/scripts/seed_demo.py`. Idempotent (safe to rerun). Creates one
  login per RFP role (`admin@aaranyak-demo.org` … `auditor@aaranyak-demo.org`,
  all password `Demo@1234` — not `aaranyak.org` itself, so these can't be
  mistaken for real staff emails, and deliberately not a reserved TLD like
  `.test`/`.example` either, since `EmailStr` rejects those as non-routable),
  two divisions, a project, two sites (one with a
  geo-fence), four leave types, and sample attendance/leave/asset/salary-
  structure/appraisal-cycle records so the UI isn't empty on first run.
- **Dev-only fixed OTP**: `Settings.DEV_FIXED_OTP` (default `"000000"`)
  makes every email OTP that value instead of random, so manual testing
  never has to read `mailer.OUTBOX`. `tests/conftest.py` forces this back to
  `""` (disabled) for the test suite, so real random-OTP behaviour (wrong
  code rejected, etc.) is still what's actually tested. Never set this in a
  real deployment.

## Running it

```bash
cd backend
source venv/bin/activate          # venv already exists; if not: python3.11 -m venv venv
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8010   # 8010, not 8002 — AVFU uses 8002
./venv/bin/python scripts/seed_demo.py      # one-time: demo logins + sample data
```

Interactive API docs: `http://localhost:8010/docs`.

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000, points at :8010 by default
```
Override the backend URL via `NEXT_PUBLIC_API_BASE_URL` (see `.env.example`).

**CORS gotcha**: if port 3000 is already taken (e.g. AVFU's frontend is
running), Next.js silently falls back to 3001, 3002, etc. The backend's
`CORS_ORIGINS` (default `http://localhost:3000` only, see
`app/core/config.py`) won't allow that origin, and the symptom is a 400 on
the browser's `OPTIONS` preflight before login even gets a chance to run.
Fix: either free up port 3000, or add the actual port to
`backend/.env`'s `CORS_ORIGINS` (comma-separated) and restart the backend.

Tests:
```bash
cd backend
./venv/bin/python -m pytest             # full suite
./venv/bin/python -m pytest -m unit     # fast, no DB
./venv/bin/python -m pytest -m integration
```
All green as of the last commit on this file (well over 200 tests — run it
yourself rather than trusting a hardcoded count here, since this note won't
be kept in sync). If the suite is failing when you pick this up, that's a
real regression to fix, not something to work around.

## Codebase map

```
aaranyak-hrms/
├── CHECKLIST.md          ← what's done, what's left. Read first.
├── CLAUDE.md             ← this file
├── design/
│   ├── index.html        ← 7 designed screens, sample data, published to user
│   └── tokens.css        ← canonical colour/type/spacing tokens
├── backend/
│   ├── app/
│   │   ├── core/         ← config, database, security, audit, permissions
│   │   │                    catalogue, scope helpers, rbac_sync, auto_migrate
│   │   ├── models/       ← one file per domain area (identity, organisation,
│   │   │                    employee, notification, audit)
│   │   ├── routers/      ← one file per API area (auth, organisation,
│   │   │                    employee, notification)
│   │   ├── schemas/      ← Pydantic request/response models, mirrors routers
│   │   └── services/     ← business logic routers call into (geofence math,
│   │                        employee_code generation, mailer, notify, xlsx)
│   ├── scripts/
│   │   └── seed_demo.py   ← one-time demo data for manual testing
│   └── tests/
│       ├── unit/          ← no DB, no HTTP — pure logic
│       └── integration/   ← real Postgres test DB + FastAPI TestClient
└── frontend/
    ├── src/app/login/      ← two-step sign-in (password → OTP)
    ├── src/app/(app)/      ← one folder per module, shell layout with
    │                          permission-gated sidebar/bottom-tab-bar nav
    ├── src/lib/api.ts      ← fetch wrapper (bearer token, 401 handling,
    │                          downloadFile() for xlsx exports)
    └── src/lib/auth.tsx    ← auth context: user, permissions, login/
                               verifyOtp/logout, hasPermission()
```

## Key architectural decisions already made — don't relitigate these

- **Permissions are `<module>:<action>` codes** (e.g. `employee:view`,
  `leave:approve`), 7 possible actions (view/create/edit/delete/approve/
  export/admin), only the actions that make sense per module are registered.
  See `app/core/permissions.py`. 10 RFP roles, each granted an explicit
  permission bundle — don't add a role without updating
  `tests/unit/test_permissions_catalogue.py`'s assumptions.
- **Scope is derived from role, not stored redundantly on the user.**
  `app/core/scope.scope_for_role(role_code)` maps a role to
  `Scope.organisation / division / project / own`. An unassigned
  scoped user (e.g. a Division Head with no division yet) sees **nothing**,
  never everything — this is an explicit RFP requirement, tested in
  `test_employee_api.py::test_unassigned_division_head_sees_nothing`.
- **`Scope.project` (Project Lead, Coordinator) is not yet enforceable.**
  There's no employee↔project assignment table yet — those roles currently
  fall through to "own record only" rather than silently granting broader
  access. This is intentional and tested
  (`test_project_lead_scope_is_not_yet_enforceable_sees_only_own_record`).
  Building the staffing/assignment link properly belongs to Phase 5
  (recruitment/onboarding) or wherever division/project allocation lands —
  check `CHECKLIST.md` before assuming it's done.
- **Bank/statutory fields are a separate table** (`EmployeeConfidential`),
  not columns on `Employee`, gated by `employee_confidential:view/edit`
  permissions distinct from ordinary `employee:view`. This is structural
  restriction (a join that doesn't happen) — don't "simplify" it back onto
  one table.
- **MFA (email one-time code) is a role-level policy**
  (`Role.requires_mfa`), not a per-user toggle. Currently `True` for
  `admin`, `hr_admin`, `finance` only — the roles that see confidential
  data. `sync_rbac()` re-applies this from `DEFAULT_ROLES` on every system
  role on every boot (an admin can't accidentally weaken it by forgetting
  it was ever set) — but never touches a custom role's `requires_mfa`.
- **Logout is real, not just "client discards the token."** Every JWT
  carries a `jti`; `app.models.Session` tracks which are revoked. See
  `app/core/deps.get_current_user` and `app/routers/auth.logout`.
- **Email sender has a dev/test mode built in.** `SMTP_HOST` empty (the
  default) means every "sent" email lands in
  `app.services.mailer.OUTBOX` (an in-memory list) instead of touching the
  network — this is what the test suite relies on. Don't require a real
  SMTP server for local dev or tests.
- **Geo-fence math is pure, dependency-free** (`app/services/geofence.py`
  — haversine for circles, ray-casting for polygons). No mapping library
  needed server-side; Leaflet is frontend-only, for drawing the fence on a
  map and reading GPS coordinates in the browser.
- **Employee codes are `AAR-<division code>-####`**, permanent once issued,
  never reused even after an employee is separated. See
  `app/services/employee_code.py`.

## What's actually done vs. left

Don't trust this section once it's gone stale — **`CHECKLIST.md` is
authoritative, re-read it.** As a rough map at last update:

- **Done (Phases 0–9, backend + frontend):** project setup, 7 designed
  screens, organisation structure, full RBAC, sign-in with MFA, real logout,
  audit log, email sender, on-screen notifications, the complete employee
  master, the generic workflow/approval engine, attendance & leave
  (including geo-fenced check-in with selfie), recruitment/onboarding/
  orientation, payroll, performance appraisal, asset management, dashboards
  & reports. Every module has a working frontend page, not just an API.
  User/role administration (`app/routers/user.py`, `app/routers/role.py`)
  was added during the Phase 3–9 push — the RFP's "admin manages logins and
  roles" requirement had permission codes (`user:*`, `role:*`) reserved from
  Phase 2 but no router had ever been written for them until now.
- **Explicitly deferred by the user:** Phase 10 (migration tooling,
  security/load testing, deployment, UAT) — skip this until told otherwise.
- **Not built, and not RFP-blocking:** a geo-fence map-drawing UI for admins
  (the math exists server-side; nobody has a screen to draw a new fence yet
  — sites currently need their geofence fields set directly, e.g. via the
  seed script or a future admin screen). Workflow chain editing
  (`PUT /api/workflows/{request_type}`) has no frontend screen either —
  the defaults seeded by `workflow_seed.py` are sensible and usable as-is,
  but an admin can't yet change "2 levels" to "3 levels" without the API
  directly. PDF/Word report export (Excel only, see Stack table above).

## Demo data

`backend/scripts/seed_demo.py` (idempotent) creates one login per role, a
small org structure, and sample records in every module. Password for every
seeded login is `Demo@1234`; combined with `DEV_FIXED_OTP = "000000"`, any
MFA-required role (`admin`, `hr_admin`, `finance`, `executive`) can be
logged into with that fixed code — no need to read `mailer.OUTBOX`.

## Attribution

Commit messages and PR descriptions in this repo end with:
```
Co-Authored-By: Claude <noreply@anthropic.com>
```
(or whatever the live system reminder says at the time — check the current
session's instructions rather than hardcoding a specific model name here,
since that changes over time and this file won't be kept in sync with it.)
