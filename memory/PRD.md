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
| **EC3 — Quotes, Orders, Order Items, Pricing Snapshots** | **COMPLETE** | `/app/evidence/EC3_evidence.md` |
| EC4 — Documents, Portals, Customer Workflow | NOT STARTED | pending owner prompt |
| EC5–EC14 | NOT STARTED | dependency-ordered per master plan |

## Completed capabilities

- Auth / Tenants / Users / Permissions (staff + platform + portal scopes) — EC1.
- Startup guards, terminology guard, money helpers, LOCKED navigation shell — EC1.
- Settings / Activity / Notifications / SendGrid webhook / Upload validation / File+Document links / Feature entitlements / Integration status — EC2.
- **Quote line items + revisions + expiration + approval-state foundation** — EC3.
- **Rich Order Item schema with backend-derived totals, pricing snapshots, manual override with reason** — EC3.
- **`production_required` rule + override + reason** — EC3.
- **Idempotent race-safe Quote-to-Order conversion copying line items + snapshots + source revision** — EC3.
- **Work Order snapshot filters by `production_required`** — EC3.

## Testing

- Backend: `cd /app/backend && python -m pytest tests/ -q` → 117 passed (34 EC1 + 58 EC2 + 25 EC3).
- Frontend smoke tested via preview URL.

## Test credentials

`AUTH_DEV_BYPASS=true` in development; dev-bypass banner visible in UI. No production credentials exist in `.env`.

## Priority backlog (P0/P1/P2)

### P0 — Immediate next checkpoint
- Await EC4 execution prompt (Documents, Portals, Customer Workflow).

### P1 — After EC4
- EC5 Inventory, Purchasing, Finance & Reporting.
- EC6 Team & Payroll.

### P2 — Later
- EC7 Webstores (add-on + standalone).
- EC8 Wrap Lab.
- EC9 Creative Studio + AI foundations.
- EC10 AI Tools + Assistant.
- EC11 Platform Governance & Community.
- EC12 Commercial Systems & Billing.
- EC13 Marketing & Public Pricing.
- EC14 Final Integration & Hardening.

## Known deferred items (from EC3)

- Public / portal approval of Quotes → EC4 shared Approvals system.
- Rich order-item UI editor (category, dimensions, production_required override form) → next frontend iteration (backend already supports it).
- Invoice dual-status redesign, unified Payments, Stripe → EC4.
- Production Board → EC5.

## Authority references

- `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`
- `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`
- `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`
- `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`
- `/app/memory/AGENT_INSTRUCTIONS.md`
- `/app/memory/progress_register.md`
