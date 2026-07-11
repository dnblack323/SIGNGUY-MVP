# SignGuy AI — Agent Instructions

**Authority order:**
1. Owner-approved consolidated master plan: `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`.
2. Final scope + decision register: `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`.
3. Feature readiness matrix: `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`.
4. Repository + architecture source map: `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`.
5. Progress register: `/app/memory/progress_register.md`.
6. Completion register: `/app/memory/completion_register.md`.
7. Architecture docs: `/app/docs/architecture/*.md`.
8. Security docs: `/app/docs/security/*.md`.

## Permanent LOCKED rules (EC1)

### Repository roles
- `dnblack323/SIGNGUY-MVP` = permanent product. Only repo that receives new development.
- Donor repositories (`SIGNGUY-AI-OS`, `signguyai_rebuild_version`, `signguy-ai-feb22`, `signguyai`) are read-only references. No deletion until final commercial completion.

### Terminology
- Canonical: Customer, Lead, Quote, Order, Order Item, Work Order, Invoice, Payment, etc.
- Prohibited canonical: `Job`, `Job Item`, `Job Ticket`, `Production Ticket`, `Job Ticket Summary`.
- Guard: `python -m app.core.terminology_guard /app`.

### Money policy
- Commerce fields stored as integer cents with `_cents` suffix.
- Pricing configuration remains dollar-based (`Decimal` internally).
- Single conversion boundary at `backend/app/core/money.py::dollars_to_cents`.
- Stripe amounts are integer cents on wire and Payment row.

### Navigation
- Collapsible left sidebar with side flyouts. Home + six areas + divider.
- Source of truth: `frontend/src/lib/navigation.js`.

### Security
- Production startup guards enforced by `app/core/security_guards.py`.
- Dev routes (`/api/auth/dev-*`, `/api/auth/_dev/*`) refuse to run outside `ENV=development`.
- JWT placeholders forbidden in production.

### Permissions
- Three disjoint scopes: `Perm` (staff), `PlatformPerm`, `PortalPerm`.
- Backend enforcement is authoritative.
- Frontend consumes permissions from `/api/auth/me`.

### Module standard
- New modules use `models/ + repositories/ + routers/ + services/` layout.
- Do NOT refactor stable MVP modules into repositories.
- Routers stay thin; repositories own tenant filters; services own algorithms.

## Working MVP systems (do not destabilize)

Auth, Tenants, Users, Roles, Customers, Quotes, Orders, Work Orders, Invoices, Manual Payments, Object Storage, Attachments, Audit, Sequences, Pricing Foundation + Calculator, SendGrid outbound, frontend design system, MoneyInput.

## Checkpoint execution rules

- Complete one execution checkpoint at a time.
- Do not begin the next checkpoint automatically. Wait for the next execution prompt.
- Every checkpoint exit ships an evidence package at `/app/evidence/EC<n>_evidence.md`.
- Update `/app/memory/progress_register.md` at every checkpoint transition.

## Test commands

- Backend: `cd /app/backend && python -m pytest tests/ -q`.
- Terminology: `python -m app.core.terminology_guard /app`.
- Backend health: `curl -s http://localhost:8001/api/health` or the external `REACT_APP_BACKEND_URL/api/health`.
- Supervisor: `sudo supervisorctl status`.

## Never-again enforcement

All 42 Never-Again rules from Final Scope Register Part 12 apply. Highlights:
- No parallel Customer/Order/Invoice/Payment/User/File/Audit systems.
- No Base64-in-Mongo storage.
- No frontend-only permissions.
- No missing tenant filters or hardcoded tenant IDs.
- No direct payment-status mutation.
- No unverified payment webhooks.
- No portal/staff JWT crossover.
- No production dev bypass.
- No giant App.js / router files / pricing files.
- No duplicate menus or dashboards.
- No destructive delete on financials.
- No wholesale donor copy.
- No AI before credit metering + cost controls.
