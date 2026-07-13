# SignGuy AI — Final Consolidated Source-Driven Master Build Plan

**Document date:** 2026-07-11 (final consolidated planning pass)
**Author:** Consolidated planning pass using the corrected scope register, readiness matrix, repository source map, prior master plan, and source-driven migration plan — no application code changed
**Permanent destination:** `dnblack323/SIGNGUY-MVP` — the permanent commercial product. Not a rebuild. Not a disposable MVP.
**Companion authorities (in priority order):**
1. Explicit current owner decisions.
2. `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`.
3. `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`.
4. `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`.
5. `/app/memory/AGENT_INSTRUCTIONS.md`.
6. Module-specific specifications (REB `memory/MODULE SPECS MDS/*`, REB `ORDER_PORTAL_*_SPEC.md`).
7. Existing code behavior (MVP `backend/app/**` + `frontend/src/**`).
8. Older planning documents.

**Terminology contract (LOCKED):** Only the canonical vocabulary in Part 2 of the Final Scope & Decision Register applies. `Job / Job Item / Job Ticket / Production Ticket / Job Ticket Summary` are prohibited as canonical terms.

**Navigation contract (LOCKED):** Collapsible left sidebar with side flyouts per the Final Scope & Decision Register Part 3.1 — Home / Shop Operations / Business & Finance / Team & Workflow / Creative Studio / (divider) / Control Center / Help & Community. Permanent second-level module navigation is NOT placed across the top of every page.

**Money policy (OWNER APPROVED — Decision 1):** Commerce values stored in integer cents with `_cents` suffix. Pricing configuration remains dollar-based with `Decimal` internally. Single pricing→commerce conversion boundary.

**Evidence-level legend** (carried forward): RV / STHV / FSV / PSI / SS / SO / RS.

**Reuse classifications** (LOCKED): KEEP / COPY AND INTEGRATE / COPY AND TARGETED REFACTOR / EXTRACT BUSINESS LOGIC AND REHOUSE / MERGE DUPLICATE IMPLEMENTATIONS / REBUILD AGAINST MVP SHARED SERVICES / REMOVE / DEPRECATE / MODULE PREFLIGHT REQUIRED / OWNER DECISION REQUIRED.

> **Final consolidation rule.** This document is both the construction manual and the migration manual. The nine **Program Checkpoints (PC1-PC9)** provide executive governance and release grouping. The fifteen **Execution Checkpoints (EC0-EC14)** are the actual implementation units used for coding, testing, evidence packages, and branch work. When a PC and EC appear to conflict, the EC dependency sequence governs implementation while the PC retains reporting and commercial-gate ownership.

> **Exact-source rule.** No donor path, copy instruction, or reuse claim is authoritative unless it appears in Part 7A (Exact Source and Migration Map) or is confirmed by a completed module preflight. A path named elsewhere but absent from Part 7A must be treated as `TO CONFIRM DURING PREFLIGHT`, not as verified fact.

---

> ## ⚠️ DOCUMENT-LEVEL NOTICE (2026-02 intake — SignGuy AI Checkpoint Specification Pack)
>
> This document remains the **authoritative build plan for EC0–EC8** (all COMPLETE/CLOSED). For **EC9 onward**, this document is **SUPERSEDED — HISTORICAL REFERENCE ONLY — NOT IMPLEMENTATION AUTHORITY** by the owner-approved **SignGuy AI Checkpoint Specification Pack** (15 documents: Master Index + EC09–EC22, at `/app/specs_pack/extracted/`). The new pack renumbers and expands the remaining work into **EC9–EC22** (see `/app/memory/checkpoint_reference_table.md`). Specific superseded sections inside this document are marked inline (Part 30A.10–30A.15, Appendix A.4). Full authority order is in `/app/memory/documentation_authority_register.md`. No checkpoint from either the old or new sequence begins without explicit owner authorization.

# PART 1 — EXECUTIVE BUILD SUMMARY

SignGuy AI ships as **nine Program Checkpoints (PC1-PC9)** delivering the permanent commercial product on top of the existing MVP foundation. The MVP already contains a production-safe Auth / Tenants / Permissions / Customers / Quotes / Orders / Work Orders / Invoices / Object Storage / Pricing Foundation & Calculator surface. The remaining work is a mixture of targeted extensions, donor-code extractions (FEB financial logic; REB Settings / Communications / DocuLink / Wrap Lab / Platform Admin / AI catalog / Quote+Order shapes; ORIG signatures / approvals / portal / webstore feature discovery), and greenfield builds (portal identity, background jobs, feature entitlements, AI credit ledger, custom report builder, global search, tax provider boundary).

The nine checkpoints are dependency-ordered so that (a) money-safety and tenant-safety land before any higher module, (b) shared foundations are complete before feature modules, (c) the customer/quote/order/invoice/payment spine is complete before documents/portals, (d) add-ons (Webstores, Wrap Lab) never precede their dependencies (entitlements, portals, payments), (e) AI never precedes credit metering and cost caps, (f) commercial hardening runs last.

**First program checkpoint:** PC1 — Product Rules, Security Guards, and Money Policy Landing.

**Checkpoint counts and totals** (see Part 34 for exact totals):
- 9 Program Checkpoints (PC1-PC9) plus 15 Execution Checkpoints (EC0-EC14).
- 152 module rows in the master matrix (rows preserved 1:1 from Final Scope & Decision Register Part 4; no bounded module removed).
- 27 owner decisions answered and recorded: 23 fully approved, 1 approved with a module-preflight condition, and 3 approved subject to cost/model audit.
- 20 module preflights scheduled.
- 0 application code changes performed in this document.

---

# PART 2 — AUTHORITY AND SOURCE HIERARCHY

## 2.1 Authority Order

When any two references conflict, the higher-numbered priority wins:

1. Explicit current owner decisions (this Prompt + subsequent owner ratifications).
2. `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md` (LOCKED scope contract).
3. `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (per-feature evidence).
4. `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` (per-repository evidence).
5. `/app/memory/AGENT_INSTRUCTIONS.md` (implementation rules).
6. Module-specific specifications (REB memory specs; ORDER_PORTAL specs).
7. Existing MVP code behavior (RV baseline).
8. Older planning documents (`/app/plan.md`, `/app/PRICING_DEFAULTS_AUDIT.md`).

## 2.2 What Overrides What (worked examples)

- Owner statement "Founders receive complete platform + Webstores + Wrap Lab + defined AI credits" **overrides** REB `billing_rules.py` candidate values.
- Final Scope & Decision Register Part 2 terminology lock **overrides** any FEB or ORIG file that uses `job_id`.
- Final Scope & Decision Register Part 3 navigation LOCK **overrides** any older `/app/plan.md` navigation sketch.
- Feature Readiness Matrix `FSV` evidence **overrides** older assumptions about donor-code completeness.
- MVP RV behavior **overrides** REB/ORIG code style where MVP is already working (do not refactor working modules).

## 2.3 Prohibited Overrides

- Donor code never overrides a LOCKED terminology, navigation, or money policy.
- REB `billing_rules.py` values never silently become production prices.
- Legacy `App.js` structure never resurfaces as an implementation pattern.
- No planning agent may replace the permanent repo, delete a donor before commercial completion, or begin implementation inside a scope prompt.

---

# PART 3 — LOCKED PRODUCT RULES

## 3.1 Repository Rules (LOCKED)

- `dnblack323/SIGNGUY-MVP` = permanent product. Only repo that receives new commits.
- `SIGNGUY-AI-OS` = frozen mirror. No new development. Archive only after final commercial completion. No delete.
- `signguyai_rebuild_version` (REB) = architecture + spec + scaffold donor. Read-only reference. Sanitize `PreviewEnvelope` and resolve `core_runtime` imports on port.
- `signguy-ai-feb22` (FEB) = financial-logic donor. Read-only reference. Rename Job→Order on every ported line.
- `signguyai` (ORIG) = feature-discovery + targeted donor. Read-only reference. Module preflight required before any port. Never copy monolithic App.js, dev/backup routes, or Job-domain routes.

## 3.2 Terminology Rules (LOCKED)

- Canonical vocabulary from Final Scope & Decision Register Part 2. Every donor port targeted-refactors prohibited terms.
- API routes plural + kebab-case; no `/jobs`, `/job-tickets`, `/production-tickets`.
- MongoDB collections: `customers, leads, quotes, quote_line_items, orders, order_items, work_orders, invoices, invoice_line_items, payments, wrap_projects, attachments, documents, document_shares, file_links, document_links, portal_identities, magic_link_tokens, public_action_tokens, notifications, email_activity, sms_logs, ai_responses, ai_credit_ledger, subscriptions, feature_entitlements, webstores, webstore_products, webstore_orders, payouts, audit_events`. Never `jobs`.
- Field names: money commerce = `_cents` (integer); pricing config = dollars (float/`Decimal`); FKs = `<entity>_id`; timestamps = `<verb>_at` UTC.

## 3.3 Navigation Rules (LOCKED)

- Collapsible left sidebar with side flyouts.
- Home + Shop Operations + Business & Finance + Team & Workflow + Creative Studio + (divider) + Control Center + Help & Community.
- No permanent second-level module nav across the top of every page.
- Page-specific tabs, ribbons, filters, view selectors, actions, and breadcrumbs are allowed and must not duplicate the sidebar.
- Payroll / Time Clock / Timesheets / Employee Scheduling → Team & Workflow.
- Inventory / Vendors / Purchasing → Shop Operations → Inventory & Purchasing flyout.
- Pricing configuration → Control Center → Pricing Defaults. Pricing Calculator may appear as an operational shortcut inside Quotes/Orders.
- Tenant subscription + AI credits → Control Center → Subscriptions & AI Credits.
- AI creation tools → Creative Studio.
- Help, community, bugs, feature requests, contact support, what's new → Help & Community.
- Portals + public systems are separately routed; they do not become internal sidebar areas.

## 3.4 Money Policy (OWNER APPROVED — Decision 1)

- Commerce values (`Quote.total_cents`, `QuoteLineItem.line_total_cents`, `Order.total_cents`, `OrderItem.unit_price_cents`, `OrderItem.line_total_cents`, `WorkOrderItemSnapshot.unit_price_cents`, `Invoice.total_cents`, `InvoiceLineItem.unit_price_cents`, `Payment.amount_cents`, and future `tax_cents`, `discount_cents`, `fee_cents`, `amount_paid_cents`, `balance_due_cents`) are integer cents.
- Pricing configuration in `pricing_settings` remains dollar-based with `Decimal` math internally.
- One pricing→commerce conversion boundary: on writing a commerce field from a calculator output.
- Stripe amounts remain integer cents on wire and on our Payment row (no conversion).
- Reports sum integer cents; display formatting happens in the renderer.

## 3.5 Security Rules (LOCKED)

- Startup guard on `ENV=production` blocks: `AUTH_DEV_BYPASS=true`, placeholder JWT secret, missing SendGrid webhook secret, missing Stripe webhook secret, unset production Stripe key on any Stripe write path.
- Object storage private by default; no Base64-in-Mongo.
- Portal tokens never interchangeable with staff JWTs (LOCKED). `sub_scope="portal"` claim.
- Webhook signatures verified on SendGrid + Stripe + future providers. Replay-safe via unique event ID index.
- Payment writes require idempotency (Idempotency-Key + DuplicateKeyError race handling).
- Audit event on every write.

## 3.6 Data Integrity Rules (LOCKED)

- Every tenant-scoped collection has `(tenant_id, id)` and per-collection indexes registered in `core/db.py::ensure_indexes()`.
- Unique constraints: `(tenant_id, number)` on numbered documents; `(tenant_id, order_id)` on invoices; `(tenant_id, quote_id, converted_to_order_id)` guarded for idempotent conversion.
- Soft-delete/archive on financial and customer records; no destructive delete.
- Cross-tenant sweep test mandatory after every new module.

---

# PART 4 — OWNER-APPROVED DECISION REGISTER

All 27 owner decisions have now been answered and are controlling instructions for the permanent product. These decisions replace the former pending-decision table. An implementation agent may not reopen them merely because a donor repository uses a different pattern or an older document contains different candidate values.

**Decision status summary**

- Fully owner approved: 23
- Owner approved with module-preflight condition: 1 (Decision 7)
- Owner approved subject to cost/model audit before live commercial activation: 3 (Decisions 12, 13, and 18)
- Unanswered decisions: 0
- EC0 governance status: COMPLETE
- Next executable checkpoint: EC1 — Security and Permanent App Guardrails

## Decision 1 — Permanent Money Representation Policy

**OWNER-APPROVED SELECTION:** Preserve the existing MVP split.

- Every stored transactional commerce value uses integer cents.
- Transactional fields use the `_cents` suffix.
- Pricing configuration may remain dollar-based and use `Decimal` internally.
- One explicit pricing-to-commerce conversion boundary converts calculator dollars to commerce cents.
- Stripe values remain integer cents.
- No ambiguous unsuffixed money fields are allowed on Quotes, Orders, Work Orders, Invoices, Payments, taxes, discounts, or fees.

**Implementation effect:** No destructive money migration is authorized. FEB invoice/payment logic must be rehoused into the existing MVP cents contract.

**STATUS:** OWNER APPROVED

## Decision 2 — Permission Catalog

**OWNER-APPROVED SELECTION:** Use a permanent module-based permission catalog. Reuse REB's structured enum pattern, but do not blindly copy all donor permissions.

Permissions must be organized around permanent modules, including Customers, Quotes, Orders, Work Orders, Invoices, Payments, Documents, Inventory, Purchasing, Employees, Time Clock, Timesheets, Payroll, Reports, Webstores, Wrap Lab, AI Tools, Settings, Platform Administration, and Portals.

Backend enforcement is authoritative. Frontend permission checks only control presentation.

**STATUS:** OWNER APPROVED

## Decision 3 — Repository-Class Pattern

**OWNER-APPROVED SELECTION:** Use repository classes for new or substantially rebuilt modules only.

Do not refactor stable MVP modules merely for visual uniformity. Every new repository must enforce tenant scope, own collection indexes, provide scoped CRUD methods, and keep routers thin.

**STATUS:** OWNER APPROVED

## Decision 4 — SendGrid Webhook Production Behavior

**OWNER-APPROVED SELECTION:** Fail closed in production.

Production startup must fail when the SendGrid webhook is enabled but the verification secret is missing. Development may leave the webhook disabled, but unverifiable production events must never be accepted.

**STATUS:** OWNER APPROVED

## Decision 5 — SIGNGUY-AI-OS Archive Timing

**OWNER-APPROVED SELECTION:** Freeze immediately, compare completely before archival, archive only after commercial completion, and never delete as part of this rebuild.

**STATUS:** OWNER APPROVED

## Decision 6 — Webstores Add-On and Standalone Policy

**OWNER-APPROVED SELECTION:** Webstores is both a paid Core add-on and a standalone product using the same backend and shared domain systems.

Standalone mode uses entitlements and a reduced interface. It must not create separate Customer, Order, Payment, Document, User, File, Email, or Audit systems. Upgrading to Core requires no data migration.

**STATUS:** OWNER APPROVED

## Decision 7 — Wrap Lab Standalone Policy

**OWNER-APPROVED SELECTION:** Wrap Lab is founder-included and available as a paid add-on. It must be designed for possible standalone sale, but standalone activation requires a completed preflight proving shared-core reuse without duplication.

**STATUS:** OWNER APPROVED WITH MODULE-PREFLIGHT CONDITION

## Decision 8 — Portal Authentication Mode

**OWNER-APPROVED SELECTION:** Separate portal identities with password and magic-link access for recurring users, plus scoped, expiring, single-purpose tokens for proof approval, quote approval, signatures, invoice views, payment links, and questionnaires.

Portal credentials and tokens must never be interchangeable with staff JWTs. Customer, Employee, Webstore Owner, and Webstore Manager scopes remain distinct.

**STATUS:** OWNER APPROVED

## Decision 9 — Sales-Tax Strategy

**OWNER-APPROVED SELECTION:** Initial release uses shop-configured multiple tax jurisdictions, customer exemption records and certificate storage, invoice tax snapshots, audited manual overrides, and a clean future tax-provider service boundary.

Historical invoices must never be silently recalculated after configuration changes. Avalara or TaxJar is not required for the first commercial release.

**STATUS:** OWNER APPROVED

## Decision 10 — General Commercial Subscription Pricing

**OWNER-APPROVED SELECTION:**

- SignGuy AI Core: **$149/month**
- Webstores add-on to Core: **$59/month**
- Wrap Lab add-on to Core: **$79/month**
- Complete Bundle: **$249/month**
- Webstores standalone: **$89/month**
- Wrap Lab standalone: **$119/month**, only after standalone readiness is approved

Core business records must not be limited by customer, quote, order, invoice, employee, or revenue quotas. AI use beyond included credits is purchased separately.

**STATUS:** OWNER APPROVED

## Decision 11 — Founder Pricing

**OWNER-APPROVED SELECTION:** One Founder Edition for the first 50 shops at **$149/month**, price-locked while continuously active.

Includes Core, Webstores, Wrap Lab, all standard business features, and 1,000 monthly AI credits. No artificial business-record limits. Includes a one-week free trial with limited AI use.

**STATUS:** OWNER APPROVED

## Decision 12 — AI-Credit Top-Up Pricing

**OWNER-APPROVED SELECTION:** Initial structure:

- 100 credits: **$19**
- 300 credits: **$45**
- 800 credits: **$99**

The structure is approved, but live billing activation requires a measured provider-cost audit. Values may be adjusted before activation if margins are unsafe.

**STATUS:** OWNER APPROVED SUBJECT TO COST AUDIT

## Decision 13 — Included AI-Credit Amounts

**OWNER-APPROVED SELECTION:**

- Core: 300 credits/month
- Webstores standalone: 300 credits/month
- Wrap Lab standalone: 500 credits/month
- Complete Bundle: 1,000 credits/month
- Founder Edition: 1,000 credits/month
- Seven-day trial: 50 total credits

Included credits reset monthly. Exact per-tool charges require the provider-cost audit before commercial activation.

**STATUS:** OWNER APPROVED SUBJECT TO COST AUDIT

## Decision 14 — AI-Credit Expiration

**OWNER-APPROVED SELECTION:** Included credits reset each billing cycle and do not roll over. Purchased top-up credits do not expire while the account remains active and are consumed after included credits. Provider failures refund credits. Administrative adjustments require a reason and audit event.

**STATUS:** OWNER APPROVED

## Decision 15 — Transaction Fees

**OWNER-APPROVED SELECTION:**

- Founder first three paid months: 0% standard / 0% Webstore platform fee
- Founder ongoing: 0.5% standard / 1.5% Webstore
- General availability: 1% standard / 2% Webstore

Stripe processing fees remain separate. Platform fees must be calculated server-side, stored with the transaction, reported clearly, and never accepted from client calculations.

**STATUS:** OWNER APPROVED

## Decision 16 — Setup and Onboarding Fees

**OWNER-APPROVED SELECTION:**

- DIY onboarding: free
- Guided setup session: $299 one time
- Done-for-you basic configuration: $799 one time
- Larger data/template/pricing/workflow setup: custom quote

Founder customers receive standard DIY onboarding at no additional charge.

**STATUS:** OWNER APPROVED

## Decision 17 — Non-Founder Free Trial

**OWNER-APPROVED SELECTION:** Seven-day free trial with 50 AI credits and no artificial limits on normal Core records. A payment method is required before conversion to paid service. Live transaction processing and production SMS may remain disabled until verification.

**STATUS:** OWNER APPROVED

## Decision 18 — AI Provider and Model Rules

**OWNER-APPROVED SELECTION:** Use the Emergent-managed AI integration initially behind a provider abstraction. Route models by task category and intensity rather than hardcoding one provider everywhere.

Every AI request must record tenant, tool, model, estimated cost, credit charge, result, refund behavior, cost cap, and audit metadata. Exact model assignments and per-tool credit costs require a cost-and-quality audit.

**STATUS:** OWNER APPROVED SUBJECT TO MODEL/COST AUDIT

## Decision 19 — SMS/MMS Provider

**OWNER-APPROVED SELECTION:** Twilio initially, behind a provider adapter.

Must support outbound SMS/MMS, delivery webhooks, inbound replies, opt-out handling, tenant-scoped logs, idempotency, US 10DLC registration, and production credential rotation. Previously pasted credentials must never be reused.

**STATUS:** OWNER APPROVED

## Decision 20 — Custom Report Builder Scope

**OWNER-APPROVED SELECTION:** Curated reports plus a staged Custom Report Builder are required permanent-product scope.

The staged builder includes data-source selection, column selection, filters, sorting/grouping, saved reports, exports, and approved chart options. It must not expand into a general-purpose BI platform. It may be built in controlled stages but may not be silently moved to an undefined backlog.

**STATUS:** OWNER APPROVED

## Decision 21 — Platform-Admin Impersonation

**OWNER-APPROVED SELECTION:** Read-only “View As Tenant” mode only.

Requires a reason, persistent banner, audit history, tenant-visible notification/audit entry, automatic expiration, and strict prohibition on payment, billing, security, deletion, or user-identity changes. No unrestricted full impersonation.

**STATUS:** OWNER APPROVED

## Decision 22 — Customer Portal Payment Methods

**OWNER-APPROVED SELECTION:** Launch with Stripe credit/debit card payments plus authorized internal recording of manual payments. ACH is a later addition after card reconciliation is stable.

**STATUS:** OWNER APPROVED

## Decision 23 — Employee Portal Payroll Visibility

**OWNER-APPROVED SELECTION:** Employees may view their own full approved payroll information, including pay periods, hours, rates, gross pay, advances, adjustments, carryover, payments, history, and payslip/statement downloads.

Employees may never view another employee's records. Sensitive payroll information must not leak through general team permissions.

**STATUS:** OWNER APPROVED

## Decision 24 — Final Navigation Structure

**OWNER-APPROVED AND LOCKED:** Collapsible left sidebar:

- Home
- Shop Operations
- Business & Finance
- Team & Workflow
- Creative Studio
- Divider
- Control Center
- Help & Community

Each area uses a side flyout. Page ribbons, tabs, and filters may not duplicate permanent navigation. Home remains an icon to the main dashboard.

**STATUS:** OWNER APPROVED AND LOCKED

## Decision 25 — Final Build and Checkpoint Order

**OWNER-APPROVED AND LOCKED:** Use the consolidated plan's nine program checkpoints and fifteen execution checkpoints. EC0 is now complete. EC1 is the first code-bearing checkpoint.

**STATUS:** OWNER APPROVED AND LOCKED

## Decision 26 — Subscription Payment-Failure Grace Period

**OWNER-APPROVED SELECTION:**

- Days 1-7: normal access with billing warning
- Days 8-14: soft restriction on paid add-ons and new AI usage
- After day 14: paid modules blocked until billing is corrected

Data is preserved. Billing, export, and support remain accessible. Platform administrators may grant a documented temporary extension.

**STATUS:** OWNER APPROVED

## Decision 27 — SMS/MMS Commercial-Release Timing

**OWNER-APPROVED SELECTION:** SMS/MMS remains permanent-product scope but does not block the first commercial sale.

First commercial release may proceed when email and portal messaging work and SMS architecture/entitlement hooks are prepared. Twilio SMS/MMS ships in a later controlled commercial release after 10DLC registration, opt-out handling, delivery webhooks, inbound replies, and compliance testing.

**STATUS:** OWNER APPROVED — LATER COMMERCIAL RELEASE

## Part 4 Completion Effect

- EC0 is complete.
- No owner-response packet is required before EC1.
- EC1 may begin using these decisions as locked governance.
- Decisions 12, 13, and 18 do not block EC1; their audits block live AI commercial activation.
- Decision 7 does not block Core implementation; its preflight blocks standalone Wrap Lab activation.
- Decision 27 does not block first commercial release, but SMS/MMS remains tracked permanent scope.

# PART 5 — PROGRAM CHECKPOINT ARCHITECTURE


## 5.0 Program vs Execution Checkpoints

The nine PC groups are reporting and commercial-gate containers. They are not intended to be single giant coding branches. Actual implementation uses the EC sequence in Part 30A. Each EC has its own branch, entry conditions, exit conditions, evidence package, and stop point.

| Program checkpoint | Execution checkpoints contained |
|---|---|
| PC1 Product Rules and Security | EC0, EC1 |
| PC2 Shared Platform Foundations | EC2 |
| PC3 Core Money and Order Pipeline | EC3, EC4, EC5 |
| PC4 Documents, Portals, Customer Workflow | EC6 |
| PC5 Inventory, Purchasing, Finance, Reporting | EC7 |
| PC6 Team and Workflow | EC8 |
| PC7 Add-ons | EC9, EC10 |
| PC8 AI, Platform, Commercial Systems | EC11, EC12, EC13 |
| PC9 Final Hardening | EC14 |

## 5.1 The Nine Program Checkpoints

| # | Name | Purpose | Commercial-release relevance |
|---|---|---|---|
| **CP1** | Product Rules, Security Guards, and Money Policy Landing | Land non-negotiable rules + startup guards + money policy so every subsequent checkpoint is safe by construction | LOCKED foundation for every CR gate |
| **CP2** | Shared Platform Foundations | Settings, Notifications, Communications (SendGrid webhook + email activity), Upload Validation, Feature Entitlements scaffold, Webhook Infrastructure, Portal Auth foundation, Background Jobs scaffold, Monitoring | Blocker for CP3–CP9 |
| **CP3** | Core Money and Order Pipeline | Quote (line items, expiration, revisions) + Order (rich item schema + `production_required`) + Pricing Snapshot + Invoice (dual status) + Payment (unified, idempotent, controlled void) + Work Order gate | Blocker; the product spine |
| **CP4** | Documents, Portals, and Customer Workflow | DocuLink→Asset Library, Templates, Forms, Questionnaires, Signatures, Proofs, Approvals, Customer Portal, Public Forms, Public Proof Approval, Public Signatures | Blocker (portal + approvals + signatures required for CR) |
| **CP5** | Inventory, Purchasing, Finance, and Reporting | Inventory + Vendors + Purchasing (Shop Ops nav) AND Financials + Sales + Expenses + Taxes + Reports + Custom Report Builder + Business Analytics (Business & Finance nav) — one implementation checkpoint because both depend on CP3 | Blocker (financial reporting required) |
| **CP6** | Team & Workflow | Employees, Tasks, Kanban, Team Schedule, Time Clock, Timesheets, Payroll, Messages & Notes, Announcements, Employee Portal | Blocker (time clock + payroll required for CR) |
| **CP7** | Add-ons — Webstores + Wrap Lab | Webstores (add-on + standalone shell), Public Storefront, Webstore Owner/Manager Portals, Stripe Connect, Payouts, Wrap Lab 11-stage workflow, Wrap Portal projection | Blocker for founder launch (founders bundle Webstores + Wrap) |
| **CP8** | AI, Platform, and Commercial Systems | Creative Studio + AI Assistant + AI Tools (24) + Prompt Library + Artwork Workspace + Generated Assets + AI History + AI Credit Ledger + provider abstraction + Subscription Billing + Add-on Purchases + AI Credit Purchases + Transaction Fees + Founders promo + Platform Admin + Community + Onboarding + Marketing site + Public Pricing | Blocker (commercial billing required) |
| **CP9** | Final Integration and Commercial-Release Hardening | SMS/MMS integration (if Decision 27 = a), production secret rotation, dev-bypass hard disable, end-to-end regressions across every checkpoint, performance/accessibility/monitoring reviews, docs finalization, terms & policies, support processes, marketing/pricing pages, launch runbook | LOCKED final gate before commercial sale |

## 5.2 Rationale for Nine Program Checkpoints

The Final Scope & Decision Register recommended Groups A–H. This plan condenses Group A into a single boot checkpoint (CP1), keeps Group B (CP2), keeps the spine (CP3), keeps documents+portals (CP4), merges Group E into CP5 (Inventory, Purchasing, Finance, Reporting — same dependencies), keeps Team & Workflow (CP6), keeps Add-ons (CP7), keeps AI+Platform+Commercial (CP8), and adds CP9 as a dedicated final-integration and commercial-release hardening gate so that SMS/MMS timing (Decision 27), production secret rotation, cross-checkpoint regression, and launch readiness get an explicit checkpoint rather than being scattered.

## 5.3 Why This Order

- CP1 first because every subsequent checkpoint depends on terminology, security guards, and money policy being LOCKED.
- CP2 second because every feature checkpoint depends on the shared services (Settings, Notifications, Webhooks, Entitlements, Portal auth foundation).
- CP3 third because the money/order spine dominates the entire commercial flow.
- CP4 fourth because customer-portal + proof + signature + document workflow depend on the spine and file infra.
- CP5 fifth because inventory + finance + reporting depend on completed orders + invoices + payments.
- CP6 sixth because payroll depends on portal auth + time clock which depend on CP2 + CP4.
- CP7 seventh because Webstores + Wrap Lab depend on entitlements, portals, DocuLink, approvals, signatures, and payment reconciliation (all delivered by CP2, CP3, CP4).
- CP8 eighth because Subscription billing + AI credits + commercial billing require Stripe reconciliation + entitlements to be trusted.
- CP9 last because final commercial hardening + optional SMS/MMS timing + docs + terms must run only after every feature is in place.

---

# PART 6 — CHECKPOINT DEPENDENCY MAP

## 6.1 Dependency DAG

```
CP1 ─┬─► CP2 ─┬─► CP3 ─┬─► CP4 ─┬─► CP6 ─────────────────► CP9
     │        │        │        │
     │        │        │        └─► CP7 (Webstores + Wrap Lab)
     │        │        │
     │        │        └─► CP5 (Inv+Purchasing+Finance+Reporting)
     │        │
     │        └─► (Portal auth foundation used by CP4, CP6, CP7)
     │
     └─► (Security guards enforced in every CP)

CP8 depends on CP2 (Entitlements) + CP3 (Payments/Stripe Core) + CP7 (Stripe Connect for Webstores billing paths)
CP9 depends on all of CP1–CP8
```

## 6.2 Parallel-safe pairs

- CP4 and CP5 may run in partial parallel after CP3 exits (DocuLink work and Reports data model can proceed independently, but cross-tenant sweep + integration tests wait for both to complete).
- CP5 and CP6 may run in partial parallel because they depend on CP3, not on each other.
- CP7 Webstores and CP7 Wrap Lab may run in partial parallel because they share dependencies but not each other.
- CP8 subsections (Creative Studio + AI Tools) and (Subscription Billing) may run in partial parallel; AI Credit Ledger must land before the AI Tools use it.

## 6.3 Non-parallel pairs

- CP2 and CP3 must not run in parallel — the shared services CP3 depends on (Settings, Notifications, Entitlements, Webhook infra, Portal auth foundation) must be complete first.
- CP4 and CP7 must not run in parallel — Wrap Lab and Webstores both require the completed DocuLink + Approvals + Signatures + Customer Portal from CP4.
- CP3 and CP5 must not run in parallel — Inventory valuation and financial reports rely on the completed Payment/Invoice/OrderItem shapes from CP3.

## 6.4 Required Prior CPs per Checkpoint

| CP | Requires |
|---|---|
| CP1 | (none) |
| CP2 | CP1 |
| CP3 | CP1, CP2 |
| CP4 | CP1, CP2, CP3 |
| CP5 | CP1, CP2, CP3 |
| CP6 | CP1, CP2, CP3 (partial), CP4 (Employee Portal auth) |
| CP7 | CP1, CP2, CP3, CP4 (portals + docs + signatures + approvals) |
| CP8 | CP1, CP2, CP3, CP4 (AI-doc review), CP5 (finance reporting for platform view), CP7 (Stripe Connect for Webstore commercial billing paths) |
| CP9 | All of CP1–CP8 |

---

# PART 7 — SHARED FOUNDATIONS MAP

Every foundation below is owned by exactly one checkpoint and referenced by all downstream ones.

| Foundation | Current state | Permanent owner (CP) | Source | Reuse method | Dependent modules | Security requirements | Tenant requirements | Audit requirements | Release-blocker |
|---|---|---|---|---|---|---|---|---|---|
| Authentication | RV | CP1 | MVP | KEEP | All | Bcrypt + JWT + single-use email reset token; production dev-bypass guard | tenant_id claim in JWT | login/logout events | Yes |
| Tenants | RV | CP1 | MVP | KEEP | All | Tenant filter on every read/write | | tenant create/rename | Yes |
| Users | RV | CP1 | MVP | KEEP | All | Password rules | tenant_id FK | user CRUD | Yes |
| Roles | RV+FSV | CP1 | MVP+REB | REF (adopt REB StrEnum shape) | All | Backend-enforced | tenant scoped | role change events | Yes |
| Permissions | FSV | CP1 | MVP+REB Part 9 | REF (module-based catalog) | All | require_permission() dep | tenant scoped | permission change events | Yes |
| Application Shell | RV | CP1 | MVP | KEEP | All FE | | | | Yes |
| Navigation (sidebar + flyouts) | New (nav LOCKED Part 3.3) | CP1 | Final Scope Register Part 3 | New | All FE | Client + backend consistent | | | Yes |
| Shared UI Components | RV | CP1 | MVP (shadcn/ui + Tailwind) | KEEP | All FE | | | | Yes |
| Settings Framework | Not built | CP2 | REB `routes/settings.py` + `models/settings.py` | REF | All modules with tenant config | Namespaced settings; audit | tenant scoped | settings change events | Yes |
| Audit Log | RV | CP1 | MVP `services/audit.py` | KEEP + EXTEND | All writes | Immutable append-only | tenant scoped | (self) | Yes |
| Activity History | RV+FSV | CP2 | MVP + REB | REF | Documents, orders, wrap, portal | | tenant scoped | activity events | Yes |
| Notifications (in-app) | Not built | CP2 | REB `routes/communications.py` + `services/communications.py` | REF | All modules | | tenant + user scoped | notification events | Yes |
| SendGrid Outbound Email | RV | CP1 | MVP `services/email.py` | KEEP | All | Fail on missing key | tenant + template scoped | email send events | Yes |
| SendGrid Webhook + Email Activity | Not built | CP2 | REB webhook shape | EXTRACT + REBUILD | All | Fail-closed prod on missing secret (Decision 4) | tenant scoped by metadata | delivery events | Yes |
| Internal Messaging | Not built | CP6 | ORIG+REB | REBUILD | Team | | tenant scoped | message events | Yes |
| SMS/MMS | Not built | CP9 (per Decision 27 timing) | ORIG | REBUILD | Portal, Notifications, Order events | Provider webhook signature; carrier 10DLC | tenant scoped | sms events | Decision 27 |
| Object Storage | RV | CP1 | MVP + ORIG | KEEP | All file modules | Private by default; tenant path prefix | tenant scoped | file events | Yes |
| File Uploads | RV | CP1 | MVP | KEEP + EXTEND | All file modules | Upload validation (CP2) | tenant scoped | file events | Yes |
| Upload Validation | Not built | CP2 | REB `services/upload_validation.py` | EXTRACT | All file modules | MIME + magic-byte + size + SHA-256 | tenant scoped | file rejection events | Yes |
| Attachments (polymorphic) | RV+FSV | CP2 | MVP + REB | REF (adopt `file_links`, `document_links`, `document_shares`) | Docs, Orders, Wrap, Portal | | tenant scoped | link events | Yes |
| Templates (doc + email) | Not built | CP4 | REB + ORIG | REF | Docs, Emails | | tenant scoped | template events | Yes |
| Forms | Not built | CP4 | ORIG | REBUILD | Public + Portal | Rate limit + captcha | tenant slug scoped | submission events | Yes |
| Questionnaires | Not built | CP4 | ORIG + REB | REBUILD | Orders, Webstores, Wrap | Rate limit + captcha | tenant slug scoped | submission events | Yes |
| Signatures | Not built | CP4 | ORIG PSI | REF + preflight | Contracts, Proofs, Packets, Webstore agreements, Wrap packets | Single-action tokens; short expiry | tenant scoped | signature events | Yes |
| Global Search | Not built | PC8 / EC12 | New | REBUILD | All modules | Tenant scoping | tenant scoped | | Yes unless the owner explicitly approves later commercial timing |
| Background Jobs | Not built | CP2 (scaffold) + CP5/CP8 (jobs) | ORIG reference + New | REBUILD | Reports, Payments dunning, digest emails, reconciliation sweeps | Dead-letter | tenant scoped | job events | Yes |
| Webhook Infrastructure | Partial (SendGrid FSV) | CP2 | REB + FEB Stripe pattern | REBUILD (shared framework) | Emails, Payments, Portals | Signature verify + replay-safe | tenant scoped via metadata | webhook events | Yes |
| Error Logging | RV | CP1 | MVP | KEEP | All | | | | Yes |
| Monitoring | Not built | CP9 | New | New | All | | | | Yes |
| Feature Entitlements | Not built | CP2 (scaffold) + CP8 (billing wire-up) | REB `FeatureEntitlementRepository` spec + New | REBUILD | Add-ons, AI, SMS, Wrap Lab, Webstores | Backend-checked | tenant scoped | entitlement events | Yes |
| Subscription Access | Not built | CP8 | REB `billing_rules.py` candidate + New | EXTRACT + REBUILD | Every add-on and standalone product | Stripe idempotency | tenant scoped | subscription events | Yes |
| AI Credit Ledger | Not built | CP8 (before AI Tools land) | REB + New | REBUILD | AI Tools, AI Assistant | Debit/refund atomicity; cost cap | tenant scoped | credit events | Yes |
| Portal Authentication | Not built | CP2 (foundation) + CP4/CP6/CP7 (consumers) | ORIG PSI | REBUILD | Customer, Employee, Webstore Owner, Webstore Manager portals + public tokens | `sub_scope=portal`; magic-link single-use; brute-force lockout | tenant scoped | portal auth events | Yes |
| DocuLink (Asset Library) | Not built | CP4 | REB (FSV) | EXTRACT + REBUILD (rewire storage to Emergent) | Orders, Wrap, Webstores, Portal, AI generated | Private by default; source_type=ai_generated → requires_review | tenant scoped | document events | Yes |
| Money-Safe Reconciliation | Not built | CP3 | FEB `services/payment_service.py` + `services/invoice_service.py` | EXTRACT + REBUILD | Invoices, Payments, Reports | Idempotency, dual status, controlled void | tenant scoped | payment events | Yes |
| Sequence Generation | RV | CP1 | MVP `services/sequence.py` | KEEP | Quote/Order/Invoice/WorkOrder numbering | Race-safe atomic increment | tenant scoped | (implicit) | Yes |

---

# PART 7A — EXACT SOURCE AND MIGRATION MAP

This part is the controlling source-level migration authority. It answers, for every major system: permanent destination, verified donor source, exact files, evidence level, whether whole-file copying is allowed, what behavior is preserved, what code is rejected, required terminology changes, MVP rewiring, and preflight/test obligations.

**Interpretation rules:**
- `KEEP` means preserve the working MVP implementation and extend only where stated.
- `COPY AND INTEGRATE` is permitted only for a small, fully verified file explicitly classified that way.
- `COPY AND TARGETED REFACTOR` means the donor structure is useful but imports, tenant scope, permissions, audit, storage, and terminology must be adapted.
- `EXTRACT BUSINESS LOGIC AND REHOUSE` means copy only the verified algorithms or workflows, not the donor router/model/application architecture.
- `REBUILD AGAINST MVP SHARED SERVICES` means donor code is behavioral evidence only.
- `MODULE PREFLIGHT REQUIRED` means exact file movement is forbidden until the full trace is complete.


This is the controlling section for where each system comes from and how it is moved into SIGNGUY-MVP.

## 7A.1 Auth / JWT / password reset

- **Assigned checkpoint:** 1
- **Source of truth:** MVP
- **Specific source files/evidence:** `backend/app/core/security.py`, `routers/auth.py`, `deps.py`, `models/user.py`
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.2 Tenants / org boundaries

- **Assigned checkpoint:** 1
- **Source of truth:** MVP
- **Specific source files/evidence:** `models/user.py::Tenant`, `deps.py::get_current_tenant`, `core/db.py::ensure_indexes`
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.3 Permissions catalog

- **Assigned checkpoint:** 1
- **Source of truth:** REB `models/access.py` (57 permissions) → MVP `core/permissions.py`
- **Specific source files/evidence:** REB `models/access.py`, MVP `core/permissions.py`
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.4 Audit event

- **Assigned checkpoint:** 2
- **Source of truth:** MVP `services/audit.py` (actor required) + adopt REB `models/activity.py` shape
- **Specific source files/evidence:** MVP `services/audit.py`, REB `services/activity.py` + `routes/activity.py` + `models/activity.py`
- **Evidence level:** RV+FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.5 Object storage

- **Assigned checkpoint:** 1
- **Source of truth:** MVP `services/storage.py` (Emergent)
- **Specific source files/evidence:** MVP `services/storage.py`
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.6 Atomic sequence numbering

- **Assigned checkpoint:** 1
- **Source of truth:** MVP `services/sequence.py`
- **Specific source files/evidence:** MVP `services/sequence.py`
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.7 Upload validation

- **Assigned checkpoint:** 2
- **Source of truth:** REB `services/upload_validation.py` → MVP `services/upload_validation.py`
- **Specific source files/evidence:** REB `services/upload_validation.py`
- **Evidence level:** FSV
- **Migration method:** EXT
- **Copy the complete donor file/module?** No
- **Required action:** Copy only the verified algorithm, enum, catalog, or narrowly scoped model/service behavior into a clean MVP service/model.
- **Do not bring over:** Copying donor routers, Job-domain models, or unrelated dependencies.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.8 Attachments / polymorphic links / shares

- **Assigned checkpoint:** 2
- **Source of truth:** MVP attachments + REB `file_links` + `document_links` + `document_shares`
- **Specific source files/evidence:** MVP files router; REB `routes/doculink.py` + `models/doculink.py`
- **Evidence level:** RV+FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.9 Settings framework

- **Assigned checkpoint:** 2
- **Source of truth:** REB `routes/settings.py` + `models/settings.py` → new MVP module `routers/settings.py`
- **Specific source files/evidence:** REB files
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.10 Notifications

- **Assigned checkpoint:** 2
- **Source of truth:** REB `routes/communications.py` (notification portion) → new MVP module
- **Specific source files/evidence:** REB `routes/communications.py` + `services/communications.py`
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.11 Email — outbound send

- **Assigned checkpoint:** 1
- **Source of truth:** MVP `services/email.py` (SendGrid live)
- **Specific source files/evidence:** MVP `services/email.py`, `routers/emails.py`
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.12 Email — inbound webhook (bounces, opens, clicks)

- **Assigned checkpoint:** 2
- **Source of truth:** REB `POST /communications/webhooks/sendgrid` → new MVP endpoint
- **Specific source files/evidence:** REB `routes/communications.py::ingest_sendgrid_webhook`
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.13 Email activity log

- **Assigned checkpoint:** 2
- **Source of truth:** REB `email_activity` collection → new MVP collection
- **Specific source files/evidence:** REB `routes/communications.py::create_email_activity_record`
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.14 Documents / DocuLink

- **Assigned checkpoint:** 6
- **Source of truth:** REB `routes/doculink.py` (rewire storage adapter to Emergent)
- **Specific source files/evidence:** REB `routes/doculink.py`, `services/doculink_storage.py`, `services/doculink_bridge.py`, `models/doculink.py`
- **Evidence level:** FSV
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.15 Signatures

- **Assigned checkpoint:** 6
- **Source of truth:** ORIG `routes/signatures.py` (rename job→order)
- **Specific source files/evidence:** ORIG `routes/signatures.py`, ORIG `services/object_storage.py`
- **Evidence level:** PSI (head only — full trace required during module preflight)
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.16 Approvals / Artwork proofs

- **Assigned checkpoint:** 6
- **Source of truth:** ORIG `routes/approvals.py` (dual-parent already)
- **Specific source files/evidence:** ORIG `routes/approvals.py`
- **Evidence level:** PSI (head only — full trace required during module preflight)
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.17 Quotes

- **Assigned checkpoint:** 3
- **Source of truth:** REB `routes/quotes.py` + `models/quotes.py` → merge into MVP `routers/quotes.py`
- **Specific source files/evidence:** REB files
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.18 Orders / Order Items

- **Assigned checkpoint:** 3
- **Source of truth:** REB `routes/orders.py` + `models/orders.py` + `services/order_schemas.py`
- **Specific source files/evidence:** REB files
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.19 `production_required` gate

- **Assigned checkpoint:** 3
- **Source of truth:** REB `services/order_item_rules.py`
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.20 Pricing snapshots on OrderItem/QuoteLineItem

- **Assigned checkpoint:** 3
- **Source of truth:** REB `services/pricing_engine.py` result → MVP OrderItem/QuoteLineItem field `latest_pricing_snapshot`
- **Specific source files/evidence:** REB `services/pricing_engine.py`, REB `routes/orders.py::save-pricing/override-pricing`, MVP `services/pricing.py`
- **Evidence level:** FSV+RV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.21 Pricing Foundation & Calculator

- **Assigned checkpoint:** 3
- **Source of truth:** MVP `services/pricing.py` + `starter_defaults.py` (already delivered)
- **Specific source files/evidence:** MVP files
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.22 Work Orders

- **Assigned checkpoint:** 5
- **Source of truth:** MVP `routers/work_orders.py` + REB `generate_work_order_draft` snapshot rule
- **Specific source files/evidence:** MVP + REB `routes/orders.py::generate_work_order_placeholder`
- **Evidence level:** RV+FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.23 Invoices — dual status

- **Assigned checkpoint:** 4
- **Source of truth:** FEB `services/invoice_service.py` + `models/jobs.py::InvoiceBase` (document_status + financial_status fields) → MVP `models/invoice.py`
- **Specific source files/evidence:** FEB files
- **Evidence level:** FSV
- **Migration method:** EXT
- **Copy the complete donor file/module?** No
- **Required action:** Copy only the verified algorithm, enum, catalog, or narrowly scoped model/service behavior into a clean MVP service/model.
- **Do not bring over:** Copying donor routers, Job-domain models, or unrelated dependencies.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.24 Payments — unified collection + void-with-reason + idempotency

- **Assigned checkpoint:** 4
- **Source of truth:** FEB `services/payment_service.py` + `models/payments.py` → new MVP module
- **Specific source files/evidence:** FEB files
- **Evidence level:** FSV
- **Migration method:** EXT
- **Copy the complete donor file/module?** No
- **Required action:** Copy only the verified algorithm, enum, catalog, or narrowly scoped model/service behavior into a clean MVP service/model.
- **Do not bring over:** Copying donor routers, Job-domain models, or unrelated dependencies.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.25 Stripe Connect

- **Assigned checkpoint:** 9
- **Source of truth:** ORIG + FEB `routes/stripe_connect.py` + FEB `services/payment_service.py::confirm_stripe_invoice_payment`
- **Specific source files/evidence:** ORIG + FEB files
- **Evidence level:** FSV
- **Migration method:** REF (safety-critical)
- **Copy the complete donor file/module?** No
- **Required action:** Complete security/financial preflight, then port only verified onboarding/reconciliation pieces behind MVP services.
- **Do not bring over:** Trusting client totals, unverified webhooks, or direct status mutation.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.26 Money representation policy

- **Assigned checkpoint:** 0
- **Source of truth:** Ratify MVP's existing "commerce in integer cents / configuration in float dollars" split (documented in the corrected Feature Readiness Matrix). Do NOT adopt FEB's float+cents boundary compromise.
- **Specific source files/evidence:** MVP `models/quote.py`, `models/order.py`, `models/invoice.py`, `models/work_order.py`, `services/pricing.py`, `services/starter_defaults.py`, `frontend/src/lib/format.js`, `frontend/src/components/forms/MoneyInput.jsx`; FEB `services/invoice_service.py::_derive_states` + `models/payments.py` for reference
- **Evidence level:** FSV
- **Migration method:** Decision (owner sign-off)
- **Copy the complete donor file/module?** Not applicable
- **Required action:** Record the approved policy in AGENT_INSTRUCTIONS and the master plan before dependent implementation.
- **Do not bring over:** Letting existing code silently decide policy.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.27 Customer portal

- **Assigned checkpoint:** 6
- **Source of truth:** Rebuild against MVP shared services using ORIG `routes/portal.py` as blueprint
- **Specific source files/evidence:** ORIG `routes/portal.py`
- **Evidence level:** PSI (head only — full trace required during module preflight)
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.28 Employee portal

- **Assigned checkpoint:** 8
- **Source of truth:** Rebuild against MVP shared services using ORIG + FEB `routes/employee_portal.py` as blueprint
- **Specific source files/evidence:** ORIG + FEB files
- **Evidence level:** RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.29 Wrap Lab

- **Assigned checkpoint:** 10
- **Source of truth:** REB `services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py`
- **Specific source files/evidence:** REB files
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.30 Webstores (Order Portal Manager)

- **Assigned checkpoint:** 9
- **Source of truth:** REB `ORDER_PORTAL_*_SPEC.md` (blueprint) + REB `routes/webstores.py` (capabilities scaffold) + ORIG `routes/webstores.py` (feature map only)
- **Specific source files/evidence:** REB + ORIG files
- **Evidence level:** SO+SV
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.31 Public storefront

- **Assigned checkpoint:** 9
- **Source of truth:** REB `ORDER_PORTAL_PUBLIC_STOREFRONT_SPEC.md` (spec) + ORIG `routes/public_website.py` (reference)
- **Specific source files/evidence:** REB + ORIG files
- **Evidence level:** SO+RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.32 Community Hub

- **Assigned checkpoint:** 12
- **Source of truth:** REB `routes/shared_systems.py::community/*`
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.33 AI tool catalog

- **Assigned checkpoint:** 11
- **Source of truth:** REB `routes/shared_systems.py::AI_TOOLS` (24 tools)
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** EXT
- **Copy the complete donor file/module?** No
- **Required action:** Copy only the verified algorithm, enum, catalog, or narrowly scoped model/service behavior into a clean MVP service/model.
- **Do not bring over:** Copying donor routers, Job-domain models, or unrelated dependencies.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.34 AI generation (real provider)

- **Assigned checkpoint:** 11
- **Source of truth:** New MVP module using EMERGENT_LLM_KEY + persist to `ai_responses` collection per REB shape
- **Specific source files/evidence:** REB `routes/shared_systems.py::POST /ai/generate` (stub) as target shape
- **Evidence level:** FSV
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.35 Subscription plans & fees catalog

- **Assigned checkpoint:** 13
- **Source of truth:** REB `services/billing_rules.py`
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** EXT
- **Copy the complete donor file/module?** No
- **Required action:** Copy only the verified algorithm, enum, catalog, or narrowly scoped model/service behavior into a clean MVP service/model.
- **Do not bring over:** Copying donor routers, Job-domain models, or unrelated dependencies.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.36 AI credits & top-up packs

- **Assigned checkpoint:** 11
- **Source of truth:** REB `services/billing_rules.py` (CREDIT_TOP_UP_PRODUCTS) + new MVP credit ledger collection
- **Specific source files/evidence:** REB file + new MVP collection
- **Evidence level:** FSV
- **Migration method:** EXT+RB
- **Copy the complete donor file/module?** No
- **Required action:** Extract the verified declarative rules/catalog, then build the missing permanent service and collections in MVP.
- **Do not bring over:** Copying the donor billing/AI module wholesale.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.37 Feature flags / entitlements

- **Assigned checkpoint:** 2
- **Source of truth:** REB `FeatureEntitlementRepository` (referenced by `webstore_service.py`) → new MVP module
- **Specific source files/evidence:** REB `services/webstore_service.py` + spec
- **Evidence level:** SS
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.38 Platform administration

- **Assigned checkpoint:** 12
- **Source of truth:** REB `routes/platform_admin.py`
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.39 Community bug / feature reports

- **Assigned checkpoint:** 12
- **Source of truth:** REB `routes/shared_systems.py::community` (already categorises `bug_report`, `feature_request`)
- **Specific source files/evidence:** REB file
- **Evidence level:** FSV
- **Migration method:** REF
- **Copy the complete donor file/module?** Usually no
- **Required action:** Port selected structures/functions or merge donor fields into the MVP module. Rewrite imports, tenant access, permissions, audit, and prohibited terminology.
- **Do not bring over:** Copying the complete donor module, preview helpers, legacy routes, or donor frontend.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.40 Global search

- **Assigned checkpoint:** 2
- **Source of truth:** No donor — build against MVP after core stable
- **Specific source files/evidence:** —
- **Evidence level:** —
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

## 7A.41 Background job runner

- **Assigned checkpoint:** 2
- **Source of truth:** No donor with production-grade scheduler; build against MVP shared services + REB `digest_scheduler.py` (from ORIG) as reference
- **Specific source files/evidence:** ORIG `services/digest_scheduler.py`, `services/workflow_engine.py`
- **Evidence level:** RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.42 SMS / MMS

- **Assigned checkpoint:** 12
- **Source of truth:** Build against MVP shared services using ORIG `routes/sms.py` + `services/sms_service.py` as reference
- **Specific source files/evidence:** ORIG files
- **Evidence level:** RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.43 Global reports & analytics

- **Assigned checkpoint:** 7
- **Source of truth:** Build against MVP shared services using ORIG `services/profit_analytics.py`, `services/productivity_query.py`, and various ORIG dashboards as reference
- **Specific source files/evidence:** ORIG files
- **Evidence level:** RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.44 Inventory / Vendors / Purchasing

- **Assigned checkpoint:** 7
- **Source of truth:** Build against MVP shared services using ORIG `routes/inventory.py` + `services/inventory_service.py` + REB `INVENTORY_PURCHASING_VENDOR_MANAGEMENT_REBUILD_DOC.md`
- **Specific source files/evidence:** ORIG + REB files
- **Evidence level:** RS+SO
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.45 Payroll / Time clock / Employees

- **Assigned checkpoint:** 8
- **Source of truth:** Build against MVP shared services using ORIG `routes/employees.py`, `services/timeclock_service.py` as reference
- **Specific source files/evidence:** ORIG files
- **Evidence level:** RS
- **Migration method:** RB
- **Copy the complete donor file/module?** No
- **Required action:** Create a fresh MVP module using donor behavior and specs as acceptance criteria.
- **Do not bring over:** Treating legacy code as production-ready or recreating a second shared system.
- **Required compatibility work:** Replace prohibited Job terminology; use MVP tenant dependencies, permissions, audit/activity services, object storage, IDs, error shapes, indexes, and frontend component standards.
- **Preflight status:** Required before implementation. The preflight must name exact functions/components that are reusable and exact code that is rejected.

## 7A.46 Frontend page / component library

- **Assigned checkpoint:** 1
- **Source of truth:** MVP `frontend/src/components/*` + `pages/*` (shadcn/ui + tailwind + design tokens)
- **Specific source files/evidence:** MVP files
- **Evidence level:** RV
- **Migration method:** KEEP
- **Copy the complete donor file/module?** No
- **Required action:** Preserve the existing MVP files. Add only the named fields/endpoints.
- **Do not bring over:** Replacing working MVP code or importing duplicate donor models.
- **Preflight status:** No broad donor investigation required beyond implementation-level dependency verification.

# PART 8 — MODULE-BY-MODULE MASTER MATRIX

Every module row from Final Scope & Decision Register Part 4 is preserved. Rows are grouped by Part-4 section for reference and each row shows: **Product area** / **Flyout destination** / **Scope** / **CR status** / **Add-on** / **Standalone** / **Current source** / **Evidence** / **Reuse** / **Preflight** / **Owner decision** / **Dependencies (foundations)** / **Assigned checkpoint** / **Tests** / **Docs** / **CR blocker**.

**Legend:** Scope = I/P/Pu/Pl. CR = REQ / REQ-DEP / ADD / OWNER / REMOVE. Tests columns: Unit / Integration / E2E / Cross-tenant / Perm / Portal / Money / Idempotency / Webhook / File / UI / Regression.

## 8.1 Foundation and Shared Systems (Part 4.1 — 31 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Authentication and Account Access | Control Center | Users & Permissions | I,P | REQ | MVP | RV+FSV | KEEP | N | — | (self) | CP1 | U,I,E2E,Perm | AuthDocs | Y |
| Tenants and Organizations | Control Center | Company Settings | I,Pl | REQ | MVP | RV | KEEP | N | — | Auth | CP1 | U,I,CT | TenantDocs | Y |
| Users | Control Center | Users & Permissions | I | REQ | MVP | RV | KEEP | N | — | Auth,Tenants | CP1 | U,I,Perm | UsersDocs | Y |
| Roles | Control Center | Users & Permissions | I | REQ | REB+MVP | FSV+RV | REF | N | Dec 2 | Users | CP1 | U,I,Perm | RolesDocs | Y |
| Permissions | Control Center | Users & Permissions | I | REQ | REB+MVP | FSV | REF (module-based) | N | Dec 2 | Roles | CP1 | U,I,Perm,CT | PermDocs | Y |
| Application Shell | All | Home | I,P | REQ | MVP | RV | KEEP | N | — | Auth | CP1 | UI | ShellDocs | Y |
| Navigation (sidebar+flyouts) | All | (all) | I,P | REQ | New | New | New | N | Dec 24 (LOCKED) | Shell | CP1 | UI,Regression | NavDocs | Y |
| Shared UI Components | All | — | I,P | REQ | MVP | RV | KEEP+EXTEND | N | — | Shell | CP1 | UI | ComponentDocs | Y |
| Settings Framework | Control Center | Company Settings | I | REQ | REB | FSV | REF | N | — | Auth,Tenants,Audit | CP2 | U,I,CT,Perm | SettingsDocs | Y |
| Audit Log / Activity History | Control Center | Data & Security | I,Pl | REQ | MVP+REB | RV+FSV | KEEP+EXTEND | N | — | Auth | CP1(base)+CP2(extend) | U,I,CT | AuditDocs | Y |
| Notifications (in-app) | Control Center | Integrations | I,P | REQ | REB | FSV | REF | N | — | Auth,Tenants,Audit | CP2 | U,I,CT,Perm | NotifyDocs | Y |
| Email (SendGrid outbound) | Control Center | Integrations | I,P | REQ | MVP | RV | KEEP | N | — | Auth | CP1 | U,I,CT | EmailDocs | Y |
| Email Activity Log + Webhook | Control Center | Integrations | I,Pl | REQ | REB | FSV | REF | N | Dec 4 | Email,Webhook infra | CP2 | U,I,Webhook,CT | EmailWebhookDocs | Y |
| SMS/MMS | Control Center | Integrations | I,P | OWNER (Dec 27) | ORIG | RS | REBUILD | Y | Dec 19,Dec 27 | Notifications,Portal Auth | CP9 (if a) | U,I,Webhook,CT | SmsDocs | Depends on Dec 27 |
| Internal Messaging | Team & Workflow | Messages & Notes | I | REQ-DEP | ORIG+REB | RS+FSV | REBUILD | N | — | Users,Tenants,Notifications | CP6 | U,I,CT,Perm | MessagingDocs | Y |
| Object Storage | Control Center | Data & Security | I,P | REQ | MVP | RV | KEEP | N | — | Auth | CP1 | U,I,File,CT | StorageDocs | Y |
| File Uploads | Shop Ops + others | Asset Library | I,P | REQ | MVP | RV | KEEP+EXTEND | N | — | Storage | CP1 | U,I,File,CT | UploadDocs | Y |
| Upload Validation | Shared | (implicit) | I,P | REQ | REB | FSV | EXTRACT | N | — | File Uploads | CP2 | U,I,File | UploadValDocs | Y |
| Attachments (polymorphic) | Shared | (implicit) | I,P | REQ | MVP+REB | RV+FSV | REF | N | — | Storage,File Uploads | CP2 | U,I,CT | AttachDocs | Y |
| Forms | Shop Ops (surface: public) | (external) | I,Pu | REQ | ORIG | RS | REBUILD | Y | — | Attachments,Storage,Rate limit | CP4 | U,I,E2E,CT | FormsDocs | Y |
| Questionnaires | Shop Ops (surface: public + portal) | (external + Orders) | I,Pu | REQ | ORIG+REB | RS+SO | REBUILD | Y | — | Forms,Attachments | CP4 | U,I,E2E,CT | QuestionnaireDocs | Y |
| Templates (doc + email) | Control Center | Company Settings | I | REQ | REB+ORIG | FSV+RS | REF | N | — | Storage,Email | CP4 | U,I,CT | TemplatesDocs | Y |
| Signatures | Shop Ops / Wrap Lab / Webstores | (workflow) | I,P,Pu | REQ | ORIG | PSI | REF + preflight | Y | Dec 8 | Portal Auth,Storage,Public tokens | CP4 | U,I,E2E,CT,Portal | SignaturesDocs | Y |
| Global Search | Cross-cutting | (bar) | I | REQ-DEP | New | New | REBUILD | N | Explicit decision required only if commercially deferred | Modules with search | PC8 / EC12 | U,I,CT,Perm | SearchDocs | Y unless owner approves later commercial timing |
| Background Jobs / Scheduler | Shared | — | I,Pl | REQ-DEP | ORIG+New | RS+New | REBUILD | N | — | Auth,Tenants,Audit | CP2 (scaffold), CP5/CP8 (jobs) | U,I | JobsDocs | Y |
| Webhook Infrastructure | Shared | — | I,Pl | REQ | REB+FEB | FSV | REBUILD | N | Dec 4 | Auth,Audit,Idempotency utility | CP2 | U,I,Webhook,CT | WebhookDocs | Y |
| Error Logging | Shared | Data & Security | I | REQ | MVP | RV | KEEP | N | — | — | CP1 | U | ErrLogDocs | Y |
| Monitoring | Shared | Data & Security | I,Pl | REQ | New | New | New | N | — | Deploy | CP9 | I | MonitoringDocs | Y |
| Feature Flags / Entitlements | Control Center | Feature Access | I,Pl | REQ | REB+SS | FSV+SS | REBUILD | N | — | Auth,Tenants,Subscriptions | CP2 (scaffold), CP8 (wire) | U,I,CT,Perm | EntitlementDocs | Y |
| Subscription Access | Control Center | Subscriptions & AI Credits | I,Pl | REQ | REB | FSV | EXTRACT + REBUILD | Y | Dec 10,11,15,16,17,26 | Stripe Core,Entitlements | CP8 | U,I,Webhook,Money,Idempotency | SubDocs | Y |
| AI Credit Ledger | Control Center + Creative Studio | Subscriptions & AI Credits + Creative Studio | I,Pl | REQ-DEP | REB+ORIG | FSV+RS | REBUILD | Y | Dec 12,13,14,18 | Subscriptions,AI Provider | CP8 | U,I,CT,Money | AICreditDocs | Y |

## 8.2 Shop Operations (Part 4.2 — 33 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Customer CRM | Shop Ops | Customers | I,P | REQ | MVP | RV | KEEP + EXTEND (portal) | N | — | Auth,Tenants | CP3 (extend for portal) | U,I,CT,Perm | CustomerDocs | Y |
| Customer Detail | Shop Ops | Customers | I,P | REQ | MVP | RV | KEEP | N | — | Customer CRM | CP3 | U,I,CT,Perm | CustomerDocs | Y |
| Communication History | Shop Ops | Customers | I | REQ | REB+MVP | FSV+RV | REF | N | — | Email Activity,Notifications | CP3 | U,I,CT | CommHistoryDocs | Y |
| Quotes | Shop Ops | Quotes | I,P | REQ | REB | FSV | REF | N | Dec 1 | Customer,Pricing | CP3 | U,I,E2E,Money,CT,Perm | QuoteDocs | Y |
| Quote Line Items | Shop Ops | Quotes | I | REQ | REB | FSV | REF | N | Dec 1 | Quotes | CP3 | U,I,Money | QuoteLineItemDocs | Y |
| Quote Approval | Shop Ops + Portal | Quotes + Customer Portal | I,P | REQ | REB | FSV | REF | N | Dec 8 | Portal Auth,Signatures | CP4 | U,I,E2E,Portal | QuoteApprovalDocs | Y |
| Quote-to-Order Conversion | Shop Ops | Quotes → Orders | I | REQ | MVP+REB | RV+FSV | KEEP + EXTEND | N | — | Quotes,Orders | CP3 | U,I,Idempotency,CT | QOConversionDocs | Y |
| Orders | Shop Ops | Orders | I,P | REQ | REB | FSV | REF (rich item schema) | N | Dec 1 | Customer,Pricing,Sequences | CP3 | U,I,E2E,Money,CT,Perm | OrderDocs | Y |
| Order Items (40+ fields) | Shop Ops | Orders | I | REQ | REB | FSV | REF | N | Dec 1 | Orders,Order Item Rules | CP3 | U,I,Money | OrderItemDocs | Y |
| Order Pricing Snapshots | Shop Ops | Orders | I | REQ | REB | FSV | REF | N | Dec 1 | Pricing,Order Items | CP3 | U,I,Money | PricingSnapshotDocs | Y |
| `production_required` gate | Shop Ops | Orders → Production | I | REQ | REB | FSV | REF (order_item_rules.py) | N | — | Order Items | CP3 | U,I | ProductionRequiredDocs | Y |
| Invoices (dual status) | Shop Ops | Orders (invoice section) | I,P | REQ | FEB | FSV | EXTRACT | N | Dec 1,9 | Orders,Sequences,Tax,Payments | CP3 | U,I,E2E,Money,CT,Perm | InvoiceDocs | Y |
| Payments (unified) | Shop Ops | Orders (payments) | I,P | REQ | FEB | FSV | EXTRACT | N | Dec 1,15 | Invoices,Stripe Core | CP3 | U,I,E2E,Money,Idempotency,Webhook,CT,Perm | PaymentDocs | Y |
| Payment History | Shop Ops + Portal | Orders / Customer Portal | I,P | REQ | FEB | FSV | EXTRACT | N | — | Payments | CP3 | U,I,CT,Portal | PaymentHistoryDocs | Y |
| Production | Shop Ops | Production | I | REQ | MVP+REB | RV+FSV | KEEP+REF | N | — | Work Orders | CP3 | U,I,CT,Perm | ProductionDocs | Y |
| Work Orders | Shop Ops | Production | I | REQ | MVP+REB | RV+FSV | KEEP+REWORK (production_required only) | N | — | Order Items | CP3 | U,I,CT | WorkOrderDocs | Y |
| Work Order Summaries | Shop Ops | Production | I | REQ | MVP+ORIG | RV+RS | KEEP+REF | N | — | Work Orders | CP3 | U,I | WorkOrderSummaryDocs | Y |
| Production Board | Shop Ops | Production | I | REQ | REB+ORIG | SS+RS | REBUILD | Y | — | Work Orders | CP3 | U,I,UI | ProductionBoardDocs | Y |
| Proofs | Shop Ops + Portal | Orders → Proofs (workflow) | I,P | REQ | ORIG | PSI | REF + preflight | Y | — | DocuLink,Portal Auth | CP4 | U,I,E2E,Portal,CT | ProofDocs | Y |
| Artwork Approvals | Shop Ops + Portal | Orders → Approvals (workflow) | I,P | REQ | ORIG | PSI | REF + preflight | Y | — | Proofs,Signatures | CP4 | U,I,E2E,Portal | ApprovalDocs | Y |
| Asset Library (DocuLink) | Shop Ops | Asset Library | I,P | REQ | REB | FSV | EXTRACT + REBUILD | N | — | Storage,Attachments,Templates | CP4 | U,I,File,CT,Perm | AssetLibraryDocs | Y |
| Document Templates | Shop Ops | Asset Library | I | REQ | REB+ORIG | FSV+RS | REF | N | — | Templates,DocuLink | CP4 | U,I,CT | DocTemplatesDocs | Y |
| Shop Schedule | Shop Ops | Shop Schedule | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Calendar,Orders,Work Orders,Employees | CP3 (basic)+CP6 (rich) | U,I,UI,CT | ShopScheduleDocs | Y |
| Inventory & Purchasing (flyout wrapper) | Shop Ops | Inventory & Purchasing | I | REQ | (nav) | (nav) | (nav) | N | — | Inventory,Vendors,Purchasing | CP5 | UI,Regression | InvPurchDocs | Y |
| Inventory | Shop Ops (under I&P) | Inventory & Purchasing | I | REQ | ORIG+REB | RS+SO | REBUILD | Y | — | Auth,Tenants,Audit | CP5 | U,I,CT,Perm | InventoryDocs | Y |
| Vendors | Shop Ops (under I&P) | Inventory & Purchasing | I | REQ | ORIG | RS | REBUILD | Y | — | Auth,Tenants,Audit | CP5 | U,I,CT | VendorsDocs | Y |
| Purchasing | Shop Ops (under I&P) | Inventory & Purchasing | I | REQ | ORIG | RS | REBUILD | Y | — | Vendors,Inventory,Payments,Expenses | CP5 | U,I,CT,Money | PurchasingDocs | Y |
| Webstores | Shop Ops | Webstores | I,P,Pu | ADD | REB+ORIG | FSV+SO+RS | REBUILD | Y | Dec 6,15 | Entitlements,DocuLink,Stripe Connect,Portal Auth | CP7 | U,I,E2E,CT,Money,Perm,Portal | WebstoreDocs | Y (Webstore GA) |
| Webstore Setup Wizard | Shop Ops | Webstores | I,P | ADD | REB | SO | REBUILD | Y | — | Webstores | CP7 | U,I,E2E,UI | WebstoreWizardDocs | Y (Webstore GA) |
| Webstore Products | Shop Ops + Portal | Webstores | I,P,Pu | ADD | ORIG | RS | REBUILD | Y | — | Webstores,DocuLink | CP7 | U,I,CT,Perm | WebstoreProductDocs | Y (Webstore GA) |
| Product Variants | Shop Ops + Portal | Webstores | I,P,Pu | ADD | ORIG | RS | REBUILD | Y | — | Webstore Products | CP7 | U,I,Perm | ProductVariantDocs | Y (Webstore GA) |
| Webstore Orders | Shop Ops + Portal | Webstores | I,P,Pu | ADD | ORIG | RS | REBUILD | Y | — | Webstores,Orders,Payments,Stripe Connect | CP7 | U,I,E2E,CT,Money,Idempotency,Webhook | WebstoreOrderDocs | Y (Webstore GA) |
| Stripe Connect | Shop Ops (integration) | Webstores | I,Pl | ADD | FEB+ORIG | FSV+RS | REBUILD (extract confirm pattern) | Y | Dec 15 | Stripe Core | CP7 | U,I,Webhook,Money,Idempotency,CT | StripeConnectDocs | Y (Webstore GA) |
| Payouts | Shop Ops | Webstores | I,Pl | ADD | FEB+ORIG | FSV+RS | REBUILD | Y | Dec 15 | Stripe Connect | CP7 | U,I,Money,Idempotency,Webhook | PayoutDocs | Y (Webstore GA) |
| Wrap Lab / Wrap Command Center | Shop Ops | Wrap Lab | I,P | ADD | REB+ORIG | FSV+RS | REF (workflow engine + models + routes) | Y | Dec 7 | DocuLink,Signatures,Approvals,Portal Auth,Orders | CP7 | U,I,E2E,CT,Portal | WrapLabDocs | Y (Wrap GA) |

## 8.3 Business & Finance (Part 4.3 — 8 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Finance Dashboard | B&F | Overview | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Payments,Invoices,Expenses | CP5 | U,I,UI,CT | FinDashDocs | Y |
| Financials (revenue, A/R, refunds/voids, GP, NP, margins, cash-flow, per-channel revenue, tax collected, payment-method breakdown) | B&F | Financials | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Payments,Invoices,Expenses,Taxes | CP5 | U,I,Money,CT | FinancialsDocs | Y |
| Sales | B&F | Sales | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Orders,Payments | CP5 | U,I,CT | SalesDocs | Y |
| Expenses | B&F | Expenses | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Purchasing,Payments | CP5 | U,I,CT | ExpenseDocs | Y |
| Taxes | B&F | Taxes | I | REQ | New | New | REBUILD (provider boundary) | Y | Dec 9 | Invoices,Settings | CP5 | U,I,Money,CT | TaxDocs | Y |
| Reports | B&F | Reports | I | REQ | ORIG+New | RS+New | REBUILD | Y | Dec 20 | All modules with data | CP5 | U,I,CT,Perm | ReportsDocs | Y |
| Custom Report Builder | B&F | Reports | I | REQ-DEP | ORIG+New | RS+New | REBUILD (staged) | Y | Dec 20 | Reports catalog | CP5 | U,I,CT,Perm | CustomReportDocs | Y |
| Business Analytics | B&F | Business Analytics | I,Pl | REQ | ORIG+New | RS+New | REBUILD | Y | — | Reports,Finance | CP5 | U,I,CT | AnalyticsDocs | Y |

## 8.4 Team & Workflow (Part 4.4 — 17 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Team Dashboard | T&W | Overview | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Users,Tasks,Time Clock | CP6 | U,I,UI,CT | TeamDashDocs | Y |
| Employees | T&W | Employees | I,P | REQ | ORIG+FEB | RS | REBUILD | Y | — | Users,Auth | CP6 | U,I,CT,Perm | EmployeeDocs | Y |
| Tasks | T&W | Tasks & Kanban | I | REQ | ORIG+FEB | RS | REBUILD | Y | — | Users,Orders (task-on-order) | CP6 | U,I,CT | TasksDocs | Y |
| Kanban | T&W | Tasks & Kanban | I | REQ | ORIG | RS | REBUILD | Y | — | Tasks | CP6 | U,I,UI | KanbanDocs | Y |
| Team Schedule (shifts, availability, TO) | T&W | Team Schedule | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | Employees,Calendar | CP6 | U,I,UI,CT | TeamScheduleDocs | Y |
| Calendar | T&W | Team Schedule | I | REQ | ORIG | RS | REBUILD | Y | — | Employees,Team Schedule | CP6 | U,I,UI | CalendarDocs | Y |
| Appointments | T&W | Team Schedule / Shop Schedule shared surface | I,P | REQ | ORIG | RS | REBUILD | Y | — | Calendar,Customers | CP6 | U,I,CT,Portal | AppointmentDocs | Y |
| Install Scheduling | Shop Ops | Shop Schedule | I | REQ | ORIG | RS | REBUILD | Y | — | Orders,Team Schedule | CP6 | U,I,CT | InstallSchedDocs | Y |
| Production Scheduling | Shop Ops | Shop Schedule / Production | I | REQ | ORIG | RS | REBUILD | Y | — | Work Orders,Team Schedule | CP6 | U,I,CT | ProdSchedDocs | Y |
| Time Clock | T&W + Employee Portal | Time Clock | I,P | REQ | ORIG+FEB | RS | REBUILD | Y | — | Employees,Employee Portal | CP6 | U,I,CT,Portal | TimeClockDocs | Y |
| Timesheets | T&W + Employee Portal | Timesheets | I,P | REQ | ORIG+FEB | RS | REBUILD | Y | — | Time Clock | CP6 | U,I,CT,Portal | TimesheetsDocs | Y |
| Payroll (pay periods, calc, advances, adjustments, carryover, payments, history, exports) | T&W | Payroll | I,P | REQ | ORIG+FEB | RS | REBUILD | Y | Dec 23 | Timesheets,Employees | CP6 | U,I,Money,CT | PayrollDocs | Y |
| Employee Scheduling | T&W | Team Schedule | I | REQ | ORIG | RS | REBUILD | Y | — | Employees,Team Schedule | CP6 | U,I,CT | EmployeeSchedDocs | Y |
| Messages & Notes | T&W | Messages & Notes | I | REQ | REB+ORIG | FSV+RS | REBUILD (unify internal notes + comm) | N | — | Notifications,Users | CP6 | U,I,CT | MessagesDocs | Y |
| Announcements | T&W | Announcements | I | REQ | ORIG | RS | REBUILD | Y | — | Notifications | CP6 | U,I,CT | AnnouncementsDocs | Y |
| Reminders | T&W | Team Schedule | I | REQ-DEP | New | New | New | N | — | Notifications | CP6 | U,I | RemindersDocs | Y |
| Employee Portal | T&W (admin) + Portal | Employee Portal | P | REQ | ORIG+FEB+New | RS+New | REBUILD | Y | Dec 23 | Portal Auth,Time Clock,Timesheets,Payroll | CP6 | U,I,E2E,CT,Portal,Perm | EmployeePortalDocs | Y |

## 8.5 Creative Studio and AI (Part 4.5 — 15 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AI Tools Grid (24 tools) | Creative Studio | (all sub-flyouts) | I | REQ | REB | FSV | EXTRACT (catalog) + REBUILD (execution) | Y | Dec 12,13,14,18 | AI Credit Ledger,AI Provider | CP8 | U,I,Money,CT,Perm | AIToolsDocs | Y |
| AI Assistant | Creative Studio | AI Assistant | I | REQ | ORIG+REB | RS+FSV | REBUILD | Y | Dec 18 | AI Credit Ledger,AI Provider | CP8 | U,I,E2E,CT | AIAssistDocs | Y |
| Image Tools (catalog slice) | Creative Studio | Image Tools | I | REQ | REB+ORIG | FSV+RS | REBUILD (curated slice of AI Tools) | Y | Dec 18 | AI Tools Grid | CP8 | U,I,UI | ImageToolsDocs | Y |
| Design Tools (catalog slice) | Creative Studio | Design Tools | I | REQ | REB+ORIG | FSV+RS | REBUILD (curated slice) | Y | Dec 18 | AI Tools Grid | CP8 | U,I,UI | DesignToolsDocs | Y |
| Writing Tools (catalog slice) | Creative Studio | Writing Tools | I | REQ | REB+ORIG | FSV+RS | REBUILD (curated slice) | Y | Dec 18 | AI Tools Grid | CP8 | U,I,UI | WritingToolsDocs | Y |
| Prompt Library | Creative Studio | Prompt Library | I | REQ | ORIG | RS | REBUILD | Y | — | AI Tools Grid,Templates | CP8 | U,I,CT | PromptLibDocs | Y |
| Artwork Workspace | Creative Studio | Artwork Workspace | I | REQ | ORIG+New | RS+New | REBUILD | Y | — | AI Tools,Storage | CP8 | U,I,UI | ArtworkDocs | Y |
| Generated Assets (with `requires_review`) | Creative Studio + Portal | Generated Assets | I,P | REQ | REB | FSV | REF | N | — | DocuLink | CP8 | U,I,File,Perm | GeneratedAssetsDocs | Y |
| AI History | Creative Studio + Platform | AI History | I,Pl | REQ | REB | FSV | REF | N | — | AI Credit Ledger | CP8 | U,I,CT | AIHistoryDocs | Y |
| AI Generated Files | Creative Studio + Portal | Generated Assets | I,P | REQ | REB | FSV | REF | N | — | DocuLink | CP8 | U,I,File | AIGenFilesDocs | Y |
| AI Generated Documents | Creative Studio + Portal | Generated Assets / Asset Library | I,P | REQ | REB | FSV | REF | N | — | DocuLink | CP8 | U,I,File | AIGenDocsDocs | Y |
| AI Context Retrieval | Creative Studio (internal) | (internal) | I | REQ-DEP | ORIG | RS | REBUILD | Y | Dec 18 | AI Provider | CP8 | U,I | AIContextDocs | Y |
| AI Result Storage | Creative Studio + Portal | (internal) | I,P | REQ | REB | FSV | REF | N | — | DocuLink | CP8 | U,I | AIResultDocs | Y |
| Creative Studio Workspace | Creative Studio | Studio Overview | I | REQ | ORIG | RS | REBUILD | Y | — | AI Tools,AI Assistant | CP8 | U,I,UI | StudioWorkspaceDocs | Y |
| Artwork Assets | Creative Studio | Artwork Workspace / Generated Assets | I | REQ | New | New | New | N | — | Storage | CP8 | U,I | ArtworkAssetsDocs | Y |

## 8.6 Control Center — tenant configuration (Part 4.6 — 16 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Company Settings | Control Center | Company Settings | I | REQ | New | New | New | N | — | Settings Framework | CP2 | U,I,CT | CompanySettingsDocs | Y |
| Users & Permissions (surface) | Control Center | Users & Permissions | I | REQ | MVP+New | RV+New | KEEP+EXTEND | N | Dec 2 | Users,Roles,Permissions | CP2 | U,I,Perm,CT | UsersPermSurfaceDocs | Y |
| Integrations (surface) | Control Center | Integrations | I | REQ | MVP+New | RV+New | KEEP+EXTEND | N | Dec 4,9,18,19 | All integrations | CP2 | U,I,CT | IntegrationsDocs | Y |
| Portals (settings) | Control Center | Portals | I | REQ | New | New | REBUILD | N | Dec 8 | Portal Auth,Webstores,Wrap Lab | CP2 (scaffold), CP4/6/7 (extend) | U,I,CT | PortalSettingsDocs | Y |
| Feature Access | Control Center | Feature Access | I | REQ | REB+New | FSV+New | REBUILD | N | — | Feature Entitlements | CP2 (scaffold), CP8 (wire) | U,I,CT | FeatureAccessDocs | Y |
| Data & Security | Control Center | Data & Security | I | REQ | MVP+New | RV+New | KEEP+EXTEND | N | — | Audit,Storage,Auth | CP2 | U,I,CT | DataSecurityDocs | Y |
| Pricing Defaults — Foundation | Control Center | Pricing Defaults | I | REQ | MVP | RV | KEEP | N | — | Settings | CP1 | U,I,CT | PricingFoundationDocs | Y |
| Pricing Defaults — Setup | Control Center | Pricing Defaults | I | REQ | MVP | RV | KEEP | N | — | Pricing Foundation | CP1 | U,I,CT | PricingSetupDocs | Y |
| Pricing Defaults — Shop Rate | Control Center | Pricing Defaults | I | REQ | MVP | RV | KEEP | N | — | Pricing Setup | CP1 | U,I | ShopRateDocs | Y |
| Pricing Defaults — Labor Rates | Control Center | Pricing Defaults | I | REQ | MVP | RV | KEEP | N | — | Pricing Setup | CP1 | U,I | LaborRatesDocs | Y |
| Pricing Defaults — Material Pricing | Control Center | Pricing Defaults | I | REQ | ORIG+REB | RS+FSV | REBUILD (tenant catalog editor) | N | — | Pricing Foundation | CP3 (extend) | U,I,CT | MaterialPricingDocs | Y |
| Pricing Defaults — Calculators (9 categories) | Control Center | Pricing Defaults (config); operational shortcut inside Quotes/Orders | I | REQ | MVP | RV | KEEP | N | — | Pricing Foundation | CP1 | U,I,Money,CT | CalculatorsDocs | Y |
| Pricing Defaults — Administration | Control Center | Pricing Defaults | I | REQ | MVP | RV | KEEP | N | — | Pricing Foundation | CP1 | U,I,Perm | PricingAdminDocs | Y |
| Subscriptions & AI Credits — Tenant Subscription | Control Center | Subscriptions & AI Credits | I,Pl | REQ | REB | FSV | REBUILD | Y | Dec 10,11,15,16,26 | Stripe Core,Entitlements | CP8 | U,I,Webhook,Money,Idempotency,CT | TenantSubDocs | Y |
| Subscriptions & AI Credits — Tenant AI Credits | Control Center | Subscriptions & AI Credits | I,Pl | REQ-DEP | REB | FSV | REBUILD | Y | Dec 12,13,14 | AI Credit Ledger,Stripe Core | CP8 | U,I,Money,CT | TenantCreditDocs | Y |
| Platform Governance | Control Center | Platform Governance | Pl | REQ | REB | FSV | REF | Y | Dec 21 | Platform Admin | CP8 | U,I,CT,Perm | PlatformGovDocs | Y |

## 8.7 Platform and Support (Part 4.7 — 14 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onboarding | Help & Community | Onboarding | I | REQ | ORIG | RS | REBUILD | N | — | Notifications,Docs | CP8 | U,I,UI | OnboardingDocs | Y |
| Help Center / Documentation | Help & Community + public | Help Center / Documentation | I,Pu | REQ | FEB+ORIG | RS | REBUILD | N | — | (docs) | CP8 | UI | HelpCenterDocs | Y |
| Community Hub | Help & Community | Community | I | REQ | REB | FSV | REF | N | — | Users,Notifications | CP8 | U,I,CT,Perm | CommunityDocs | Y |
| Bug Reports (Community-backed, direct flyout) | Help & Community | Bug Reports | I,Pl | REQ | REB | FSV | REF | N | — | Community | CP8 | U,I | BugReportsDocs | Y |
| Feature Requests (Community-backed, direct flyout) | Help & Community | Feature Requests | I,Pl | REQ | REB | FSV | REF | N | — | Community | CP8 | U,I | FeatureRequestsDocs | Y |
| Contact Support | Help & Community + public | Contact Support | I,Pu | REQ | New | New | New | N | — | Email,Tickets | CP8 | U,I | SupportDocs | Y |
| What's New | Help & Community | What's New | I | REQ | New | New | New | N | — | (release notes) | CP8/CP9 | U,I | WhatsNewDocs | Y |
| Platform Admin Dashboard | Control Center (Platform Governance) | Platform Governance | Pl | REQ | REB+ORIG | FSV+RS | REF + preflight | Y | Dec 21 | Auth,Tenants,Audit | CP8 | U,I,CT,Perm | PlatformAdminDocs | Y |
| Platform Tenant Management | Control Center (Platform Governance) | Platform Governance | Pl | REQ | REB | FSV | REF | Y | Dec 21 | Platform Admin | CP8 | U,I,CT,Perm | PlatformTenantDocs | Y |
| Platform Analytics | Control Center (Platform Governance) | Platform Governance | Pl | REQ | ORIG+New | RS+New | REBUILD | Y | — | Reports | CP8 | U,I,CT | PlatformAnalyticsDocs | Y |
| Platform Audit Logs | Control Center (Platform Governance) | Platform Governance | Pl | REQ | MVP+REB | RV+FSV | KEEP+EXTEND | N | — | Audit | CP1(base)+CP8(surface) | U,I,CT | PlatformAuditDocs | Y |
| Platform Email & Broadcasts | Control Center (Platform Governance) | Platform Governance | Pl | REQ | ORIG | RS | REBUILD | Y | — | Email | CP8 | U,I,CT | PlatformEmailDocs | Y |
| Subscription Administration (platform) | Control Center (Platform Governance) | Platform Governance | Pl | REQ | REB | FSV | REBUILD | Y | Dec 10,11,15,26 | Subscriptions | CP8 | U,I,CT,Money | SubAdminDocs | Y |
| AI Credit Administration (platform) | Control Center (Platform Governance) | Platform Governance | Pl | REQ | REB | FSV | REBUILD | Y | Dec 12,13,14 | AI Credit Ledger | CP8 | U,I,CT | AICreditAdminDocs | Y |

## 8.8 Portals and Public Systems (Part 4.8 — 13 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Customer Portal | Portal | (external) | P | REQ | ORIG+New | PSI+New | REBUILD | Y | Dec 8,22 | Portal Auth,Orders,Invoices,Payments,Proofs,Approvals,Stripe Core | CP4 | U,I,E2E,Portal,CT | CustomerPortalDocs | Y |
| Employee Portal | Portal | (external) | P | REQ | ORIG+FEB+New | RS+New | REBUILD | Y | Dec 8,23 | Portal Auth,Time Clock,Timesheets,Payroll | CP6 | U,I,E2E,Portal,CT | EmployeePortalDocs | Y |
| Webstore Owner Portal | Portal | (external) | P | ADD | ORIG+REB | RS+SO | REBUILD | Y | Dec 6,8 | Portal Auth,Webstores,Stripe Connect,Payouts | CP7 | U,I,E2E,Portal,CT | WebstoreOwnerPortalDocs | Y (Webstore GA) |
| Webstore Manager Portal | Portal | (external) | P | ADD | REB | SO | REBUILD | Y | Dec 6,8 | Portal Auth,Webstore Owner Portal | CP7 | U,I,E2E,Portal,CT | WebstoreManagerPortalDocs | Y (Webstore GA) |
| Public Storefront | Public | (public) | Pu | ADD | ORIG+REB | RS+SO | REBUILD | Y | Dec 6 | Webstores,Stripe Connect | CP7 | U,I,E2E,CT | StorefrontDocs | Y (Webstore GA) |
| Public Forms | Public | (public) | Pu | REQ | ORIG | RS | REBUILD | Y | — | Forms,Rate limit,Captcha | CP4 | U,I,E2E,CT | PublicFormsDocs | Y |
| Public Questionnaires | Public | (public) | Pu | REQ | ORIG+REB | RS+SO | REBUILD | Y | — | Questionnaires,Rate limit,Captcha | CP4 | U,I,E2E,CT | PublicQuestDocs | Y |
| Public Quote Requests | Public | (public) | Pu | REQ | ORIG | RS | REBUILD | Y | — | Public Forms,Leads,Quotes | CP4 | U,I,E2E,CT | PublicQuoteDocs | Y |
| Public Customer Intake | Public | (public) | Pu | REQ | ORIG | RS | REBUILD | Y | — | Public Forms,Customers | CP4 | U,I,E2E,CT | PublicIntakeDocs | Y |
| Public Proof Approval | Public | (public) | Pu | REQ | ORIG | PSI | REBUILD | Y | Dec 8 | Public tokens,Proofs,Approvals | CP4 | U,I,E2E,Portal,CT | PublicProofDocs | Y |
| Public Signature Pages | Public | (public) | Pu | REQ | ORIG | PSI | REBUILD | Y | Dec 8 | Public tokens,Signatures | CP4 | U,I,E2E,Portal,CT | PublicSigDocs | Y |
| Marketing Website | Public | (public) | Pu | REQ | ORIG+FEB | RS | REBUILD | Y | — | (static) | CP8/CP9 | UI | MarketingDocs | Y |
| Public Pricing and Plan Selection | Public | (public) | Pu | REQ | ORIG+FEB | RS | REBUILD | Y | Dec 10,11 | Subscriptions | CP8 | UI | PublicPricingDocs | Y |

## 8.9 Commercial and Billing Systems (Part 4.9 — 5 modules)

| Module | Area | Flyout | Sc | CR | Src | Ev | Reuse | Pref | OD | Dep | CP | Tests | Docs | CR blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Subscription Billing | Control Center + Platform | Subscriptions & AI Credits + Platform Governance | I,Pl | REQ | REB | FSV | REBUILD | Y | Dec 10,11,15,16,26 | Stripe Core,Entitlements,Subscriptions | CP8 | U,I,Webhook,Money,Idempotency,CT | SubBillingDocs | Y |
| Add-on Purchases | Control Center + Platform | Subscriptions & AI Credits | I,Pl | REQ | REB | FSV | REBUILD | Y | Dec 6,7,10 | Subscription Billing | CP8 | U,I,Money,Idempotency | AddonDocs | Y |
| AI Credit Purchases | Control Center | Subscriptions & AI Credits | I,Pl | REQ-DEP | REB | FSV | REBUILD | Y | Dec 12,13,14 | AI Credit Ledger,Stripe Core | CP8 | U,I,Money,Idempotency | AICreditPurchaseDocs | Y |
| Transaction Fees | Payments + Payouts | (backend) | I,Pl | ADD | REB | FSV | REBUILD | Y | Dec 15 | Payments,Payouts | CP7/CP8 | U,I,Money | TxnFeeDocs | Y |
| Founders Promo | Control Center + Platform | Subscriptions & AI Credits | I,Pl | REQ | REB | FSV | REBUILD (reconcile "25 redemptions" candidate vs "first 50" direction) | Y | Dec 10,11,15 | Subscription Billing | CP8 | U,I,Money | FoundersPromoDocs | Y |

---

# PART 9 — MODULE PREFLIGHT SCHEDULE

Prompt 4 schedules the preflights. Implementation prompts execute them.

Preflight output convention: every preflight produces a document at `/app/preflight/<module>_preflight.md` with the sections `Purpose / Source Files Inspected / Models / Routes / Collections / Frontend Surfaces / Integrations / Permission Behavior / Tenant Safety Risks / Reuse Recommendation / Cross-references / Test Expectations / Open Questions`.

| # | Preflight | Why required | Source repo | Donor files (inspect) | Questions to answer | Deps to trace | Models to identify | Routes to identify | Collections to identify | FE surfaces | Integrations | Permission behavior | Tenant safety risks | Expected reuse | Blocking checkpoint |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PF1 | Customer Portal | ORIG portal 2195 lines; must sanitize preview envelope | ORIG | `routes/portal.py`, `services/portal_service.py`, `models/portal_*.py` | How is portal identity separated from user? | Portal Auth,Orders,Invoices,Payments,Proofs | portal_identity,portal_session | /api/portal/* | portal_identities,magic_link_tokens,public_action_tokens | Customer Portal pages | Stripe (portal payment) | portal:* scope | preview-user impersonation | REBUILD | CP4 |
| PF2 | Employee Portal | ORIG + FEB have overlapping impls | ORIG+FEB | ORIG `routes/employee.py`, FEB `routes/employee_portal.py` | Which payroll fields are visible? | Portal Auth,Time Clock,Timesheets,Payroll | employee_portal_view | /api/employee-portal/* | (uses employee, timesheet, payroll) | Employee Portal pages | (none) | portal:employee_* | payroll data leak | REBUILD | CP6 |
| PF3 | Signatures | ORIG 658 lines; dual-parent workflow | ORIG | `routes/signatures.py`, `models/signature.py`, `services/signature_service.py` | How are single-action tokens issued? | Public tokens,Documents,Contracts | signature_request,signature_action | /api/signatures/*, /api/public/sign/* | signatures,public_action_tokens | Sign pages (portal + public) | Email (send link) | signature:*, public token | token reuse | REF+preflight | CP4 |
| PF4 | Approvals | ORIG 355 lines; dual-parent | ORIG | `routes/approvals.py`, `models/approval.py`, `services/approval_service.py` | Which parent types are supported? | Proofs,Contracts,Work Order Summary | approval,approval_action | /api/approvals/*, /api/public/approve/* | approvals,public_action_tokens | Approve pages | Email | approval:*, public token | token reuse | REF+preflight | CP4 |
| PF5 | Public Forms | ORIG public routes; rate-limit needed | ORIG | `routes/public/forms.py` | How are slugs owned by tenant? | Rate limit,Captcha,Leads | form,form_submission | /api/public/forms/* | forms,form_submissions | Public form pages | (none) | (public) | slug hijack | REBUILD | CP4 |
| PF6 | Questionnaires | ORIG + REB; multi-step | ORIG+REB | ORIG `routes/questionnaires.py`, REB `models/questionnaire.py` | Are questionnaires linked to Order or Wrap? | Public Forms,Orders,Wrap,Webstores | questionnaire,questionnaire_response | /api/questionnaires/*, /api/public/quest/* | questionnaires,questionnaire_responses | Portal + public pages | (none) | portal + public | data leak | REBUILD | CP4 |
| PF7 | Webstores | ORIG 3775 lines; huge donor file | ORIG+REB | ORIG `routes/webstores.py`, REB `ORDER_PORTAL_*_SPEC.md`, `models/webstore.py` | Which pieces are Webstore-specific vs shared with Orders? | Entitlements,DocuLink,Stripe Connect,Portal Auth | webstore,webstore_product,webstore_order,payout | /api/webstores/*, /api/public/store/* | webstores,webstore_products,webstore_orders,payouts | Owner Portal,Manager Portal,Storefront | Stripe Connect | webstore:*, portal | tenant cross-leak | REBUILD | CP7 |
| PF8 | Stripe Connect | Financial safety mandatory | FEB+ORIG | FEB `services/stripe_service.py`, ORIG `routes/stripe_connect.py` | How are payouts idempotent? | Stripe Core,Payouts | stripe_connect_account,payout | /api/stripe-connect/* | stripe_connect_accounts,payouts | Owner Portal | Stripe | payment:*,webstore:* | webhook replay | REBUILD (extract confirm) | CP7 |
| PF9 | Wrap Lab portal projection | REB workflow engine + ORIG portal fragments | REB+ORIG | REB `services/wrap_lab_service.py`, ORIG `routes/wrap.py` | Which stages project to portal? | DocuLink,Approvals,Signatures,Portal Auth | wrap_project,wrap_stage | /api/wrap/* | wrap_projects,wrap_stages | Wrap Lab pages + Customer Portal projection | (none) | wrap:*, portal | allowlist enforcement | REF | CP7 |
| PF10 | Inventory | ORIG RS | ORIG+REB | ORIG `routes/inventory.py`, `models/inventory.py`, REB spec | Locations, low-stock alerts, valuation | Vendors,Purchasing,Storage | inventory_item,stock_level,location | /api/inventory/* | inventory_items,stock_levels,inventory_locations | Inventory & Purchasing surface | (none) | inventory:* | tenant leak | REBUILD | CP5 |
| PF11 | Vendors | ORIG RS | ORIG | `routes/vendors.py`, `models/vendor.py` | Vendor + Purchase Order linkage | Audit,Notifications | vendor,vendor_contact | /api/vendors/* | vendors | Inventory & Purchasing surface | (none) | vendor:* | tenant leak | REBUILD | CP5 |
| PF12 | Purchasing | ORIG RS | ORIG | `routes/purchasing.py`, `models/purchase_order.py` | Receiving flow; expense creation | Vendors,Inventory,Payments,Expenses | purchase_order,po_line_item,receiving_record | /api/purchasing/* | purchase_orders,po_line_items,receiving_records | Inventory & Purchasing surface | (none) | purchasing:* | vendor cross-leak | REBUILD | CP5 |
| PF13 | Payroll | ORIG + FEB RS | ORIG+FEB | ORIG `routes/payroll.py`, `models/payroll.py`, FEB `services/payroll_service.py` | Sat–Fri period; Friday payday; advances/carryover semantics | Timesheets,Employees | payroll_period,payroll_line,pay_advance,pay_adjustment | /api/payroll/* | payroll_periods,payroll_lines,pay_advances,pay_adjustments | Payroll page + Employee Portal payslip | (none) | payroll:*, portal:employee_payslip_view | employee cross-leak; PII | REBUILD | CP6 |
| PF14 | Time Clock | ORIG + FEB RS | ORIG+FEB | ORIG `routes/timeclock.py`, FEB `routes/timeclock.py` | Manual adjustments; portal punch source | Employees,Employee Portal | time_punch,time_adjustment | /api/timeclock/* | time_punches,time_adjustments | Employee Portal + admin time clock backup | (none) | time_clock:* | punch fraud | REBUILD | CP6 |
| PF15 | Reports | ORIG RS + New | ORIG+New | ORIG `routes/reports.py` | Which reports at launch vs custom builder later? | All modules with data | report_definition,saved_report | /api/reports/* | report_definitions,saved_reports | Reports flyout | (none) | report:* | data leak on shared reports | REBUILD | CP5 |
| PF16 | Business Analytics | ORIG + New | ORIG+New | ORIG `routes/analytics.py` | Which slices at launch? | Reports | analytics_query | /api/analytics/* | analytics_queries | Business Analytics flyout | (none) | analytics:read | tenant leak | REBUILD | CP5 |
| PF17 | AI Assistant | ORIG + REB | ORIG+REB | ORIG `routes/ai_assistant.py`, REB `services/ai_catalog.py` | Provider abstraction; per-tool cost | AI Credit Ledger,AI Provider | ai_conversation,ai_message | /api/ai/assistant/* | ai_conversations,ai_messages | AI Assistant page | Emergent LLM key | ai_assistant:use | credit misdebit | REBUILD | CP8 |
| PF18 | Individual AI tools (24) | REB catalog + ORIG surfaces | REB+ORIG | REB `models/ai_tool.py`, ORIG per-tool routes | Which tools cost what intensity? | AI Credit Ledger,AI Provider | ai_tool_definition,ai_run | /api/ai/tools/* | ai_tools,ai_runs,ai_responses | Image/Design/Writing flyouts | Emergent LLM key | ai_tool:use | credit misdebit | REBUILD | CP8 |
| PF19 | Marketing Website | ORIG + FEB | ORIG+FEB | ORIG `frontend/marketing/*`, FEB `frontend/marketing/*` | Public routes vs static site? | Public Pricing,Contact Support | (static) | (static routes) | (none) | Landing/About/Features/Contact/Pricing | (none) | (public) | brand accuracy | REBUILD | CP8/CP9 |
| PF20 | Platform Admin | REB + ORIG | REB+ORIG | REB `routes/platform_admin.py`, ORIG `routes/admin.py` | Impersonation scope (Dec 21) | Auth,Tenants,Audit | platform_role,impersonation_session | /api/platform-admin/* | platform_roles,impersonation_sessions,audit_events | Platform Governance page | (none) | platform:admin, platform:tenant_read/write/status | cross-tenant leak; audit gaps | REF+preflight | CP8 |
| PF21 | SMS/MMS | ORIG + carrier 10DLC | ORIG | `routes/sms.py`, `services/sms_service.py` | 10DLC registration; provider abstraction | Portal Auth,Notifications | sms_conversation,sms_message | /api/sms/* | sms_logs,sms_conversations | Notification prefs, portal messaging | Twilio (Dec 19) | sms:read/send | phone number leak | REBUILD | CP9 (per Dec 27) |

---

# PART 10 — CORE PIPELINE BUILD PLAN (CP3)

## 10.1 Pipeline

```
Customer ──► Quote ──► Quote Line Items ──► Quote Approval ──► Quote-to-Order Conversion (idempotent)
       ──► Order ──► Order Items (rich schema, pricing snapshot, production_required)
       ──► Work Orders (production_required only) ──► Work Order Summary ──► Production
       ──► Invoice (dual status: document_status + financial_status)
       ──► Payment (unified: manual + Stripe; idempotency; partial; multiple; overpayment reject; controlled void; refund path)
```

## 10.2 Required Behaviors

- **Quote revisions:** every save on a sent Quote creates an immutable revision; the latest revision is the source of truth for conversion.
- **Quote expiration:** per-quote `expires_at` timestamp; expired quotes cannot be converted without owner override.
- **Quote approval:** customer portal `POST /api/portal/quotes/{id}/approve` writes an approval + optional signature; internal accept path preserved.
- **Idempotent quote-to-order conversion:** MVP `find_one_and_update({tenant_id, quote_id, converted_to_order_id: None}, ...)` pattern preserved; race safe.
- **Rich Order Item schema (~40 fields):** category, quantity, unit_price_cents, line_total_cents, description, dimensions, material_id, complexity, artwork_status, proof_status, custom fields, `production_required`, pricing_snapshot.
- **Order Item pricing snapshots:** `pricing_snapshot` embeds calculator inputs + outputs at commit time; historical quotes remain accurate on config changes.
- **`production_required`:** defaults from `services/order_item_rules.py::default_production_required(item_category)`; owner-editable per item.
- **Work Order snapshot behavior:** on generation, snapshot only `order_items` where `production_required=True`.
- **Work Order Summary:** printable PDF/print view.
- **Invoice dual status:** independent `document_status` (draft/sent/void) and `financial_status` (unpaid/partially_paid/paid/refunded/overpaid).
- **Unified Payment:** single `payments` collection; `source` = manual/stripe; `stripe_payment_intent_id` optional; Idempotency-Key required for writes.
- **Manual + Stripe + partial + multiple payments:** all supported; each payment is a row.
- **Overpayment reject:** total paid may not exceed invoice total.
- **Controlled void:** manual payment only; requires reason; Stripe never voided.
- **Refund path:** Stripe refund creates a Payment row with negative `amount_cents`; audit trail includes reason.
- **Idempotency:** every payment write requires `Idempotency-Key` header + DuplicateKeyError race handling; webhook confirm never mutates unrelated payment.
- **Audit history:** every state transition (quote_sent, quote_approved, quote_declined, order_created, invoice_sent, payment_recorded, payment_voided, invoice_voided) writes an event with actor, entity, changes, metadata.
- **Tenant isolation:** every read + write filters `tenant_id`; cross-tenant sweep test mandatory.
- **Permission enforcement:** `quote:*`, `order:*`, `invoice:*`, `payment:*`, `work_order:*` per Part 9.3 of Final Scope Register.
- **Customer portal visibility:** Customers see only their own quotes, orders, invoices, payments; portal identity scope filter enforced.

## 10.3 No competing systems

No higher-level module (Webstore Orders, Wrap Projects, AI-generated documents, Payroll payments) creates a competing customer/order/invoice/payment schema. All flow through the same collections.

---

# PART 11 — DOCUMENT AND PORTAL BUILD PLAN (CP4)

## 11.1 Shared Backend Foundations

| System | Backend owner | Portal-visible? | Public-visible? | Notes |
|---|---|---|---|---|
| Asset Library (DocuLink) | shared `documents` + `attachments` collections | Y (with review markers) | scoped tokens only | AI-generated docs: `source_type=ai_generated`, `requires_review=True` |
| Files (Object Storage) | shared `storage` service | Y | scoped tokens only | Tenant path prefix |
| Attachments | shared polymorphic `file_links` + `document_links` | Y | N | REB shape |
| Templates | shared `templates` | N | N | Tenant-owned |
| Forms | shared `forms` + `form_submissions` | Y (portal-owned submissions) | Y (public tenant slug) | Rate limit + captcha |
| Questionnaires | shared `questionnaires` + `questionnaire_responses` | Y | Y (public + portal) | Multi-step |
| Signatures | shared `signatures` + `public_action_tokens` | Y | Y (single-action tokens) | Short expiry |
| Proofs | shared `proofs` (parent = Order Item) | Y | Y (public approval link) | Watermarked variants |
| Approvals | shared `approvals` (dual-parent: Proof/Contract/WOS) | Y | Y (public approval link) | Portal + staff surfaces |

## 11.2 Portal Identity vs Public Tokens

- **Portal identity (`portal_identities`):** Customer Portal, Employee Portal, Webstore Owner Portal, Webstore Manager Portal. Separate collection from `users`. `sub_scope="portal"` JWT claim.
- **Public single-action tokens (`public_action_tokens`):** proof approval, signature, quote view, invoice view. Bound to ONE action. Signed, expiring, single-use for terminal actions.

## 11.3 Portal Actions and Side Effects

| Portal action | Triggers |
|---|---|
| Customer approves proof | Email to shop, activity event, DocuLink status change |
| Customer signs contract | Email to shop, PDF regenerated with signature block, activity event |
| Customer pays invoice | Stripe payment → webhook confirm → Payment row + Invoice financial_status update |
| Customer messages | Email to shop (or SMS if Decision 27=a), notification to assigned owner |
| Employee clocks in | Time punch row, notification if outside allowed window |
| Employee views payslip | Read-only view scoped by Decision 23 |
| Webstore Owner adds product | Webstore product row, notification to Managers |
| Webstore Manager fulfills order | Order status update, notification, email (or SMS per Decision 27) |
| Public form submission | Lead row, email to shop |
| Public questionnaire submission | Response row, links to Order/Wrap, email |
| Public proof approval | Approval row, email, activity event |
| Public signature | Signature row, PDF regeneration, email |

## 11.4 Files / Public Visibility

- Every file linked to a portal action carries an `is_portal_visible` flag.
- Public-viewable files require a scoped token with URL signature validation.

---

# PART 12 — INVENTORY, FINANCE, AND REPORTING BUILD PLAN (CP5)

## 12.1 Navigation Placement (LOCKED — unchanged by checkpoint grouping)

- Inventory / Vendors / Purchasing → Shop Operations → Inventory & Purchasing.
- Financials / Sales / Expenses / Taxes / Reports / Business Analytics → Business & Finance.

## 12.2 Implementation Sub-plan

**Inventory:** `inventory_items`, `stock_levels` (per-location), `inventory_locations`, low-stock alerts (Notifications).

**Vendors:** `vendors` with contacts + payment terms + tax settings.

**Purchasing:** `purchase_orders`, `po_line_items`, `receiving_records`. Received purchase orders create an Expense row.

**Material cost history:** `material_price_history` row per received PO line; feeds pricing calculator historical inputs.

**Expense creation from purchasing:** on receiving completion, generate expense row linked to PO + Vendor.

**Financials:** Revenue = sum(payments where source in [manual, stripe]) grouped by period. A/R = sum(invoice.balance_due_cents where financial_status in [unpaid, partially_paid]). Payments received = sum(payments where date in period). Unpaid/overdue = A/R filtered by due date. Refunds/voids = sum(payments where amount_cents < 0 OR voided_at is not null). Gross profit = revenue − COGS (from material_cost_history + timesheet-linked labor cost). Net-profit estimates = gross − expenses. Margins = per-order and per-category. Cash-flow snapshots = period-by-period. Webstore revenue = filter by webstore_id. Wrap Lab revenue = filter by wrap_project_id. Tax collected = sum(invoice.tax_cents). Payment-method breakdown = group by payment.source.

**Sales reporting:** by owner, by category, by month.

**Tax snapshots:** `invoice.tax_snapshot` frozen on Invoice send. Historical invoices never recalculated.

**Tax exemption records:** `tax_exemptions` per customer with certificate storage + audit.

**Report catalog:** ~25 curated reports (see PF15 preflight).

**Custom Report Builder:** staged delivery — v1 = column picker + filter + group-by; v2 = joins; v3 = chart types. Do not scope-creep to full BI.

**Business Analytics:** high-level KPIs, growth trends, funnel views.

## 12.3 Rule

Business & Finance does not duplicate operational Invoice Detail or Payment History screens. Those remain accessible from Shop Operations → Orders.

---

# PART 13 — TEAM AND PAYROLL BUILD PLAN (CP6)

## 13.1 Modules and Placement

All modules navigated through **Team & Workflow** flyout except Install Scheduling + Production Scheduling which appear on **Shop Operations → Shop Schedule** (same underlying `team_schedule` + `shop_schedule` collections).

## 13.2 Payroll Rules (LOCKED per prior owner statements)

- **Pay period:** Saturday through Friday.
- **Payday:** Friday.
- **Manual time adjustments:** supported via `time_adjustments` (audit-tracked).
- **Advances:** `pay_advances` collection; deducted from next payroll.
- **Adjustments:** `pay_adjustments` per employee per period.
- **Carryover:** unpaid amounts roll into next period.
- **Payments:** payroll payments create rows in a distinct `payroll_payments` collection (NOT in the shop-facing `payments` collection to avoid conflating employee pay with customer invoice payments — but audit-linked).
- **History:** per-employee payroll history endpoint.
- **Exports:** CSV export for external payroll services.

## 13.3 Employee Portal

- Primary employee **clock-in surface**.
- Admin time clock is a **backup** for kiosk / non-portal shops.
- Payslip visibility per Decision 23.
- Employee identity is a `portal_identity` scoped to `portal:employee_*`.

## 13.4 Payroll Reports in Business & Finance

Payroll reports may **appear** in Business & Finance → Reports without moving payroll management out of Team & Workflow. Reports read from `payroll_periods` + `payroll_lines`.

---

# PART 14 — WEBSTORES BUILD PLAN (CP7 — half A)

## 14.1 Product Modes

- **SignGuy AI Webstores add-on** (default for shops adding storefronts).
- **Webstores standalone** (own tenant; entitlement-gated).
- **Founder-included** (bundled with the founder plan).
- Shared backend for all modes.

## 14.2 Included Modules and Behaviors

- **Feature entitlements:** `webstores`, `stripe_connect`.
- **Tenant model:** every Webstore has `tenant_id` + `owner_identity_id` + `slug` + `store_type`.
- **Setup wizard:** guided flow producing a Webstore + branding + first product.
- **Store types (LOCKED):** B2B, Fundraiser, Event, Promotional, Employee Store, and General Store. School spirit, team gear, corporate merchandise, race-team merchandise, and similar concepts are use cases or templates within those types, not replacement canonical store types.
- **Customer and owner onboarding:** onboarding via portal invite → magic-link setup token.
- **Questionnaires:** intake per Webstore; AI summarization stored per Webstore.
- **AI summarization:** consumes credits from tenant credit ledger; owner reviews before publishing.
- **Store branding:** logo, colors, banner, custom domain (later).
- **Per-store catalog:** each Webstore has its own product list. **No global product catalog shared across all stores.**
- **Shared product templates:** a separate `product_templates` library at tenant level; a store may instantiate from a template.
- **Products + Variants + Costs + Selling prices + Owner share + Platform fees:** all `_cents` on Payment/Order settlement.
- **Owner approvals:** owner-facing approval on manager-created products/orders as configurable.
- **Stripe Connect onboarding:** OAuth + Standard/Express account choice; onboarding link + return handling.
- **Direct payouts:** payouts routed to Owner's Stripe Connect account per Payout Schedule.
- **Public storefront:** slug-based route; captcha + rate limit on order submission.
- **Orders:** Webstore Orders flow through the shared `orders` collection with `source=webstore` + `webstore_id` FK.
- **QR codes / Store slugs:** slug per store; QR generator utility.
- **Promo codes:** per-store promo entities.
- **Donations / Fundraiser goals / Event deadlines / Pickup rules / Auto-close:** per-store settings.
- **Owner Portal / Manager Portal:** distinct portal identities with scoped permissions.
- **Webstore analytics:** per-store dashboard.
- **Downgrade behavior:** entitlement off → storefront read-only; existing data preserved.
- **Standalone-to-Core upgrade path:** flip entitlements; no data migration required.

## 14.3 Do NOT Create

No global product catalog shared across all stores. Each Webstore has its own catalog. A separate reusable **product-template library** may exist at tenant level.

---

# PART 15 — WRAP LAB BUILD PLAN (CP7 — half B)

## 15.1 Modes

- **Add-on mode** (default).
- **Conditional standalone mode** — approved only after PF9 preflight confirms shared-core reuse without duplication.

## 15.2 Shared Systems

- Customers, Orders, Documents, Approvals, Signatures, Customer Portal — all shared with SignGuy AI Core.

## 15.3 Workflow

**Canonical 11-stage workflow** (verified in REB `services/wrap_lab_service.py`, `routes/wrap_lab.py`, and `models/wrap_lab.py`):

1. Intake.
2. Quote.
3. Contract.
4. Design.
5. Proof Approval.
6. Inspection.
7. Production.
8. Install.
9. Pickup.
10. Aftercare.
11. Complete.

Vehicle information, consultation, measurements, deposits, material acquisition, scheduling, and required packets are tasks, records, or stage gates inside this canonical engine. They do not silently replace the verified stage names.

**Stage gates:** each stage advances only when required deliverables are complete (owner-configurable).

**Portal projection:** Wrap-project portal view surfaces vehicle info + design + install schedule + aftercare with an allowlist of visible fields.

## 15.4 Wrap Documents

Vehicle info + inspection + measurement + pre-install packet + final packet — all stored in DocuLink with wrap-specific document types.

## 15.5 Permission Rules

`wrap_lab:read`, `wrap_lab:write`, `wrap_lab:advance_stage`, `wrap_lab:admin`, plus `portal:customer_view` scoped to allowlisted fields.

## 15.6 Do NOT

Do not approve Wrap Lab standalone until PF9 preflight confirms shared-core reuse without duplication.

---

# PART 16 — CREATIVE STUDIO AND AI BUILD PLAN (CP8 — half A)

## 16.1 Modules

- AI Assistant.
- 24-tool AI Tools Grid (curated slices: Image / Design / Writing).
- Prompt Library.
- Artwork Workspace.
- Generated Assets (with `requires_review`).
- AI History.
- AI-generated files + documents.
- Context Retrieval.
- Result Storage.

## 16.2 AI Credit Ledger

- `ai_credit_ledger` collection: rows for debits, credits (top-up purchase), admin adjustments, refunds.
- Atomic debit + generation: create ledger row before dispatching to provider; refund row if provider fails.
- Monthly included credits reset on subscription cycle.
- Top-up credits never expire (per Decision 14 recommendation).
- Balance = SUM(ledger rows).

## 16.3 Provider Abstraction

- `services/ai_provider.py` interface.
- Model selection rules by tool intensity (low / medium / high / vision / image).
- Emergent LLM key (Decision 18 direction LOCKED; model rules pending owner ratification).

## 16.4 Tool Catalog

- REB `AI_TOOL_CATALOG` extracted verbatim (24 tools).
- Each tool: `intensity`, `credit_cost` (provisional), `input_schema`, `output_schema`, `requires_review` flag.

## 16.5 Per-Tool Cost Rules

- Exact per-tool costs remain **provisional** (marker `provisional=True`) until measured cost audit (Decisions 12, 13 DEFERRED UNTIL COST AUDIT).

## 16.6 Review Requirements

- AI-generated documents customer-facing = `requires_review=True`; not portal-visible until reviewed by a staff user with `document:write` permission.

## 16.7 Cost Caps

- Soft warning at 200% of plan credits.
- Hard cap at 400% (RECOMMENDED default; owner ratifies in Prompt 5+).

## 16.8 Rate Limits

- Per-tenant + per-user + per-tool rate limiting; anomaly detection for sudden spikes.

## 16.9 Provider Outage Behavior

- Mark tool `provider_down`; do not debit credits; queue for retry; notify tenant if outage > 15 min.

## 16.10 Credit Refunds

- Every provider failure refunds credits via a ledger credit row with reason.

## 16.11 Tenant Usage History

- `ai_responses` collection retains every generation with metadata + credit cost.

## 16.12 Platform Credit Administration

- Platform Admin can credit/debit any tenant with required reason + audit event.

## 16.13 AI Prohibitions (LOCKED)

- No autonomous email send.
- No autonomous SMS send.
- No payment recording.
- No invoice alteration.
- No pricing change.
- No refund issuance.
- No Stripe event trigger.
- No proof approval.
- No document signature.

---

# PART 17 — CONTROL CENTER BUILD PLAN (CP2 + CP8)

## 17.1 Flyout Entries

Overview / Company Settings / Users & Permissions / Integrations / Pricing Defaults / Portals / Subscriptions & AI Credits / Feature Access / Platform Governance / Data & Security.

## 17.2 Distinctions

- **Tenant settings** = per-tenant configuration (Company Settings, Portals settings, Data & Security, Pricing Defaults).
- **Platform settings** = cross-tenant configuration under Platform Governance (visible only to platform-authorized roles).
- **Tenant billing** = tenant's subscription + AI credit purchases (Subscriptions & AI Credits).
- **Customer billing** = the shop's invoices to its customers (Shop Operations → Orders → Invoice/Payment).
- **Pricing configuration** = Control Center → Pricing Defaults (shop rate, labor, materials defaults, markups, minimums, category defaults, complexity, formulas).
- **Operational pricing calculations** = the pricing calculator surfaced inside Quotes/Orders (uses configuration read-only).
- **Feature entitlements** = per-tenant module access (Feature Access; may be shop-editable or platform-only per Prompt 5 ratification).
- **User permissions** = per-role capabilities (Users & Permissions).
- **Platform administration** = Platform Governance (Platform Admin dashboard, tenant management, analytics, audit logs, email broadcasts, subscription admin, AI credit admin).

## 17.3 Platform Governance Visibility

Only visible to identities with `platform:admin` or platform-scope roles. Backend enforcement: `require_platform_role()` dep.

---

# PART 18 — HELP AND COMMUNITY BUILD PLAN (CP8)

## 18.1 Flyout Entries

Help Center / Documentation / Onboarding / Community / Bug Reports / Feature Requests / Contact Support / What's New.

## 18.2 Shared Backend

Bug Reports + Feature Requests share the Community backend (categorised posts) but remain **directly accessible flyout destinations**.

## 18.3 Included Systems

- **Moderation:** community moderator role (`community:moderate`) may hide, edit, close posts.
- **Status tracking:** Bug/Feature posts carry status (open/in_progress/resolved/wont_do).
- **Notifications:** subscribers notified on status change.
- **Support ticket routing:** Contact Support submissions create a support ticket + email to support inbox.
- **Release notes:** What's New backed by a `release_notes` collection with admin publishing controls.
- **Contextual help links:** every page ribbon may include a "?" that deep-links to Documentation.
- **Onboarding progress:** per-tenant onboarding_state.
- **Admin publishing controls:** Platform Admin publishes release notes + documentation.

---

# PART 19 — INTEGRATION BUILD ORDER

| Order | Integration | Introduced in | Requires | Blocks CR | Secrets | Webhooks | Signature verify | Idempotency | Retry | Monitoring | Audit | Tenant ownership | Failure handling | Test mode | Production cutover | Rollback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SendGrid outbound | CP1 (already RV) | Auth | Y | `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` | N | N/A | Per-send | Provider | Delivery metrics | Y | Per-tenant | Log + retry queue | Sandbox | Rotate keys before GA | Env swap |
| 2 | Object Storage | CP1 (already RV) | Auth | Y | Emergent Storage key | N | N/A | Per-file UUID | Provider | Error rate | Y | Per-tenant path | Fail closed | Sandbox | Rotate keys | Env swap |
| 3 | Webhook Infrastructure | CP2 | Auth,Audit | Y | (per integration) | Y (framework) | Y | Yes (event ID unique index) | Retry with dedup | Verification success | Y | Per-tenant via metadata | Reject unverified | Sandbox | Cutover with signature | (framework) |
| 4 | SendGrid webhook | CP2 | Webhook Infra | Y | `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` (HMAC-SHA256) | Y | Y | Event ID | Provider | Webhook success rate | Y | Per-tenant metadata | 401 unverified; alert on repeated | Sandbox | Prod = fail-closed on missing secret (Decision 4) | Disable route |
| 5 | Portal Authentication | CP2 (foundation), CP4/6/7 (consumers) | Auth | Y | JWT secrets | N | N/A | Magic-link single-use | N/A | Auth success | Y | Per-tenant | Rate limit + lockout | Sandbox | Rotate secrets before GA | Env swap |
| 6 | Background Jobs | CP2 (scaffold), CP5/CP8 (jobs) | Auth,Audit | Y | (internal) | N/A | N/A | Job ID | Dead-letter | Job success rate | Y | Per-tenant | Alert on failure | Sandbox | (internal) | Env swap |
| 7 | Public forms protection | CP4 | Rate limit + captcha | Y | Captcha keys | N | N/A | Per-submission dedup | N/A | Submission volume + spam rate | Y | Per-tenant slug | Reject spam | Sandbox | Cutover | Disable route |
| 8 | Stripe Core | CP3 | Webhook Infra | Y | `STRIPE_API_KEY` (test key already in env), `STRIPE_WEBHOOK_SECRET` | Y | Y | Idempotency-Key + DuplicateKeyError race | Provider | Payment success rate | Y | Per-tenant Stripe customer | Never mark success without webhook | Test key | Prod live key rotate; webhook secret set | Void unpaid pending payments |
| 9 | Tax provider boundary | CP5 | Invoices | Y | (provider key if used) | N | N/A | Per-invoice tax snapshot | Provider | Tax API errors | Y | Per-tenant | Allow manual override | Manual initially | Provider integration later | Manual mode |
| 10 | Stripe Connect | CP7 | Stripe Core | Y (Webstore GA) | Stripe Connect keys | Y | Y | Payout idempotency | Provider | Payout success + reconciliation deltas | Y | Per-tenant Stripe Connect account | Never trust client-computed payout amounts | Test onboarding | Prod live | Void pending payouts |
| 11 | AI provider (Emergent LLM key) | CP8 | AI Credit Ledger | Y | `EMERGENT_LLM_KEY` | N | N/A | Per-generation ledger idempotency | Adapter policy | Provider latency + cost per tool | Y | Per-tenant credit metering | Refund credits on provider failure | Sandbox provider | Rotate key | Disable AI tools |
| 12 | Monitoring | CP9 | Deploy | Y | Monitoring API keys | N | N/A | N/A | N/A | (self) | N | (self) | Alert | Sandbox | Cutover before GA | Env swap |
| 13 | SMS/MMS | CP9 (if Decision 27=a) | Webhook Infra | Depends on Dec 27 | Twilio (Dec 19) | Y | Y | Per-send Idempotency-Key | Provider | Deliverability | Y | Per-tenant | Log + retry | Sandbox | Prod live | Disable module |
| 14 | Future Google Calendar | Post-GA | OAuth | N (post-GA acceptable — see Part 15.8 accepted-limitation example) | OAuth tokens | Y | Y | Provider ID | Provider | Sync success | Y | Per-user | Log sync failures | Sandbox | Deferred | Disable module |
| 15 | Future accounting (QB/Xero) | Post-GA | OAuth | N | OAuth tokens | Y | Y | Per-invoice + per-payment external ID | Provider | Sync success | Y | Per-tenant | Log sync failures | Sandbox | Deferred | Disable module |
| 16 | Future Meta lead ads | Post-GA | Meta API | N | Meta keys | Y | Y | Per-lead source_id | Provider | Ingestion success | Y | Per-tenant | Log + do not lose data | Sandbox | Deferred | Disable module |

**Rule:** every third-party integration must route through `integration_playbook_expert_v2` before implementation.

---

# PART 20 — COMMERCIAL SYSTEMS BUILD PLAN (CP8)

## 20.1 Modules

Subscription Billing, Add-on Purchases, AI Credit Purchases, Transaction Fees, Founders Promo, Trials, Plan changes, Entitlements enforcement, Grace periods, Cancellations, Downgrades, Upgrades, Billing history, Public Pricing, Subscription checkout, Failed-payment behavior, Data preservation.

## 20.2 Behaviors

- **Subscription checkout:** Stripe Checkout Session (or Payment Element) with idempotency-safe creation.
- **Plan changes:** Stripe Subscription update with proration; entitlements flip on webhook confirm.
- **Entitlements enforcement:** every gated request reads entitlement; returns 402/403 with `entitlement_missing` error code on absence.
- **Grace period on payment failure:** 7 days soft grace → 14 days soft block → hard block (Decision 26 recommended default).
- **Cancellation:** entitlements off at period end; data preserved.
- **Downgrade:** entitlements flip off; storefronts/wrap projects flagged read-only; data preserved.
- **Upgrade:** entitlements flip on; no data migration.
- **Billing history:** per-tenant billing history endpoint.
- **Public Pricing:** static page reads from `plans` config; Prompt 5+ ratifies final prices.
- **Failed-payment behavior:** grace → block per Decision 26; Stripe dunning integration reference.
- **Data preservation after downgrade:** all data retained; UI hides non-entitled areas.

## 20.3 Do NOT

Do not lock candidate prices until owner approves them. Do not allow REB `billing_rules.py` values to silently become production pricing.

---

# PART 21 — PARALLEL EXECUTION AND COLLISION RULES

## 21.1 May Run in Parallel

- Backend and frontend work within a single module.
- CP4 (Documents/Portals) and CP5 (Inv+Fin+Reports) after CP3 exit.
- CP5 and CP6 after CP3 exit.
- CP7 Webstores subteam and CP7 Wrap Lab subteam after CP4 exit.
- CP8 Creative Studio and CP8 Subscription Billing (after AI Credit Ledger exists).
- Documentation updates alongside implementation.

## 21.2 Must NOT Run in Parallel

- CP2 and CP3 (foundations before spine).
- CP4 and CP7 (Webstores + Wrap depend on completed Portal + Documents + Approvals + Signatures).
- CP3 and CP5 (financial reports depend on completed Payments/Invoices).
- AI Tools (CP8) and AI Credit Ledger (CP8) — ledger must exist first.
- Stripe Core (CP3) and Stripe Connect (CP7) — Core reconciliation pattern must be verified first.
- Permissions (CP1) and any permission-consuming module.
- Entitlements scaffold (CP2) and any entitlement-consuming module.

## 21.3 Shared Files That Cause Merge Conflicts

- `backend/app/core/db.py::ensure_indexes()` — every new module adds indexes here; coordinate.
- `backend/app/deps.py::require_permission()` — every new permission touches this.
- `backend/server.py` router registration — every new router imports here.
- `frontend/src/App.js` — sidebar + flyout definitions.
- `frontend/src/contexts/AuthContext.jsx` — role catalog.
- `frontend/src/lib/api.js` (or equivalent) — API client base.

## 21.4 Shared Models Likely to Cause Schema Collisions

- `Order`, `OrderItem`, `Invoice`, `Payment`, `Customer` — all touched by CP3, CP4, CP5, CP6, CP7, CP8. Freeze after CP3; only additive changes downstream (new optional fields, new indexes).

## 21.5 Shared Services Likely to Cause Architectural Collisions

- `services/audit.py`, `services/sequence.py`, `services/storage.py`, `services/email.py`, `services/pricing.py`. Freeze API surface after CP2; add new methods only, never rename.

## 21.6 Required Branch Strategy

- One long-lived main.
- One feature branch per CP (`checkpoint/cp2`, `checkpoint/cp3`, etc.).
- One sub-branch per module inside a CP (`cp3/quotes-lineitems`, `cp3/invoice-dual-status`).
- Merge order = dependency order.
- Every checkpoint merged into main only after Evidence Package sign-off.

## 21.7 Required Integration Order

Foundation → Spine → Documents/Portals → Business systems → Team systems → Add-ons → Commercial systems → Final hardening.

## 21.8 Required Code-Owner Review

Shared foundations (auth, tenants, permissions, storage, audit, sequences, money) require an additional review pass regardless of implementer.

---

# PART 22 — TESTING STRATEGY

## 22.1 Test Types

| Type | Location | Runs |
|---|---|---|
| Unit tests | `backend/tests/unit/` | Per PR |
| Integration tests | `backend/tests/integration/` | Per PR + per CP exit |
| End-to-end tests | via `testing_agent_v3_fork` (Playwright) | Per CP exit + pre-CR |
| Cross-tenant sweep | `backend/tests/cross_tenant/` | Per new module |
| Permission matrix | `backend/tests/permissions/` | Per new module |
| Portal isolation | `backend/tests/portals/` | Per new portal module |
| Money safety | `backend/tests/money/` | Per commerce module |
| Idempotency | `backend/tests/idempotency/` | Per Payment/Webhook path |
| Webhook | `backend/tests/webhooks/` | Per webhook integration |
| File security | `backend/tests/files/` | Per file module |
| UI state | frontend Vitest + Testing Library | Per FE change |
| Responsive | Playwright viewports | Per CP exit |
| Accessibility | axe-core | Per CP exit |
| Regression | Prior CP tests re-run | Per CP exit |
| Smoke | curl + screenshot | After every merge |

## 22.2 Test Rules

- Every commerce write path has a money-safety test (integer cents in, integer cents out; no floating-point contamination).
- Every payment path has an idempotency test (double-send returns 409 or 200-no-op, never double-writes).
- Every webhook path has a signature-verify test (invalid signature → 401).
- Every portal route has a cross-tenant test (customer A cannot see customer B's data even via ID guessing).
- Every entitlement-gated route has an entitlement-missing test (returns 402 with `entitlement_missing` code).
- Every permission has a matrix row test (role × endpoint × expected status).

## 22.3 Test Ownership

- The implementing checkpoint owns its tests.
- Regression tests from prior checkpoints must pass before a new checkpoint exit.

---

# PART 23 — EVIDENCE PACKAGE REQUIREMENTS

Every checkpoint exit ships an evidence package at `/app/evidence/CP<n>_evidence.md` containing:

1. **Files changed** — with change type (added / modified / deleted).
2. **New files.**
3. **Removed files.**
4. **Routes added/changed** — with method + path + permission + status codes.
5. **Models added/changed** — with field diff.
6. **Collections added/changed** — with index list.
7. **Indexes added/changed.**
8. **Permissions added/changed.**
9. **Audit events added.**
10. **Integrations affected.**
11. **Tests run** — with counts.
12. **Test results** — pass/fail totals + failure summaries.
13. **Tenant-isolation result** — passing cross-tenant sweep summary.
14. **Known issues** — with severity + tracking ID.
15. **Deferred items** — with rationale + follow-up CP.
16. **Documentation updated** — file list.
17. **Screenshots** — where UI changed.
18. **Rollback instructions** — exact steps + risk level.
19. **Final checkpoint status** — one of the values in Part 25 progress.

---

# PART 24 — DOCUMENTATION SYNCHRONIZATION RULES

At every checkpoint exit, update:

- `/app/memory/AGENT_INSTRUCTIONS.md` — new rules, LOCKED decisions, changed policies.
- `/app/SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md` — mark checkpoint COMPLETE; append link to Evidence Package; adjust downstream CP entry conditions if scope changed.
- Module documentation per Part 8.
- API documentation (OpenAPI / route README).
- User-facing help documentation (Help Center) where applicable.
- Running issue tracker (`/app/memory/running_issues.md`, created lazily).
- Completion register (`/app/memory/completion_register.md`, created lazily).

---

# PART 25 — PROGRESS TRACKING SYSTEM

## 25.1 Checkpoint Status Values

- NOT STARTED
- PREFLIGHT IN PROGRESS
- OWNER DECISION BLOCKED
- READY TO BUILD
- IN PROGRESS
- TESTING
- CORRECTIONS REQUIRED
- COMPLETE
- COMMERCIAL GATE BLOCKED

## 25.2 Per-Module Progress Fields

- Scope confirmed
- Source confirmed
- Preflight complete
- Owner decisions approved
- Backend complete
- Frontend complete
- Permissions complete
- Tenant tests complete
- Audit complete
- Integration tests complete
- Documentation complete
- Commercial gate passed

**Rule:** A module is NOT complete merely because backend or frontend work exists independently. All 12 fields above must pass.

## 25.3 Live Progress Register

Progress lives at `/app/memory/progress_register.md` (created lazily by CP1 implementation). Every checkpoint exit updates this register.

---

# PART 26 — COMPLETION DEFINITIONS

## 26.1 Module Complete

A module is complete when:

- Backend behavior works.
- Frontend behavior works.
- Permissions work.
- Tenant isolation works.
- Audit events work.
- Integrations work.
- Error states work.
- Empty states work.
- Tests pass.
- Documentation is updated.
- No placeholder behavior remains.

## 26.2 Checkpoint Complete

A checkpoint is complete when:

- Every included module passes its exit conditions.
- Required owner decisions are approved.
- Required preflights are complete.
- Cross-module workflows pass.
- Evidence package is complete.
- Regression tests pass.
- Documentation is synchronized.

## 26.3 Commercially Ready

Every gate in Part 15 of the Final Scope & Decision Register passes.

---

# PART 27 — NEVER-AGAIN ENFORCEMENT MAP

All 42 Never-Again rules from Final Scope & Decision Register Part 12 are enforced. Below shows which checkpoints enforce each rule.

| # | Rule | Enforced in |
|---|---|---|
| 1 | One active dev repository | CP1 (LOCKED policy) |
| 2 | No parallel customer systems | CP3, CP7, CP8 |
| 3 | No parallel order systems | CP3, CP7 |
| 4 | No Job-domain terminology | CP1 lock, enforced on every port |
| 5 | No parallel invoice/payment systems | CP3, CP7, CP8 |
| 6 | No duplicate settings systems | CP2 |
| 7 | No duplicate file-storage | CP1, CP4 |
| 8 | No Base64-in-Mongo | CP1 |
| 9 | No frontend-only permissions | CP1, every CP |
| 10 | No missing tenant filters | CP1, every CP |
| 11 | No hardcoded tenant IDs | Every CP code review |
| 12 | No direct payment-status mutation | CP3 |
| 13 | Invoice doc status ≠ financial status | CP3 |
| 14 | Verified payment webhooks | CP3 (Stripe Core), CP7 (Connect) |
| 15 | Payment idempotency | CP3, CP7 |
| 16 | No portal/staff JWT crossover | CP2, CP4, CP6, CP7 |
| 17 | No preview-user impersonation in prod | CP1 startup guard |
| 18 | No dev-login routes in prod | CP1 startup guard |
| 19 | No placeholder secrets in prod | CP1 startup guard |
| 20 | No giant App.js | CP1 nav rebuild + every CP FE review |
| 21 | No giant router files | Every CP backend review |
| 22 | No giant pricing files | CP1 (MVP pricing is target) |
| 23 | No duplicate menus | CP1 |
| 24 | No duplicate dashboards | CP1 |
| 25 | No duplicate pages | Every CP |
| 26 | No legacy redirect as permanent nav | CP1 |
| 27 | No hardcoded categories/status | Every CP |
| 28 | No scattered business formulas | Every CP (services own algorithms) |
| 29 | No client-authoritative totals | CP3 |
| 30 | No silent status changes | Every CP (audit mandate) |
| 31 | No missing audit events | Every CP |
| 32 | No destructive delete on financials | CP3, CP5 |
| 33 | No "module complete because a page renders" | Part 26 enforcement |
| 34 | No placeholder data in prod | CP9 |
| 35 | No copy without dependency review | Every donor port |
| 36 | No rewriting working code for style | Every CP |
| 37 | No module before dependencies | Part 6 DAG |
| 38 | No Webstores before entitlements/portals/payments | CP7 blocked until CP2+CP3+CP4 exit |
| 39 | No Wrap Lab before files/approvals/signatures/portal | CP7 blocked until CP4 exit |
| 40 | No AI before credit metering + cost controls | CP8 AI Tools blocked until AI Credit Ledger exists |
| 41 | No donor archive before commercial completion | Repo policy (LOCKED) |
| 42 | No scope/impl drift | Documentation sync (Part 24) |

---

# PART 28 — COMMERCIAL-RELEASE ROADMAP

## 28.1 Roadmap Layers

- **Internal implementation checkpoints:** CP1 → CP9.
- **Founder launch readiness:** requires CP1–CP8 complete with Webstores + Wrap Lab + AI + Subscription Billing operational, plus Decisions 1, 2, 4, 8, 9, 10, 11, 15, 22, 26 resolved.
- **General-availability readiness:** requires all of the above + CP9 complete + all remaining owner decisions resolved + no release blocker open per Part 15 of Final Scope Register.
- **Optional later integrations:** SMS/MMS (if Decision 27=b), Google Calendar sync, QuickBooks/Xero, Meta Lead Ads. **These are permanent product scope — not "post-launch nice-to-haves" — but their commercial timing may be later per owner decision.**

## 28.2 Commercial Release Gates (LOCKED per Final Scope Register Part 15)

- Product Completeness (all approved modules, portals, add-ons, AI).
- Security (secrets rotated; dev bypass off; dev routes blocked; tenant/permission/portal isolation tested; webhook signatures verified; audit active).
- Financial Safety (integer cents everywhere; invoice dual status; payment idempotency; overpayment reject; controlled void; Stripe webhook reconciliation; refunds; tax snapshots; entitlements; credit ledger; transaction fees approved).
- Data Integrity (indexes; unique constraints; conversions idempotent; archives preserve; no orphans; no `db.jobs`; backups tested).
- Quality (unit + integration + E2E + cross-tenant + permission + portal + payment + integration-failure + responsive + accessibility + performance).
- Operations (deploy procedure; rollback plan; incident response; error alerts; billing support; customer support; onboarding; docs; privacy; terms; status monitoring; provider outage procedures).
- Commercial Readiness (final prices approved; plans approved; trial approved; founder offer approved; AI-credit costs approved; setup fees approved; public pricing accurate; subscription checkout tested; cancellation tested; entitlement changes tested; taxes and disclaimers approved; marketing accurate; support contact active).

## 28.3 Do Not Call Required Features "Post-Launch"

SMS/MMS is a **permanent-product feature**. Its **commercial-release timing** is Decision 27. Do not label it "post-launch nice-to-have" unless the owner explicitly selects Decision 27 = (b).

---

# PART 29 — REUSABLE CHECKPOINT IMPLEMENTATION PROMPT (template)

Copy this template verbatim when starting a checkpoint.

---

**IMPLEMENT CHECKPOINT `<CP_NUMBER>` — `<CP_NAME>`**

**MANDATORY READING BEFORE ANY CODE:**
1. `/app/SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md` — this master plan.
2. Section for `<CP_NUMBER>` (Parts 5, 6, 8, 10–20 as applicable).
3. Relevant module preflight documents at `/app/preflight/<module>_preflight.md`.
4. `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md` — LOCKED scope contract.
5. `/app/memory/AGENT_INSTRUCTIONS.md` — implementation rules.
6. Existing MVP code you will touch (`grep`-inspect first; do NOT open more files than needed).
7. Existing donor code ONLY for the specific reuse instructions in this checkpoint.

**MODULES IN SCOPE:** `<module list from Part 8 for this CP>`

**OWNER DECISIONS REQUIRED (must be OWNER APPROVED before starting):** `<from Part 4 for modules in this CP>`

**SOURCE REPOSITORIES YOU MAY INSPECT (read-only reference):** `<from Part 8>`

**DONOR FILES YOU MAY INSPECT:** `<from Part 8 / preflight docs>`

**ENTRY CONDITIONS (must all be TRUE):**
- Prior checkpoint(s) `<list>` are COMPLETE with signed Evidence Package.
- Required owner decisions `<list>` are OWNER APPROVED.
- Required module preflights `<list>` are DONE and documented.
- Required integration playbooks obtained via `integration_playbook_expert_v2`.
- Existing tests are GREEN.
- Working MVP behavior is backed up and documented.

**EXIT CONDITIONS (must all be TRUE to declare COMPLETE):**
- Every module in scope passes its module-complete definition (Part 26.1).
- Every required test type in Part 22 passes.
- Cross-tenant sweep passes on every new module.
- Permission matrix passes.
- Portal isolation passes (where applicable).
- Money safety passes (where applicable).
- Idempotency tests pass (where applicable).
- Webhook signature-verify tests pass (where applicable).
- Documentation is synchronized per Part 24.
- Evidence package is complete per Part 23.

**IMPLEMENTATION SEQUENCE (obey this order):**
`<from Part 10/11/12/13/14/15/16/17/18/20 for this CP>`

**REUSE INSTRUCTIONS (obey verbatim):**
Use Part 7A as the controlling source. For every module list the exact source repository, exact verified donor files, evidence level, whole-file-copy permission, preserved behavior, rejected code, required renames, MVP destination paths, and preflight status. A generic label such as `REB — REF` is not sufficient.

**PROHIBITIONS:**
- Do not wholesale-copy donor modules or files unless Part 7A explicitly marks that exact file `COPY AND INTEGRATE`.
- Do not rewrite working MVP code for style.
- Do not create parallel domain models.
- Do not use prohibited terminology (`job`, `job_ticket`, `job_item`).
- Do not add permissions outside Part 9 of Final Scope Register.
- Do not add hardcoded secrets or hardcoded tenant IDs.
- Do not skip startup guards.
- Do not disable dev-bypass guards in prod code paths.
- Do not proceed past exit conditions failing.

**REQUIRED OUTPUTS AT EXIT:**
- Evidence package at `/app/evidence/CP<CP_NUMBER>_evidence.md`.
- Updated `/app/memory/progress_register.md`.
- Updated `/app/memory/AGENT_INSTRUCTIONS.md` (if rules changed).
- Updated `/app/SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md` marking this CP COMPLETE with a link to the evidence package.

**STOP AFTER THIS CHECKPOINT.** Do not begin the next checkpoint automatically. Await Prompt 5 (or later) for the next checkpoint.

---

## 29.1 Placeholder Fields

- `<CP_NUMBER>` — CP1 … CP9.
- `<CP_NAME>` — see Part 5.1.
- Module list — see Part 8.
- Owner decisions — see Part 4.
- Source repositories — see Part 8.
- Donor files — see Part 8 + Part 9.
- Entry conditions — see Part 6.
- Exit conditions — see Part 26.
- Tests — see Part 22.
- Documentation — see Part 24.
- Commercial relevance — see Part 28.

---

# PART 30A — EXECUTION CHECKPOINT DETAIL PAGES

The following EC units are the only units used for implementation branches and evidence packages. Each EC stops independently. The broader PC mapping remains in Part 5.


## 30A.1 EC0 — Owner Decisions and Governance Lock — COMPLETE

**Purpose:** Resolve blocking owner decisions and freeze terminology, repository roles, money, permissions, release timing, and commercial policies.

**Included work**
- All 27 owner decisions
- Commercial prices and fees remain candidate until approved
- SMS/MMS timing Decision 27

**Exit conditions**
- Updated owner decision register
- AGENT_INSTRUCTIONS policy lock
- No application code
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.2 EC1 — Security and Permanent App Guardrails

**Purpose:** Preserve MVP foundations; add startup guards; disable production bypasses; lock tenant and permission enforcement.

**Included work**
- MVP auth, tenants, users, storage, sequences, UI library remain KEEP
- Production startup guards
- Navigation shell adjusted to locked six-area structure without duplicating page controls

**Exit conditions**
- Dev bypass fails in production
- Placeholder secrets fail in production
- Existing smoke tests remain green
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.3 EC2 — Shared Platform Services

**Purpose:** Settings, activity, notifications, email activity/webhooks, upload validation, file links, entitlements, monitoring, and webhook infrastructure.

**Included work**
- REB settings scaffold
- REB notification/email activity scaffold
- REB upload validation
- MVP attachments plus REB polymorphic links
- Entitlements and webhook infrastructure

**Exit conditions**
- Tenant-scoped repositories
- Signed/replay-safe webhooks
- Cross-tenant tests for every new shared service
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.4 EC3 — Quotes, Orders, and Pricing Snapshots

**Purpose:** Extend the working MVP sales spine with rich quote/order items, approvals, revisions, pricing snapshots, and production-required rules.

**Included work**
- REB quote and order schemas merged into MVP
- MVP idempotent quote-to-order preserved
- MVP pricing calculator preserved
- REB item pricing snapshots and production_required rule integrated

**Exit conditions**
- No parallel quote/order collections
- Historical pricing snapshots immutable
- Conversion remains idempotent
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.5 EC4 — Invoices, Payments, and Stripe Core

**Purpose:** Rehouse FEB financial logic; implement dual invoice status, unified payments, idempotency, voids, refunds, and Stripe reconciliation.

**Included work**
- FEB invoice reconciliation logic extracted
- FEB payment service extracted
- MVP cents policy retained
- Stripe Core added behind signed webhook infrastructure

**Exit conditions**
- Dual invoice status
- Partial/multiple payments
- Overpayment rejection
- Void with reason
- Webhook replay safety
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.6 EC5 — Production and Work Orders

**Purpose:** Correct work-order generation, production board, work-order summaries, scheduling hooks, and production audit events.

**Included work**
- MVP Work Orders extended
- REB production gate and draft behavior integrated
- Production board rebuilt from REB/ORIG behavior

**Exit conditions**
- Only production_required items appear
- Work Order Summary printable
- Production completion separate from customer approval
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.7 EC6 — Asset Library, Proofs, Signatures, and Customer Portal

**Purpose:** Build DocuLink on MVP storage, then forms, questionnaires, proofs, approvals, signatures, portal auth, and customer portal workflows.

**Included work**
- REB DocuLink rebuilt on MVP object storage
- ORIG proofs/approvals/signatures after preflight
- Fresh portal identity service
- Customer Portal rebuilt from ORIG behavior

**Exit conditions**
- Private files by default
- Scoped public tokens
- Portal/staff JWT separation
- End-to-end proof/sign/pay flow
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.8 EC7 — Inventory, Purchasing, Finance, and Reporting

**Purpose:** Build inventory/vendor/purchasing systems and financial/reporting layers on the completed commerce pipeline.

**Included work**
- Inventory/Vendors/Purchasing rebuilt from ORIG behavior and REB spec
- Finance/Reports rebuilt on completed invoice/payment data
- Custom report builder constrained to approved data sources

**Exit conditions**
- Purchasing creates auditable expenses
- Tax snapshots immutable
- Reports tenant-safe and server-authoritative
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.9 EC8 — Team, Scheduling, Time, and Payroll

**Purpose:** Employees, tasks, calendar, schedules, time clock, timesheets, payroll, internal communications, and Employee Portal.

**Included work**
- Employees, tasks, schedules, time clock, timesheets, payroll rebuilt against MVP
- REB notes/communications reused selectively
- Employee Portal built fresh

**Exit conditions**
- Saturday-Friday pay week
- Friday payday
- Manual adjustments and advances
- Employee portal isolation
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

> ---
> ## ⚠️ SUPERSEDED BLOCK — SECTIONS 30A.10 THROUGH 30A.15 (EC9–EC14 AS ORIGINALLY NUMBERED)
>
> **STATUS: SUPERSEDED — HISTORICAL REFERENCE ONLY — NOT IMPLEMENTATION AUTHORITY.**
>
> As of the owner-approved **SignGuy AI Checkpoint Specification Pack** (intake dated 2026-02, 15 documents: `00_Master_Index_and_Owner_Decision_Register.docx` + `EC09`–`EC22`), the six checkpoint detail pages below (old EC9 Webstores/Stripe Connect, old EC10 Wrap Lab, old EC11 Creative Studio/AI Credits, old EC12 Control Center/Governance/Community, old EC13 Commercial Billing/Marketing, old EC14 Commercial Release Hardening) are **replaced by a new, renumbered, and expanded EC9–EC22 sequence**. The old five-checkpoint condensation of this remaining work was too coarse to act as a safe build authority and has been retired in favor of one controlling document per checkpoint.
>
> **New controlling authority:** `/app/memory/checkpoint_reference_table.md` (EC9–EC22 sequence + controlling document map) and `/app/memory/documentation_authority_register.md` (full priority order). Source documents retained at `/app/specs_pack/extracted/*.docx`.
>
> **Do not implement against the sections below.** They remain in this file only for provenance (to show what the product's history/lineage of planning looked like). Any agent picking up work on Webstores, Wrap Lab, AI credits, Control Center/Community, Commercial Billing, or Final Hardening MUST use the new EC9–EC22 pack, not this block.
> ---

## 30A.10 EC9 — Webstores and Stripe Connect  _(SUPERSEDED — see banner above; this old EC9 slot is now EC14 Webstores in the new pack)_

**Purpose:** Build Webstores from REB specifications and ORIG feature map, using shared core, portals, entitlements, and secure payout reconciliation.

**Included work**
- REB ORDER_PORTAL specs control behavior
- ORIG webstores is discovery map only
- Stripe Connect uses security-reviewed FEB/ORIG pieces
- Shared Orders, Customers, Documents, Payments

**Exit conditions**
- No separate Webstore core collections for shared domains
- Direct payout reconciliation
- Standalone upgrades by entitlement only
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.11 EC10 — Wrap Lab / Wrap Command Center  _(SUPERSEDED — this old EC10 slot is now EC15 Wrap Lab in the new pack; "Wrap Command Center" naming is retired in favor of "Wrap Lab")_

**Purpose:** Integrate the REB 11-stage workflow into shared Orders, DocuLink, approvals, signatures, portal auth, and entitlements.

**Included work**
- REB Wrap Lab model/service/router targeted refactor
- Shared DocuLink, approvals, signatures, portal, customer, order systems

**Exit conditions**
- All 11 stages and stage gates verified
- public_project allowlist prevents internal pricing leaks
- Standalone only after zero-duplication preflight
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.12 EC11 — Creative Studio and AI Credits  _(SUPERSEDED — this old EC11 slot is now split across new EC16 Shared AI Gateway/Credits and new EC17 Studio AI Tools [OWNER REVIEW REQUIRED HOLD])_

**Purpose:** Adopt AI tool catalog, build provider abstraction, credit ledger, AI history, generated assets, review gates, and cost controls.

**Included work**
- REB 24-tool catalog extracted
- New provider adapter and credit ledger
- ORIG assistant behavior used as reference
- Generated files use DocuLink review gates

**Exit conditions**
- No generation without metering
- Provider failures refund credits
- No autonomous money/message actions
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.13 EC12 — Control Center, Platform Governance, Help, and Community  _(SUPERSEDED — this old EC12 slot is now split across new EC12 Tasks/Kanban/Messages/Calendar/Community, new EC19 Onboarding/Help, and new EC20 Platform Admin/Analytics/Dunning/Support)_

**Purpose:** Tenant configuration, platform admin, subscription administration, community, support, onboarding, help, and release notes.

**Included work**
- REB platform admin and community scaffolds targeted refactor
- MVP settings/permissions/audit remain authoritative
- Help content may copy static FEB docs after terminology review

**Exit conditions**
- Platform-only permission scope
- Read-only view-as if approved
- Support and community workflows audited
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.14 EC13 — Commercial Billing, Marketing, and Public Pricing  _(SUPERSEDED — this old EC13 slot is now split across new EC13 Commercial Billing/Entitlements/Fees/Trials/Setup and new EC21 Marketing Website/Public Pricing/Founder Offer/Signup)_

**Purpose:** Finalize plans, founders offer, trials, add-ons, AI top-ups, subscription checkout, marketing site, and public pricing.

**Included work**
- REB billing_rules extracted as candidate catalog only
- New subscription billing and entitlement orchestration
- ORIG marketing pages as design/content reference

**Exit conditions**
- Owner-approved values only
- Upgrade/downgrade preserve data
- Checkout and cancellation tested
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

## 30A.15 EC14 — Commercial Release Hardening  _(SUPERSEDED — this old EC14 slot is now new EC22 Final Integration and Commercial Release Hardening)_

**Purpose:** Full cross-tenant, permission, portal, financial, integration, accessibility, performance, operations, and release-gate verification.

**Included work**
- All modules and integrations
- Commercial release gate from Final Scope Register

**Exit conditions**
- No blocker open
- Cross-tenant and permission matrix pass
- Financial reconciliation pass
- Operations and rollback documented
- Evidence package lists files changed, routes/models/collections/indexes affected, tests run, known issues, documentation updated, and rollback instructions.
- The next checkpoint does not begin automatically.

# PART 30 — PROGRAM CHECKPOINT DETAIL PAGES

## 30.1 CP1 — Product Rules, Security Guards, and Money Policy Landing

**Purpose:** Land every non-negotiable rule so subsequent checkpoints are safe by construction.

**Included work:**
- Modules: Authentication, Tenants, Users, Roles, Permissions catalog (Part 9.3), Application Shell, Navigation (LOCKED sidebar + flyouts), Shared UI Components, Object Storage, File Uploads, SendGrid Outbound Email, Error Logging, Audit Log base, Sequence Generation, Pricing Foundation + Setup + Shop Rate + Labor Rates + Calculators + Administration (all under Control Center → Pricing Defaults).
- Shared: Terminology lock in code (grep-guard on `job`, `job_ticket`); Money policy landing (`_cents` convention documented + starter tests); Startup guards (dev-bypass block, JWT placeholder block).
- Frontend: Collapsible left sidebar shell with side flyouts; Home + six areas + divider; no permanent second-level top nav.
- Backend: `require_permission()` catalog updated; Pricing Defaults surface routes; audit event schema documented.
- Documentation: `AGENT_INSTRUCTIONS.md` updated with LOCKED rules.

**Dependencies:** none.

**Entry conditions:** Decisions 1, 2, 24 owner-approved. Working MVP tests green.

**Implementation sequence:**
1. Land the terminology grep-guard (fail CI if `job|job_ticket|job_item|production_ticket|job_ticket_summary` appear in canonical code paths outside a curated "quotes to prohibit" list).
2. Land the money policy contract: add `_cents` linting rule + starter tests demonstrating no unsuffixed money fields on Quote/Order/Invoice/Payment.
3. Land the startup guards: `ENV=production` + `AUTH_DEV_BYPASS=true` = fail; placeholder JWT secret = fail; missing SendGrid webhook secret (production) = fail; missing Stripe webhook secret when Stripe writes = fail.
4. Update the permissions catalog to match Part 9.3 of Final Scope Register.
5. Rebuild the Application Shell with the LOCKED sidebar + side flyouts (no permanent second-level top nav).
6. Ensure Pricing Defaults surface reads under Control Center flyout.

**Testing requirements:** startup-guard test on ENV=production; permission matrix test on every existing endpoint; nav render test on every flyout; money-suffix lint test.

**Exit conditions:** startup guards active; permission matrix passes; nav renders per Part 3.3; grep-guard passes.

**Evidence package:** per Part 23.

## 30.2 CP2 — Shared Platform Foundations

**Purpose:** Land shared services every module depends on.

**Included work:**
- Modules: Settings Framework, Notifications, Email Activity + SendGrid webhook, Upload Validation, Attachments (polymorphic + document_shares), Webhook Infrastructure, Feature Entitlements scaffold, Background Jobs scaffold, Portal Auth foundation (identity model + magic-link + public-token infrastructure), Company Settings, Users & Permissions surface, Integrations surface, Portals settings, Feature Access, Data & Security.
- Documentation: per-module README + Portal Auth doc.

**Dependencies:** CP1.

**Entry conditions:** CP1 COMPLETE. Decisions 3, 4, 8 owner-approved.

**Implementation sequence:**
1. Settings Framework (REB REF).
2. Audit Log extend to REB shape.
3. Notifications (REB REF).
4. Webhook Infrastructure (framework) + SendGrid webhook + email activity (fail-closed rule).
5. Upload Validation (REB EXTRACT).
6. Attachments (adopt REB `file_links`, `document_links`, `document_shares`).
7. Feature Entitlements scaffold (REB REF).
8. Background Jobs scaffold (ORIG REF + REBUILD).
9. Portal Auth foundation: `portal_identities`, `magic_link_tokens`, `public_action_tokens`; magic-link + password login endpoints; single-action token issuance + consumption utility.

**Testing requirements:** cross-tenant sweep per module; webhook signature verify; entitlement flip test; portal identity isolation smoke test.

**Exit conditions:** all shared services expose endpoints + repositories; foundations covered by smoke tests.

## 30.3 CP3 — Core Money and Order Pipeline

**Purpose:** Complete the customer → quote → order → invoice → payment spine.

**Included work:** see Part 10.

**Dependencies:** CP1, CP2.

**Entry conditions:** CP2 COMPLETE. Decisions 1, 9, 15 owner-approved. Integration playbook for Stripe Core obtained.

**Implementation sequence:**
1. Customers extend (portal-linkable).
2. Quotes shape rebuild (REB REF: line items + expiration + revisions + snapshot).
3. Quote-to-Order idempotent conversion (KEEP + EXTEND).
4. Orders rich item schema (REB REF: 40+ fields).
5. `production_required` gate (`services/order_item_rules.py`).
6. Order Pricing Snapshots.
7. Work Orders rework to snapshot only `production_required=True` items.
8. Work Order Summary printable.
9. Invoice dual status (FEB EXTRACT).
10. Payment unified (FEB EXTRACT).
11. Stripe Core integration (playbook + confirm-on-webhook + idempotency).
12. Tax snapshot on Invoice.

**Testing requirements:** all commerce tests; money safety on every field; payment idempotency; overpayment reject; controlled void; refund path; Stripe webhook signature-verify + replay; cross-tenant sweep on every module.

**Exit conditions:** every spine module passes cross-tenant + permission + payment idempotency; Stripe test-mode e2e passes.

## 30.4 CP4 — Documents, Portals, and Customer Workflow

**Purpose:** DocuLink→Asset Library, Templates, Forms, Questionnaires, Signatures, Proofs, Approvals, Customer Portal, Public Forms, Public Proof Approval, Public Signatures.

**Included work:** see Part 11.

**Dependencies:** CP1, CP2, CP3.

**Entry conditions:** CP3 COMPLETE. Decisions 8, 22 owner-approved. Preflights PF1, PF3, PF4, PF5, PF6 complete.

**Implementation sequence:**
1. Asset Library (DocuLink) — REB EXTRACT + REBUILD (rewire storage to Emergent).
2. Templates (doc + email).
3. Forms + Questionnaires (rate limit + captcha).
4. Signatures (REF + preflight; single-action tokens).
5. Proofs (REF + preflight).
6. Approvals (REF + preflight; dual-parent).
7. Customer Portal (REBUILD): magic-link login, orders view, quote approve, proof approve, sign, pay (Stripe card via Decision 22).
8. Public Forms + Public Quote Requests + Public Customer Intake.
9. Public Proof Approval + Public Signature pages (scoped tokens).

**Testing requirements:** cross-tenant + portal isolation + public-token single-action + magic-link single-use + captcha + rate limit tests; E2E flow of quote-approve → order-created → invoice-issued → invoice-paid via customer portal.

**Exit conditions:** end-to-end customer portal flow works.

## 30.5 CP5 — Inventory, Purchasing, Finance, and Reporting

**Purpose:** see Part 12.

**Included work:** Inventory, Vendors, Purchasing (Shop Ops nav); Financials, Sales, Expenses, Taxes, Reports, Custom Report Builder, Business Analytics (Business & Finance nav). Grouped in one CP due to shared dependency on CP3.

**Dependencies:** CP1, CP2, CP3.

**Entry conditions:** CP3 COMPLETE. Decisions 9, 20 owner-approved. Preflights PF10, PF11, PF12, PF15, PF16 complete.

**Implementation sequence:**
1. Inventory + Vendors + Purchasing (REBUILD).
2. Received PO → Expense row.
3. Material cost history.
4. Financials aggregations.
5. Sales + Expenses + Taxes.
6. Reports curated catalog.
7. Custom Report Builder v1 (column + filter + group-by).
8. Business Analytics KPIs.

**Testing requirements:** report tenant scoping; historical invoice tax snapshot invariance; expense creation from PO; inventory valuation consistency.

**Exit conditions:** financial dashboards render with live data; inventory + purchasing feed expenses + finance; reports pass tenant scoping.

## 30.6 CP6 — Team & Workflow

**Purpose:** see Part 13.

**Included work:** Employees, Tasks & Kanban, Team Schedule, Time Clock, Timesheets, Payroll, Messages & Notes, Announcements, Employee Portal, plus Install Scheduling + Production Scheduling (surfaced under Shop Operations → Shop Schedule but sharing backend).

**Dependencies:** CP1, CP2, CP3 (partial), CP4 (Employee Portal auth).

**Entry conditions:** CP4 COMPLETE. Decisions 23 owner-approved. Preflights PF13, PF14 complete.

**Implementation sequence:**
1. Employees (with employment fields).
2. Tasks + Kanban.
3. Team Schedule + Calendar + Appointments + Install/Production Scheduling.
4. Time Clock (portal + admin backup).
5. Timesheets.
6. Payroll (period Sat–Fri; payday Friday; advances; adjustments; carryover; payments; history; exports).
7. Messages & Notes + Announcements + Reminders.
8. Employee Portal.

**Testing requirements:** cross-tenant + portal isolation per employee; payroll data integrity; time-clock punch-fraud checks.

**Exit conditions:** employee end-to-end flow works.

## 30.7 CP7 — Add-ons (Webstores + Wrap Lab)

**Purpose:** see Parts 14 + 15.

**Dependencies:** CP1, CP2, CP3, CP4.

**Entry conditions:** CP4 COMPLETE. Decisions 6, 7 (direction), 15 owner-approved. Preflights PF7, PF8, PF9 complete. Stripe Connect playbook obtained.

**Implementation sequence (Webstores subteam):**
1. Feature entitlements (`webstores`, `stripe_connect`) wire-up.
2. Webstore model + setup wizard.
3. Store types + branding + slug + QR utility.
4. Per-store catalog + variants + costs + prices + owner share + platform fees.
5. Public storefront + captcha + rate limit.
6. Stripe Connect onboarding + payouts (FEB EXTRACT confirm pattern).
7. Webstore Orders through shared `orders` collection with `source=webstore`.
8. Owner + Manager Portals.
9. Webstore analytics.

**Implementation sequence (Wrap Lab subteam):**
1. Wrap Project model + 11-stage workflow (REB REF).
2. Stage gates.
3. Wrap documents in DocuLink.
4. Vehicle info + inspections + measurements.
5. Design workflow using shared Proofs + Approvals.
6. Contract + pre-install + final packet signatures using shared Signatures.
7. Deposit/payment scheduling using shared Payments.
8. Material acquisition linkage to Inventory & Purchasing.
9. Production + Installation + Aftercare.
10. Portal projection with allowlist enforcement.

**Testing requirements:** Stripe Connect payout reconciliation; webstore tenant isolation; wrap-project portal allowlist enforcement; end-to-end webstore order → payment → payout; end-to-end wrap stage flow.

**Exit conditions:** founder-launch-ready state for both add-ons.

## 30.8 CP8 — AI, Platform, and Commercial Systems

**Purpose:** Creative Studio + AI + Platform Admin + Community + Onboarding + Marketing + Public Pricing + Subscription Billing + AI Credit Purchases + Founders Promo + Transaction Fees admin.

**Dependencies:** CP1, CP2, CP3, CP4, CP5, CP7 (Stripe Connect for Webstore commercial billing paths).

**Entry conditions:** CP7 COMPLETE. Decisions 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 26 owner-approved (or DEFERRED with explicit acknowledgement for provisional). Preflights PF17, PF18, PF20 complete.

**Implementation sequence:**
1. AI Credit Ledger + provider abstraction (Emergent LLM key).
2. AI Tools Grid (catalog + execution).
3. Creative Studio pages (Overview, AI Assistant, Image/Design/Writing Tools, Prompt Library, Artwork Workspace, Generated Assets, AI History).
4. Subscription Billing (Stripe subscription; entitlement wire-up; grace period per Decision 26).
5. Add-on Purchases (Webstores, Wrap Lab, AI Credit top-ups).
6. Founders Promo (reconcile "25 redemption cap" candidate with "first 50 founders" direction).
7. Transaction Fees admin.
8. Platform Admin (Platform Governance flyout).
9. Community + Bug Reports + Feature Requests (direct flyout destinations).
10. Onboarding + Help Center + Contact Support.
11. Marketing website + Public Pricing.

**Testing requirements:** credit-ledger integrity; cost-cap enforcement; provider outage refund; subscription proration; entitlement flip on webhook; billing tenant isolation; platform impersonation audit trail.

**Exit conditions:** founder can sign up, receive credits, use AI tools, be metered; Platform Admin can suspend/reactivate tenants; commercial checkout works end-to-end.

## 30.9 CP9 — Final Integration and Commercial-Release Hardening

**Purpose:** Final gate before commercial sale.

**Included work:**
- SMS/MMS integration (only if Decision 27=a).
- Production secret rotation.
- Dev-bypass hard disable.
- End-to-end regressions across every checkpoint.
- Performance / accessibility / monitoring reviews.
- Documentation finalization.
- Terms & policies.
- Support processes.
- Marketing / pricing pages review.
- Launch runbook.
- What's New content.

**Dependencies:** all of CP1–CP8.

**Entry conditions:** CP8 COMPLETE. Decisions 19 (if 27=a), 27 owner-approved. Preflight PF21 complete (if 27=a). Preflight PF19 complete.

**Implementation sequence:**
1. Secret rotation checklist (JWT, SendGrid, Stripe, storage, AI provider).
2. Verify dev-bypass hard-disabled on prod.
3. Full regression sweep across CP1–CP8 modules.
4. Performance review (P95 latency, page-load).
5. Accessibility review (axe-core sweep).
6. Monitoring dashboards live.
7. Terms & Privacy Policy published.
8. Support ticket + email path live.
9. Marketing pages accuracy pass.
10. Launch runbook + rollback plan.
11. What's New v1 populated.
12. Optional: SMS/MMS if Decision 27=a.

**Testing requirements:** commercial-release-gate checklist (Part 15 of Final Scope Register).

**Exit conditions:** commercial-release checklist passes; no release blocker open.

---

# PART 31 — FINAL READINESS CONCLUSION

## MASTER BUILD PLAN COMPLETE — EC0 OWNER DECISIONS LOCKED; READY FOR EC1 IMPLEMENTATION

- **Program checkpoints:** 9 (PC1-PC9).
- **Execution checkpoints:** 15 (EC0-EC14).
- **Modules assigned:** 152 (every row in Part 8; 100% assignment).
- **Owner decisions total:** 27.
- **Owner decisions resolved (LOCKED / OWNER APPROVED):** 5 (Decisions 6, 7 direction, 18 direction, 24, 25).
- **Owner decisions still open:** 0. Decisions 12, 13, and 18 retain required cost/model audits before live AI commercial activation; Decision 7 retains a standalone-Wrap preflight condition.
- **Module preflights scheduled:** 20 (PF1–PF20; PF21 SMS/MMS conditional on Decision 27).
- **First implementation checkpoint recommended:** **EC1 — Security and Permanent App Guardrails.** EC0 is complete and all 27 owner decisions are recorded.
- **Code changes performed in this document:** **NONE.**
- **Next action:** Execute EC1 using this owner-approved consolidated plan. Do not rerun EC0 unless the owner explicitly changes a recorded decision.

**Exact next action:** Send Emergent the EC1 implementation prompt and require it to stop after the EC1 evidence package.

---


# APPENDIX A — SOURCE DOCUMENTS USED

This consolidated plan was produced from and must remain synchronized with:

1. `SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER (7).md` — authoritative scope, terminology, navigation, product boundaries, integrations, commercial gates, and 27-decision register.
2. `SIGNGUY_AI_FEATURE_READINESS_MATRIX (5).md` — per-feature readiness, evidence level, best source, migration path, dependencies, and verified donor behavior.
3. `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP (3).md` — repository roles, exact source-of-truth files, architecture rules, prohibited donor patterns, and target folder standard.
4. `SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN(1).md` — full 152-module governance matrix, program checkpoints, test strategy, evidence requirements, and release roadmap.
5. `SIGNGUY_AI_FINAL_SOURCE_DRIVEN_MASTER_BUILD_PLAN.md` — exact source/migration map and smaller execution checkpoint sequence.
6. `Feature Preflight Audit.txt` — reusable donor-feature investigation process.
7. `Module Documentation Template.txt` — required module documentation structure.

When this plan is updated, the changes must be reconciled back into the scope register, readiness matrix, source map, and `AGENT_INSTRUCTIONS.md`. No isolated planning fork is allowed.

---

## Appendix A — Owner-locked permanent-scope addenda (post-issue)

The following requirements are **permanent product scope** and must be delivered before EC14 Final Hardening (as originally numbered — see renumbering note below). Neither may be treated as an optional product idea, a deferred nice-to-have, or an implicit capability. Both are assigned to explicit named checkpoints below.

> **RENUMBERING NOTE (not superseded in substance — carried forward under new numbers):** The requirements in **A.1 (EC6.3 Order Intake Capture and Visual Markup)** and **A.2 (EC3.1 Pricing Foundation Verification)** remain fully required permanent scope. Under the new SignGuy AI Checkpoint Specification Pack, A.1's Order Intake/Visual Markup requirement is now carried forward and expanded inside the new **EC10 — Order Intake, Visual Markup, Customer Decision Room, and Templates**, and A.2's Pricing Foundation requirement is now carried forward and expanded inside the new **EC9 — Pricing Foundation, Detailed Calculators, and Exact Order Workflow**. A.3 (Supplier Catalog) and A.5 (Equipment/Training/Certification) below are already COMPLETE (delivered inside EC7 and EC8 respectively) and are unaffected. See `/app/memory/checkpoint_reference_table.md`.

### A.1 EC6.3 — Order Intake Capture and Visual Markup (permanent scope)

**Scope owner:** the Order-taking workflow.
**Nature:** permanent, required. NOT an optional idea. NOT part of any deferred register.
**Reuses:** EC2 FileRecord + file-link + object-storage + document-share + audit + activity; EC6 Proof + Approval + Signature Request + Signature + portal-visibility systems.
**Must not:** create a parallel file, drawing, approval, or signature system.

The Order-taking workflow must support:
- Uploading one or more images.
- Taking a photo directly from a supported phone, tablet, or computer camera.
- Attaching customer artwork, logos, PDFs, and reference files.
- Linking files to the Customer, Quote, Order, and individual Order Item.
- Drawing directly on an image.
- Freehand sketching on a blank canvas.
- Arrows, circles, boxes, text, notes, and measurement labels.
- Preserving the original image separately from every marked-up version.
- Version history for drawings and annotations.
- Attaching approved marked-up versions to Proofs, Work Orders, and Work Order Summaries.
- Intentionally controlled Customer Portal visibility.
- **In-person customer signature capture during Order intake.**
- Signature binding to the exact Order, Order Item, drawing, image version, measurements, or approval content.
- Signer name, timestamp, actor, source device or session metadata where appropriate, and immutable audit history.
- No silent overwrite of previously signed or approved content.

The product requires **both** delivery modes: (a) formal remote Signature Requests through scoped portal or public-token workflows (already delivered by EC6), and (b) fast in-person signature capture while staff are creating or reviewing an Order with a customer (delivered by EC6.3). The EC6.3 in-person capture surface must reuse the EC6 `SignatureRequest` + `Signature` schema — no second signature system.

### A.2 EC3.1 — Pricing Foundation Verification and Full Calculator Category Coverage (permanent scope)

**Scope owner:** the Pricing Foundation.
**Nature:** permanent, required. Confirms that the complete Pricing Foundation and all custom calculator categories remain required permanent scope even though EC3 shipped the initial subset.
**Reuses:** EC3 pricing services, Quote and Order Item integration, historical pricing snapshots.

The full Pricing Foundation must include (and be verified by tests using known expected pricing examples):
- Every calculator category (per master-plan pricing register).
- Category-specific fields and formulas.
- Shop rate.
- Labor.
- Materials.
- Waste.
- Markup and margin.
- Minimum charges.
- Complexity.
- Add-ons.
- Templates.
- Quote and Order Item integration.
- Historical pricing snapshots.
- Tests using known expected pricing examples for every calculator category.

### Scheduling constraint

Both EC6.3 and EC3.1 must land **before EC14 Final Hardening** and must not be silently absorbed into another checkpoint or dropped. They are visible in the progress register with explicit `REQUIRED — SCHEDULED` status until they are marked COMPLETE. Neither may become an "implied capability" — each must produce its own preflight, evidence, and pytest suite.

### A.3 EC7 — Supplier Catalog, Price Comparison, and Integrated Purchasing (permanent scope, added to EC7)

**Scope owner:** EC7 Inventory + Purchasing + Finance + Reporting.
**Nature:** permanent, required. NOT an optional product idea. Assigned to **EC7**.
**Reuses:** EC2 Settings + integration-secret storage, EC7 Materials + Inventory + Vendors + Purchase Orders + Receiving. Do NOT create a parallel PO or inventory system.

The Order-taking workflow must be able to:
- Determine required products + quantities; compare against current shop inventory; calculate shortages.
- Search connected supplier catalogs; show supplier-specific products, variants, prices, and availability.
- Compare total delivered cost (shipping/freight/MOQ/warehouse splits/lead times/expected arrival).
- Recommend purchasing options (lowest delivered cost / fastest arrival / preferred supplier / fewest splits / all-items-available / best combined score).
- Let the user select a supplier + product; create a purchasing cart or Purchase Order.
- Electronically submit when supported; otherwise prepare a PO + authorized vendor-site handoff.
- Link the supplier PO to the originating customer Order + Order Items; update expected + received inventory via EC7 receiving.

**Categories:** blank apparel (shirts/hoodies/hats), vinyl, laminate, application tape, substrates (boards/sheets), banner material, ink + print supplies, mounting hardware, installation supplies, other tenant-configured categories. Do NOT force apparel and non-apparel into one variant structure.

**Connection levels (reusable connector):** Direct API / EDI; catalog feed (CSV/XML/JSON/SFTP); Manual supplier (URL + handoff). No scraping. No automated checkout without explicit vendor authorization.

**Normalized supplier-product model:** supplier, supplier_product_id, manufacturer, brand, product family, SKU, UPC, description, category, variant attributes (color/size/width/length/thickness/finish), package quantity, purchase unit, warehouse, available quantity, account price (cents), list price, effective timestamp, lead time, minimum order, freight class, active/discontinued, source + sync timestamps. Raw supplier identifiers preserved and mapped to internal Materials.

**Price comparison:** most complete delivered cost (item + quantity breaks + account pricing + package quantity + shipping + freight + handling + MOQ surcharge + warehouse split + expected arrival + tax where relevant). Estimates labeled when live freight is unavailable. Never claim cheapest on unit price alone.

**Apparel workflow:** style + brand + color + size + qty-per-size + supplier SKU mapping + shop stock + variant-level shortage + supplier warehouse inventory + explicit substitutes only. Never silently substitute apparel brand/style/color/size.

**Vinyl/substrate workflow:** brand + series + color + finish + cast/calendared + adhesive + air-release + roll dims + sheet dims + thickness + cost per roll/sheet/lf/sqft + freight/regional availability. Never compare incompatible products as equivalent.

**Security:** supplier API keys + account credentials use EC2 integration-secret system; never exposed to frontend. Tenant-scoped account pricing (no cross-tenant leak). Every electronic order submission requires explicit user confirmation. Actor + supplier + products + amount + timestamp + request ID + response status audited. **Idempotency-Key** on every supplier-order submission (retry never double-orders). No PCI card storage.

**Reusable connector interface** ops: `search_catalog`, `get_product`, `get_variants`, `get_account_price`, `get_inventory`, `get_shipping_quote`, `create_supplier_order`, `retrieve_supplier_order`, `retrieve_tracking`, `cancel_order` (where supported). Each connector reports its supported capabilities. Foundation must work when a supplier supports only part of the list.

**EC7 scope boundary for this requirement:** normalized supplier catalog model; supplier connector contract; catalog import + sync foundation; vendor-to-material mapping; shortage calculation (Order Items vs Inventory); purchasing recommendation service; Supply Center staff interface; supplier comparison view; purchasing cart / draft-PO flow; secure connection settings; **at least one realistic end-to-end connector OR deterministic supplier test adapter** demonstrating catalog search → variant → price → availability → shortage recommendation → PO creation → idempotent supplier-order simulation → receiving into inventory; tests + documentation + evidence. Connecting every real supplier is NOT required before EC7 closes; static mock cards alone do NOT satisfy EC7.

**Preflight requirement:** produce a Supplier Integration Inventory listing every supplier the owner currently uses or expects to use. For each vendor document: categories carried; API availability; EDI availability; catalog-feed availability; account-pricing availability; inventory availability; order-submission availability; auth method; approval / partnership requirements; rate limits; ToS restrictions; fallback integration method. Every capability marked **verified / unavailable / pending vendor confirmation** — never guessed.

### A.5 EC8 — Equipment, Training, and Certification (permanent scope, added to EC8)

**Scope owner:** EC8 Team, Scheduling, Time, and Payroll.
**Nature:** owner-locked, permanent, required. Added to EC8 by explicit owner directive (2026-07, EC8 preflight). NOT an optional idea, NOT a separate checkpoint — assigned to **EC8**, delivered in EC8 phase 8e.
**Reuses:** EC2 Files + Documents (training materials: manuals/videos/SOPs); EC1 audit/activity; EC5 Work Order assignment (extended, not duplicated). Do NOT create a parallel file-storage or approval system.

EC8 must additionally deliver:
- **Equipment** records (printers, laminators, plotters, cutters, heat presses, embroidery machines, lifts, vehicles, specialty tools, other safety-sensitive or expensive equipment) with category, location, status, `safety_sensitive` flag, `certification_required` flag, and linked training materials/manuals/videos/procedures/maintenance references (via existing Files/Documents).
- **Training** assignments per employee (reading, video, SOP review, quiz, practical demonstration, manager signoff, retraining) with due date, progress, completion, quiz score, attempt history, acknowledgement, manager approval, and audit trail.
- **Certification** records per employee per Equipment (`not_started/in_progress/pending_signoff/certified/expired/revoked/failed`) with issued/expiration dates, trainer/approver, required vs. actual score, practical signoff, restrictions, renewal, and revocation — all audited, never overwritten in place.
- **Work Order assignment enforcement:** Work Orders may declare required equipment/certification/skill/role. Assignment lacking the required certification for `safety_sensitive` equipment is **hard-blocked by default** at the backend service layer (never frontend-only); a manager may override only with a required reason, which is always audited. Non-safety-sensitive skill/role gaps produce a warning, not a hard block. See `/app/preflight/EC8_TEAM_SCHEDULING_TIME_PAYROLL_EMPLOYEE_PORTAL_PREFLIGHT.md` §6.11 for the full warning/hard-block/override matrix.
- **Reporting:** certification matrix, expiring certifications, incomplete training, equipment access report — delivered through the existing EC7 report/export foundation, not a second report builder.

**EC8 scope boundary:** this addendum does not change EC8's dependency ordering relative to EC1–EC7, does not reopen EC7, and does not introduce a second Files/Documents/Audit/Reports system. It is delivered as EC8 phase 8e, after Employees (8a) and before EC8 closure (8f).

### A.4 Commercial Authority — Revised Pricing, Fees, Onboarding, Trials, Annual, AI Credits (REVISED 2026-07)

> **⚠️ SUPERSEDED NOTICE (2026-02 intake):** A.4 below (and its source `/app/docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md`) is now **SUPERSEDED — HISTORICAL REFERENCE ONLY** by the new SignGuy AI Checkpoint Specification Pack's **EC13 — Commercial Billing, Entitlements, Fees, Trials, and Setup Packages** (plus **EC19 — Onboarding** for setup-fee display and **EC21 — Marketing/Public Pricing** for public pricing-page rules). Almost all numeric values below (Founder $119→$189, 25 shops, Core/Webstores/Wrap/Complete add-on pricing, credit packs, setup fees, trial terms, day-based grace period) are **CONFIRMED UNCHANGED** by the new EC13 document. **One contradiction was found and is NOT silently resolved:** the new EC13 document introduces distinct **standalone** pricing (Webstores standalone $109/month, Wrap Lab standalone $139/month, both "provisional") whereas A.4 below prices standalone products the **same as the add-on price** (Webstores $89/month, Wrap Lab $119/month). This is registered as an open contradiction requiring explicit owner resolution before EC14 (Webstores) or EC15 (Wrap Lab) implementation — see `/app/memory/owner_specification_hold_register.md`. Also note: EC20 (Platform Admin) introduces a "3-strikes" dunning model that appears to conflict with the day-based grace period (Days 1-7/8-14/14+) below, also registered as an open contradiction.

**Source of truth:** `/app/docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md`.
**Revision:** REVISED-2026-07 (July 2026 owner-approved revision).
**Effect:** Appendix A.4 is the durable commercial authority. Prior conflicting numeric commercial values in this plan and in the Scope + Decision Register are SUPERSEDED by A.4 and clearly labeled as historical provenance ("SUPERSEDED BY REVISED COMMERCIAL AUTHORITY — 2026-07 — NOT FOR IMPLEMENTATION").
**Implementation rule (LOCKED):** none of A.4 is built inside EC7. A.4 is scheduled to EC11 / EC12 / EC13 as defined below.

#### A.4.1 Corrected checkpoint assignments (LOCKED)

| EC | Scope owner | Owns |
|---|---|---|
| **EC11 — AI Credits and Usage Ledger** | AI Metering | Usage ledger; provider / model cost tracking; included monthly balances (reset); top-up balances (persistent while account active); monthly resets; purchased-credit retention; refunds and adjustments; **configurable, plan-aware** launch guardrails (NOT permanently hardcoded); low-credit warnings; zero-balance blocking; provisional credit packs; cost-audit gate. |
| **EC12 — Onboarding, Documentation, Help, and Governance UX** | Product Onboarding + Support | Quick Setup wizard; Advanced Setup wizard; setup mini quizzes; setup checklist; progress tracking; setup readiness; contextual explanations; help articles; Settings mapping; save-and-continue-later; staff-assisted setup workflow; onboarding support checklist; documentation registry; module documentation; Help Center; documentation-grounded AI Help; support escalation; documentation-gap reporting; **failed-subscription warning + restriction UX**. EC12 may **display** subscription state but does NOT own billing truth. Onboarding wizard MUST work for DIY customers without requiring a paid package. |
| **EC13 — Commercial Billing and Marketing** | Commerce / Stripe / Marketing | Founder eligibility (first 25 shops); $119 for first three paid months; $189 Founder monthly renewal; $1,890 Founder annual; Core $149 / $1,490; Webstores $89 / $890; Wrap $119 / $1,190; Complete $279 / $2,790; trials; paid extended trial; $20 conversion credit; setup products + add-ons; annual billing; platform fees; Stripe products / prices / coupons; entitlements; grace periods; continuous-active Founder enforcement; public pricing page; marketing website; signup + conversion flows. Paid setup purchases MUST NOT create a parallel onboarding system — EC13 charges for setup; EC12 delivers the wizard. |

**Do not skip.** Each EC gets its own preflight before code writes. EC14 Final Hardening closes only after EC11 / EC12 / EC13 are COMPLETE.

#### A.4.2 Founder Edition (active — REVISED 2026-07)

- Availability: **first 25 signed shops**. Founder Edition closes when the 25 slots fill.
- Monthly path: **$119/month** for months 1–3, then **$189/month** while continuously active.
- Annual path: **$1,890/year upfront**; replaces the 3-month monthly introductory promotion.
- Included software: Core SignGuy AI OS + Webstores + Wrap Command Center + Customer Portal + documents + approvals + production + pricing + invoicing + payments + platform improvements.
- Included AI credits: **1,000/month** — provisional, subject to provider-cost audit.
- Platform-fee holiday: **0%** regular Payment platform fee **and 0%** Webstore platform fee for the first 3 paid months (Stripe processing still applies).
- After the holiday (Founder locked schedule): **0.5%** regular Payment platform fee, **1.5%** Webstore platform fee — locked while the account stays continuously active.
- Setup: **$299 Founder Kickstart Setup** required unless a specifically approved waiver.
- Founder pricing remains locked only while the account stays continuously active.
- Implementation: use a Stripe promotion / coupon for the $119 introductory period. Never create a permanent Founder product SKU. EC13 owns backend enforcement.

#### A.4.3 General Availability (active — REVISED 2026-07)

| Product | Monthly | Annual | Included monthly AI credits |
|---|---|---|---|
| SignGuy AI OS — Core | $149 | $1,490 | 300 |
| Webstores Add-On | $89 | $890 | 300 |
| Wrap Command Center Add-On | $119 | $1,190 | 500 |
| **Complete Bundle** | **$279** | **$2,790** | **1,100** |
| **Webstores Standalone** | **$89** | **$890** | **300** |
| **Wrap Command Center Standalone** | **$119** | **$1,190** | **500** (only after standalone readiness is verified) |

Standalone-readiness verification is a prerequisite before Wrap Command Center Standalone may be sold publicly. If later analysis shows standalone products need higher pricing than add-ons, that requires a **separate owner decision** — not a documentation cleanup change.

#### A.4.4 Platform Transaction Fees (active — REVISED 2026-07)

Fees are backend-calculated, snapshotted per transaction, plan-aware, tenant-scoped, and auditable. Fee display must be clear before checkout / payout where legally appropriate. Frontend must never set or alter fee rates.

| Account status | Regular Payment platform fee | Webstore platform fee |
|---|---|---|
| Founder months 1–3 | 0% | 0% |
| Founder month 4+ | 0.5% | 1.5% |
| General Availability | 1.0% | 2.0% |
| Custom / enterprise | negotiated after real volume | negotiated after real volume |

Refunds and partial refunds require a documented proportional-fee policy. Fees stay separate from Stripe processing, tax, supplier charges, shipping, and customer-facing line items.

#### A.4.5 AI Credits & Credit Packs (active — REVISED 2026-07)

Provisional launch prices — subject to provider-cost audit before final lock.

| Pack | Credits | Launch price | Expiration |
|---|---|---|---|
| Quick Fix | 100 | $19 | No expiration while subscription remains active |
| Growth Boost | 300 | $45 | No expiration while subscription remains active |
| Power Pack | 800 | $99 | No expiration while subscription remains active |

- Included monthly credits reset each billing cycle (no rollover).
- Top-up (purchased) credits are consumed only after included credits and remain available while the paid account remains active.
- **Guardrails at launch — PROVISIONAL CONFIGURABLE LAUNCH GUARDRAILS — SUBJECT TO PROVIDER-COST AND USAGE REVIEW**:
  - 20 image generations / tenant / day (starting value)
  - 50 AI assistant messages / tenant / day (starting value)
  - 3 historical invoice analyses / tenant / day (starting value)
  - Low-credit warning at 20% remaining
  - Block paid AI actions at 0 credits
- **EC11 must implement these as configurable, plan-aware controls — not hardcoded permanent limits.**
- Log provider + model + tokens/units + estimated cost + feature + tenant + outcome for every billable AI action.
- Credit allotments (Founder + GA) reviewed after 10–20 active paying shops; never retroactively reduce an active Founder promise.

#### A.4.6 Onboarding & Setup (active — REVISED 2026-07)

**Split ownership** (Option B):
- **EC12 owns the guided onboarding product experience** — Quick Setup, Advanced Setup, mini quizzes, setup checklist, progress tracking, setup readiness, contextual explanations, help articles, Settings mapping, save-and-continue-later, staff-assisted setup workflow, onboarding support checklist, documentation + AI Help Center integration.
- **EC13 owns the paid onboarding purchase + billing** — setup-package products, discounts / waivers, checkout, payment status, receipts, service entitlement or purchase records, billing + refund behavior.
- Onboarding wizard MUST work for DIY customers without requiring a paid package. Paid setup purchases MUST NOT create a parallel onboarding system.

| Package | Price | Availability |
|---|---|---|
| DIY Guided Setup | $0 | all plans |
| Founder Kickstart Setup | $299 one-time | first 25 Founder shops (rare waiver for case-study shops) |
| Standard Shop Setup | $499 one-time | General Availability bundle |
| Full Optimization Setup | $999 one-time | deeper configuration |
| White-Glove Implementation | $1,999+ (quoted) | larger shops / messy data / multiple locations |

Setup add-ons (locked prices): Additional Webstore Setup Basic $199; Advanced $399; Large Catalog Build $699+; Wrap Command Center Setup $299; Historical Invoice/Pricing Import Review $399 / $799 extended; Data Import Cleanup $150/hr; Extra Training $150/hr or $249/2hr; Custom Template Build $75 each or $299/5.

Boundaries: setup fees are **separate** from subscription + AI credits + Stripe processing + platform fees. Every package requires a written checklist and a documented completion point. Setup fees collected at signup or before first assisted session.

#### A.4.7 Annual Billing (active — REVISED 2026-07)

- "Pay 10, get 12" annual discount.
- AI credits still reset **monthly** even on annual plans — do not grant a full year upfront.
- Annual plans keep the same platform-fee schedule as the matching monthly plan.
- Auto-renew at the same approved annual rate unless cancelled before renewal.
- Founder annual pricing only remains available while the account stays continuously active.

#### A.4.8 Free & Paid Extended Trial (active — REVISED 2026-07)

| Trial | Price | Length | Credits | Rule |
|---|---|---|---|---|
| Free Trial | $0 | **48h** — begins on verified activation / explicit trial start | 25 AI credits | Limited access, sample data, checklist. No custom setup work. |
| Extended Trial | $20 | 7 days | 75 total credits | Apply the $20 credit toward first paid subscription if purchased within 14 days after trial expiration. |

Controls: one trial per business / owner / verified domain unless manually approved; live card / SMS / regulated integrations may stay disabled until verification; countdown + expiration + export + conversion behavior explicit.

#### A.4.9 Failed Subscription & Access State (active — REVISED 2026-07)

| Period since last-good payment | Access |
|---|---|
| Days 1–7 | Normal access with prominent billing warnings and retry notices. |
| Days 8–14 | Soft restrictions on add-ons and new AI usage. Core data remains accessible. |
| After day 14 | Paid modules blocked. Customer data preserved. Billing + export + support + account-recovery remain available. Never auto-delete tenant data because a subscription failed. Never block billing / export / support / privacy / data-deletion tools. Reactivation restores entitlements idempotently. Founder pricing is not guaranteed after cancellation or unresolved lapse beyond the approved grace period. |

Owned by EC13 (billing truth). EC12 owns the **warning + restriction UX**; it does not own the underlying enforcement.

#### A.4.10 Continuously Active Founder Enforcement — architecture reservation (LOCKED)

The following tenant / subscription commercial-state fields are permanent architecture requirements owned by EC13. **Do NOT add them to the production database in EC7** — they are documented here so their names and semantics remain stable across checkpoints:

- `founder_status`
- `founder_slot_number`
- `founder_activated_at`
- `founder_intro_started_at`
- `founder_intro_ends_at`
- `founder_locked_monthly_price_cents`
- `founder_locked_annual_price_cents`
- `founder_continuously_active`
- `founder_lost_at`
- `founder_loss_reason`
- `subscription_current_period_end`
- `subscription_grace_period_ends_at`
- `commercial_terms_version`

EC13 must implement: backend enforcement, Founder slot allocation, continuous-active evaluation, grace-period handling, Founder loss rules, audit history, historical terms snapshotting, Stripe subscription mapping. This is **not** an EC1 startup guard — it is commercial state and belongs to EC13.

#### A.4.11 Rollout Discipline (LOCKED)

- **Phase 1 (Founder):** sell only the complete Founder Edition to the first 25 shops.
- **Phase 2 (Review):** after 10–20 active paying shops, review adoption + AI cost + support burden + payment volume + churn + Webstore demand.
- **Phase 3 (GA):** open GA using the $279 bundle + approved Core / add-on / verified standalone prices.
- Never change active Founder pricing. Updated pricing applies only to new customers after Founder availability closes.

#### A.4.12 Commercial Source-of-Truth Rule (LOCKED)

Any subsequent commercial-numbers document must supersede this one **explicitly** with a new revision date. Older conflicting commercial numbers are superseded by A.4 until a new owner-approved revision is entered into this appendix. Marketing copy, Stripe product map, entitlement rules, onboarding packages, and billing tests must always match A.4.

