# SignGuy AI — Repository & Architecture Source Map

**Audit date:** 2026-07-07  
**Auditor:** E2 agent (read-only, no code changes)  
**Companion document:** `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (already produced) — used as evidence source for feature-level readiness.

## Completion checklist for this audit

| Part | Section | Status | Notes |
|---|---|---|---|
| 1 | Repository Responsibility Map | **COMPLETED** | Below. |
| 2 | Source-of-Truth Map by System | **PARTIAL — see companion matrix** | Covered per-module in `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`. This doc summarizes verdicts; per-file rows are in the matrix. Full re-render deferred to Part 2 of this audit. |
| 3 | SIGNGUY-MVP Current Architecture Snapshot | **COMPLETED** | Exact paths + collections + flows below. |
| 3A | Complete-Product Architecture Capacity Check | **COMPLETED** | Below. |
| 4 | Architectural Quality Audit | **PARTIAL** | MVP findings enumerated; donor findings marked UNKNOWN where evidence is limited to file trees. Full donor-file inspection deferred until user grants me time / repo pastes. |
| 5 | Required Target Architecture Decisions | **DEFERRED — Part 2 of this audit** | Will be produced in the next turn. |
| 6 | Proposed Permanent Module Folder Standard | **DEFERRED — Part 2** | |
| 7 | Complete-Product Shared Foundation Map | **PARTIAL** | Dependency list included below in Part 3A; full per-foundation table deferred to Part 2. |
| 8 | Repository Consolidation & Deprecation Plan | **PARTIAL — early recommendation below**; full plan deferred to Part 2. |
| 9 | Ranked Risk Register | **PARTIAL** | Top risks below; full ranked register deferred to Part 2. |
| 10 | Required Architecture Checkpoints | **DEFERRED — Part 2** | |
| 11 | Final Architecture Determination | **COMPLETED** | Conclusion below. |

**Sections requiring additional repository inspection** (I cannot verify from file trees alone; user must paste files or grant deeper access): all UNK rows in `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (about 30 modules).

**Unverified findings:** any donor-repo statement that is not backed by a filename I have listed. Every claim below about a specific donor file was verified via `api.github.com/repos/<repo>/git/trees/<branch>?recursive=1`.

**Remaining work:** Parts 2, 5, 6, 7 (full), 8 (full), 9 (full), 10.

---

# PART 1 — REPOSITORY RESPONSIBILITY MAP

## 1.1 `dnblack323/SIGNGUY-MVP`  — **PERMANENT DESTINATION**

- **URL:** https://github.com/dnblack323/SIGNGUY-MVP
- **Original intended purpose:** Fresh MVP repository per the migration instructions doc; permanent production application.
- **Current actual purpose:** Same. Live app deployed to https://production-launch-11.emergent.host and previewing at https://production-launch-11.preview.emergentagent.com.
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

## 1.2 `dnblack323/SIGNGUY-AI-OS` — **DEPRECATED (mirror of SIGNGUY-MVP)**

- **URL:** https://github.com/dnblack323/SIGNGUY-AI-OS
- **Original intended purpose:** Unclear from tree.
- **Current actual purpose:** Byte-level file-tree clone of `SIGNGUY-MVP` (same 193 items, same 21 pages, same 13 routers, same 7 services, same 11 models). Only artifact size differs (2.4 MB vs 182 KB, likely lockfile delta).
- **Development status:** Effectively dormant relative to MVP; last push 2026-07-08 same day.
- **Architecture:** identical to MVP.
- **Strongest modules:** identical to MVP.
- **Weakest modules:** identical to MVP.
- **Duplicate / abandoned systems:** the entire repo is a duplicate of MVP.
- **Recommended role in final build:** **DEPRECATED OR ARCHIVE ONLY.** Archive with a frozen tag. Do not develop here.
- **Final warnings:** leaving both active guarantees future drift and conflicting commits. Archive immediately.

## 1.3 `dnblack323/signguyai_rebuild_version` — **PRIMARY ARCHITECTURE REFERENCE (secondary: SELECTIVE CODE DONOR)**

- **URL:** https://github.com/dnblack323/signguyai_rebuild_version
- **Original intended purpose:** Rebuild-in-progress workspace.
- **Current actual purpose:** Effectively a **spec repository**. 349 files but only **5 frontend pages** (auth pages only). Backend has 18 routes and 14 services scaffolded, likely thin. Real value is `memory/MODULE SPECS MDS/` — 17 module rebuild guides — plus 8 top-level `ORDER_PORTAL_*_SPEC.md` files.
- **Development status:** Active-ish for docs; UI implementation stalled.
- **Architecture:** Python + JavaScript, similar layout to MVP; distinct `models/` folder (19 model files) suggests thoughtful data-model planning.
- **Strongest modules (assets):** SPEC DOCS — `SALES_WORKFLOW_QUOTES_ORDERS_ORDER_ITEMS_REBUILD_DOC.md`, `USERS_ROLES_PERMISSIONS_ACCESS_CONTROL_REBUILD_DOC.md`, `FILE_UPLOADS_ATTACHMENTS_STORAGE_REBUILD_DOC.md`, `EMAIL_NOTIFICATIONS_SENDGRID_REBUILD_DOC.md`, `SETTINGS_CONFIGURATION_FRAMEWORK_REBUILD_DOC.md`, all `ORDER_PORTAL_*_SPEC.md`, `WRAP_LAB_TRANSFER_COMPLETION.md`, `WEBSTORES_PRODUCT_SPEC.md`.
- **Weakest modules:** frontend (barely started); real code coverage of the specs.
- **Reusable services (code candidates):** `services/activity.py`, `services/order_item_rules.py`, `services/order_schemas.py`, `services/pricing_engine.py`, `services/doculink_bridge.py`, `services/doculink_storage.py`, `services/wrap_lab_service.py`, `services/upload_validation.py`.
- **Reusable models:** `models/access.py`, `models/settings.py`, `models/communications.py`, `models/doculink.py`, `models/wrap_lab.py`.
- **Architectural problems:** UI mismatch with backend (very few frontend pages relative to routes) suggests some routes may be dead.
- **Code that must not be copied wholesale:** entire backend or entire frontend directories — inspect file-by-file first.
- **Suitable for direct reuse:** SPEC DOCS (`memory/MODULE SPECS MDS/*.md`, `ORDER_PORTAL_*_SPEC.md`).
- **Business-logic-extraction only:** `services/order_item_rules.py`, `services/pricing_engine.py`, `services/wrap_lab_service.py`, `services/doculink_*.py`.
- **Genuinely requires rebuilding:** any UI beyond auth.
- **Recommended role:** **PRIMARY ARCHITECTURE REFERENCE** (docs), secondary **SELECTIVE CODE DONOR** (services after per-file audit).
- **Final warnings:** the ORDER_PORTAL specs are extensive and would drive the entire Webstore/Order Portal Manager rebuild — do not attempt Webstores before reading them.

## 1.4 `dnblack323/signguy-ai-feb22` — **PRIMARY BUSINESS-BEHAVIOR REFERENCE** (financial subsystem)

- **URL:** https://github.com/dnblack323/signguy-ai-feb22
- **Original intended purpose:** February backup / financial correction branch.
- **Current actual purpose:** Highest-value donor for **Invoices + Payments + Stripe Connect** logic. 442 files. Has dedicated `invoice_service.py` and `payment_service.py` — the exact files the mandated build order (Stage 6) tells us to adapt.
- **Development status:** Historical (last push 2026-07-10 for what looks like doc updates).
- **Architecture:** Python + JavaScript. Uses `Job/JobItem/JobTicket` domain (INCOMPATIBLE with MVP terminology).
- **Strongest modules:** `services/invoice_service.py`, `services/payment_service.py`, `models/payments.py` (dedicated payments model), `routes/stripe_connect.py`, `memory/FEBRUARY_BACKUP_FINANCIAL_CORRECTION_MASTER_PLAN.md`, `backend_test.py`.
- **Weakest modules:** anything Job-domain-centric conflicts with MVP.
- **Reusable services:** `services/invoice_service.py`, `services/payment_service.py`, `services/feature_gate.py`, `services/tier_config.py`.
- **Reusable models:** `models/payments.py`.
- **Reusable tests:** `backend_test.py` + `tests/` directory (audit later).
- **Reusable UI patterns:** none over MVP's existing shadcn/ui system.
- **Code that must not be copied wholesale:** `models/jobs.py`, `routes/jobs.py`, `routes/tiers.py`, `routes/portal.py`, `routes/employees.py`, `routes/employee_portal.py`, everything Job-domain.
- **Suitable for business-logic extraction only:** `invoice_service.py`, `payment_service.py`, `models/payments.py`.
- **Recommended role:** **PRIMARY BUSINESS-BEHAVIOR REFERENCE** for finance.
- **Final warnings:** every ported line must be terminology-renamed. Do not create parallel `Job*` collections in MVP.

## 1.5 `dnblack323/signguyai` — **HISTORICAL REFERENCE / FEATURE DISCOVERY**

- **URL:** https://github.com/dnblack323/signguyai
- **Original intended purpose:** Original monolithic app.
- **Current actual purpose:** Feature discovery map. 1181 files, 60 routes, 133 pages, 29 services. Everything is here in some form (webstores, wrap lab, portal, AI, payroll, community, platform admin, meta/facebook, sms, inventory).
- **Development status:** Historical but still receiving doc updates (last push 2026-07-10).
- **Architecture:** FastAPI + React; uses `Job/JobTicket` domain; scattered permission checks; monolithic frontend `App.js`; base64 file storage risk per migration doc.
- **Strongest modules:** feature INVENTORY. Nothing else.
- **Weakest modules:** architecture — the giant `App.js`, giant pricing system, and Job-domain terminology are all explicitly forbidden by the migration doc.
- **Reusable business logic:** small, isolated helpers only (identify per-file).
- **Reusable UI:** rebuild-version instructions say use it for "grouped workspace navigation, compact Office-style ribbons" concepts — inspect, don't copy.
- **Architectural problems:** monolithic `App.js`; unverified tenant checks; base64 file storage; scattered pricing.
- **Security concerns:** documented in migration doc — "unverified tenant access, portal access, Stripe Connect".
- **Code that must not be copied wholesale:** everything.
- **Suitable for business-logic extraction only:** isolated small helpers if & only if MVP has no equivalent.
- **Genuinely requires rebuilding:** every module ported must be rebuilt on MVP foundations.
- **Recommended role:** **HISTORICAL REFERENCE.**
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
| SMS / MMS | **REQUIRES MODULE-SPECIFIC WORK** | Twilio integration TBD; explicitly deferred by MVP scope. |
| Background jobs / Webhooks | **REQUIRES FOUNDATION WORK** | Not present. Needed before Stripe + email delivery tracking + digest emails. |
| Global search | **REQUIRES MODULE-SPECIFIC WORK** | Simple per-collection endpoints exist; unified search is new. |
| Reports / Custom report builder / Analytics | **REQUIRES MODULE-SPECIFIC WORK** | Data foundation exists; reporting layer is new. |
| Feature flags / Entitlements | **REQUIRES FOUNDATION WORK** | Not present; needed before webstore add-on gating and AI credit gating. |
| Multi-tenant commercial scaling | **READY WITH SMALL CHANGES** | Auth + tenant + indexes correct; need production JWT secret rotation, dev bypass off, monitoring. |
| Standalone add-on boundaries | **REQUIRES FOUNDATION WORK** | Add-on = feature-flag + module + entitlement service. All three need to exist before Webstore/Wrap-Lab as add-ons. |
| Prevention of another rebuild | **YES — with the changes above** | Current architecture is modular (routers per entity, services layer, one Pydantic model per collection, single permission dep, shared services). If the next round of migrations respects module boundaries and shared services, no rebuild is required. |

**Bottom line:** MVP's foundations are compatible with the full product. The missing pieces are all **additive** (new services, new modules) not **destructive** (no need to replace existing systems). No rebuild required — but ~5 shared foundations must be built before webstore/wrap/portal work begins.

---

# PART 11 — FINAL ARCHITECTURE DETERMINATION

## Conclusion

> **SIGNGUY-MVP IS READY AFTER LIMITED FOUNDATION CHANGES.**

### Supporting evidence
- Auth, tenants, permissions, object storage, audit, sequences, SendGrid, pricing foundation, cross-tenant isolation are all verified working (testing agent report 100% pass; smoke script passes).
- Terminology and module boundaries already match the mandated build order (Customer→Quote→Order→OrderItem→WorkOrder→Invoice→Payments). No `Job/JobTicket` contamination.
- The gaps to reach commercial complete-product readiness are all additive modules (Portal, Webstore, Wrap, AI, Payroll, Inventory, Reports) plus five shared foundations (notification service, feature flags/entitlements, background jobs, webhook infra, portal auth). None require touching existing working code.

### Answers to the closing questions
- **Is SIGNGUY-MVP the correct permanent destination?** YES.
- **Can it support the full approved feature set?** YES, after five additive foundations are in place (notifications, feature flags, background jobs, webhooks, portal auth).
- **Can it support advanced features without another rebuild?** YES.
- **Can it support all portal types?** YES, once portal-auth foundation is added.
- **Can it support Webstores as an add-on and standalone system?** YES, once feature-entitlements + Stripe Connect foundations are added.
- **Can it support Wrap Lab as an add-on?** YES, once Approvals + Signatures + shared portal are added.
- **Can it support AI credits and subscriptions?** YES, once entitlements + credit ledger + Stripe are added.
- **Can it support multi-tenant commercial use?** YES, once `AUTH_DEV_BYPASS=false`, JWT secret rotated, dev routes gated, monitoring wired.
- **What must be changed before feature migration begins?** (1) Retire `SIGNGUY-AI-OS`. (2) Read the REB spec docs (`memory/MODULE SPECS MDS/*`). (3) Adopt Stage 6 dual-status invoice model from feb22.
- **What may safely wait?** Portal auth, feature flags, background jobs, webhooks — these are only required when their dependent modules are next in line. Do not build them speculatively.
- **What existing structure should be preserved?** Everything currently in SIGNGUY-MVP.
- **What existing structure must be replaced?** Nothing in SIGNGUY-MVP.
- **Which repos should be primary code donors?** `signguy-ai-feb22` for finance; `signguyai_rebuild_version` for specs.
- **Which repos should become read-only?** `signguyai`, `signguyai_rebuild_version`, `signguy-ai-feb22`, `SIGNGUY-AI-OS` (the last one archived).
- **What unresolved decisions remain?** (1) SIGNGUY-AI-OS retirement (needs owner say-so). (2) Whether Webstores ships as add-on-only or also standalone. (3) Whether the customer portal uses magic links, passwords, or both. (4) LLM provider choice for AI Assistant. (5) Stripe Connect vs. simple Stripe Payments for MVP webstore.

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

**PARTIAL.** Parts 1, 3, 3A, 11 are complete and safe to proceed on. Parts 5, 6, 7 (full), 8 (full), 9 (full), and 10 need to be finished in a follow-up turn before Prompt 3 can be executed with full confidence. Part 4 (architectural quality audit) needs deeper donor-repo file reads to fully classify UNK rows.

**Recommendation:** approve Parts 1, 3, 3A, and 11 now; I'll write Parts 2, 5, 6, 7 (full), 8 (full), 9 (full), and 10 in the next turn without touching code.

