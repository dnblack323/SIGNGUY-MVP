# SignGuy AI — Product Requirements (PRD)

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`
(owner-approved). This PRD is the human-readable summary; the plan document
is the binding source of truth.

## Product

SignGuy AI is the permanent commercial business-management platform for
sign & graphics shops. Built on the FARM stack (FastAPI, React, MongoDB)
as the permanent commercial destination — not an MVP.

## Users

- **Shop Owner / Admin** — full permission set, tenant admin.
- **Shop Staff** — restricted permission set (customer/quote/order/invoice work).
- **Customer Portal** — external portal identity (approvals, signatures, payments) [EC4+].
- **Employee Portal** — external portal identity (time clock, payslips) [EC6+].
- **Webstore Owner / Manager** — external portal identity [EC7+].
- **Platform Operator** — cross-tenant scope (SignGuy AI staff) [EC8+].

## Locked Product Rules

- **Money.** Commerce fields use integer `_cents`. Pricing config stays float decimal.
- **Terminology.** "Job" / "Job Ticket" is prohibited. Use Order / Work Order.
- **Tenant isolation.** Every DB read/write filters by `tenant_id`.
- **Fail-closed production.** JWT + enabled-integration secrets required in production.
- **Backend authoritative.** Frontend permission checks only affect visibility.

## Checkpoint status

| EC | Name | Status |
|---|---|---|
| EC0 | Owner Decisions & Governance Lock | ✅ COMPLETE |
| EC1 | Security & Permanent Guardrails | ✅ COMPLETE |
| EC2 | Shared Platform Foundations | ✅ COMPLETE |
| EC3 | Core Money & Order Pipeline | ⬜ Awaiting owner prompt |
| EC4 | Documents, Portals, Customer Workflow | ⬜ Pending |
| EC5 | Inventory, Purchasing, Finance, Reporting | ⬜ Pending |
| EC6 | Team & Payroll | ⬜ Pending |
| EC7 | Webstores | ⬜ Pending |
| EC8 | Wrap Lab | ⬜ Pending |
| EC9 | Creative Studio & AI Foundations | ⬜ Pending |
| EC10 | AI Tools Catalog & Assistant | ⬜ Pending |
| EC11 | Platform Governance & Community | ⬜ Pending |
| EC12 | Commercial Systems & Billing | ⬜ Pending |
| EC13 | Marketing & Public Pricing | ⬜ Pending |
| EC14 | Final Integration & Release Hardening | ⬜ Pending |

## Implemented (EC0-EC2)

- Auth (JWT, dev bypass, password reset), Tenants, Users, Roles/Permissions.
- Customers, Quotes, Orders (with items), Work Orders, Invoices, Payments.
- Documents (files + attachments) with tenant-scoped object storage.
- Emails (SendGrid outbound + 5 templates + history).
- Audit trail (all mutating actions).
- Pricing foundation (per-tenant defaults + calculator).
- Dashboard.
- EC1 — Startup security guards, terminology guard, money policy contract,
  module-based permission catalog (staff + platform + portal scopes), locked
  left-sidebar + flyout navigation.
- EC2 — Tenant Settings (namespaced key/value), Activity Feed (extends audit),
  In-App Notifications (staff), Email Activity (internal + SendGrid webhook
  observability), Shared Webhook Framework (HMAC-verified, replay-safe,
  fail-closed), Upload Validation (MIME + magic-byte + size + filename),
  Polymorphic File/Document Links, Document Shares, Feature Entitlements
  (tenant read + `require_entitlement` dep), Integration Status (no secret
  leakage). Frontend: Company Settings, Integrations, Feature Access,
  Data & Security pages + NotificationBell.

## Backlog (P0)

- EC3 — Core Money & Order Pipeline (owner prompt required to begin).

## Reference documents

- `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` — binding plan.
- `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md` — owner decisions log.
- `/app/evidence/EC1_evidence.md`, `/app/evidence/EC2_evidence.md` — proof-of-completion.
- `/app/memory/progress_register.md` — EC/PC live tracker.
- `/app/memory/completion_register.md` — cumulative completion log.
- `/app/docs/architecture/`, `/app/docs/integrations/`, `/app/docs/security/`.
