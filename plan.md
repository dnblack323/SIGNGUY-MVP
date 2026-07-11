# SignGuy AI (FARM) — UPDATED plan.md (Permanent Product)

## Objectives (Updated)

- ✅ Deliver a working multi-tenant shop-management **permanent product foundation**: **Customer → Quote → Order (+OrderItems) → Work Orders (0..N) → Invoice (0..1) → Payments**, with shared **Documents**, **Email**, **Audit**, **Dashboard**.
- ✅ Prove and integrate the two failure-prone integrations first:
  1) **Mongo atomic sequence generator** (race-safe)
  2) **Object storage** upload/download with tenant-scoped storage paths
- ✅ Enforce non-negotiables throughout: **tenant isolation**, **one permission dependency**, **idempotency guards**, **append-only audit/activity events with REQUIRED actor fields**, **no `_id` in API responses**, **money policy explicitly documented**, correct terminology (**Order / OrderItem / Work Order**, never “Job / Job Ticket”).
- ✅ Provide a **Dev Auth Bypass** mode to allow UI testing without login when desired (**AUTH_DEV_BYPASS=true**), with a prominent UI banner and an explicit requirement to disable in production.
- ✅ Complete donor-repo evidence audit and lock the permanent roadmap **with accurate evidence labels**:
  - `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` corrected with explicit evidence levels (**RV / STHV / FSV / PSI / SS / SO / RS**).
  - `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` corrected and completed (Parts 1–11) with the same evidence discipline.
  - `SIGNGUY-AI-OS` confirmed as a **mirror of MVP under `backend/app/**/*.py` (STHV, scoped)** → **freeze against new development**; complete-tree comparison and archival timing deferred to owner.

> **Stage-numbering disclaimer (plan-level):** Any stage/phase number retained in this plan refers only to a prior proposed sequence. Prompt 3 and the final master build plan may rename, reorder, combine, or replace phases based on the final dependency analysis.

- 🔜 Next hardening steps (permanent product build-out; not “post-MVP defer”):
  - Record and sign off the **owner-decision items** in `memory/AGENT_INSTRUCTIONS.md` (see Next Actions section).
  - Security production gates: force-fail on `AUTH_DEV_BYPASS=true` in production; rotate JWT secret away from dev placeholder.
  - Extract REB `upload_validation.py` into MVP for stronger MIME/magic-byte/size/SHA-256 enforcement.
  - Correctness upgrades: Quotes line items + pricing snapshots; `production_required` gate for Work Orders; invoice dual-status + payment reconciliation + void behavior.

---

## Phase 0 — POC (Isolation): Mongo atomic numbering + Object Storage
**Status:** ✅ Completed

**User stories**
1. As an admin, I want Quote/Order/WorkOrder/Invoice numbers to be unique per tenant even under concurrent creates.
2. As a staff user, I want to upload a file once and attach it to multiple records without re-uploading.
3. As a staff user, I want files to be private-by-default and accessible only when authorized.
4. As an admin, I want storage paths to enforce tenant isolation.
5. As a developer, I want a storage abstraction so we can swap providers later.

**Implementation steps (as delivered)**
- ✅ Implemented atomic sequence generator using Mongo `find_one_and_update($inc)` + upsert.
- ✅ Implemented Emergent object storage adapter using platform integration.
- ✅ POC script: `backend/scripts/poc_core.py`
  - Concurrency test for counters (0 duplicates, per-tenant isolation).
  - Upload + download integrity verification.
  - Tenant-scoped storage key convention.

**Deliverables**
- ✅ `scripts/poc_core.py` proves both atomic sequences and object storage round-trip.
- ✅ Storage abstraction in backend (`app/services/storage.py`).

**Success criteria**
- ✅ Sequence POC: 0 duplicates under concurrency; tenant-isolated counters.
- ✅ Storage POC: upload+download works; tenant path isolation enforced.

---

## Phase 1 — Scaffold + Auth + Tenant + Permissions + Sequence (App foundation)
**Status:** ✅ Completed

**User stories**
1. As a user, I can register a tenant and log in to get a backend-verified session.
2. As an owner, I can create staff users and assign roles.
3. As staff, I can only access routes my role permits.
4. As any user, I can request a password reset and use a single-use token within 60 minutes.
5. As the system, every entity created gets a tenant-scoped sequential number when applicable.

**Implementation steps (as delivered)**
- ✅ Fresh repo scaffold (no prior repo code copied).
- ✅ FastAPI backend with Motor/Mongo.
- ✅ Auth: bcrypt password hashing, JWT access token, logout.
- ✅ Password reset: single-use token, 60-minute expiry.
- ✅ Tenant model and tenant_id on every domain record.
- ✅ Exactly one shared permission dependency (`app/deps.py::require_permission`).
- ✅ Permissions are fetched by frontend from `/api/auth/me` (no frontend-maintained permission enum).
- ✅ Shared atomic sequence service (`app/services/sequence.py`).

**Deliverables**
- ✅ Working auth, roles, permissions, tenant isolation, atomic numbering.

**Success criteria**
- ✅ Testing agent verified auth flows and permission enforcement (staff cannot `user:write`).

---

## Phase 2 — Customers
**Status:** ✅ Completed

**User stories**
1. As staff, I can create a Customer with contact info and notes.
2. As staff, I can search/list customers and open a profile.
3. As staff, I can edit customer details with audit history recorded.
4. As staff, I can see linked Quotes/Orders/Work Orders/Invoices/Emails on the customer page.
5. As owner, I can’t see another tenant’s customers even if I guess an ID.

**Implementation steps (as delivered)**
- ✅ Customer CRUD endpoints.
- ✅ Customer list + detail UI.
- ✅ Related-records endpoint `/api/customers/{id}/related`.
- ✅ Audit logging wired for create/update/archive.

**Deliverables**
- ✅ Customers pages + API + audit events.

**Success criteria**
- ✅ Cross-tenant fetch returns 404; audit events recorded.

---

## Phase 3 — Quotes (manual price) + Convert-to-Order (idempotent)
**Status:** ✅ Completed

**User stories**
1. As staff, I can create a draft Quote with manual total price.
2. As staff, I can set Quote status draft/sent/approved/declined.
3. As staff, I can convert a Quote to exactly one Order (double-click safe).

**Implementation steps (as delivered)**
- ✅ Quote CRUD + status endpoints.
- ✅ Sequential quote numbering.
- ✅ Convert-to-order idempotency implemented with `find_one_and_update` claim guard.
- ✅ Frontend quote list/detail + convert button.

**Deliverables**
- ✅ Quote module + conversion workflow.

**Success criteria**
- ✅ Testing agent verified idempotent convert returns same order on repeated calls.

---

## Phase 4 — Orders + Order Items
**Status:** ✅ Completed (baseline)

**User stories**
1. As staff, I can create an Order for a customer (from quote or standalone).
2. As staff, I can add 1..N Order Items with manual description + manual price.
3. As staff, I can move order status through draft→confirmed→in_production→completed/cancelled.

**Implementation steps (as delivered)**
- ✅ Order CRUD + status transition endpoint.
- ✅ Order items sub-resource endpoints.
- ✅ Frontend order list/detail with inline editable items table.

**Deliverables**
- ✅ Orders + Order Items fully usable.

**Success criteria**
- ✅ Testing agent verified order item add/update/delete + status transitions.

**Permanent-product upgrade notes (from donor evidence audit)**
- 🔜 REB model is significantly richer (40+ OrderItem fields, pricing snapshots, `production_required`, entry modes, QC, artwork/proof flags). This is a planned build-out, not an optional defer.

---

## Phase 5 — Work Orders (0..N per Order)
**Status:** ✅ Completed (Multiple per Order enabled)

**User stories**
1. As staff, I can create multiple Work Orders for one Order.
2. As staff, I can include production instructions + internal notes.
3. As staff, I can set production status (not_started/in_progress/on_hold/completed).
4. As staff, I can snapshot Order Items into the Work Order at creation.

**Implementation steps (as delivered)**
- ✅ WorkOrder model + sequential numbering.
- ✅ Create-from-order service that snapshots order items.
- ✅ Frontend list/detail with production status updates.

**Deliverables**
- ✅ Work Orders module with status.

**Success criteria**
- ✅ Testing agent verified multiple work orders per single order.

**Permanent-product upgrade notes (from donor evidence audit)**
- 🔜 Correction required: Work Orders must snapshot only `production_required=True` items (REB `services/order_item_rules.py` provides the default gate). This is a targeted replacement/extension, not a rebuild.

---

## Phase 6 — Invoice (0..1 per Order) + Payments
**Status:** ✅ Completed (baseline)

**User stories**
1. As staff, I can create an Invoice from an Order once (idempotent guard).
2. As staff, I can record multiple partial payments and see balance due.
3. As staff, invoice status updates automatically (partially_paid/paid).

**Implementation steps (as delivered)**
- ✅ Invoice model with unique index `(tenant_id, order_id)` to enforce one-per-order.
- ✅ Invoice creation endpoint returns `already_exists=true` when attempted twice.
- ✅ Payment model linked to invoice; idempotency via `Idempotency-Key`.
- ✅ Auto status derivation after payments.
- ✅ Frontend invoice list/detail + payment panel.

**Deliverables**
- ✅ Invoices + payments working end-to-end.

**Success criteria**
- ✅ Testing agent verified invoice idempotency + payment dedupe + paid status.

**Permanent-product upgrade notes (from donor evidence audit)**
- 🔜 Financial migration is planned and evidence-backed (FEB `InvoiceService`/`PaymentService` are FSV for specific files):
  - Independent `document_status` vs `financial_status`.
  - Void-with-reason (manual only).
  - Overpayment rejection.
  - Stripe two-step (pending → webhook confirm) when Stripe is introduced.
  - Central reconciliation formula ownership.

---

## Phase 7 — Documents/Files + Attachments (shared)
**Status:** ✅ Completed (baseline)

**User stories**
1. As staff, I can upload a file once and attach it to records.
2. As staff, I can mark a file internal-only or customer-visible.
3. As staff, I can download/view only when authorized.
4. As owner, I can verify no file endpoint works without auth + tenant scope.

**Implementation steps (as delivered)**
- ✅ `files` collection (metadata + storage_key) + `attachments` collection.
- ✅ Upload endpoint `POST /api/files/upload` (multipart) with validation.
- ✅ Download + view endpoints proxy through backend and require auth/tenant scope.
- ✅ Tenant path enforcement: storage key must contain `/tenants/{tenant_id}/`.
- ✅ Frontend Documents page (upload/list/toggle visibility/download/archive).

**Deliverables**
- ✅ App-wide shared file system.

**Success criteria**
- ✅ Testing agent verified unauth download blocked (401) and cross-tenant blocked (404).

**Permanent-product upgrade notes (from donor evidence audit)**
- 🔜 Extract REB `upload_validation.py` for magic-byte + MIME + size + SHA-256 enforcement.
- 🔜 Build DocuLink (REB scaffold) on top of this foundation: polymorphic `file_links`, `document_links`, and `document_shares` (with `customer_visible` + `access_level`).

---

## Phase 8 — SendGrid Email + Email Log
**Status:** ✅ Completed (live integration)

**User stories**
1. As staff, I can draft a custom message and send email for Quote/Invoice/general.
2. As staff, I can use templates: Quote sent, Invoice sent, Invoice reminder, Document sent, General.
3. As staff, I can see email history.
4. As staff, email failures are logged and shown clearly.

**Implementation steps (as delivered)**
- ✅ Shared email service (`app/services/email.py`) with SendGrid SDK.
- ✅ EmailLog stored and queryable from `/api/emails/history`.
- ✅ Frontend compose modal and Email History page.

**Deliverables**
- ✅ Email send + templates + log.

**Known gap / next step (permanent product)**
- 🔜 Binary attachments to outbound SendGrid payload.
- 🔜 SendGrid inbound event webhook + email-activity tracking (REB `routes/communications.py` scaffold) with HMAC signature verification.

**Success criteria**
- ✅ Testing agent verified email send returns 201 and logs.

---

## Phase 9 — Audit review + Dashboard
**Status:** ✅ Completed

**User stories**
1. As staff, I can see a dashboard of active Orders, attention Work Orders, unpaid Invoices.
2. As staff, I can see recent emails and recent activity.
3. As owner, I can view audit history on each record.
4. As staff, every meaningful write produces exactly one audit entry.

**Implementation steps (as delivered)**
- ✅ Shared AuditEvent helper with REQUIRED actor fields (`record_audit`).
- ✅ Audit list endpoint `/api/audit`.
- ✅ Dashboard aggregation endpoint `/api/dashboard/summary`.
- ✅ Frontend dashboard page with focused lists (no charts).

**Deliverables**
- ✅ Dashboard + audit trail view components.

**Success criteria**
- ✅ Testing agent verified actor fields present for all events.

**Permanent-product upgrade notes (from donor evidence audit)**
- 🔜 Adopt REB activity-event shape where useful (`module`, `event_type`, `severity`, `changes`, richer filter endpoints).

---

## Phase 10 — Full end-to-end test pass
**Status:** ✅ Completed

**User stories**
1. As an owner, I can complete the full workflow without hitting errors.
2. As staff, I can’t access other tenants’ records/files even with direct URLs.
3. As staff, double-click actions don’t create duplicates (convert/invoice/payment/email).
4. As staff, the UI navigation pages all load and basic CRUD works.

**Implementation steps (as delivered)**
- ✅ Backend smoke + testing agent suite: auth, tenant isolation, happy-path workflow, idempotency, file auth sweep.
- ✅ Frontend smoke: navigation + create/edit flows.

**Deliverables**
- ✅ Testing report: 100% backend pass + frontend flow verification.

**Success criteria**
- ✅ Acceptance criteria met end-to-end; no unauthenticated file access; no cross-tenant leakage.

---

## Post-Phase Addendum — Dev Auth Bypass (per user request)
**Status:** ✅ Completed

**Goal**
Temporarily disable worrying about login while doing product iteration.

**Implementation**
- ✅ Backend env flag: `AUTH_DEV_BYPASS=true|false`.
- ✅ Endpoints:
  - `GET /api/auth/dev-config` → `{ dev_bypass: boolean }`
  - `POST /api/auth/dev-login` → provisions/returns a Dev Shop owner JWT (DEV ONLY)
- ✅ Frontend:
  - Auto-calls dev-login when no token exists and bypass is enabled.
  - Shows an amber banner: “Auth bypass ON… set AUTH_DEV_BYPASS=false before deploying.”

**Safety / Deployment requirement (updated)**
- 🔒 MUST set `AUTH_DEV_BYPASS=false` in production.
- 🔒 Add a startup guard to force-fail if `AUTH_DEV_BYPASS=true` AND `ENV=production`.

---

## Documentation/Audit Phase — Donor Repository Evidence Pass (Permanent Roadmap Lock)
**Status:** ✅ Completed (2026-07-11)

**Goals**
1. Correct and complete `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` using direct donor repo inspection (no user file pastes).
2. Correct and complete `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` in place (preserve Parts 1/3/3A/11 as draft findings, then verify and finish Parts 2/4/5/6/7/8/9/10).
3. Remove all language implying features are "deferred by MVP scope".
4. Produce a final consistent evidence standard: fully verified claims (FSV), partially inspected claims (PSI), reference-only claims (RS), and scoped tree-hash verification (STHV).

**Implementation steps (as delivered)**
- ✅ Inspected donor repos with explicit evidence discipline (per-file evidence levels):
  - FEB (FSV for listed files): `invoice_service.py`, `payment_service.py`, `models/payments.py`, `models/jobs.py`
  - REB (FSV for listed files): settings, communications (+ SendGrid webhook), doculink, wrap_lab, quotes, orders, invoices, access, pricing_foundation, pricing_engine, activity, webstores, platform_admin, shared_systems, upload_validation, billing_rules, order_schemas, order_item_rules
  - ORIG: `object_storage.py` (FSV), and approvals/signatures/portal (PSI — head sections only; module preflight required)
- ✅ Verified `SIGNGUY-AI-OS` matches MVP **under `backend/app/**/*.py` only** via scoped source-tree hash comparison (STHV). (No full-tree, branch, tag, or commit-history comparison performed in this phase.)
- ✅ Rewrote `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` with corrected money-representation facts, evidence levels, and corrected COPY/REF/EXT/RB decisions.
- ✅ Updated `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` in place and applied consistency-only cleanup:
  - Stage-numbering disclaimer
  - Removed claims of “no unverified findings” / “every file read line-by-line”
  - Reclassified ORIG portal/signatures/approvals as PSI
  - Downgraded REB `billing_rules.py` from canonical/final → implementation candidate requiring owner approval
  - Replaced OS repo “archive within 7 days” with freeze/compare/retain/decide-after-completion language
  - Corrected money-policy locked-vs-owner-decision split

**Deliverables**
- ✅ `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (corrected; 493 lines)
- ✅ `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` (completed; 915 lines)

**Success criteria**
- ✅ No donor-file pastes requested.
- ✅ Every donor claim has an explicit evidence label; PSI/RS are clearly separated from FSV.
- ✅ Audit documents updated in place; no competing architecture doc created.

---

## Next Actions / Backlog (Permanent Product Build-Out)

> These are the next planning items before implementation. Prompt 3 will finalize checkpoint ordering and commercial scope.

1. **SIGNGUY-AI-OS handling (owner decision: timing)**
   - Freeze against new development immediately.
   - Perform a complete-tree comparison (all tracked files, branches, tags, docs, and commit history).
   - Retain as a read-only reference throughout the build.
   - Decide archival timing after final commercial completion.

2. **Record and sign off owner-decision items in `/app/memory/AGENT_INSTRUCTIONS.md`**
   - Money representation policy:
     - **LOCKED factual finding:** MVP currently stores commerce values as integer cents and pricing configuration/calculator values as dollar-based numbers with Decimal internal math.
     - **OWNER DECISION:** ratify that observed split as the permanent money policy, including `_cents` naming and a single pricing-to-commerce conversion boundary.
   - REB permission catalog adoption (candidate; owner review required).
   - Repository pattern for new modules (candidate; owner review required).
   - SendGrid webhook secret enforcement behavior (fail-closed in production; owner sign-off).
   - Commercial pricing: confirm or replace every candidate value from REB `billing_rules.py` (plans/prices/credits/promo/fee rates).
   - Portal auth method (magic link vs password vs both).
   - Webstores mode (add-on-only vs standalone).
   - Sales-tax strategy.
   - AI provider and credit-cost model.

3. **Production safety gates (implementation later, decision now)**
   - Force-fail on `AUTH_DEV_BYPASS=true` in production.
   - Rotate JWT secret away from placeholder.

4. **Shared security hardening (implementation later)**
   - Extract REB `upload_validation.py` into MVP and enforce for all uploads.

5. **Focused correctness upgrades (implementation later; ordering set by Prompt 3)**
   - Quote upgrade: line items + pricing snapshots + expiration + approval metadata (REB model).
   - Order upgrade: pricing snapshot fields and per-item pricing override with audit.
   - Work Order correction: add `production_required` to OrderItem; Work Orders snapshot only production-required items.
   - Invoice/payment migration: introduce dual-status `document_status`/`financial_status`, central reconciliation, payment void-with-reason, overpayment reject, Stripe-ready two-step pattern.

6. **Shared platform services (implementation later)**
   - Settings framework (REB scaffold).
   - Notifications service + email activity + SendGrid inbound webhook (REB scaffold).
   - Feature entitlements service (needed for add-on modules).

7. **Findings requiring module-level verification during feature preflight (do not block Prompt 3)**
   - Customer portal (ORIG blueprint; PSI until full trace).
   - Signatures and approvals (ORIG; PSI until full trace).
   - Stripe Connect (security review required).
   - Webstores (deep donor/spec analysis required).
   - Inventory, payroll, reports, AI systems (reference-only donors require module preflight).
