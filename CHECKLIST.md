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
- [ ] 2.1 Organisation: divisions, projects, offices and field sites (with geo-fence boundary)
- [ ] 2.2 The 10 RFP roles, permissions per module (view, create, edit, delete, approve, export, admin), scope by organisation / division / project / own
- [ ] 2.3 Sign-in: password policy, email one-time code, logout, session expiry; every sign-in and sign-out audited
- [ ] 2.4 Email sender (pluggable, with a test outbox) and on-screen notifications
- [ ] 2.5 Employee master: all RFP field groups incl. contract dates, PF/ESI, status (active, on notice, separated); restricted fields hidden by role

## Phase 3 — Workflow engine
- [ ] 3.1 Approval levels per request type, set by the administrator
- [ ] 3.2 Approve, reject, return for correction; name, time and remark on each step
- [ ] 3.3 Approvals Center with pending counts; reminders

## Phase 4 — Attendance and leave
- [ ] 4.1 Geo-fence check-in/out: GPS inside boundary, accuracy check, selfie compressed to ~100 KB
- [ ] 4.2 Field duty outside a boundary, with reason and supervisor approval
- [ ] 4.3 Attendance regularisation, travel records, daily register, monthly summary
- [ ] 4.4 Leave types and rules set by the administrator (accrual, carry forward, limits, eligibility)
- [ ] 4.5 Leave application, approval, balances, overlap check, link to attendance

## Phase 5 — Recruitment, onboarding, orientation
- [ ] 5.1 Vacancies, ToR, approval, public job page, candidates, shortlist, interviews, selection, appointment letter
- [ ] 5.2 Onboarding checklist incl. division/project allocation, assets, policy acknowledgement
- [ ] 5.3 Orientation schedule, sessions, attendance, completion

## Phase 6 — Payroll integration
- [ ] 6.1 Salary structure (configurable heads), revisions
- [ ] 6.2 Attendance/leave inputs, payslips, payroll reports by division and project
- [ ] 6.3 Bank salary file and accounting export

## Phase 7 — Performance appraisal
- [ ] 7.1 Cycles, KPIs, rating scales; self → supervisor → Division Head; recommendations

## Phase 8 — Asset management
- [ ] 8.1 Register, issue/return/transfer through the workflow, repairs, disposal, reports

## Phase 9 — Dashboards and reports
- [ ] 9.1 Role dashboards; HR reports; PDF, Excel and Word export with permission checks

## Phase 10 — Migration and go-live
- [ ] 10.1 Import templates, row validation, error and count reports
- [ ] 10.2 Security, 300-user performance, backup/restore tests; deployment; UAT
