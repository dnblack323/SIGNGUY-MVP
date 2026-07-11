# SIGNGUY-MVP Agent Instructions

This file captures the controlling rules for all work in this repository. **Every migration or new feature MUST follow these rules.** See the source instructions doc (attached by user) for the full text; this file is the operating summary.

## Repository role
This repo (SIGNGUY-MVP) is the **permanent production application**. It is the **only** repo where new implementation may continue.

## Donor repos (READ-ONLY reference)
| Priority | Repo | Role |
|---|---|---|
| 2 | `signguyai_rebuild_version` | UI, navigation, workspace, DocuLink, Wrap Lab, Webstores — visual/workflow donor |
| 3 | `signguy-ai-feb22` | Invoice/payment/migration/security-test — financial-logic donor |
| 4 | `signguyai` | Original feature inventory / historical behavior — discovery only |

> I (the agent) do **not** have direct access to those donor repos. When migration work requires inspecting donor code, the user must paste the relevant file/section, or grant me read access.

## Source-conflict order (highest wins)
1. Current written user instruction
2. Current MVP implementation / approved spec
3. Module-specific migration audit
4. rebuild-version workflow spec
5. February financial behavior
6. Original-repo historical behavior

## Preflight audit — REQUIRED before any migration
Before touching code for a module I must produce a **Feature Migration Preflight Audit** that:
- Names the exact MVP module + current files/models/routes/services/pages/tests/deps
- Inspects the same feature in each donor repo (or notes that the user must paste it)
- Identifies authoritative source for behavior, UI, data, tests, terminology
- Defines the final MVP data model and ownership boundaries
- Classifies each item **reuse / adapt / rewrite / reject**
- Lists required data migrations for existing MVP data
- Only THEN begin implementation, under MVP auth/tenant/permission/audit/money/storage/email foundations
- Adds tests: success, failure, permissions, tenant isolation, duplicate requests, status transitions, migration safety, regression
- Documents what was implemented, what donor code was used, what was rejected, what was deferred
- Marks the donor implementation retired for that module

## Prohibited actions
- Create a new repo or restart from scratch
- Merge donor repos wholesale
- Continue implementing features in donor repos
- Rename OrderItem → JobTicket, or use Job as primary shop-order entity
- Module-specific copies of shared services (email, storage, audit, permission, customer, payment, notification, settings)
- Treat polished UI as proof of production-ready backend
- Skip tenant-isolation / permission tests
- Hard-delete financial or audit history
- Store uploaded files as base64 in MongoDB (must use object storage)
- Mark a module "complete" from folders/READMEs/placeholders
- Add Webstores or Wrap Lab depth before shared core is stable

## Completion standard for every stage
- No duplicate implementation active
- All protected resources tenant-scoped on backend
- Permissions enforced at route/service, not just hidden in UI
- Business state backend-derived where possible
- Important mutations produce audit/activity evidence
- Financial records use reversal / void / adjustment (never destructive rewrite)
- Files use object storage + controlled access
- Frontend screens have loading, empty, error, permission, success states
- Legacy data has explicit migration + rollback strategy
- Focused + regression tests pass
- Docs updated before next stage

## Mandatory build order
0. Repo & Architecture Control
1. Auth, Tenants, Users, Roles, Permissions
2. Shared Platform Services (audit, storage, email, notifs, settings, feature flags, entitlements, IDs, money, dates, validation, errors, shared API client)
3. Customers & Contacts
4. Quotes (items, pricing snapshots, approvals, expiration, revisions, sending, portal visibility, idempotent convert-to-order)
5. Orders & Order Items (central business record; item entry, pricing snapshots, statuses, notes, files, activity, `production_required` flag, source links)
6. Invoices & Payments (Feb22 financial behavior: independent document vs financial status, partial payments, history, void rules, reconciliation, Stripe readiness, migrations)
7. Production & Work Orders (only from `production_required` items; WO summaries, assignments, stages, board views, completion history, packets)
8. DocuLink & Shared Files (templates, generated docs, uploads, links, shares, categories, questionnaires, attachments, access rules, portal visibility, retention)
9. Email, Notifications, Customer Communication (SendGrid templates, logs, triggers, failed-send behavior, comm history, notif preferences, later SMS)
10. Customer Portal Lite
11. Proof Approval, Signatures, Packets
12. Pricing Foundation & Calculators
13. Inventory, Purchasing, Finance, Reports
14. Team, Time Clock, Payroll, Scheduling
15. Webstores / Order Portal Manager (only after shared core stable)
16. Wrap Lab (built on shared services)
17. AI Tools, Community, Platform Admin, Launch Hardening

## Notes on current state (as of adoption of these rules)
- Stages 0–3 complete ✅
- Stage 4 Quotes: **gaps** — quote items with pricing snapshots, expiration dates, revisions, portal visibility
- Stage 5 Orders/OrderItems: **gaps** — item-level pricing snapshots, `production_required` flag on items, richer source links
- Stage 6 Invoices/Payments: **gaps** — independent `document_status` vs `financial_status`, void with reason + Stripe restrictions, reconciliation service, Stripe readiness, legacy-payment migration scripts
- Stage 7 Work Orders: **gaps** — currently snapshots ALL order items; must be gated by `production_required`. Missing stages, board views, completion history, production packets.
- Stage 8 Documents: ✅ basics; missing template library, generated documents, shares, retention
- Stage 9 Email: ✅ SendGrid live; missing notification preferences, notif system separate from email
- Stage 10 Portal Lite: **not built**
- Stage 11 Proof/Signatures: **not built**
- Stage 12 Pricing Foundation: ✅ MVP delivered
- Stages 13–17: **not built**
