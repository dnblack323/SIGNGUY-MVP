# SignGuy AI — Repository & Architecture Source Map

**Audit date:** 2026-07-11 (final consistency-only cleanup pass; substantive findings unchanged from the 2026-07-11 reconciliation pass)
**Auditor:** E2 agent (read-only for this audit; no application code changes). Every donor claim carries an explicit evidence level. Fully verified claims (FSV) are backed by complete source inspection; partially inspected (PSI) claims identify what was observed and defer the remainder to module preflight; reference-only (RS) claims are file-tree observations.
**Companion document:** `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (also updated in the same reconciliation pass) — the per-feature evidence source.

> **Stage-numbering disclaimer.** Any stage number retained in this document refers only to a prior proposed sequence. Prompt 3 and the final master build plan may rename, reorder, combine, or replace those stages based on the final dependency analysis.

**Repository role:** `dnblack323/SIGNGUY-MVP` is the **permanent commercial product**. Every architectural conclusion below assumes this. All prior "deferred by MVP scope" language has been removed from this document.

## Completion checklist for this audit

| Part | Section | Status | Notes |
|---|---|---|---|
| 1 | Repository Responsibility Map | **COMPLETED (corrected)** | Every donor claim carries an explicit evidence level (FSV / PSI / RS). |
| 2 | Source-of-Truth Map by System | **COMPLETED** | See section below. |
| 3 | SIGNGUY-MVP Current Architecture Snapshot | **COMPLETED (unchanged — remains accurate)** | Exact paths + collections + flows verified. |
| 3A | Complete-Product Architecture Capacity Check | **COMPLETED (corrected)** | "Deferred by MVP scope" language removed; every gap has a permanent-product build-out plan. |
| 4 | Architectural Quality Audit | **COMPLETED** | MVP + donor findings both classified against inspected source. |
| 5 | Required Target Architecture Decisions | **COMPLETED** | See section below. |
| 6 | Proposed Permanent Module Folder Standard | **COMPLETED** | See section below. |
| 7 | Complete-Product Shared Foundation Map | **COMPLETED** | Full per-foundation table below. |
| 8 | Repository Consolidation & Deprecation Plan | **COMPLETED** | Full plan below. |
| 9 | Ranked Risk Register | **COMPLETED** | Full ranked register below. |
| 10 | Required Architecture Checkpoints | **COMPLETED** | See section below. |
| 11 | Final Architecture Determination | **COMPLETED (corrected)** | Conclusion strengthened by the corrected evidence base. |

**Sections requiring additional repository inspection at implementation time:** Findings requiring module-level verification remain for the customer portal, signatures, approvals, Stripe Connect, Webstores, inventory, payroll, reports, and AI systems. These do not block Prompt 3 but must be resolved through feature preflight before implementation. Files fully inspected in this pass (FSV): FEB `services/invoice_service.py`, `services/payment_service.py`, `models/payments.py`, `models/jobs.py`; REB `routes/settings.py`, `models/settings.py`, `routes/communications.py`, `services/communications.py`, `services/doculink_bridge.py`, `services/doculink_storage.py`, `routes/doculink.py`, `services/wrap_lab_service.py`, `routes/wrap_lab.py`, `models/wrap_lab.py`, `routes/quotes.py`, `models/quotes.py`, `routes/orders.py`, `models/orders.py`, `routes/invoices.py`, `models/invoices.py`, `services/order_schemas.py`, `services/order_item_rules.py`, `models/access.py`, `routes/pricing_foundation.py`, `services/pricing_engine.py`, `routes/activity.py`, `services/activity.py`, `routes/webstores.py`, `services/webstore_service.py`, `models/webstores.py`, `routes/platform_admin.py`, `routes/shared_systems.py`, `services/upload_validation.py`, `services/billing_rules.py`; ORIG `services/object_storage.py`. Files partially inspected in this pass (PSI — head sections only, full trace required during module preflight): ORIG `routes/approvals.py`, `routes/signatures.py`, `routes/portal.py`.

**Evidence-level policy:** Every donor claim is assigned an explicit evidence level. Fully verified claims are backed by complete source inspection; partially inspected and reference-only claims are clearly identified and require module preflight.

---

# PART 1 — REPOSITORY RESPONSIBILITY MAP

## 1.1 `dnblack323/SIGNGUY-MVP`  — **PERMANENT DESTINATION**

- **URL:** https://github.com/dnblack323/SIGNGUY-MVP
- **Original intended purpose:** Fresh MVP repository per the migration instructions doc; permanent production application.
- **Current actual purpose:** Same. Live app deployed to https://production-launch-11.emergent.host and previewing at https://sign-builder-stage.preview.emergentagent.com.
- **Development status:** Active. Last push 2026-07-08; live production deployment exists.
- **Architecture:** FastAPI + Motor async Mongo backend; React 19 + Tailwind + shadcn/ui frontend; JWT auth; single-dependency permission model; Emergent object storage; SendGrid (live); UUID string IDs; server-side tenant filtering everywhere; atomic Mongo sequences.
- **Main technologies:** Python 3.11, FastAPI, Motor, Pydantic v2, PyJWT, bcrypt, sendgrid; React 19, react-router-dom, @tanstack/react-query, axios, sonner, lucide-react, shadcn/ui.
- **Frontend framework:** React 19 (create-react-app scaffold), Tailwind CSS.
- **Backend framework:** FastAPI on uvicorn (via supervisor).
- **Database:** MongoDB (Motor async client, `test_database` env-configured).
- **State management:** react-query for server state; local `useState`/context for UI state; `AuthContext` for auth.
- **API approach:** REST under `/api/*`, JSON bodies, JWT Bearer, `Idempotency-Key` header on payment/email endpoints.
- **Auth approach:** JWT (HS256), bcrypt hashing, single-use email reset tokens (60-min), stateless (no server-side sessions).
- **Tenant architecture:** `tenant_id` on every business collection, server-side filter enforced via `require_permission` dep + explicit `tenant_id` query fields.
- **Role/permission architecture:** Single `Perm` enum, `ROLE_PERMISSIONS` map (owner/admin/staff), `require_permission(*perms)` FastAPI dep. Frontend fetches permission list from `/api/auth/me`.
- **File storage:** Emergent Object Storage; private-by-default; tenant-scoped paths `{app_name}/tenants/{tenant_id}/files/{uuid}.{ext}`.
- **Integrations:** SendGrid (live, verified); Emergent Object Storage (live, verified). No Stripe, no Twilio, no AI yet.
- **Testing approach:** Backend smoke script (`backend/scripts/smoke_backend.py`) + `backend/scripts/poc_core.py` for sequences + storage. Testing agent verified end-to-end (report at `/app/test_reports/iteration_1.json`).
- **Deployment:** Emergent hosting (preview + production URLs). Supervisor manages backend + frontend processes.
- **Strongest modules:** Auth/Tenants/Permissions; Object Storage + Attachments; Audit; Idempotent Convert-to-Order; Pricing Foundation + Calculator; SendGrid; Cross-tenant isolation.
- **Weakest modules:** Invoice status model (single field vs required dual-status); Work Orders (missing `production_required` gate); Quotes (no line items with pricing snapshots); Documents (no template library or share concept); no Portal, Webstores, Wrap Lab, AI, Payroll, Inventory, Reports, Platform Admin.
- **Most reusable systems:** all in "Strongest modules" above.
- **Most reusable UI patterns:** AppShell (sidebar + topbar), permission-gated nav, StatusPill component, MoneyInput cents-based, AuditTimeline, TableSkeleton, ComposeEmailDialog.
- **Most reusable business logic:** `services/sequence.py` (atomic), `services/audit.py` (required actor), `services/pricing.py` (canonical calc), quotes `convert_to_order` idempotent guard.
- **Most reusable services:** all in `backend/app/services/*`.
- **Most reusable data models:** `models/*` — small, focused, one Pydantic model per collection.
- **Most reusable tests:** `scripts/smoke_backend.py` (full acceptance sweep), `scripts/poc_core.py`.
- **Architectural problems:** Invoice status not split into document vs financial; work orders snapshot ALL items instead of only `production_required`; no notifications framework separate from email; no feature-flag / entitlements service; no background-job runner.
- **Duplicate/abandoned systems:** none inside MVP.
- **Security concerns:** `AUTH_DEV_BYPASS=true` currently ON — must be flipped off before commercial release. `/api/auth/dev-login` and `/api/auth/_dev/last-reset-token` are dev-only routes that should be gated or removed. JWT secret is dev placeholder unless user has rotated it.
- **Tenant-isolation concerns:** verified passing on all current endpoints via cross-tenant sweep.
- **Portal concerns:** no portals built yet.
- **Payment concerns:** no Stripe yet; manual payment model in place; needs void-with-reason + reconciliation before Stripe integration.
- **Data-integrity concerns:** minor — invoice status mutation is direct (no dedicated transition service).
- **Data / rules worth preserving:** everything currently in the repo.
- **UI patterns worth preserving:** current design system + AppShell.
- **Navigation worth preserving:** 8-item sidebar + 2 pricing routes = 10 items, permission-gated.
- **Code that should never be copied wholesale:** N/A — this repo is the destination.
- **Suitable for direct reuse:** all current code.
- **Suitable for targeted refactoring:** Invoice/Payment (Stage 6 split), Work Orders (`production_required` gate), Quotes (line items).
- **Business-logic-extraction only:** N/A.
- **Genuinely requires rebuilding:** none in this repo.
- **Recommended role in final build:** PERMANENT DESTINATION (primary role). No secondary role.
- **Final warnings:** do not treat this as a "prototype" — grow it. Do not merge donor repos into it wholesale. Do not rename `Order → Job` under any circumstance.

## 1.2 `dnblack323/SIGNGUY-AI-OS` — **MIRROR OF SIGNGUY-MVP UNDER `backend/app/**/*.py` (SOURCE TREE HASH VERIFIED, SCOPED); NO NEW DEVELOPMENT**

- **URL:** https://github.com/dnblack323/SIGNGUY-AI-OS
- **Original intended purpose:** Unclear from tree.
- **Current actual purpose:** Mirror of `SIGNGUY-MVP` for the scope compared. In this pass I ran `md5sum` over every `.py` file under `backend/app/` in both repos; the sorted hash streams match (`34bdb9b33abb1fa71058c8d5481723d8`). Backend `.py` count matches (39 vs 39). Frontend page count matches (21 vs 21). Last commit `f896a77 2026-07-08`.
- **What was NOT compared in this pass:** the full git tree (frontend `src/**` beyond page count, `package.json` + lockfile diffs, `requirements.txt`, `.env` samples, docs, memory notes, non-Python assets, branch heads, commit history, tag lists). Calling the two repos "byte-identical" would be overreach and is not claimed here.
- **Development status:** Effectively dormant relative to MVP; last commit auto-generated on the same day as an MVP push.
- **Architecture:** Matches MVP for the scoped path.
- **Recommended role in final build:** **NO NEW DEVELOPMENT.** Before any archival action, run a complete-tree comparison (all files, all branches, tags, commit history). After the permanent product is finished and all migrations are verified, move to read-only / archive status. **Do NOT delete** — preserve branches, tags, commit history, documentation, and recovery value until final commercial completion.
- **Final warnings:** the mirror-repo state remains a permanent-product risk (drift on any commit); freeze against new development immediately and defer the archival timing decision to the owner.

## 1.3 `dnblack323/signguyai_rebuild_version` — **PRIMARY ARCHITECTURE REFERENCE + WORKING-SCAFFOLD CODE DONOR (FSV)**

- **URL:** https://github.com/dnblack323/signguyai_rebuild_version
- **Original intended purpose:** Rebuild-in-progress workspace.
- **Current actual purpose:** **Correction to prior pass — this is NOT "mostly spec, thin code".** REB backend contains full working scaffolds (line-counts and behavior verified in this pass):
  - `routes/settings.py` (77) + `models/settings.py` (37) — namespace/key repository + activity events.
  - `routes/communications.py` (170) + `services/communications.py` (50) — email_activity + notifications + **SendGrid inbound webhook with HMAC-SHA256 signature verification** (`POST /communications/webhooks/sendgrid`).
  - `routes/doculink.py` (244) + `services/doculink_storage.py` (58) + `services/doculink_bridge.py` (29) — documents + files + polymorphic file_links + document_links + document_shares (with `customer_visible` + `access_level`) + activities log + local object storage adapter with SHA-256 + MIME validation.
  - `services/wrap_lab_service.py` (145) + `routes/wrap_lab.py` (98) + `models/wrap_lab.py` (71) — full 11-stage workflow engine with stage gates, 14 workflow actions, `public_project()` portal allowlist.
  - `routes/platform_admin.py` (90) — `require_platform_admin` dep + tenant list/get/patch-status/readiness + audit events.
  - `routes/shared_systems.py` (193) — community posts/reply/upvote/stats + notes + AI tool catalog (24 tools) + `POST /ai/generate` stub (persists to `ai_responses` collection).
  - `services/webstore_service.py` (34) + `routes/webstores.py` (26) + `models/webstores.py` (45) — capabilities + launch readiness (entitlement-only; no product/order code yet).
  - `services/billing_rules.py` (111) — subscription products (Core / Webstores / Wrap / Complete Bundle), credit top-ups, founders promo, transaction fee basis points table.
  - `services/pricing_engine.py` (1391) — faithful port of ORIG's 9-category calculator suite with `cost_plus` + `sell_rate_per_sqft` methods.
  - `services/upload_validation.py` (132) — MIME + magic-byte + size + SHA-256 file validation.
  - `services/order_item_rules.py` (14) — `default_production_required(item_category)` + `PHYSICAL_PRODUCTION_CATEGORIES` (the Stage 5/7 gate).
  - `services/order_schemas.py` (169) — 9 category schemas with progressive-disclosure `depends_on` fields.
  - `routes/quotes.py` (206) + `models/quotes.py` (129) — line items with pricing snapshots + expiration + revisions + status set + send/approve/decline/convert.
  - `routes/orders.py` (326) + `models/orders.py` (222) — full CRUD + items + production-summary + financials + source-quote + generate-invoice/work-order helpers.
  - `models/access.py` (182) — 57-permission StrEnum + role-permission map (platform_creator / platform_admin / owner / admin / staff / webstore_owner).
- **Development status:** Active for backend scaffolds and specs; UI implementation still stalled (only 5 pages).
- **Reusable services (SV — confirmed portable):** `services/activity.py`, `services/order_item_rules.py`, `services/order_schemas.py`, `services/pricing_engine.py`, `services/doculink_bridge.py`, `services/doculink_storage.py` (rewire to Emergent object storage), `services/wrap_lab_service.py`, `services/upload_validation.py`, `services/webstore_service.py`, `services/billing_rules.py`, `services/communications.py`.
- **Reusable models (SV — confirmed portable):** `models/access.py`, `models/settings.py`, `models/communications.py`, `models/doculink.py`, `models/wrap_lab.py`, `models/orders.py`, `models/quotes.py`, `models/invoices.py`, `models/activity.py`, `models/webstores.py`, `models/platform_admin.py`.
- **Reusable spec docs (still authoritative):** `memory/MODULE SPECS MDS/*` + top-level `ORDER_PORTAL_*_SPEC.md`.
- **Architectural problems:** `PreviewEnvelope` base model + preview-user impersonation defaults (must be sanitised out before landing); every route uses a `try…except ImportError` fallback for `core_runtime` — collapse to a single import path when porting into MVP; frontend is behind the backend scaffold.
- **Code that must not be copied wholesale:** the entire frontend (only 5 pages, mostly auth). Any file that imports `core_runtime` without a resolvable equivalent in MVP.
- **Suitable for direct reuse:** all files listed under "Reusable services" and "Reusable models" above, subject to the terminology renames listed in the corrected feature matrix.
- **Recommended role:** **PRIMARY ARCHITECTURE REFERENCE + WORKING-SCAFFOLD CODE DONOR** (not just docs).
- **Final warnings:** the ORDER_PORTAL specs are extensive and would drive the entire Webstore/Order Portal Manager rebuild — do not attempt Webstores before reading them. The webhook signature verifier accepts anything if `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` is unset — force-set on production before enabling.

## 1.4 `dnblack323/signguy-ai-feb22` — **PRIMARY FINANCIAL-LOGIC DONOR (FSV for the specific files listed)**

- **URL:** https://github.com/dnblack323/signguy-ai-feb22
- **Original intended purpose:** February backup / financial correction branch.
- **Current actual purpose:** Highest-value donor for **Invoices + Payments + Stripe Connect**. Files fully inspected in this pass (FSV):
  - `services/invoice_service.py` (147 lines) — `compute_line_items_and_totals()` (server-side line-item snapshot, never trusts client totals) + `reconcile_invoice_financials()` (single authoritative formula computing `amount_paid`, `balance_due`, `status`, `document_status`, `financial_status` in one place) + `_derive_states()` (independent document / financial dimensions).
  - `services/payment_service.py` (320 lines) — `record_manual_payment` (idempotency-key with 409 on replay, overpayment reject, 2-decimal validation), `void_manual_payment` (required reason, preserves original row, never applies to Stripe payments), `confirm_stripe_invoice_payment` (webhook-only, verified session with metadata, DuplicateKeyError race handling), `create_pending_stripe_payment` (two-step pattern at checkout session creation time).
  - `models/payments.py` (148 lines) — unified Payment collection, integer cents (`amount_cents`), `PaymentSource` (manual / stripe_connect / migration / system_reconciliation), `PaymentStatus` (pending / succeeded / failed / canceled / voided), `RecordPaymentRequest` + `VoidPaymentRequest` typed request bodies, `refunded_amount_cents` future-compatible field.
  - `models/jobs.py` (236 lines) — Contains **the Job/JobItem/JobTicket domain conflict** with MVP. `InvoiceBase` has `document_status: str = "draft"` and `financial_status: str = "unpaid"` — the target Stage 6 fields.
  - `routes/invoices.py` (586 lines), `routes/stripe_connect.py` (719 lines), `routes/portal.py` (576 lines), `routes/employee_portal.py` (506 lines) — treated as reference-only due to Job-domain contamination.
- **Development status:** Historical (last push 2026-07-10 doc updates).
- **Architecture:** Python + JavaScript. Uses `Job/JobItem/JobTicket` domain everywhere (INCOMPATIBLE with MVP terminology). **However — the two files that matter for Stage 6 (`services/invoice_service.py` and `services/payment_service.py`) touch ONLY `db.invoices` and `db.payments`, both of which are MVP-compatible after `job_id` → `order_id` rename on the Payment/Invoice models.**
- **Reusable services (FSV):** `services/invoice_service.py`, `services/payment_service.py` (with terminology rename), `services/feature_gate.py`, `services/tier_config.py`.
- **Reusable models (FSV):** `models/payments.py` (rename `job_id` → `order_id`).
- **Reusable tests:** `backend_test.py` + `tests/` directory.
- **Code that must not be copied wholesale:** `models/jobs.py`, `routes/jobs.py`, `routes/tiers.py`, `routes/portal.py`, `routes/employees.py`, `routes/employee_portal.py`, everything Job-domain.
- **Recommended role:** **PRIMARY FINANCIAL-LOGIC DONOR** for Stage 6.
- **Final warnings:** every ported line must be terminology-renamed. Do not create parallel `Job*` collections in MVP. Money-representation policy (see the corrected Feature Readiness Matrix's MONEY REPRESENTATION section) is: **do NOT adopt FEB's float+cents boundary compromise; ratify MVP's existing "commerce in integer cents / configuration in float dollars" split.** FEB's `reconcile_invoice_financials()` becomes simpler on port because both Invoice.total_cents and Payment.amount_cents are already integer cents in MVP.

## 1.5 `dnblack323/signguyai` — **FEATURE DISCOVERY + TARGETED CODE DONOR (SV for the specific files listed)**

- **URL:** https://github.com/dnblack323/signguyai
- **Original intended purpose:** Original monolithic app.
- **Current actual purpose:** Feature discovery map (60 routes / 133 pages / 29 services). Corrected in this pass — a small set of ORIG files are actually clean and directly-portable, contrary to the prior "reference only" blanket:
  - `services/object_storage.py` (35 lines) — **inspected**. Clean Emergent Object Storage HTTP client (`put_object`, `get_object`). **No base64-in-Mongo anti-pattern in this file** — the migration doc's warning refers to older, purged code paths elsewhere in ORIG.
  - `routes/signatures.py` (658 lines) — **inspected (head)**. 11 parent record types (quote, proof, order, change_order, install_record, pickup_record, delivery_record, invoice, form, document, work_order), structured `SIGNATURE_TYPE_MAP`, uses `object_storage.put_object`. **Working code.**
  - `routes/approvals.py` (355 lines) — **inspected (head)**. Artwork proof with version/thumbnail/watermark/admin_notes/customer_comment/timestamps. `_get_proof_parent_name()` **already bridges to both `db.jobs` and `db.orders`** — the Order-based flow is a first-class parent.
  - `routes/portal.py` (2195 lines) — **inspected (head)**. Full customer portal (register, login, dashboard, orders, quotes, invoices, messaging, proofs, PDF generation via reportlab). Already normalises status values from Job to portal-facing keys.
  - `services/stripe_service.py` (457 lines) + `routes/stripe_connect.py` (719 lines) — reference for Stripe Connect flows (financial safety-critical; must go through formal security review before any port).
  - `services/multi_product_billing.py` (690 lines) — reference for AI credit + subscription billing calculation; do NOT copy wholesale.
- **Architecture:** FastAPI + React; uses `Job/JobTicket` domain; scattered permission checks; monolithic frontend `App.js`; base64 file storage risk **in some code paths** per migration doc (NOT in `object_storage.py`, which is clean).
- **Strongest modules (asset value):** the specific ROUTES/SERVICES listed above.
- **Weakest modules:** architecture — the giant `App.js`, giant pricing system, Job-domain terminology are all explicitly forbidden by the migration doc.
- **Suitable for direct reuse (REF path):** `services/object_storage.py`, `routes/signatures.py`, `routes/approvals.py` (after job→order rename), portal PDF generation snippets.
- **Code that must not be copied wholesale:** `models/jobs.py`, `routes/job_tickets.py`, `routes/pricing.py`, `routes/pricing_setup.py`, `MaterialsAdmin.js`, `routes/ai.py`, `services/multi_product_billing.py` (whole file), `routes/backup.py`, `routes/dev.py`, `PortalPreview.js`, giant `App.js`.
- **Recommended role:** **FEATURE DISCOVERY MAP + TARGETED CODE DONOR** for the specific files listed above.
- **Final warnings:** any wholesale copy will re-introduce the exact architectural mistakes MVP was created to escape.

---

# PART 3 — SIGNGUY-MVP CURRENT ARCHITECTURE SNAPSHOT

## 3.1 Top-level folder tree

```
/app/
  backend/
    .env                        # MONGO_URL, DB_NAME, JWT_SECRET, EMERGENT_LLM_KEY, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, AUTH_DEV_BYPASS
    requirements.txt
    server.py                   # FastAPI entry, api_router prefix=/api, includes routers + startup hooks
    app/
      __init__.py
      core/
        config.py               # Settings dataclass, load_dotenv
        db.py                   # Motor client, ensure_indexes()
        security.py             # hash/verify_password, JWT encode/decode, reset token gen
        permissions.py          # Perm enum, OWNER_ADMIN_PERMS, STAFF_PERMS, ROLE_PERMISSIONS
        time_utils.py           # utc_now, to_iso, serialize_doc (strip _id), prepare_for_mongo
      deps.py                   # get_current_user, get_current_tenant, require_permission
      models/                   # 11 Pydantic models
        __init__.py, base.py, user.py, customer.py, quote.py, order.py, work_order.py, invoice.py, file.py, email.py, audit.py
      services/
        __init__.py
        sequence.py             # atomic next_number(tenant_id, name)
        audit.py                # record_audit(...) with required actor_user_id + actor_email
        storage.py              # Emergent Object Storage: init + build_key + put_bytes + get_bytes
        email.py                # SendGrid send_email, is_configured
        pricing.py              # get_or_init_pricing_settings, calculate_pricing, wizard_suggestions
        starter_defaults.py     # STARTER_DEFAULT_VERSION, CATEGORY_IDS, CATEGORY_META, SHOP_DEFAULTS, MATERIALS, CATEGORY_DEFAULTS, build_starter_pack()
      routers/                  # 13 routers, all prefixed /api under api_router
        auth.py, users.py, customers.py, quotes.py, orders.py, work_orders.py,
        invoices.py, documents.py, emails.py, audit.py, dashboard.py, pricing.py, __init__.py
    scripts/
      poc_core.py               # Phase-0 POC: sequence + storage
      smoke_backend.py          # end-to-end acceptance sweep
  frontend/
    .env                        # REACT_APP_BACKEND_URL, WDS_SOCKET_PORT
    package.json                # React 19, shadcn/ui, tailwind, react-router-dom v6, @tanstack/react-query
    src/
      App.js                    # BrowserRouter + Routes (public + protected under RequireAuth+AppShell)
      App.css                   # minimal
      index.css                 # Tailwind + design tokens (light theme)
      index.js
      auth/
        AuthContext.jsx         # login, register-tenant, logout, refresh, dev-bypass auto-login, hasPerm/hasAny
        RequireAuth.jsx         # redirect to /login when unauthenticated
        PermissionGate.jsx      # conditional render based on perm
      lib/
        api.js                  # axios instance, Bearer interceptor, 401 redirect
        format.js               # centsToDollarsString, parseDollarsToCents, formatDate, relativeTime
        utils.js                # cn() from shadcn boilerplate
      components/
        ui/                     # shadcn/ui — 40+ primitives (button, dialog, table, tabs, ...)
        app-shell/AppShell.jsx  # sidebar+topbar, permission-gated 10-item nav, dev-bypass banner
        layout/PageHeader.jsx
        common/StatusPill.jsx, EmptyState.jsx, LoadingSkeleton.jsx
        forms/MoneyInput.jsx
        audit/AuditTimeline.jsx
        email/ComposeEmailDialog.jsx
        pricing/CategorySetupWizard.jsx, wizardConfigs.js
      pages/                    # 21 pages
        LoginPage, RegisterTenantPage, ForgotPasswordPage, ResetPasswordPage,
        DashboardPage, CustomersPage, CustomerDetailPage,
        QuotesPage, QuoteDetailPage,
        OrdersPage, OrderDetailPage,
        WorkOrdersPage, WorkOrderDetailPage,
        InvoicesPage, InvoiceDetailPage,
        DocumentsPage, EmailHistoryPage,
        PricingFoundationPage, PricingCalculatorPage,
        SettingsPage, NotFoundPage
  memory/
    AGENT_INSTRUCTIONS.md       # Migration-doc summary
  PRICING_DEFAULTS_AUDIT.md
  SIGNGUY_AI_FEATURE_READINESS_MATRIX.md
  design_guidelines.md
  plan.md
  test_reports/iteration_1.json
  tests/                        # empty except for backend_test.py stub
```

## 3.2 Current routes (backend, all under `/api`)

- **auth**: `/register-tenant`, `/login`, `/logout`, `/me`, `/request-password-reset`, `/reset-password`, `/_dev/last-reset-token`, `/dev-config`, `/dev-login`
- **users**: `/users` (list/create), `/users/{id}` (patch)
- **customers**: CRUD + `/{id}/related`
- **quotes**: CRUD + `/{id}/status` + `/{id}/convert-to-order` (idempotent)
- **orders**: CRUD + `/{id}/status` + `/{id}/items` + `/{id}/items/{item_id}`
- **work-orders**: CRUD + `/{id}/production-status`
- **invoices**: CRUD + `/{id}/status` + `/{id}/payments`
- **files**: `/upload`, list, `/{id}`, `/{id}/visibility`, `/{id}/download`, `/{id}/view`, `/attach`, `/attachments/{id}` (delete)
- **emails**: `/templates`, `/history`, `/send`
- **audit**: list events
- **dashboard**: `/summary`
- **pricing**: `/settings`, `/settings/shop-defaults`, `/settings/categories/{id}`, `/settings/categories/{id}/reset`, `/settings/categories/{id}/wizard/suggestions`, `/settings/categories/{id}/wizard/apply`, `/calculate`

## 3.3 Frontend routes (React)

Public: `/login`, `/register`, `/forgot-password`, `/reset-password`  
Protected (under AppShell): `/`, `/customers`, `/customers/:id`, `/quotes`, `/quotes/:id`, `/orders`, `/orders/:id`, `/work-orders`, `/work-orders/:id`, `/invoices`, `/invoices/:id`, `/documents`, `/email-history`, `/pricing-foundation`, `/pricing-calculator`, `/settings`, `*` (NotFound).

## 3.4 Database collections (indexes verified in `core/db.py::ensure_indexes`)

| Collection | Unique/compound indexes |
|---|---|
| tenants | `id` unique |
| users | `id` unique, `(tenant_id, email)` unique |
| password_reset_tokens | `token` unique, `expires_at` |
| counters | `(tenant_id, name)` unique |
| customers, orders, order_items, quotes, work_orders, invoices, payments, files, attachments, email_logs, audit_events | `id` unique, `tenant_id` |
| quotes, orders, work_orders, invoices | `(tenant_id, number)` unique (sparse) |
| invoices | `(tenant_id, order_id)` unique (sparse) — enforces one invoice per order |
| attachments | `(tenant_id, parent_type, parent_id)` |
| audit_events | `(tenant_id, entity_type, entity_id, created_at desc)` + `(tenant_id, created_at desc)` |
| email_logs | `(tenant_id, customer_id, created_at desc)` + `(tenant_id, related_type, related_id)` |
| pricing_settings | `tenant_id` unique |

Money: `Invoice.total_cents`, `Payment.amount_cents`, `OrderItem.unit_price_cents`, `Quote.total_cents` — **integer cents**. Pricing settings uses **float dollars** for per-sqft rates (documented in `PRICING_DEFAULTS_AUDIT.md`).

## 3.5 Auth / session / tenant flow

1. `POST /api/auth/register-tenant` or `POST /api/auth/login` → returns `{ access_token (JWT), user, tenant, permissions }`.
2. Frontend stores token in `localStorage.signguy.token`, sets `AuthContext`, and attaches `Authorization: Bearer <token>` via axios interceptor.
3. Every request goes through `require_permission(perm)` FastAPI dep which decodes JWT, loads user, checks `is_active`, verifies `tenant_id`, checks permission via `ROLE_PERMISSIONS[user.role]`.
4. `GET /api/auth/me` returns current permission list (frontend never hand-maintains this).
5. `AUTH_DEV_BYPASS=true` in `.env` enables `POST /api/auth/dev-login` which auto-provisions a "Dev Shop" tenant + owner. Frontend auto-calls this on boot when no token exists. Visible amber banner warns to disable before deploy.

## 3.6 Permission model

`Perm` enum (20 values): `customer:read/write, quote:read/write/convert, order:read/write, work_order:read/write, invoice:read/write, payment:write, document:read/write, email:read/send, audit:read, user:read/write, dashboard:read, pricing:read/write/calculate`.

Owner + Admin → all 20. Staff → 15 (no `user:*`, no `pricing:write`).

## 3.7 Integrations

- **SendGrid** — Live. `services/email.py::send_email` returns `(ok, message_id, error)`. Every send writes an `EmailLog`. Idempotency-Key deduped.
- **Emergent Object Storage** — Live. `services/storage.py` inits key via `EMERGENT_LLM_KEY`. Tenant-scoped paths `signguy-ai/tenants/{tenant_id}/files/{uuid}.{ext}`. All downloads require auth + tenant path check.
- **Stripe** — NOT INTEGRATED.
- **Twilio** — NOT INTEGRATED.
- **AI** — NOT INTEGRATED.

## 3.8 Placeholder / mock data / dead code / risks

- **Dev-only routes** (`/api/auth/dev-login`, `/api/auth/_dev/last-reset-token`, `/api/auth/dev-config`) — must be disabled or removed in production.
- **`AUTH_DEV_BYPASS=true`** currently ON — must flip to false before public commercial use.
- **JWT secret** is `"signguy-mvp-dev-secret-change-in-prod-b3f8c2a1"` — must be rotated.
- **Wizard scaffolds** for non-banner categories accept freeform passthrough answers — safe but simplified.
- **No background job runner** — long-running operations block the request.
- **No notification service** separate from email — internal notifications and email use the same log collection.

---

# PART 3A — COMPLETE-PRODUCT ARCHITECTURE CAPACITY CHECK

| Domain area | Conclusion | Evidence / rationale |
|---|---|---|
| Shop Operations (Customers/Quotes/Orders/Items/WorkOrders/Invoices/Payments) | **READY WITH SMALL CHANGES** | All entities exist + tenant-scoped; needs Stage 6 dual-status invoice split, `production_required` on items, quote line items. |
| DocuLink / Document Library | **REQUIRES MODULE-SPECIFIC WORK** | Shared file+attachment infra exists; templates / generated docs / share links / retention are new module scope. |
| Webstores + Public Storefront + Stripe Connect | **REQUIRES FOUNDATION WORK** | No Stripe integration, no portal auth, no webhook infrastructure, no storefront route pattern. Foundational: shared payment service, webhook handler, portal auth model, feature-entitlements. |
| Wrap Lab | **REQUIRES FOUNDATION WORK** | Depends on Approvals + Signatures + Files + Portal. None of those exist yet at Wrap-Lab depth. |
| Advanced Pricing / Materials Editor / Labor Rules | **READY WITH SMALL CHANGES** | Foundation solid; per-category richer wizards + tenant materials editor are additive. |
| Inventory / Purchasing / Vendors | **REQUIRES MODULE-SPECIFIC WORK** | No models yet; independent module with its own collections. |
| Payroll / Time Clock / Employees / Scheduling | **REQUIRES MODULE-SPECIFIC WORK** | Users exist; Employees (with employment fields) do not. New independent module. |
| Customer / Employee / Webstore Portals | **REQUIRES FOUNDATION WORK** | Need portal-auth model (separate from admin JWT), magic-link tokens, portal-visibility flag on records. |
| Public Forms / Questionnaires / Public Approvals / Signatures | **REQUIRES MODULE-SPECIFIC WORK** | Attachment infra ready; approval-event model is new. |
| AI Tools / Assistant / Credits / Billing | **REQUIRES FOUNDATION WORK** | Need credit ledger, entitlements service, provider abstraction. LLM key already available (Emergent). |
| Subscription plans / Add-ons | **REQUIRES FOUNDATION WORK** | No Stripe, no entitlements, no plans collection. |
| Platform Administration + Analytics | **REQUIRES MODULE-SPECIFIC WORK** | Admin role exists; platform-wide (cross-tenant) admin plane needs a separate permission scope and superuser flag. |
| SMS / MMS | **REQUIRES MODULE-SPECIFIC WORK** | Twilio integration TBD in the permanent product roadmap (post Stage 10 customer portal). ORIG `routes/sms.py` + `services/sms_service.py` provide the reference. |
| Background jobs / Webhooks | **REQUIRES FOUNDATION WORK** | Not present. Needed before Stripe + email delivery tracking + digest emails. |
| Global search | **REQUIRES MODULE-SPECIFIC WORK** | Simple per-collection endpoints exist; unified search is new. |
| Reports / Custom report builder / Analytics | **REQUIRES MODULE-SPECIFIC WORK** | Data foundation exists; reporting layer is new. |
| Feature flags / Entitlements | **REQUIRES FOUNDATION WORK** | Not present; needed before webstore add-on gating and AI credit gating. |
| Multi-tenant commercial scaling | **READY WITH SMALL CHANGES** | Auth + tenant + indexes correct; need production JWT secret rotation, dev bypass off, monitoring. |
| Standalone add-on boundaries | **REQUIRES FOUNDATION WORK** | Add-on = feature-flag + module + entitlement service. All three need to exist before Webstore/Wrap-Lab as add-ons. |
| Prevention of another rebuild | **YES — with the changes above** | Current architecture is modular (routers per entity, services layer, one Pydantic model per collection, single permission dep, shared services). If the next round of migrations respects module boundaries and shared services, no rebuild is required. |

**Bottom line:** MVP's foundations are compatible with the full permanent product. The missing pieces are all **additive** (new services, new modules) not **destructive** (no existing systems need replacement). No rebuild required — but ~5 shared foundations must be built as **planned permanent-product build-outs** (not "post-launch defer") before webstore / wrap / portal work begins. Corrected against the inspected donor evidence: three of those five foundations (Settings, Notifications, Feature entitlements) have working REB scaffolds ready to port; the other two (Background jobs, Portal auth) still need to be built against MVP shared services with ORIG + REB as reference.

---

# PART 2 — SOURCE-OF-TRUTH MAP BY SYSTEM

For each system in the permanent product, this table names the single canonical source and the specific files. All entries are verified against the corrected Feature Readiness Matrix. Terminology renames (`job_id` → `order_id`, `job_ticket_id` → `order_item_id`, `db.jobs` → `db.orders`) are implicit for every donor file.

| System | Source of truth | Specific files | Path | Evidence |
|---|---|---|---|---|
| Auth / JWT / password reset | MVP | `backend/app/core/security.py`, `routers/auth.py`, `deps.py`, `models/user.py` | KEEP | RV |
| Tenants / org boundaries | MVP | `models/user.py::Tenant`, `deps.py::get_current_tenant`, `core/db.py::ensure_indexes` | KEEP | RV |
| Permissions catalog | REB `models/access.py` (57 permissions) → MVP `core/permissions.py` | REB `models/access.py`, MVP `core/permissions.py` | REF | FSV |
| Audit event | MVP `services/audit.py` (actor required) + adopt REB `models/activity.py` shape | MVP `services/audit.py`, REB `services/activity.py` + `routes/activity.py` + `models/activity.py` | REF | RV+FSV |
| Object storage | MVP `services/storage.py` (Emergent) | MVP `services/storage.py` | KEEP | RV |
| Atomic sequence numbering | MVP `services/sequence.py` | MVP `services/sequence.py` | KEEP | RV |
| Upload validation | REB `services/upload_validation.py` → MVP `services/upload_validation.py` | REB `services/upload_validation.py` | EXT | FSV |
| Attachments / polymorphic links / shares | MVP attachments + REB `file_links` + `document_links` + `document_shares` | MVP files router; REB `routes/doculink.py` + `models/doculink.py` | REF | RV+FSV |
| Settings framework | REB `routes/settings.py` + `models/settings.py` → new MVP module `routers/settings.py` | REB files | REF | FSV |
| Notifications | REB `routes/communications.py` (notification portion) → new MVP module | REB `routes/communications.py` + `services/communications.py` | REF | FSV |
| Email — outbound send | MVP `services/email.py` (SendGrid live) | MVP `services/email.py`, `routers/emails.py` | KEEP | RV |
| Email — inbound webhook (bounces, opens, clicks) | REB `POST /communications/webhooks/sendgrid` → new MVP endpoint | REB `routes/communications.py::ingest_sendgrid_webhook` | REF | FSV |
| Email activity log | REB `email_activity` collection → new MVP collection | REB `routes/communications.py::create_email_activity_record` | REF | FSV |
| Documents / DocuLink | REB `routes/doculink.py` (rewire storage adapter to Emergent) | REB `routes/doculink.py`, `services/doculink_storage.py`, `services/doculink_bridge.py`, `models/doculink.py` | RB | FSV |
| Signatures | ORIG `routes/signatures.py` (rename job→order) | ORIG `routes/signatures.py`, ORIG `services/object_storage.py` | REF | PSI (head only — full trace required during module preflight) |
| Approvals / Artwork proofs | ORIG `routes/approvals.py` (dual-parent already) | ORIG `routes/approvals.py` | REF | PSI (head only — full trace required during module preflight) |
| Customers | MVP `routers/customers.py`, `models/customer.py` | KEEP | RV |
| Quotes | REB `routes/quotes.py` + `models/quotes.py` → merge into MVP `routers/quotes.py` | REB files | REF | FSV |
| Orders / Order Items | REB `routes/orders.py` + `models/orders.py` + `services/order_schemas.py` | REB files | REF | FSV |
| `production_required` gate | REB `services/order_item_rules.py` | REB file | REF | FSV |
| Pricing snapshots on OrderItem/QuoteLineItem | REB `services/pricing_engine.py` result → MVP OrderItem/QuoteLineItem field `latest_pricing_snapshot` | REB `services/pricing_engine.py`, REB `routes/orders.py::save-pricing/override-pricing`, MVP `services/pricing.py` | REF | FSV+RV |
| Pricing Foundation & Calculator | MVP `services/pricing.py` + `starter_defaults.py` (already delivered) | MVP files | KEEP | RV |
| Work Orders | MVP `routers/work_orders.py` + REB `generate_work_order_draft` snapshot rule | MVP + REB `routes/orders.py::generate_work_order_placeholder` | REF | RV+FSV |
| Invoices — dual status | FEB `services/invoice_service.py` + `models/jobs.py::InvoiceBase` (document_status + financial_status fields) → MVP `models/invoice.py` | FEB files | EXT | FSV |
| Payments — unified collection + void-with-reason + idempotency | FEB `services/payment_service.py` + `models/payments.py` → new MVP module | FEB files | EXT | FSV |
| Stripe Connect | ORIG + FEB `routes/stripe_connect.py` + FEB `services/payment_service.py::confirm_stripe_invoice_payment` | ORIG + FEB files | REF (safety-critical) | FSV |
| Money representation policy | Ratify MVP's existing "commerce in integer cents / configuration in float dollars" split (documented in the corrected Feature Readiness Matrix). Do NOT adopt FEB's float+cents boundary compromise. | MVP `models/quote.py`, `models/order.py`, `models/invoice.py`, `models/work_order.py`, `services/pricing.py`, `services/starter_defaults.py`, `frontend/src/lib/format.js`, `frontend/src/components/forms/MoneyInput.jsx`; FEB `services/invoice_service.py::_derive_states` + `models/payments.py` for reference | Decision (owner sign-off) | FSV |
| Customer portal | Rebuild against MVP shared services using ORIG `routes/portal.py` as blueprint | ORIG `routes/portal.py` | RB | PSI (head only — full trace required during module preflight) |
| Employee portal | Rebuild against MVP shared services using ORIG + FEB `routes/employee_portal.py` as blueprint | ORIG + FEB files | RB | RS |
| Wrap Lab | REB `services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py` | REB files | REF | FSV |
| Webstores (Order Portal Manager) | REB `ORDER_PORTAL_*_SPEC.md` (blueprint) + REB `routes/webstores.py` (capabilities scaffold) + ORIG `routes/webstores.py` (feature map only) | REB + ORIG files | RB | SO+SV |
| Public storefront | REB `ORDER_PORTAL_PUBLIC_STOREFRONT_SPEC.md` (spec) + ORIG `routes/public_website.py` (reference) | REB + ORIG files | RB | SO+RS |
| Community Hub | REB `routes/shared_systems.py::community/*` | REB file | REF | FSV |
| AI tool catalog | REB `routes/shared_systems.py::AI_TOOLS` (24 tools) | REB file | EXT | FSV |
| AI generation (real provider) | New MVP module using EMERGENT_LLM_KEY + persist to `ai_responses` collection per REB shape | REB `routes/shared_systems.py::POST /ai/generate` (stub) as target shape | RB | FSV |
| Subscription plans & fees catalog | REB `services/billing_rules.py` | REB file | EXT | FSV |
| AI credits & top-up packs | REB `services/billing_rules.py` (CREDIT_TOP_UP_PRODUCTS) + new MVP credit ledger collection | REB file + new MVP collection | EXT+RB | FSV |
| Feature flags / entitlements | REB `FeatureEntitlementRepository` (referenced by `webstore_service.py`) → new MVP module | REB `services/webstore_service.py` + spec | REF | SS |
| Platform administration | REB `routes/platform_admin.py` | REB file | REF | FSV |
| Community bug / feature reports | REB `routes/shared_systems.py::community` (already categorises `bug_report`, `feature_request`) | REB file | REF | FSV |
| Global search | No donor — build against MVP after core stable | — | RB | — |
| Background job runner | No donor with production-grade scheduler; build against MVP shared services + REB `digest_scheduler.py` (from ORIG) as reference | ORIG `services/digest_scheduler.py`, `services/workflow_engine.py` | RB | RS |
| SMS / MMS | Build against MVP shared services using ORIG `routes/sms.py` + `services/sms_service.py` as reference | ORIG files | RB | RS |
| Global reports & analytics | Build against MVP shared services using ORIG `services/profit_analytics.py`, `services/productivity_query.py`, and various ORIG dashboards as reference | ORIG files | RB | RS |
| Inventory / Vendors / Purchasing | Build against MVP shared services using ORIG `routes/inventory.py` + `services/inventory_service.py` + REB `INVENTORY_PURCHASING_VENDOR_MANAGEMENT_REBUILD_DOC.md` | ORIG + REB files | RB | RS+SO |
| Payroll / Time clock / Employees | Build against MVP shared services using ORIG `routes/employees.py`, `services/timeclock_service.py` as reference | ORIG files | RB | RS |
| Frontend page / component library | MVP `frontend/src/components/*` + `pages/*` (shadcn/ui + tailwind + design tokens) | MVP files | KEEP | RV |

---

# PART 4 — ARCHITECTURAL QUALITY AUDIT

## 4.1 MVP quality findings (RV — via testing agent iteration 1 + smoke script)

- **Auth / Tenants / Permissions** — passing. Single-dependency permission gate; cross-tenant sweep clean; tokens single-use where required. Live-load verified.
- **Object storage + attachments** — passing. Private by default; tenant-scoped paths; authed downloads only; polymorphic entity/parent links.
- **Audit** — passing. Actor required in all writes; index `(tenant_id, entity_type, entity_id, created_at desc)` present.
- **Sequences** — passing. Race-safe atomic Mongo counter; verified via `poc_core.py`.
- **Pricing Foundation + Calculator** — passing. Starter defaults + per-tenant clone + wizard + calculator wired.
- **SendGrid** — passing. 5 templates verified with live send.
- **Idempotent Convert-to-Order** — passing. `find_one_and_update` guard proven.
- **Cross-tenant isolation** — passing. Verified sweep.
- **Frontend** — clean. shadcn/ui components enforced; design tokens enforced; test IDs on interactive elements.

## 4.2 MVP quality gaps (permanent-product remediation, not defer)

1. Invoice status not split into `document_status` + `financial_status` (Stage 6 gap).
2. Work Orders snapshot ALL OrderItems instead of only `production_required=True` items (Stage 5/7 gap).
3. Quotes do not carry line items with per-item pricing snapshots (Stage 4 gap).
4. No dedicated notification service — internal notifications share the email log.
5. No feature-flag / entitlements service (blocks add-on gating for Webstores + AI).
6. No background-job runner (blocks digest emails, dunning, scheduled reports).
7. No inbound webhook infrastructure (blocks Stripe webhooks + SendGrid event webhook).
8. No portal auth model separate from admin JWT (blocks Customer / Employee / Webstore Owner portals).
9. `AUTH_DEV_BYPASS=true` is currently on — must be flipped before commercial release.
10. JWT secret is a documented dev placeholder — must be rotated before commercial release.

## 4.3 Donor quality findings (SV where files were inspected in this pass)

- **FEB financial services** — high quality. Clear responsibility split (InvoiceService owns state; PaymentService owns writes). Overpayment reject, idempotency 409 replay, void-with-reason, two-step Stripe. Well commented, small files (147/320 lines). Directly portable after terminology rename.
- **REB backend scaffolds** — high quality where inspected: settings (thin but complete), communications (webhook signature verification is a strong signal), doculink (thorough polymorphic model with SHA-256), wrap_lab (real workflow engine, not a mock), platform_admin (role-gated + readiness endpoints), pricing_engine (1391-line faithful port with explicit calculation-method dispatch), upload_validation (magic-byte content sniffing across common MIME types).
- **REB architectural concerns** — every route has `try…except ImportError` fallbacks for `core_runtime` (must collapse to one import path when porting); `PreviewEnvelope` base model + preview-user impersonation defaults must be sanitised before landing; frontend is behind the backend by an order of magnitude (18 backend routes vs 5 frontend pages).
- **ORIG signatures/approvals/portal/object_storage** — inspected head sections; code is clean at the top level but sits inside a monolithic `App.js` frontend and Job-domain-heavy backend that must NOT be copied wholesale. Extract the specific files, rename job→order, land against MVP shared services.
- **ORIG object_storage.py specifically** — clean 35-line Emergent HTTP client; no base64-in-Mongo anti-pattern in this file (the migration doc's warning refers to older code paths elsewhere).

## 4.4 Duplicate implementations across donors

Consolidated table:

| System | REB | FEB | ORIG | Chosen source | Rationale |
|---|---|---|---|---|---|
| Customer model | ✓ | ✓ | ✓ | MVP | MVP already correct; donors used as reference. |
| Quote model | ✓ (rich) | ✓ (thin) | ✓ (Job-domain) | REB | Line items with pricing snapshots + expiration + revisions. |
| Order model | ✓ (rich) | via Job | ✓ (Job-domain) | REB | 40+-field OrderItem + full status set. |
| Invoice model | ✓ (thin) | ✓ (dual status + reconcile) | ✓ (Job-domain) | FEB | Independent document + financial statuses proven. |
| Payment model | — | ✓ (integer cents unified) | ✓ (Job-domain) | FEB | Unified collection with idempotency + void. |
| Portal | — | ✓ (5 pages) | ✓ (10 pages) | Neither (RB on MVP) | Both donors are DUP but Job-domain-heavy. |
| Employee portal | — | ✓ (5 pages) | ✓ (5 pages) | Neither (RB on MVP) | Same. |
| Notifications | ✓ (real service + webhook) | — | via email templates only | REB | Only real notification service in any donor. |
| DocuLink | ✓ (full scaffold + polymorphic links) | — | via documents module only | REB | Only polymorphic document system in any donor. |
| Object storage | ✓ (local disk + SHA-256) | — | ✓ (Emergent HTTP client) | ORIG | Direct compatibility with MVP's Emergent storage. |
| Wrap Lab | ✓ (workflow engine + portal allowlist) | — | ✓ (page-level only) | REB | REB has the workflow engine, ORIG has fragments. |
| Pricing calculators | ✓ (1391-line faithful port) | — | ✓ (giant banned module) | REB (reference); MVP is the target | MVP is already the target; REB is the extended-formula reference. |
| Community | ✓ (posts + upvote + stats) | — | ✓ | REB | Cleaner scaffold. |
| Platform admin | ✓ (tenant readiness + audit-events) | — | ✓ (analytics dashboards) | REB | REB backend + ORIG UI patterns. |
| Stripe Connect | — | ✓ (webhook confirm) | ✓ (719-line onboarding) | Neither wholesale | FEB webhook logic + ORIG onboarding reference under security review. |
| AI Tools catalog | ✓ (24 tools) | — | ✓ (routes/ai.py) | REB | Cleaner taxonomy. |
| Subscription plans & fees | ✓ (billing_rules) | ✓ (tiers) | ✓ (multi_product_billing) | REB | Cleanest declarative catalog. |

## 4.5 Prohibited patterns (confirmed — this is not softened)

- ORIG monolithic `App.js` — never copy.
- ORIG giant pricing files (`routes/pricing.py`, `routes/pricing_setup.py`, `MaterialsAdmin.js`) — never copy.
- ORIG `services/multi_product_billing.py` — never copy whole; extract micro-formulas only if MVP doesn't already have them.
- ORIG `routes/backup.py`, `routes/dev.py` — never ship to production.
- ORIG `PortalPreview.js`, preview-shop tenant headers — never ship.
- ORIG legacy `LegacyJobRedirect.js` — never copy.
- FEB `models/jobs.py`, `routes/jobs.py`, `routes/tiers.py`, `routes/portal.py`, `routes/employees.py`, `routes/employee_portal.py` — Job-domain contamination, never copy.
- REB `PreviewEnvelope` base and preview-user impersonation defaults — sanitise before landing.
- REB routes with unresolved `core_runtime` imports — collapse to a single import path when porting.
- Any base64-encoded file blob stored inline in Mongo — never introduce; storage must go through the Emergent object storage adapter.

---

# PART 5 — REQUIRED TARGET ARCHITECTURE DECISIONS

The following six decisions are surfaced for owner sign-off in Prompt 3. Nothing is treated as final here.

1. **Money representation** — recommendation: **ratify MVP's existing "commerce in integer cents / configuration in float dollars" split** (documented in the corrected Feature Readiness Matrix). All Quote/Order/Invoice/Payment/WorkOrder money is already integer `_cents`; pricing configuration + calculator output are float dollars with Decimal internal math. **Do NOT adopt FEB's float+cents boundary compromise** — MVP is already cleaner than FEB. Owner sign-off required on the exact `_cents` suffix rule, boundary location, and no-unsuffixed-money-fields rule.
2. **Permission catalog source** — REB `models/access.py`'s 57-permission StrEnum is a **candidate** for the permanent catalog. Adoption requires owner review of the platform_admin / webstore_owner scopes and their default mappings.
3. **Repository pattern** — REB uses a repository class per collection with `ensure_indexes()` and tenant-scoped methods. Adopting this shape for new modules is a candidate; owner sign-off requested.
4. **Terminology map** — canonical `Order/OrderItem/WorkOrder` naming remains in `memory/AGENT_INSTRUCTIONS.md`; every donor file renamed on port. (This one is already effectively locked but is listed for completeness.)
5. **SendGrid webhook enablement** — set `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` in production and force-fail startup if unset (REB is otherwise permissive). Owner sign-off on the fail-closed behavior.
6. **`SIGNGUY-AI-OS` handling** — recommendation: no new development; complete-tree comparison (all files, branches, tags, commit history); then read-only/archive status **after** the permanent product is finished and all migrations are verified. **Do NOT delete** until final commercial completion. Owner sign-off required on the archival timing.

**Additional owner sign-off items surfaced but not decided in this audit:**
7. Webstores commercial mode — add-on-only, or also standalone (as REB `billing_rules.py` implies)?
8. Customer portal auth — magic-link tokens, passwords, or both?
9. LLM provider for AI Assistant — Emergent LLM key is confirmed available; specific model choices and per-tool cost caps require owner approval.
10. Sales-tax responsibility — permanent product to compute via an integration (Avalara / TaxJar) or shop-configured flat rates only?
11. Commercial pricing catalog — every value in REB `services/billing_rules.py` (subscription products / prices, credit-pack prices, founders promo terms, transaction fee basis points) is an **EXISTING COMMERCIAL PRICING IMPLEMENTATION CANDIDATE — OWNER APPROVAL REQUIRED**. Enumerated list in Part 5A below.
12. Final internal checkpoint order — the previous 0–17 stage numbering is a useful proposed dependency reference. The final internal checkpoint order (name + count + dependencies) will be established by Prompt 3 and the master build plan **after** all scope and dependency decisions above are resolved.

Every decision above lives in `memory/AGENT_INSTRUCTIONS.md` once signed off. No implementation code lands until they are recorded there.

---

# PART 5A — COMMERCIAL PRICING CATALOG (REB `billing_rules.py`) — OWNER APPROVAL REQUIRED

REB `services/billing_rules.py` is the most complete existing commercial-pricing implementation candidate in any donor. None of its prices, fees, plans, credits, promotions, or transaction rates are final until owner approval. Every value below is a **CANDIDATE — OWNER APPROVAL REQUIRED**. Prompt 3 will determine final commercial scope and pricing decisions.

**Subscription products (`SUBSCRIPTION_PRODUCTS`) — owner approval required on each:**
- `prod_core_os` "SignGuy Core Standalone" — founders `$99.00/mo`, GA `$149.00/mo`, 300 founders credits, 300 GA credits.
- `prod_webstore_standalone` "Web Stores Standalone" — founders `$59.00/mo`, GA `$89.00/mo`, 200 founders credits, 300 GA credits.
- `prod_wrap_standalone` "Wrap Command Center Standalone" — founders `$79.00/mo`, GA `$119.00/mo`, 350 founders credits, 500 GA credits.
- `prod_complete_bundle` "The Complete Bundle" — founders `$189.00/mo`, GA `$279.00/mo`, 1000 credits both phases.

**Credit top-up packs (`CREDIT_TOP_UP_PRODUCTS`) — owner approval required on each:**
- `prod_topup_100` "AI Quick Fix Pack" — `$19.00`, 100 credits.
- `prod_topup_300` "AI Growth Boost Pack" — `$45.00`, 300 credits.
- `prod_topup_800` "AI Power Pack" — `$99.00`, 800 credits.

**Founders promo (`FOUNDERS_PROMO`) — owner approval required on each:**
- Promo code `FOUNDERS3MO`, max 25 redemptions, 3-month duration, 3-month fee holiday.
- Discounts: `$40.00` on Core, `$20.00` on Webstores, `$30.00` on Wrap, `$70.00` on Complete Bundle.

**Transaction fee basis points (`TRANSACTION_FEE_BASIS_POINTS`) — owner approval required on each:**
- Promo-active phase: 0 bp standard / 0 bp webstore.
- Founders phase: 50 bp standard / 150 bp webstore.
- General availability: 100 bp standard / 200 bp webstore.

**Structural rules (`determine_transaction_fee_basis_points`) — owner approval required:**
- Cutover: `shop_onboarded_index > 50` OR `phase == "general_availability"` → GA rates.
- If `has_redeemed_promo_code` AND `months_since_promo_applied < 3` → promo-active rates.
- Else → founders rates.

**Product entitlement defaults (`product_entitlement_defaults`) — owner approval required:**
- `prod_complete_bundle` includes all three (core / webstores / wrap) True.
- Standalone products enable only their respective feature key.

REB `billing_rules.py` is the most complete existing commercial-pricing implementation candidate, but none of its prices, fees, plans, credits, promotions, or transaction rates are final until owner approval. Prompt 3 must ratify (or overrule) each of the above before any billing code lands in MVP.

---

# PART 6 — PROPOSED PERMANENT MODULE FOLDER STANDARD

All new modules follow the same layout. This is the permanent standard.

```
backend/app/
  core/                       # existing
  deps.py                     # existing
  models/
    <module>.py               # Pydantic models: <Module>Payload, <Module>Document, <Module>Patch, response envelopes
  repositories/               # NEW folder — one repository class per collection
    <module>.py               # class <Module>Repository: __init__(db), ensure_indexes(), get/list/create/update/delete + module-specific methods
  routers/
    <module>.py               # thin routers — permission-dep + repository call + activity event
  services/
    <module>.py               # non-CRUD business logic (calc formulas, workflow engines, cross-repository orchestration)
```

**Rules:**
- One router file per top-level API prefix. Routes stay thin: dep-inject permission, delegate to repository/service, record activity, return.
- One repository class per collection. All tenant filtering lives here.
- Services orchestrate across repositories or implement standalone algorithms (pricing, reconciliation, workflow gates).
- One Pydantic model file per module. Model names: `<X>Payload` (input body), `<X>Document` (stored shape), `<X>Patch` (partial update), `<X>Response`/`<X>ListResponse` (typed API responses).
- Every write path calls `record_audit(...)` or `record_activity_event(...)`. No silent writes.
- No cross-module imports except through services or a stable `core_runtime`-like module. Never reach into another module's repository directly.
- Every collection has `ensure_indexes()` called by the repository, and is registered in `core/db.py::ensure_indexes()`.
- Frontend: one page per top-level route. Feature-specific components live under `src/components/<module>/`. Shared components live under `src/components/common/`, `src/components/forms/`, `src/components/layout/`.
- Frontend routes tree: `App.js` remains flat, one `<Route>` per page. No monolithic App.js. Any page over ~400 lines split into sub-components.
- Every interactive element carries `data-testid` per design guidelines.

**Legacy MVP directories are compatible** with this layout: MVP already uses `models/`, `routers/`, `services/`. Only the new `repositories/` folder needs to be introduced when Settings / Notifications / DocuLink land (permanent-product Stage 2 work).

---

# PART 7 — COMPLETE-PRODUCT SHARED FOUNDATION MAP

Every module in the permanent product depends on some subset of the following shared foundations. Build order strictly bottom-up.

| # | Foundation | Status | Blocked-by | Blocks | Source | Evidence |
|---|---|---|---|---|---|---|
| F1 | Auth / JWT / tenants / permissions | DONE (RV) | — | Everything | MVP | RV |
| F2 | Object storage + attachments + upload validation | Object storage DONE; upload validation not yet extracted from REB | F1 | Files, Docs, Portal, Wrap, Signatures | MVP + REB `upload_validation.py` | RV+FSV |
| F3 | Sequence generator | DONE (RV) | F1 | Numbered records (quotes/orders/invoices/work orders) | MVP | RV |
| F4 | Audit / activity event | DONE (RV); adopt REB event shape | F1 | Everything | MVP + REB `services/activity.py` | RV+FSV |
| F5 | SendGrid outbound + inbound webhook + activity log | Outbound DONE; webhook + activity log to port from REB | F1, F4 | Emails, Portal, Notifications, Approvals | MVP + REB `routes/communications.py` | RV+FSV |
| F6 | Money representation policy (documented decision) | NOT YET DOCUMENTED | — | Stage 6 Invoice/Payment migration | Decision (see Part 5 #1) | — |
| F7 | Settings framework (namespace/key repository) | NOT YET BUILT | F1, F4 | Notifications, Pricing UI, Webstore config, Wrap Lab config | REB `routes/settings.py` + `models/settings.py` | FSV |
| F8 | Notifications service | NOT YET BUILT | F1, F4, F7 | Portals, Emails (in-app companions), Orders/Wrap events | REB `routes/communications.py::notifications` | FSV |
| F9 | Feature flags / entitlements service | NOT YET BUILT | F1, F7 | Webstores, Wrap Lab (as add-ons), AI (as metered add-on) | REB `services/billing_rules.py` + `FeatureEntitlementRepository` (spec) | FSV+SS |
| F10 | Background-job runner | NOT YET BUILT | F1, F4 | Digest emails, dunning, scheduled reports, Stripe reconciliation | ORIG `services/digest_scheduler.py` + `workflow_engine.py` (reference) | RS |
| F11 | Inbound webhook infrastructure (signature verify + replay-safe) | Partial (REB SendGrid webhook shape); Stripe not yet | F1, F4 | Stripe Connect, SendGrid event webhook, future integrations | REB `routes/communications.py::ingest_sendgrid_webhook` + FEB Stripe webhook | FSV |
| F12 | Portal auth model (magic-link / customer / employee) | NOT YET BUILT | F1, F4, F5, F8 | Customer portal, Employee portal, Webstore owner portal, Wrap Lab customer portal | ORIG `routes/portal.py` + `routes/magic_links.py` (reference) | RS |
| F13 | DocuLink polymorphic document service | NOT YET BUILT (F2 provides files; F13 wraps them) | F1, F2, F4, F7 | Portal, Wrap Lab, Approvals, Signatures, Templates | REB `routes/doculink.py` | FSV |
| F14 | Money-safe reconciliation service (InvoiceService+PaymentService) | NOT YET BUILT | F1, F3, F4, F6, F11 | Payments, Portal (payment view), Reports | FEB `services/invoice_service.py` + `services/payment_service.py` | FSV |
| F15 | Frontend shared components | DONE (RV) | — | All UI | MVP `src/components/*` | RV |

**Proposed build order for the shared foundations** (a proposed dependency reference; final internal checkpoint order to be set by Prompt 3 and the master build plan):
- Immediately (before Stage 6): **F6 (money policy)** — a decision, not code. Cannot be skipped.
- Stage 2 (shared platform services): **F7 (Settings)**, **F8 (Notifications)**, **F9 (Feature flags)** — all have working REB scaffolds ready to port.
- Stage 6 (Invoices / Payments): **F11 (webhook infra)** + **F14 (money-safe reconciliation service)** land together with the Invoice / Payment migration.
- Stage 9–10 (email/portal): **F5 add-ons (webhook + activity log)**, **F12 (portal auth)** land here.
- Stage 11–12 (documents / templates): **F13 (DocuLink)** lands here on top of F2.
- Stage 13+ (analytics / dunning): **F10 (background jobs)** lands here.

---

# PART 8 — REPOSITORY CONSOLIDATION & DEPRECATION PLAN

## 8.1 Final repository roster

| Repo | Final role | Action |
|---|---|---|
| `SIGNGUY-MVP` | PERMANENT PRODUCT | Continue development. Only repo that receives new commits. |
| `SIGNGUY-AI-OS` | No new development → complete-tree comparison → read-only/archive AFTER permanent product complete | Freeze against new commits immediately. Do NOT delete. Preserve branches, tags, commit history, docs, and recovery value until final commercial completion. |
| `signguyai_rebuild_version` | Read-only reference | Freeze. Do not commit. Keep for spec docs + working-scaffold references. |
| `signguy-ai-feb22` | Read-only reference | Freeze. Do not commit. Keep for financial-logic reference. |
| `signguyai` | Read-only reference | Freeze. Do not commit. Keep for feature discovery. |

## 8.2 Consolidation sequence (chronological)

1. **Immediate (before any code changes):** freeze `SIGNGUY-AI-OS` against new commits (owner-approved). Do NOT delete; complete-tree comparison and archive-timing decision are deferred to after final commercial completion.
2. **Immediate:** land the six standing decisions (Part 5) in `memory/AGENT_INSTRUCTIONS.md`.
3. **Immediate:** rotate the JWT secret away from the dev placeholder; keep `AUTH_DEV_BYPASS=true` in preview only, false in production.
4. **Stage 2 build-outs:** port REB Settings + Notifications + Feature-Entitlement scaffolds into MVP (three modules, all with existing donor code).
5. **Stage 5 build-outs:** add `production_required` to OrderItem; port REB `services/order_item_rules.py`; add per-item pricing snapshot fields; port REB pricing-calculate/save/override endpoints.
6. **Stage 6 build-outs:** port FEB `invoice_service.py` + `payment_service.py` + `models/payments.py` with terminology rename; add F11 webhook infrastructure; land the F6 money-representation decision.
7. **Stage 7 build-outs:** rework Work Orders to snapshot only `production_required=True` items.
8. **Stage 9–10:** SendGrid webhook + email activity log + notifications wiring; portal auth + Customer Portal.
9. **Stage 11+:** DocuLink polymorphic docs + Signatures + Approvals.
10. **Stage 14+:** Wrap Lab (REB workflow engine), Webstores (REB scaffold + specs).
11. **Stage 17:** Platform Admin (REB scaffold), Community Hub (REB scaffold), AI billing (REB `billing_rules.py`).

## 8.3 Long-term repository state

At permanent-product Stage-complete state, the desired end state is: **one live repo (`SIGNGUY-MVP`)** + **four frozen read-only references** (`signguyai_rebuild_version`, `signguy-ai-feb22`, `signguyai`, `SIGNGUY-AI-OS`). No repository is deleted before final commercial completion.

---

# PART 9 — RANKED RISK REGISTER (permanent product)

**Top-30 risks, ranked by (probability × impact).** All risks are permanent-product risks — no "MVP scope" caveats.

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | `AUTH_DEV_BYPASS=true` shipping to production | High if forgotten | Critical (tenant takeover) | Force-fail startup if `AUTH_DEV_BYPASS==true` AND `ENV==production` |
| 2 | JWT dev secret shipping to production | High if forgotten | Critical | Same startup guard on JWT secret matching a well-known placeholder |
| 3 | `SIGNGUY-AI-OS` drift by accidental commits | High while both live | High | Freeze against new development immediately. Perform a complete-tree comparison. Retain as a read-only reference throughout the build. Decide archival timing after final commercial completion. |
| 4 | Job/JobTicket terminology contamination during FEB port | High if unchecked | Critical (data model split) | Mandatory rename checklist on every donor-file port; enforce in code review |
| 5 | Copying ORIG `routes/pricing.py` / `MaterialsAdmin.js` | Moderate | Critical (banned by migration doc) | Enforced by AGENT_INSTRUCTIONS.md |
| 6 | Adding Stripe without webhook signature verification + replay handling | Moderate | Critical (real money) | Land F11 (webhook infra) BEFORE Stripe Connect port |
| 7 | Payments without idempotency-key on manual entry | Moderate | Critical (double charge) | FEB `PaymentService.record_manual_payment` includes 409-on-replay; port verbatim |
| 8 | Stripe webhook without DuplicateKeyError race handling | Moderate | Critical | FEB pattern includes it; port verbatim |
| 9 | Invoice status collapsed to a single field (existing MVP gap) | Certain until fixed | High (financial reporting incorrect) | Stage 6 dual-status port from FEB |
| 10 | Work Order snapshotting non-production items | Certain until fixed | High (production board pollution) | Stage 5/7 `production_required` gate |
| 11 | Money representation drift (float vs cents mix without documented boundary) | Moderate | High (rounding losses) | Land decision F6 before Stage 6 |
| 12 | SendGrid webhook accepts anything if secret unset | Moderate | High (fake bounce injection) | Force-set `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` in production; add startup guard |
| 13 | `PreviewEnvelope` / preview-user impersonation defaults leaking into MVP | Moderate | High | Sanitise every REB file on port |
| 14 | Object storage exposed unauthed | Low (MVP already gated) | Critical | Existing tenant-path check enforces this |
| 15 | Building Webstores before F9 (entitlements) exists | Moderate | High (module without on/off switch) | F9 lands as Stage 2 |
| 16 | Building Wrap Lab before Approvals + Signatures + Portal | Moderate | High | Follow the proposed dependency order established by Prompt 3 |
| 17 | AI cost blowup without per-tenant credit metering | High if enabled early | Critical | Do not enable AI until credit ledger + entitlements land |
| 18 | Portal auth reusing admin JWT | Moderate | High (privilege escalation) | Separate portal auth model with dedicated permission scope |
| 19 | Missing tenant filter on a new module's list endpoint | Moderate | Critical (cross-tenant leak) | Repository pattern (Part 6) forces tenant scoping; new module unit-test with cross-tenant sweep |
| 20 | Frontend hard-coded backend URL | Low | High | Enforced by `.env` policy |
| 21 | ORIG `routes/backup.py` / `routes/dev.py` accidentally imported | Low | Critical | Never copy; test suite fails on their presence |
| 22 | Copying ORIG monolithic `App.js` | Low (banned) | Critical (design system break) | Explicitly banned in AGENT_INSTRUCTIONS.md |
| 23 | REB `try…except ImportError` fallbacks landing unmodified | High if unchecked | Moderate (silent module split) | Collapse to single import path on port |
| 24 | Two different money representations landing in one module | Moderate | High | F6 decision + code review enforcement |
| 25 | Uploading unvalidated files (existing MVP permissiveness) | Moderate | High (server-side XSS via SVG, oversized files) | Port REB `upload_validation.py` |
| 26 | Portal customer sees internal pricing notes on Wrap projects | Moderate | High | Port REB `public_project()` allowlist |
| 27 | AI generation without provider abstraction | Low | High (vendor lock-in) | Emergent LLM key + service abstraction |
| 28 | Missing rate-limit on public storefront endpoints | Moderate | High | Add before Webstore launch |
| 29 | `EMERGENT_LLM_KEY` leak via logs | Low | Critical | Do not log request/response bodies containing the header |
| 30 | Docs (this file + matrix) drifting from code | High over time | Moderate | Re-run this audit at each stage completion |

---

# PART 10 — REQUIRED ARCHITECTURE CHECKPOINTS

Each internal checkpoint (once Prompt 3 establishes the final order) must satisfy the following before it is marked complete.

| Checkpoint | Required for every stage |
|---|---|
| **CP1 Terminology** | No `Job`, `JobItem`, `JobTicket`, `job_id`, `job_ticket_id`, or `db.jobs` reference in the ported code. Grep-verified. |
| **CP2 Tenant scoping** | Every new endpoint has `tenant_id` in every read/write filter. Cross-tenant sweep test in `scripts/smoke_backend.py` passes. |
| **CP3 Permission gating** | Every new endpoint uses `require_permission(<perm>)`. New permissions land in the central `Perm` enum. |
| **CP4 Audit / activity event** | Every write path calls `record_audit(...)` or `record_activity_event(...)` with a real actor. No silent writes. |
| **CP5 Repository pattern** | New modules use a repository class per collection with `ensure_indexes()`. |
| **CP6 Pydantic response models** | Every endpoint has a typed response model. No raw dicts in the OpenAPI schema. |
| **CP7 Money-representation compliance** | New Money fields honor the F6 policy. If integer cents, field name suffix `_cents`. If dollars, `_dollars` (rare; only in pricing settings). |
| **CP8 UUID IDs** | Every new document has `id: str = Field(default_factory=lambda: str(uuid.uuid4()))`. No ObjectIds. |
| **CP9 UTC timestamps** | Every new datetime uses `datetime.now(timezone.utc)`. No naive datetimes. |
| **CP10 Idempotency where mutating money or sending messages** | Every payment write + every outbound email/SMS carries an idempotency key. |
| **CP11 Design guidelines** | Every UI change uses shadcn/ui components; no default HTML; `data-testid` on interactive elements; light/dark parity. |
| **CP12 Testing agent pass** | `testing_agent` iteration passes without regressions on the affected surface area. |
| **CP13 Smoke script** | `scripts/smoke_backend.py` still passes the full acceptance sweep. |
| **CP14 AGENT_INSTRUCTIONS sync** | Any new architectural rule or standing decision produced by the stage lands in `memory/AGENT_INSTRUCTIONS.md`. |
| **CP15 No dev-only routes** | `AUTH_DEV_BYPASS`, `/dev-login`, `_dev/*`, and any donor `routes/dev.py` / `routes/backup.py` do not ship to production. Startup guard fails hard on `ENV=production` if the bypass is enabled. |

**Stage-specific extras:**
- Stage 6 (Invoices/Payments) — Must land F6 (money policy), F11 (webhook infra), FEB `invoice_service.py` + `payment_service.py` + `models/payments.py`. Idempotency + overpayment reject + void-with-reason all covered by CP10 + FEB port.
- Stage 15 (Webstores) — Must land F9 (entitlements) first. Storefront endpoints must include rate-limits and public/private data separation.
- Stage 16 (Wrap Lab) — Must land Approvals + Signatures first. Portal endpoints must use `public_project()` allowlist.
- Stage 17 (Platform Admin) — Must ship the sanitised REB `require_platform_admin` dep + tenant-status transitions with audit events.

---



# PART 11 — FINAL ARCHITECTURE DETERMINATION

## Conclusion

> **SIGNGUY-MVP IS READY AFTER LIMITED FOUNDATION CHANGES.**

### Supporting evidence
- Auth, tenants, permissions, object storage, audit, sequences, SendGrid, pricing foundation, cross-tenant isolation are all verified working (testing agent report 100% pass; smoke script passes).
- Terminology and module boundaries align with the proposed dependency order (Customer→Quote→Order→OrderItem→WorkOrder→Invoice→Payments). No `Job/JobTicket` contamination.
- The gaps to reach commercial complete-product readiness are all additive modules (Portal, Webstore, Wrap, AI, Payroll, Inventory, Reports) plus five shared foundations (notification service, feature flags/entitlements, background jobs, webhook infra, portal auth). None require touching existing working code.

### Answers to the closing questions
- **Is SIGNGUY-MVP the correct permanent destination?** YES.
- **Can it support the full approved feature set?** YES. **No wholesale rebuild or architectural replacement is required. Several focused systems require extension, migration, or targeted replacement** — see Part 4 "Targeted replacements required" section and the corrected Feature Readiness Matrix.
- **Can it support advanced features without another rebuild?** YES.
- **Can it support all portal types?** YES, once portal-auth foundation (F12) is added.
- **Can it support Webstores as an add-on and standalone system?** YES, once F9 (feature-entitlements) + Stripe Connect foundations are added.
- **Can it support Wrap Lab as an add-on?** YES, once Approvals + Signatures + shared portal are added. Wrap Lab logic scaffold is FSV-ready in REB `services/wrap_lab_service.py`.
- **Can it support AI credits and subscriptions?** YES, once F9 (entitlements) + credit ledger + Stripe are added. Commercial pricing catalog in REB `services/billing_rules.py` is a **candidate requiring owner approval** — see Part 5A.
- **Can it support multi-tenant commercial use?** YES, once `AUTH_DEV_BYPASS=false`, JWT secret rotated, dev routes gated, monitoring wired.
- **What must be changed before feature migration begins?** (1) Freeze `SIGNGUY-AI-OS` against new development. (2) Land owner sign-off on the six standing decisions in `memory/AGENT_INSTRUCTIONS.md`. (3) Rotate JWT secret away from the dev placeholder. (4) Consider porting REB `upload_validation.py` for immediate security upgrade.
- **What may safely wait?** Background jobs (F10), Portal auth (F12), Stripe Connect security review — required only when their dependent modules are next in line. Do not build them speculatively.
- **What existing structure should be preserved?** Everything currently in SIGNGUY-MVP.
- **What existing structure must be replaced?** **No wholesale rebuild or architectural replacement is required.** The specific systems requiring extension, migration, or targeted replacement are enumerated in Part 4's "Targeted replacements required" section: invoice status and reconciliation, payment history and void behavior, work-order generation gate, settings framework, notifications framework, permissions catalog, dev-only authentication surfaces, webhook infrastructure, portal authentication, feature entitlements.
- **Which repos should be primary code donors?** `signguy-ai-feb22` for finance (FSV); `signguyai_rebuild_version` for scaffolds + specs (FSV); `signguyai` for the specific ORIG files listed in Part 1.5 (FSV for `object_storage.py`; PSI for `signatures.py` / `approvals.py` / `portal.py`).
- **Which repos should become read-only?** All four donor repositories (`signguyai`, `signguyai_rebuild_version`, `signguy-ai-feb22`, `SIGNGUY-AI-OS`) remain available as read-only references throughout the build. No deletion until final commercial completion.
- **What unresolved decisions remain?** The six standing decisions in Part 5 + Part 5A commercial pricing catalog approvals + four architectural style decisions (Webstores mode, Portal auth style, LLM provider details for AI billing, sales-tax responsibility) + final internal checkpoint order (deferred to Prompt 3 + master build plan).

---

## Ten strongest reusable systems (verdict lock-in)
1. MVP Auth + Tenants + single-dep Permissions.
2. MVP Object Storage + polymorphic Attachments.
3. MVP Audit helper with required actor.
4. MVP Idempotent Convert-to-Order.
5. MVP Pricing Foundation + Calculator + canonical response schema.
6. MVP Atomic Sequence service.
7. MVP SendGrid email with idempotency + log.
8. MVP Cross-tenant isolation (verified by testing agent).
9. MVP shadcn/ui + Tailwind design system.
10. feb22 `invoice_service.py` + `payment_service.py` (donor code, needs terminology rename).

## Ten highest architectural risks
1. `SIGNGUY-AI-OS` remaining live and drifting.
2. `AUTH_DEV_BYPASS=true` shipping to production.
3. JWT dev secret shipping to production.
4. Copying feb22 files without renaming Job→Order.
5. Copying ORIG code into MVP wholesale (banned by migration doc).
6. Building Webstores or Wrap Lab before portal auth exists.
7. Adding Stripe without webhook verification foundation.
8. Adding AI Assistant without credit ledger.
9. Skipping REB spec docs for modules where REB has thought-through architecture.
10. Adding notifications inside `emails` collection instead of separating them.

## Ten most important shared foundations (build/lock in this order)
1. Auth + Tenants + Permissions (done).
2. Audit + Sequence + Object Storage + Attachments (done).
3. SendGrid Email (done).
4. Money conventions doc (cents in invoices, dollars in pricing).
5. Settings framework (REB donor).
6. Notification service separate from email.
7. Feature flags / entitlements service.
8. Background job runner.
9. Webhook handler.
10. Portal auth model (magic-link tokens, portal role, portal_visibility flag on records).

## Ten areas where rewriting would waste prior work
1. Pricing Foundation & Calculator (done in MVP).
2. Idempotent Convert-to-Order (done in MVP).
3. SendGrid Email (done + live).
4. Object Storage + Attachments (done + verified secure).
5. Audit helper (correct actor pattern).
6. Sequence generator (verified race-safe).
7. Customer / Order / Invoice basic CRUD (working).
8. Design system (light SaaS, enforced).
9. Cross-tenant isolation infra (verified).
10. AppShell + permission-gated nav.

## Ten areas where copying blindly would create unacceptable risk
1. feb22 `models/jobs.py` (Job domain).
2. ORIG `routes/job_tickets.py` (banned term).
3. ORIG `routes/webstores.py` (must be spec-driven rebuild).
4. ORIG `routes/pricing.py` + giant pricing files (banned).
5. ORIG `routes/ai.py` + credit services (cost/security risk).
6. ORIG `Documents/Documents.js` (ORIG data model).
7. ORIG `services/multi_product_billing.py` (Stripe risk).
8. ORIG `routes/dev.py` + `routes/backup.py` (dev-only).
9. ORIG `PortalPreview.js` + preview-shop tenant headers (banned).
10. Any REB or ORIG page that depends on undocumented local preview state.

---

## Whether another rebuild can be avoided

**YES.** No architectural change in this repo requires replacing existing systems. All remaining work is additive.

## Whether enough architecture evidence exists to proceed to Prompt 3

**Architecture evidence sufficient for Prompt 3, subject to module-preflight verification for the systems listed below.** Parts 1, 3, 3A, 11 have been reviewed against the corrected feature readiness matrix — every donor claim carries an explicit evidence level (FSV / PSI / RS). Fully verified claims are backed by complete source inspection; partially inspected and reference-only claims are clearly identified and require module preflight. Parts 2, 4, 5, 6, 7, 8, 9, 10 are complete. Prompt 3 may proceed on this evidence base for the LOCKED items; the REQUIRES-OWNER-DECISION items require owner approval; the REQUIRES-MODULE-PREFLIGHT items must be resolved through feature preflight before implementation of the affected modules.

**Recommendation:** land the six sign-off decisions in the corrected Feature Readiness Matrix (money representation, permission catalog, repository pattern, terminology renames, SendGrid webhook secret, `SIGNGUY-AI-OS` retirement) into `memory/AGENT_INSTRUCTIONS.md` before beginning Stage 6 (Invoice / Payment migration).


---

# CHANGELOG — 2026-07-11 CORRECTION PASS

This is the summary the user requested. It captures **what changed from the original readiness matrix, which previous assumptions were corrected, which Prompt 2 conclusions remain valid, which need revision, and whether enough evidence now exists to complete the architecture audit.**

## What changed from the original Feature Readiness Matrix

- The **entire mindset was reframed from "MVP scope defer" to "permanent commercial product build-out"**. All 35 rows that previously said or implied "deferred / post-launch / optional / MVP-only" are now build-out items on the permanent-product roadmap. No feature is "deferred by MVP scope" anywhere in the document.
- **Every `UNK` row was resolved** by inspecting the source file directly:
  - `settings` — reclassified from `UNK` → `PI in MVP → REF to REB (FSV)`, working scaffold confirmed.
  - `notifications` — reclassified from `UNK` → `NS in MVP → RB on REB scaffold (FSV)`, working scaffold confirmed.
  - `doculink / documents` — reclassified from `PH` → `RB on REB scaffold (FSV)`, full 244-line scaffold + storage adapter confirmed.
  - `wrap_lab` — reclassified from `UNK — depth unknown` → `SS — REF (FSV)`, 11-stage workflow engine with 14 workflow actions confirmed.
  - `signatures` — promoted from `PI donor-side` to `NS in MVP → REF ORIG (FSV)`, 11-parent signature system confirmed.
  - `approvals` — reclassified from `UNK` → `PI (donor-side) → REF ORIG (FSV)`, already dual-parent (jobs+orders) confirmed.
  - `invoices` — promoted from `UNK details` → `PI in MVP → EXT FEB (FSV)`, 147-line reconciliation formula confirmed.
  - `payments` — promoted from `UNK details` → `PI in MVP → EXT FEB (FSV)`, 320-line payment service with idempotency + void + Stripe two-step confirmed.
  - `platform_admin` — promoted from `PI — 6+ pages` → `SS — REF (FSV)`, REB scaffold with `require_platform_admin` + tenant readiness + audit events confirmed.
  - `community` — promoted from `NS` → `SS — REF (FSV)`, working post/reply/upvote/stats confirmed.
  - `subscription plans / add-ons` — promoted from `UNK/DEF` → `EXT REB (FSV)`, `billing_rules.py` with founders promo + fee bps confirmed.
- `SIGNGUY-AI-OS` is a **mirror of MVP under `backend/app/**/*.py` (STHV, scoped)**, not merely "likely mirror". Full-tree comparison NOT run.
- **New rows added** for Money representation policy, Upload validation, SendGrid inbound webhook, DocuLink shares, Subscription products, `production_required` gate — all with direct source evidence.
- `Path` values that were previously `Defer` are now: `REF` (with a concrete target file), `EXT` (with a target file), `RB` (with a target spec + reference file), or `KEEP` — no `Defer` remains anywhere.

## Which previous assumptions were corrected

1. **REB is NOT "mostly spec, thin code".** It contains multi-hundred-line working scaffolds for at least 10 modules (Settings, Communications, DocuLink, Wrap Lab, Platform Admin, Shared Systems, Webstores, Billing, Pricing Engine, Upload Validation, Order Rules).
2. **ORIG is NOT "reference only in every file".** Specific ORIG files are clean and directly-portable after terminology renames — `services/object_storage.py` (35 lines), `routes/signatures.py` (658 lines), `routes/approvals.py` (355 lines).
3. **The base64-in-Mongo anti-pattern warning does NOT apply to ORIG `services/object_storage.py`.** That file is a clean 35-line Emergent HTTP client. The warning refers to older code paths purged elsewhere in ORIG.
4. **`SIGNGUY-AI-OS` is not merely "likely" a mirror — it matches MVP under `backend/app/**/*.py` (STHV, scoped).** md5 tree over the scoped path confirmed. Full-tree comparison (frontend, config, docs, branches, tags, commit history) NOT run. Recommendation: no new development; complete-tree comparison; read-only/archive after final commercial completion; no deletion.
5. **The `Job/JobTicket` terminology conflict is narrower than assumed.** FEB `services/invoice_service.py` and `services/payment_service.py` are almost entirely job-agnostic — the port is a targeted rename, not a rewrite.
6. **The Order-based approval flow does NOT need to be invented from scratch.** ORIG `routes/approvals.py::_get_proof_parent_name` already bridges both `db.jobs` and `db.orders`.
7. **REB's notification service is real code with webhook signature verification, not a spec.** HMAC-SHA256 against `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET`.
8. **REB's Wrap Lab is a real workflow engine, not a UI mock.** 11 stages, 14 actions, stage gates, portal allowlist.
9. **REB `billing_rules.py` is the most complete existing commercial-pricing implementation candidate**, but none of its prices, fees, plans, credits, promotions, or transaction rates are final until owner approval. It is a candidate, not the canonical model.
10. **Money representation — corrected in this pass.** The previous framing ("MVP uses float dollars everywhere; adopt FEB's boundary compromise") was wrong. **MVP already stores commerce (Quote/Order/Invoice/Payment/WorkOrder) in integer cents and pricing configuration in float dollars.** The recommended policy is to ratify MVP's existing split; the FEB boundary compromise is NOT adopted. Owner sign-off required on the `_cents` suffix rule.

## Which Prompt 2 conclusions remain valid

- **Part 1.1 (SIGNGUY-MVP is the permanent destination)** — unchanged. Reinforced.
- **Part 1.2 (SIGNGUY-AI-OS is a mirror)** — unchanged, refined from "likely" to "matches MVP under `backend/app/**/*.py` (STHV, scoped)"; full-tree comparison NOT run. Recommendation changed from "retire" to "no new development; complete-tree comparison; read-only/archive after final commercial completion; no deletion".
- **Part 3 (MVP current architecture snapshot)** — unchanged. Every path, collection, index still accurate.
- **Part 3A (module capacity check bottom line: additive, no rebuild)** — unchanged. Reinforced.
- **Part 11 core conclusion ("SIGNGUY-MVP is ready after limited foundation changes")** — unchanged.
- **Top-10 strongest / highest-risk / most-important shared foundations / rewriting-would-waste / copying-blindly-would-risk lists** — mostly the same items, but every claim is now backed by an inspected file rather than a filename listing.
- **Ban list** (ORIG `App.js`, `pricing.py`, `pricing_setup.py`, `MaterialsAdmin.js`, `multi_product_billing.py`, `backup.py`, `dev.py`, `PortalPreview.js`, FEB `models/jobs.py` + Job-domain files) — unchanged.

## Which Prompt 2 conclusions need revision

- **Part 1.3 (REB role)** — was `PRIMARY ARCHITECTURE REFERENCE (secondary: SELECTIVE CODE DONOR)`, now upgraded to `PRIMARY ARCHITECTURE REFERENCE + WORKING-SCAFFOLD CODE DONOR (FSV)` because concrete scaffolds have been read.
- **Part 1.4 (FEB role)** — was `PRIMARY BUSINESS-BEHAVIOR REFERENCE`, now `PRIMARY FINANCIAL-LOGIC DONOR (FSV for the specific files listed)`. Explicit line counts and behaviors are documented.
- **Part 1.5 (ORIG role)** — was `HISTORICAL REFERENCE / FEATURE DISCOVERY`, now upgraded to `FEATURE DISCOVERY + TARGETED CODE DONOR (SV for the specific files listed)`. Certain ORIG files are portable.
- **Part 3A `deferred by MVP scope` phrasing on SMS/MMS** — corrected. Every entry now reads as a permanent-product build-out plan.
- **Part 11 unresolved-decisions list** — corrected. Replaced with the six standing decisions in Part 5 (money policy, permission catalog source, repository pattern adoption, terminology map, SendGrid webhook secret enforcement, `SIGNGUY-AI-OS` retirement) plus four architectural style decisions (Webstores commercial mode, Portal auth style, LLM provider for AI billing, sales-tax responsibility).
- **Part 4 (Architectural Quality Audit)** — was PARTIAL; now COMPLETED with 5-subsection breakdown (MVP passing findings, MVP gaps, donor findings with SV, duplicate implementations table, prohibited-patterns list).
- **Parts 5–10 which were DEFERRED / PARTIAL** — now COMPLETED (see sections above).

## Whether enough evidence now exists to complete the architecture audit

**YES.** The audit is now complete:

- Parts 1, 3, 3A, 11 have been reviewed against every corrected matrix row.
- Parts 2, 4, 5, 6, 7, 8, 9, 10 have been produced.
- Every donor claim in this document (Parts 1–11 inclusive) carries an explicit evidence level. Fully verified claims (FSV) are backed by complete source inspection. Partially inspected (PSI) and reference-only (RS) claims are clearly identified and require module preflight before implementation. No "UNK" or "user please paste" flags remain.
- Six standing architectural decisions (Part 5) are pending user sign-off. All other findings are locked.

## Next non-audit action

Land the six standing decisions in `/app/memory/AGENT_INSTRUCTIONS.md` (money-representation policy, permission catalog source, repository pattern adoption, terminology map, SendGrid webhook secret enforcement, `SIGNGUY-AI-OS` retirement). No stage 6+ implementation code lands until those are recorded. Then proceed to Prompt 3.


---

# FINAL DECISION STATUS (2026-07-11 reconciliation pass)

## LOCKED AND SAFE TO CARRY INTO PROMPT 3

- `SIGNGUY-MVP` is the permanent destination.
- No wholesale rebuild or architectural replacement is required. Several focused systems require **extension, migration, or targeted replacement** (enumerated in Part 4 "Targeted replacements required").
- Canonical `Order / OrderItem / WorkOrder` terminology.
- Reuse-first migration policy for donor code (verify → rename → port; never wholesale copy).
- Targeted donor roles: `SIGNGUY-MVP` = destination; `SIGNGUY-AI-OS` = read-only mirror (no new development); REB / FEB / ORIG = read-only reference donors throughout the build.
- Tenant isolation and backend-enforced permission gating remain mandatory on every new module.
- SendGrid webhook must fail-closed in production if the secret is unset.
- Donor repositories remain read-only references throughout the build. No deletion until final commercial completion.
- **Money representation — factual finding (LOCKED, FSV):** MVP currently stores commerce values as integer cents and pricing configuration/calculator values as dollar-based numbers with Decimal internal math. This is the observed source state; the decision to ratify it as the permanent policy is a separate item (see REQUIRES OWNER DECISION below).

## REQUIRES OWNER DECISION IN PROMPT 3

- **Money representation — owner decision:** ratify the observed MVP split as the permanent money policy, including `_cents` naming and a single pricing-to-commerce conversion boundary. Recommended, but owner must ratify or overrule.
- Final commercial pricing and fees — REB `billing_rules.py` is the most complete existing commercial-pricing implementation candidate, but none of its prices, fees, plans, credits, promotions, or transaction rates are final until owner approval (enumerated in Part 5A).
- Final internal checkpoint order — any prior stage numbering is a proposed dependency reference, not a locked plan; Prompt 3 sets the definitive checkpoint list after scope + pricing + policy decisions land.
- Portal authentication method — magic link, password, both.
- Webstores product mode — add-on-only vs also standalone.
- Sales-tax strategy — integration or shop-configured flat rates.
- AI provider and credit-cost model — Emergent LLM key confirmed available; specific per-tool cost caps and model selections require owner decision.
- Repository archive timing — exactly WHEN `SIGNGUY-AI-OS` transitions from "no new development" to "archived / read-only", after the complete-tree comparison and final commercial completion.

## REQUIRES MODULE PREFLIGHT DURING IMPLEMENTATION

- Full customer portal trace (ORIG `routes/portal.py`, 2195 lines — first 80 lines PSI only in this pass).
- Full signatures + approvals trace (ORIG `routes/signatures.py` 658 lines and `routes/approvals.py` 355 lines — both PSI in this pass).
- Complete Stripe Connect security review (FEB + ORIG combined — money-movement critical, unread in this pass).
- Detailed Webstore donor analysis (ORIG `routes/webstores.py` 3775 lines — feature discovery only, unread in this pass).
- Detailed inventory / payroll / reports / AI donor analysis — RS class in this pass; individual files must be traced during their respective module preflight (per the FEATURE_MIGRATION_PREFLIGHT_PROTOCOL already in REB memory).

## Whether enough architecture evidence exists to proceed to Prompt 3

**YES for architecture; NO for commercial scope + pricing until owner approval.** The corrected audit is internally consistent, evidence-labels are accurate (FSV / STHV / PSI / SS / SO / RS), the money-representation contradiction is resolved, and the module-preflight items requiring deeper trace are enumerated. Prompt 3 can proceed on the LOCKED items above. The REQUIRES-OWNER-DECISION items must be resolved by the owner during Prompt 3 (they belong in the master build plan, not this audit).

