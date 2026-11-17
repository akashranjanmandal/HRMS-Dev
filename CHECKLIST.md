# Aaranyak HRMS — build checklist

Source: RFP AA/GCA/42C/26-27/4243 and the Xeta Labs proposal.
Rule: an item is ticked only when its tests pass. UI is built only after the client approves the designs.

## Phase 0 — Setup
- [x] 0.1 Project folder with its own git repository
- [x] 0.2 Backend core reused from the AVFU build (config, database, security, permission guards, audit, schema sync, file storage, Excel export) and the test harness

## Phase 1 — Designs for client approval
- [x] 1.1 Design tokens (colour, type, spacing) in `design/tokens.css`, later used by the frontend as-is
- [x] 1.2 Screens: sign-in with email code, field staff check-in (geo-fence + selfie), HR dashboard, geo-fence map, leave, Approvals Center, employee profile
- [ ] 1.3 Client sign-off on the designs

## Phase 2 — Foundation
- [x] 2.1 Organisation: divisions, projects, offices and field sites (with geo-fence boundary)
- [x] 2.2 The 10 RFP roles, permissions per module (view, create, edit, delete, approve, export, admin), scope by organisation / division / project / own
- [x] 2.3 Sign-in: password policy, email one-time code, logout, session expiry; every sign-in and sign-out audited
- [x] 2.4 Email sender (pluggable, with a test outbox) and on-screen notifications
- [x] 2.5 Employee master: all RFP field groups incl. contract dates, PF/ESI, status (active, on notice, separated); restricted fields hidden by role

## Phase 3 — Workflow engine
- [x] 3.1 Approval levels per request type, set by the administrator
- [x] 3.2 Approve, reject, return for correction; name, time and remark on each step
- [x] 3.3 Approvals Center with pending counts; reminders

## Phase 4 — Attendance and leave
- [x] 4.1 Geo-fence check-in/out: GPS inside boundary, accuracy check, selfie compressed to ~100 KB
- [x] 4.2 Field duty outside a boundary, with reason and supervisor approval
- [x] 4.3 Attendance regularisation, travel records, daily register, monthly summary
- [x] 4.4 Leave types and rules set by the administrator (accrual, carry forward, limits, eligibility)
- [x] 4.5 Leave application, approval, balances, overlap check, link to attendance

## Phase 5 — Recruitment, onboarding, orientation
- [x] 5.1 Vacancies, ToR, approval, public job page, candidates, shortlist, interviews, selection, appointment letter
- [x] 5.2 Onboarding checklist incl. division/project allocation, assets, policy acknowledgement
- [x] 5.3 Orientation schedule, sessions, attendance, completion

## Phase 6 — Payroll integration
- [x] 6.1 Salary structure (configurable heads), revisions
- [x] 6.2 Attendance/leave inputs, payslips, payroll reports by division and project
- [x] 6.3 Bank salary file and accounting export

## Phase 7 — Performance appraisal
- [x] 7.1 Cycles, KPIs, rating scales; self → supervisor → Division Head; recommendations

## Phase 8 — Asset management
- [x] 8.1 Register, issue/return/transfer through the workflow, repairs, disposal, reports

## Phase 9 — Dashboards and reports
- [x] 9.1 Role dashboards; HR reports; Excel export with permission checks (PDF/Word deferred — RFP's bank/accounting exports and reports are Excel; no blocking requirement found for PDF/Word)

## Phase 9.5 — Frontend (built ahead of formal design sign-off, per user instruction)
- [x] 9.5.1 Next.js app scaffolded, Aaranyak design tokens applied, auth (login + OTP) wired to the real backend
- [x] 9.5.2 User/role administration backend added (`app/routers/user.py`, `app/routers/role.py`) — RFP requirement that had permission codes reserved since Phase 2.2 but no router until now
- [x] 9.5.3 Working UI for every module: dashboard, attendance (camera + geolocation check-in), leave, recruitment, appraisal, assets, payroll, approvals center, reports/exports, employee directory, admin (users + roles)
- [x] 9.5.4 Demo/seed data script (`backend/scripts/seed_demo.py`) + dev-only fixed OTP for manual testing
- [ ] 9.5.5 Geo-fence map-drawing admin screen (not built — fences are set via seed data / API only)
- [ ] 9.5.6 Workflow chain admin screen (not built — defaults from `workflow_seed.py` are usable as-is via the API)

## Phase 11 — Security audit fixes (post-launch-review pass)
- [x] 11.1 `DEV_FIXED_OTP` defaults off; app refuses to start if set alongside a real `SMTP_HOST`
- [x] 11.2 Scope check added to `employee_confidential` endpoints — a division-scoped role granted that permission can no longer reach another division's bank/statutory data
- [x] 11.3 Division/project scope filtering added to every asset endpoint (list/get/issue/transfer/repair/dispose)
- [x] 11.4 Rate limiting on `/api/auth/login` (10/15min) and `/api/auth/verify-otp` (5/10min), keyed by email
- [x] 11.5 Selfie upload rejected on size before decode/decompress, using the existing `MAX_UPLOAD_MB` limit
- [x] 11.6 JWT-in-localStorage tradeoff documented in CLAUDE.md as an accepted risk, not silently left unexamined
- [x] 11.7 UI/UX pass, test-first throughout (backend) and build-checked after every page (frontend):
  - [x] 11.7.1 Visual density: every module page (employees, assets, leave, attendance, payroll, appraisal, recruitment, admin) widened and given real summary-stat strips, search/filters, and proper empty states instead of bare lists
  - [x] 11.7.2 Dashboard: fixed the 5th KPI tile and the broken per-division bar (was `width: n*10`, capped/wrong past 10 staff) — now a real present/field-duty/on-leave composition chart plus an activity feed, all tiles linked to their module
  - [x] 11.7.3 Global smart search (`GET /api/search`, `GlobalSearch.tsx` in the top bar on every screen) across people/requests/assets — permission- and scope-gated identically to each owning module, never a visibility leak
  - [x] 11.7.4 Kanban-style boards: Approvals Center (board/list toggle, grouped by request type) and Recruitment (candidate pipeline columns by stage)
  - [x] 11.7.5 In-app report preview (`/preview` JSON endpoints alongside every existing `/export` one) so reports can be read before downloading Excel
  - [x] 11.7.6 Wired up the orphaned `payroll_cost_by_division_for_run` service function as a real preview + export endpoint

## Phase 10 — Migration and go-live
- [ ] 10.1 Import templates, row validation, error and count reports
- [ ] 10.2 Security, 300-user performance, backup/restore tests; deployment; UAT
