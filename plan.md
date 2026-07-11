# SignGuy AI (FARM) — UPDATED plan.md (Permanent Product)

## Objectives (Updated)

- ✅ Deliver a working multi-tenant shop-management **permanent product foundation**: **Customer → Quote → Order (+OrderItems) → Work Orders (0..N) → Invoice (0..1) → Payments**, with shared **Documents**, **Email**, **Audit**, **Dashboard**.
- ✅ Prove and integrate the two failure-prone integrations first:
  1) **Mongo atomic sequence generator** (race-safe)
  2) **Object storage** upload/download with tenant-scoped storage paths
- ✅ Enforce non-negotiables throughout: **tenant isolation**, **one permission dependency**, **idempotency guards**, **append-only audit/activity events with REQUIRED actor fields**, **no `_id` in API responses**, **money policy explicitly documented**, correct terminology (**Order / OrderItem / Work Order**, never “Job / Job Ticket”).
- ✅ Provide a **Dev Auth Bypass** mode to allow UI testing without login when desired (**AUTH_DEV_BYPASS=true**), with a prominent UI banner and an explicit requirement to disable in production.
- ✅ Complete donor-repo evidence audit and lock the permanent roadmap:
  - `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` corrected with rigorous evidence levels (**RV/SV/SS/SO/RS**).
  - `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` corrected and completed (Parts 1–11).
  - Confirmed `SIGNGUY-AI-OS` is byte-identical to `SIGNGUY-MVP` (md5 tree match) → retire.
- 🔜 Next hardening steps (permanent product build-out; not “post-MVP defer”):
  - Record and sign off the **six standing architecture decisions** in `memory/AGENT_INSTRUCTIONS.md`:
    1) Money representation policy (FEB boundary compromise vs cents-everywhere)
    2) Permissions catalog adoption (REB 57-permission enum)
    3) Repository pattern adoption for new modules
    4) Canonical terminology map (Order/OrderItem/WorkOrder)
    5) SendGrid webhook secret enforcement behavior
    6) Retire `SIGNGUY-AI-OS`
  - Security production gates: force-fail on `AUTH_DEV_BYPASS=true` in production; rotate JWT secret away from dev placeholder.
  - Extract REB `upload_validation.py` into MVP for stronger MIME/magic-byte/size/SHA-256 enforcement.
  - Stage 4/5/6 correctness upgrades (quotes line items, pricing snapshots, `production_required` gate, invoice dual-status + payment reconciliation).

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
- 🔜 Stage 5/7 correction required: Work Orders must snapshot only `production_required=True` items (REB `services/order_item_rules.py` provides the canonical default gate).

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
- 🔜 Stage 6 financial migration is planned and evidence-backed:
  - FEB `InvoiceService.reconcile_invoice_financials()` is the single authoritative formula.
  - FEB `PaymentService` supports: integer cents Payment collection, idempotency 409 replay, overpayment reject, void-with-reason (manual only), Stripe two-step (pending → webhook confirm), and independent `document_status` vs `financial_status`.
- 🔜 Requires explicit sign-off on the money representation policy before porting.

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

**Implementation steps (as delivered)**
- ✅ Cloned and inspected 4 donor repos line-by-line:
  - FEB: `invoice_service.py`, `payment_service.py`, `models/payments.py`, `models/jobs.py`
  - REB: settings, communications (+ SendGrid webhook), doculink, wrap_lab, quotes, orders, invoices, access, pricing_foundation, pricing_engine, activity, webstores, platform_admin, shared_systems, upload_validation, billing_rules, order_schemas, order_item_rules
  - ORIG: `object_storage.py`, approvals/signatures/portal (head sections)
- ✅ Verified `SIGNGUY-AI-OS` byte-identical to MVP (md5 tree match).
- ✅ Rewrote `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` with evidence levels and corrected COPY/REF/EXT/RB decisions.
- ✅ Updated `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` in place:
  - Updated Parts 1/3/3A/11 against corrected matrix
  - Completed Parts 2/4/5/6/7/8/9/10
  - Appended final correction changelog and evidence sufficiency verdict (YES)

**Deliverables**
- ✅ `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (corrected)
- ✅ `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` (completed)

**Success criteria**
- ✅ No donor-file pastes requested.
- ✅ Every prior `UNK` resolved to SV/SS/SO/RS or explicitly bounded.
- ✅ Audit documents updated in place; no competing architecture doc created.

---

## Next Actions / Backlog (Permanent Product Build-Out)

1. **Retire the mirror repo**
   - Archive `dnblack323/SIGNGUY-AI-OS` (byte-identical mirror) and point README to `SIGNGUY-MVP`.

2. **Sign off and record the six standing architecture decisions**
   - Add to `/app/memory/AGENT_INSTRUCTIONS.md`:
     - Money representation policy (FEB boundary compromise vs cents-everywhere)
     - REB permission catalog adoption (57-permission enum)
     - Repository pattern for new modules
     - Terminology map (Order/OrderItem/WorkOrder)
     - SendGrid webhook secret enforcement
     - OS repo retirement plan

3. **Production safety gates**
   - Force-fail on `AUTH_DEV_BYPASS=true` in production.
   - Rotate JWT secret away from placeholder.

4. **Shared security hardening**
   - Extract REB `upload_validation.py` into MVP and enforce for all uploads.

5. **Stage correctness upgrades (per mandated build order)**
   - Stage 4 upgrade: Quotes with line items + pricing snapshots + expiration + approve/decline metadata (REB model).
   - Stage 5 fix + Stage 7: Add `production_required` to OrderItem; Work Orders snapshot only production-required items (REB rules).
   - Stage 6 migration: Port FEB InvoiceService + PaymentService + Payment model; implement dual `document_status`/`financial_status`, void-with-reason, reconciliation; add webhook infra as required.

6. **Shared platform services (Stage 2 build-outs)**
   - Settings framework (REB scaffold).
   - Notifications service + email activity + SendGrid inbound webhook (REB scaffold).
   - Feature entitlements service (needed for add-on modules).

7. **Deferred only by dependency (not by scope)**
   - Portal auth + Customer Portal (ORIG blueprint).
   - DocuLink documents/shares (REB scaffold + rewire storage).
   - Webstores / Order Portal Manager (REB specs + scaffold + ORIG feature map).
   - Wrap Lab (REB workflow engine).
   - AI credits + billing (REB billing rules + ORIG credit/billing reference).
   - Inventory/Purchasing/Vendors, Payroll/Employees/Timeclock, Reports/Analytics.
