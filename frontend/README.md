# Aaranyak HRMS — frontend

Next.js 15 / React 19 / Tailwind CSS 4 / TypeScript. This is the frontend
for the Aaranyak HRMS backend (FastAPI) in `../backend`. It is a
**completely separate project** from the sibling AVFU HRMS frontend at
`../../frontend` — no shared code, no shared config, different backend
port. See `../CLAUDE.md` for full backend/architecture context.

## Running it

```bash
npm install
cp .env.example .env.local   # only needed if the backend isn't on the default port
npm run dev
```

Open http://localhost:3000 — it redirects to `/login`.

The backend must be running separately:

```bash
cd ../backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8010
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8010` | Base URL of the FastAPI backend. **8010, not 8002** — AVFU's backend uses 8002, so both stacks can run side by side. |

## Folder layout

```
src/
├── app/
│   ├── layout.tsx            Root layout: fonts, <AuthProvider>
│   ├── page.tsx               "/" — redirects to /login or /dashboard
│   ├── globals.css            Tailwind 4 @theme block with the Aaranyak
│   │                            teal/amber tokens (mirrors ../design/tokens.css
│   │                            — keep the two in sync if the palette changes)
│   ├── login/page.tsx         Two-step sign-in: email+password, then email OTP
│   └── (app)/                 Authenticated route group
│       ├── layout.tsx          App shell: desktop sidebar / mobile bottom
│       │                        tab bar, both driven by src/components/nav.ts
│       │                        and gated per item by useAuth().hasPermission()
│       ├── dashboard/
│       ├── attendance/
│       ├── leave/
│       ├── recruitment/        (covers onboarding too, for now)
│       ├── payroll/
│       ├── appraisal/
│       ├── assets/
│       ├── approvals/
│       ├── reports/
│       ├── employees/          Employee directory
│       └── admin/              Users / roles / workflow config
├── components/
│   ├── nav.ts                  Single source of truth for nav items + the
│   │                            permission code each one requires
│   └── ModuleStub.tsx           "Coming soon" placeholder used by every
│                                 stub page above
└── lib/
    ├── api.ts                  fetch wrapper: NEXT_PUBLIC_API_BASE_URL base,
    │                            attaches the JWT from localStorage, redirects
    │                            to /login on 401
    └── auth.tsx                 AuthProvider / useAuth(): current user +
                                  permissions from GET /api/auth/me, plus
                                  hasPermission()/hasAnyPermission()
```

## What's wired up for real

- Login: `POST /api/auth/login` → `{mfa_required, access_token?}`. If
  `mfa_required`, the UI steps to the OTP screen and calls
  `POST /api/auth/verify-otp` with `{email, code}`.
- Current user + permissions: `GET /api/auth/me` →
  `{id, email, role_code, role_name, permissions}` (see
  `backend/app/schemas/auth.py`).
- Logout: `POST /api/auth/logout`, then the token is cleared locally.
- Every module page under `(app)/` is a stub (heading + "Coming soon").
  Routing, the auth guard, and permission-gated nav are real; the actual
  feature UIs are separate follow-up work.

## Design system

The teal (`--color-primary`, "river teal") / amber (`--color-accent`,
"golden langur amber") palette, type scale and component shapes come from
`../design/tokens.css` and the approved mockups in `../design/index.html`.
Don't introduce new colors or fonts without updating both the tokens file
and `src/app/globals.css`'s `@theme` block together.
