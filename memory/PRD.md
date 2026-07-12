# SignGuy AI — PRD

**Product:** SignGuy AI — the permanent commercial business-management platform for sign, graphics, wrap, print, and apparel shops.
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent product). Donor repos are read-only reference material.
**Stack:** FARM (FastAPI + React + MongoDB).

## Original problem statement

Owner is building SignGuy AI as a permanent commercial application (not an MVP scaffold). Execution proceeds through numbered checkpoints (EC0 → EC14) defined in `SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`. Each checkpoint requires a preflight, code, tests, evidence package, and explicit stop before the next checkpoint.

Constraints:
- No `Job / Job Item / Job Ticket / Production Ticket / Job Ticket Summary` terminology.
- Commerce values stored as integer cents with `_cents` suffix; pricing configuration remains float dollars.
- Fail-closed production guards enforced by `security_guards.py`.
- Strict tenant isolation on every read/write.
- Backend enforcement is authoritative for permissions.
- No wholesale donor copies.

## Checkpoint status (2026-02)

| Checkpoint | Status | Evidence |
|---|---|---|
| EC0 — Owner Decisions | COMPLETE | Baked into master plan §4 |
| EC1 — Security & Guardrails | COMPLETE | `/app/evidence/EC1_evidence.md` |
| EC2 — Shared Platform Services | COMPLETE | `/app/evidence/EC2_evidence.md` |
| EC3 — Quotes, Orders, Order Items, Pricing Snapshots | COMPLETE | `/app/evidence/EC3_evidence.md` |
| EC4 — Invoices, Payments, and Stripe Core | COMPLETE | `/app/evidence/EC4_evidence.md` |
| EC5 — Production and Work Orders | COMPLETE | `/app/evidence/EC5_evidence.md` |
| **EC6 — Asset Library, Proofs, Signatures, Customer Portal** | **COMPLETE** | `/app/evidence/EC6_evidence.md` — 161/161 backend + `testing_agent_v3_fork` iteration 9 100% pass |
| EC6.2 — Signed PDF Composite Rendering | DEFERRED (unscheduled) | `/app/memory/product_ideas_register.md` — reconsider during EC14 Final Hardening, or earlier only on a verified customer/compliance/operational requirement. Do NOT schedule during EC7. |
| **EC7 — Inventory, Purchasing, Finance, Reporting** | READY TO BUILD | pending owner execution prompt |
| EC8–EC14 | NOT STARTED | dependency-ordered per master plan |

## Completed capabilities

- Auth / Tenants / Users / Permissions (staff + platform + portal scopes) — EC1.
- Startup guards, terminology guard, money helpers, LOCKED navigation shell — EC1.
- Settings / Activity / Notifications / SendGrid webhook / Upload validation / File+Document links / Feature entitlements / Integration status — EC2.
- Quote line items + revisions + expiration + approval-state foundation — EC3.
- Rich Order Item schema with backend-derived totals, pricing snapshots, manual override with reason — EC3.
- `production_required` rule + override + reason — EC3.
- Idempotent race-safe Quote-to-Order conversion copying line items + snapshots + source revision — EC3.
- Work Order snapshot filters by `production_required` — EC3.
- **Functional frontend Quote/Order editors:** quick + detailed entry modes, calculator integration, override-reason validation, production-required switch, revision-warning dialog, expired-quote convert-with-override UX, source-quote link on Orders — EC3 (v2 corrections).
- Invoice dual-status (`document_status` + `financial_status`), reconciliation, `_cents` money, immutable snapshots — EC4.
- Payments: record / void / refund with idempotency; Stripe Core integration (test adapter, publishable-key + client_secret never leak to DOM/console) — EC4.
- **Work Order lifecycle (EC5):** 9-state enum, priority + due dates, immutable snapshots, versioned regenerate/supersede with reason, controlled transitions coordinating Order operational status, cross-tenant-safe assignment with in-app notifications, printable summary gated by `invoice:read`, `/api/production/board` view — EC5.
- **Production frontend (EC5):** Production Board (Kanban + HTML5 drag-drop + reason-required modal), rebuilt Work Order Detail (version banners, priority/due, allowed-transitions sidebar, assign dialog, in-page Print Summary), Generate WO dialog on Order Detail, Regenerate on both Order + WO detail, 9-state WO list filters + current-version toggle, Production Board sidebar link, all controls permission-gated via `/auth/me`.
- **Asset Library + Portal (EC6):** Documents metadata + versioning layered over existing FileRecord; scoped public-action tokens (single-purpose, expiring, revocable, hashed at rest); magic-link portal login (hashed, single-use, audience-scoped); portal JWT separation (`sub_scope="portal"`, disjoint dependency graph); Portal Identity n:1 mapping to Customer with 5 backend-authoritative permission-bundle presets; staff surfaces for Proofs (create/version/transition), Approvals (dual-parent incl. WOS), Signature Requests + Signatures; Public single-action endpoints (proof approve, sign, quote_view, invoice_view, public quote request, customer intake with staged-changes review); Portal customer routes (Quotes/Orders/Invoices/Documents/Proofs/Messages/Profile) with tenant+customer scope on every query; Portal messages via existing email service (no new messaging schema); Portal shell + login/magic-link/verify + list pages at `/portal/*` and public token pages at `/p/*`, both mounted OUTSIDE the staff `<AppShell>`.

## Testing

- Backend: `cd /app/backend && python -m pytest tests/ -q` → **161 passed** (34 EC1 + 58 EC2 + 25 EC3 + 17 EC4 + 9 EC5 + 18 EC6/EC6.1).
- Frontend: `testing_agent_v3_fork` iteration 9 (EC6 corrections): 100% pass (27/27 backend curl E2E + 25/25 Playwright UI, no action items, no retest). Prior EC5 iteration 8: 100% pass.

## Test credentials

`AUTH_DEV_BYPASS=true` in development; dev-bypass banner visible in UI. No production credentials exist in `.env`.

## Priority backlog (P0/P1/P2)

### P0 — Immediate next checkpoint
- Await owner's EC7 execution prompt: **EC7 — Inventory, Purchasing, Finance, and Reporting** (authoritative title per master plan).

### P1 — After EC7
- EC8 Team, Scheduling, Time, Payroll (+ Employee Portal).
- EC9 Webstores + Stripe Connect (add-on + standalone shell).
- EC10 Wrap Lab.

### P2 — Later
- EC9 Creative Studio + AI foundations.
- EC10 AI Tools + Assistant.
- EC11 Platform Governance & Community.
- EC12 Commercial Systems & Billing.
- EC13 Marketing & Public Pricing.
- EC14 Final Integration & Hardening.

## Known deferred items (from EC3)

- Sales-tax provider integration (accepted as pass-through data).
- Assigned-team / install-notes / packaging-notes fields on OrderItem → owning module checkpoints (Team & Workflow, Wrap Lab).
- Public/portal quote approval → EC6 shared Approvals system.

## Authority references

- `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`
- `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`
- `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`
- `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`
- `/app/memory/AGENT_INSTRUCTIONS.md`
- `/app/memory/progress_register.md`
