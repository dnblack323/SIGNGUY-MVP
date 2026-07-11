# SignGuy AI — Feature Readiness Matrix

**Audit date:** 2026-07-07  
**Auditor:** E2 agent (read-only inspection, no code changes)  
**Repositories inspected (public, verified HTTP 200 on GitHub API):**

| Repo | Default branch | Last push | Files | Notes |
|---|---|---|---|---|
| `dnblack323/SIGNGUY-MVP` | main | 2026-07-08 | 161 | Destination. Current production. |
| `dnblack323/SIGNGUY-AI-OS` | main | 2026-07-08 | 161 | **Identical file tree to SIGNGUY-MVP** — appears to be a mirror or older snapshot of the same codebase. |
| `dnblack323/signguyai_rebuild_version` | main | 2026-07-07 | 349 | Primarily specs + partial rebuild. 46 spec docs; only 5 frontend pages (auth only). Backend has 18 routes and 14 services scaffolded. |
| `dnblack323/signguy-ai-feb22` | main | 2026-07-10 | 442 | Financial-logic donor. 22 routes, 59 pages, 6 services (`invoice_service.py`, `payment_service.py`). Uses `Job` domain. |
| `dnblack323/signguyai` | main | 2026-07-10 | 1181 | Original giant repo. 60 routes, 133 pages, 29 services. Full feature footprint incl. Wrap Lab, Webstores, Portal, AI, Payroll, Community, Platform Admin, Meta. Uses `Job/JobTicket` domain. |

> **Scope note.** This audit reasons from file-tree evidence + spec docs. I did not run the donor apps and did not read every file. Where implementation depth cannot be inferred from structure + spec docs, the row is marked **UNKNOWN DUE TO MISSING EVIDENCE** and the specific missing evidence is listed in the closing "Missing information" section.

---

## Critical up-front findings

1. **SIGNGUY-MVP ≡ SIGNGUY-AI-OS.** Both repos contain the same 193 items, 21 frontend pages, 13 backend routers, 7 services, 11 models. `SIGNGUY-AI-OS` is 2.4 MB vs MVP's 182 KB (lockfile / node_modules delta), but the source tree matches exactly. **Recommendation: retire `SIGNGUY-AI-OS`** or explicitly document its intended distinct role. Otherwise it will inevitably drift and create a fifth conflicting source.
2. **`signguyai_rebuild_version` is 90% specs, ~10% code.** Its true value is the `memory/MODULE SPECS MDS/` folder (17 module spec MDs) and the ORDER_PORTAL specs at repo root. The backend has 18 routes but the frontend has only 5 pages. Treat this repo as an **architecture-and-spec donor**, not a UI donor.
3. **`signguy-ai-feb22` financial services are the highest-value donor asset for MVP.** `backend/services/invoice_service.py` and `backend/services/payment_service.py` are the specific files the mandated build order (Stage 6) tells us to adapt. Everything else in feb22 conflicts with MVP terminology (`Job`, `JobTicket`).
4. **`signguyai` is the feature discovery map, nothing more.** It has 133 pages and 60 routes, but the mandated instructions explicitly say do not import wholesale, and its terminology (`job_tickets.py`, `jobs.py`) is banned in MVP.
5. **Frontend pages missing from MVP** (present in donors): Webstores, Wrap Lab, Portal (Customer/Owner/Employee), AI Tools, Approvals, Payroll, Time Clock, Tasks, Community, Platform Admin, Inventory, Financials, Templates, Signatures, Promo codes, Stripe Connect, Onboarding, Meta/Facebook, Reports/Analytics, Public storefront/forms.
6. **Terminology conflict.** MVP uses `Order → OrderItem → WorkOrder`. Both `signguyai` and `signguy-ai-feb22` use `Job / JobTicket / JobItem`. Any migration MUST rename, never copy the term.

---

## Feature Readiness Matrix

Legend for **Best Source Repository**: `MVP`=SIGNGUY-MVP, `OS`=SIGNGUY-AI-OS (mirror of MVP), `REB`=signguyai_rebuild_version, `FEB`=signguy-ai-feb22, `ORIG`=signguyai.

Legend for **Readiness**: NS=Not Started, PH=Placeholder/Mockup Only, PI=Partially Implemented, WMP=Working w/ Major Problems, WNC=Working But Needs Cleanup, WR=Working and Reusable, AR=Advanced and Reusable, BU=Broken or Unsafe, DUP=Duplicate Implementations Exist, UNK=Unknown Due to Missing Evidence.

Legend for **Path**: CPY=Copy & Integrate, REF=Copy & Targeted Refactor, EXT=Extract Business Logic & Rehouse, RB=Rebuild, MRG=Merge Duplicates, DEF=Defer, RM=Remove/Deprecate, MD=Needs Manual Decision.

### Foundation & shared systems

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Authentication & account access | MVP | OS, REB, FEB, ORIG | WR | REF | Low | — | everything | MVP: bcrypt + JWT + 60-min reset. REB has `models/access.py` split; consider adopting. FEB has `routes/auth.py`. Rebuild not recommended. |
| Tenants & organizations | MVP | OS, REB | WR | REF | Low | Auth | everything | MVP tenant_id on every collection + server filter (already verified). REB `models/tenants.py` + `routes/tenants.py` may have richer org/membership model — inspect. |
| Users, roles, permissions | MVP | OS, REB, FEB, ORIG | WR | REF | Low | Auth, Tenants | everything | MVP single-dep enforcement (verified). REB `USERS_ROLES_PERMISSIONS_ACCESS_CONTROL_REBUILD_DOC.md` should be read before extending. |
| Application shell & navigation | MVP | ORIG, FEB | WNC | REF | Low | Auth | UI screens | MVP: sidebar+topbar, permission-gated nav. ORIG has "grouped workspace navigation, ribbons" per instructions — donor for aesthetic patterns only. |
| Shared UI component system (shadcn/ui) | MVP | OS, FEB, ORIG | WR | — | Low | — | UI screens | MVP uses shadcn/ui + Tailwind. FEB/ORIG use older component set. |
| Settings & configuration framework | REB | ORIG | PI | REF | Med | Tenants | Pricing, Webstores, Wrap Lab, notifications | MVP has ad-hoc settings only (pricing_settings). REB `routes/settings.py` + `models/settings.py` + `SETTINGS_CONFIGURATION_FRAMEWORK_REBUILD_DOC.md` looks intentional. |
| Audit log & activity history | MVP | REB, ORIG | WR | REF | Low | Auth | everything | MVP: shared record_audit helper with required actor (verified). REB has `services/activity.py`/`routes/activity.py` — inspect for richer event types. |
| Notifications (in-app + email digest) | REB | ORIG | UNK | MD | Med | Email | Customer portal, Employee portal | REB `routes/communications.py` + `services/communications.py`. ORIG `routes/digest.py`, `services/digest_scheduler.py`. Depth unknown. |
| Email (SendGrid) | MVP | REB, FEB, ORIG | WR | REF | Low | — | Quotes, Invoices, Portal, Documents | MVP: 5 templates, live sends verified. REB `EMAIL_NOTIFICATIONS_SENDGRID_REBUILD_DOC.md` for template governance. |
| SMS/MMS | ORIG | — | PI | DEF | Med | Auth | Portal, notifications | ORIG only: `routes/sms.py` + `services/sms_service.py`. Explicitly deferred by MVP scope. |
| Internal messaging | ORIG | — | UNK | DEF | Med | Auth | Team dashboard | ORIG likely has `Productivity` pages. Not in MVP scope. |
| File uploads & object storage | MVP | ORIG, FEB | WR | REF | Low | Auth, Tenants | Documents, Quotes, Orders, WorkOrders, Invoices | MVP: private-by-default Emergent object storage, tenant-scoped paths, all downloads require auth (verified). ORIG `services/object_storage.py` + `storage_config.py`. |
| Attachments (polymorphic) | MVP | — | WR | — | Low | Files | many | MVP `attachments` collection + `POST /files/attach`. Unique to MVP. |
| Forms | ORIG | REB | UNK | MD | Med | Files, Templates | Portal | ORIG `routes/questionnaires.py` + `models/questionnaires.py`. |
| Questionnaires | ORIG | REB | UNK | MD | Med | Forms | Portal, Wrap Lab | ORIG has `questionnaires.py` route and model. `EVENT_WEBSTORE_QUESTIONNAIRE_README.md` spec exists. |
| Templates (document/email) | ORIG | FEB | PI | REF | Med | Files, DocuLink | Emails, DocuLink | ORIG `routes/email_templates.py`, FEB same. |
| Signatures | ORIG | — | PI | REF | Med | Files, Approvals | Approvals, Contracts | ORIG `routes/signatures.py`. |
| Global search | — | ORIG | NS | RB | Med | Everything | UI | Not present in MVP. Not obvious in donors. |
| Background jobs / automation | ORIG | REB | UNK | MD | High | Everything | Digest, Notifications | ORIG `services/digest_scheduler.py`, `services/workflow_engine.py` + `routes/workflow_templates.py`. |
| Error handling & logging | MVP | REB | WR | — | Low | — | everything | Extractor uses Axios interceptor + toast. |

### Shop operations

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Customers & CRM | MVP | REB, FEB, ORIG | WR | REF | Low | Tenants, Auth | Quotes, Orders, Invoices | MVP has full CRUD + linked-records view. REB `models/customers.py` may be richer. |
| Customer detail & communication history | MVP | REB | WR | REF | Low | Customers, Email | UI | MVP has "Linked records" tab. REB adds explicit `communications` model. |
| Quotes | MVP | FEB, ORIG, REB | PI | REF | Med | Customers | Orders | MVP: manual price only, idempotent convert-to-order (verified). Missing: quote items with pricing snapshots, expiration, revisions, portal visibility. |
| Orders | MVP | FEB, ORIG | WR | REF | Low | Customers, Quotes | WorkOrders, Invoices | MVP: item entry + statuses (verified). Missing: item pricing snapshots, `production_required` flag, source-link enrichment. |
| Order Items | MVP | FEB, ORIG | WR | REF | Low | Orders | WorkOrders | MVP has inline editable table. Missing pricing snapshot at creation. |
| Quote-to-Order conversion | MVP | — | AR | — | — | Quotes, Orders | — | MVP: idempotent via `find_one_and_update` guard (verified). Best source. |
| Invoices | FEB | MVP, ORIG | PI | EXT | High | Orders | Payments | MVP: one-per-order (idempotent), manual pricing, single status field. FEB `invoice_service.py` has separate document vs financial status. **This is the Stage 6 migration target.** |
| Order-to-Invoice conversion | MVP | FEB | WR | REF | Low | Orders, Invoices | — | MVP handles idempotently via unique index. |
| Payments & payment history | FEB | MVP | PI | EXT | High | Invoices | — | MVP: manual payments w/ Idempotency-Key + auto status derivation. FEB `payment_service.py` adds void-with-reason, Stripe restrictions, immutable history. **Stage 6 migration target.** |
| Production / Work Orders | MVP | ORIG | PI | REF | Med | Orders, Order Items | Documents | MVP currently snapshots ALL OrderItems (spec violation — should be gated by `production_required`). Missing: stages, board view, completion history, packets. |
| Work Order Summaries | ORIG | — | UNK | MD | Med | WorkOrders | — | ORIG `routes/production_tasks.py`, `production_timeline.py`. |
| Production board | ORIG | — | UNK | RB | High | WorkOrders | — | ORIG page `ProductionBoard.js`. Not in MVP. |
| Artwork proofs | ORIG | — | UNK | MD | High | Files, Approvals, Portal | Wrap Lab | ORIG `routes/order_drawings.py` + `DrawingModal.js`. |
| Customer approvals | ORIG | FEB | UNK | REF | Med | Portal, Signatures | Proofs, Contracts | ORIG `routes/approvals.py`, FEB same. Depth unknown. |
| Document library / DocuLink | REB | ORIG | PH | RB | High | Files, Templates | Portal | REB `routes/doculink.py` + `services/doculink_bridge.py` + `services/doculink_storage.py`. Concept spec exists but code depth unclear. |
| Inventory | ORIG | REB | UNK | MD | Med | — | Orders, Purchasing | ORIG `routes/inventory.py` + `services/inventory_service.py`. REB has `INVENTORY_PURCHASING_VENDOR_MANAGEMENT_REBUILD_DOC.md`. Deferred by MVP scope. |
| Vendors | ORIG | — | UNK | DEF | Med | Inventory | Purchasing | ORIG only. Not in MVP. |
| Purchasing | ORIG | — | UNK | DEF | High | Inventory, Vendors | Finance | ORIG only. Not in MVP. |
| Webstores | ORIG | REB, FEB | UNK | RB | Critical | Orders, Stripe, Files | Public storefront | ORIG has `routes/webstores.py`, `webstore_owners.py`, dedicated `OwnerPortal.js`, `PortalWebstores.js`. REB has full `ORDER_PORTAL_*_SPEC.md` set. **Explicitly gated by Stage 15 — do not build before shared core stable.** |
| Webstore products & variants | ORIG | REB | UNK | RB | High | Webstores | Storefront | — |
| Webstore setup wizard | REB | ORIG | UNK | RB | High | Webstores | — | REB spec-heavy. |
| Webstore orders | ORIG | — | UNK | RB | High | Webstores, Orders | Payments | — |
| Stripe Connect & payouts | ORIG | FEB | PI | REF | High | Webstores | Payments | ORIG + FEB have `routes/stripe_connect.py`. Financial safety critical — do not port without security review. |
| Webstore owner portal | ORIG | REB | UNK | RB | High | Webstores | — | — |
| Webstore manager portal | REB | — | PH | RB | High | Webstores | — | REB has `ORDER_PORTAL_MANAGER_MASTER_SPEC.md`. Likely spec-only. |
| Public storefront | ORIG | REB | UNK | RB | High | Webstores | — | ORIG `routes/public_website.py`. |
| Wrap Lab / Wrap Command Center | REB | ORIG | UNK | RB | Critical | Customers, Orders, Files, Approvals, Portal | — | REB `routes/wrap_lab.py` + `services/wrap_lab_service.py` + `WRAP_LAB_TRANSFER_COMPLETION.md`. ORIG `routes/wrap/*`. **Stage 16 — after shared core stable.** |

### Business management

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Pricing foundation | MVP | REB, ORIG | AR | — | — | Tenants | Calc, Quotes, Orders | MVP: starter defaults + tenant clone + wizard + calculator (verified end-to-end). Best source. |
| Pricing setup / shop rate / labor | MVP | ORIG | AR | — | — | Pricing | Calc | MVP shop_defaults form. |
| Materials pricing | MVP | REB, ORIG | WR | REF | Low | Pricing | Calc | MVP has curated material catalog. ORIG `MaterialsAdmin.js` + REB `pricing_engine.py` may add tenant material catalog editor. |
| Pricing calculators | MVP | ORIG | WR | REF | Low | Pricing, Materials | Quotes, Orders | MVP: full 9-category calc w/ canonical response. |
| Quote pricing integration | MVP | ORIG | PI | REF | Med | Pricing, Quotes | — | MVP quote uses manual total; needs integration w/ calculator + snapshot to items. |
| Order pricing integration | MVP | ORIG | PI | REF | Med | Pricing, Orders | Invoices | Same as quotes — needs snapshot per OrderItem. |
| Finance dashboard | ORIG | — | UNK | RB | High | Invoices, Payments, Expenses | Reports | ORIG `Financials.js`. |
| Revenue & expenses | ORIG | — | UNK | RB | High | Invoices | Finance | — |
| Taxes | — | ORIG | NS | DEF | Med | Invoices | Finance | Explicitly excluded from MVP. |
| Payroll | ORIG | FEB | UNK | DEF | High | Employees, Time clock | Finance | ORIG `Payroll.js`, `PayrollDashboard.js`, `routes/employees.py`. |
| Time clock | ORIG | FEB | UNK | DEF | Med | Employees | Payroll | ORIG `services/timeclock_service.py`, `routes/job_time.py`. |
| Timesheets | ORIG | FEB | UNK | DEF | Med | Time clock | Payroll | — |
| Employee scheduling | ORIG | — | UNK | DEF | High | Employees | Production | ORIG `EmployeeSchedule.js`. |
| Reports | ORIG | — | UNK | DEF | High | Everything | — | ORIG probably has report views under Financials/Productivity. |
| Custom report builder | ORIG | — | UNK | DEF | Critical | Reports | — | Deferred. |
| Analytics | ORIG | — | UNK | DEF | High | Reports | — | ORIG `PlatformAdminAnalytics.js`, `services/productivity_query.py`. |

### Team & workflow

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Team dashboard | ORIG | — | UNK | DEF | Med | Employees, Tasks | — | — |
| Employees | ORIG | FEB | PI | RB | High | Users, Roles | Payroll, Scheduling, Portal | ORIG `routes/employees.py` + model. |
| Tasks | ORIG | FEB | UNK | DEF | Med | Users | Kanban | ORIG `routes/tasks.py`. |
| Kanban boards | ORIG | — | UNK | DEF | Med | Tasks | Team dashboard | — |
| Calendar | ORIG | — | UNK | DEF | Med | Appointments | Scheduling | — |
| Appointments | ORIG | — | UNK | DEF | Med | Customers | Calendar | ORIG `routes/appointments.py` + `AppointmentDetailPage.js`. |
| Install scheduling | ORIG | — | UNK | DEF | High | Appointments, Employees | Orders | — |
| Production scheduling | ORIG | — | UNK | DEF | High | WorkOrders | Employees | — |
| Internal notes | — | ORIG | NS | REF | Low | Any entity | UI | Simple; belongs in shared systems. |
| Team communication | ORIG | REB | UNK | DEF | Med | Users | Team | REB `communications.py`. |
| Employee portal | ORIG | FEB | PH | RB | High | Employees, Auth | Time clock | ORIG 5 EmployeePortal* pages + `routes/employee_portal.py`. |

### Design studio & AI

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Design Studio | ORIG | — | UNK | DEF | Critical | Files, AI | Wrap Lab | Not obvious in tree. |
| AI tools | ORIG | REB, FEB | PI | DEF | High | Auth, Credits | Assistant | ORIG `routes/ai.py`, `assistant_tools.py`, `AITools.js`. |
| AI Assistant | ORIG | — | PI | DEF | High | AI, Credits | — | ORIG `AIAssistant.js`, `services/ai_assistant_actions.py`. |
| Prompt Library | ORIG | — | UNK | DEF | Med | AI | — | Referenced in spec. |
| AI credit tracking | ORIG | — | PI | REF | Med | AI, Billing | — | ORIG `routes/credits.py`, `services/credit_service.py`. |
| AI usage history | ORIG | — | UNK | DEF | Low | AI Credits | Reports | — |
| AI billing logic | ORIG | — | UNK | DEF | High | Credits, Stripe | — | ORIG `services/multi_product_billing.py`. |
| AI-generated file storage | ORIG | — | UNK | DEF | Med | Files | AI | — |
| AI context retrieval | ORIG | — | UNK | DEF | High | AI | — | ORIG `services/assistant_queries.py`. |

### Platform & support

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Onboarding | ORIG | — | PI | RB | Med | Auth, Tenants, Pricing | — | ORIG `routes/onboarding.py`, `OnboardingHub.js`. |
| Help Center | ORIG | FEB | PH | RB | Low | — | — | FEB has 14 `docs/Docs*.js` pages. Static content. |
| Documentation | ORIG | FEB | WNC | CPY | Low | — | Help | FEB doc pages are the most reusable. |
| Community Hub | ORIG | — | UNK | DEF | Med | Users | — | ORIG `routes/community.py`, `CommunityHub.js`. |
| Bug reports | — | — | NS | DEF | Low | — | — | Not obvious. |
| Feature requests | — | — | NS | DEF | Low | — | — | Not obvious. |
| Platform administration | ORIG | REB | PI | REF | High | Auth | Everything | ORIG has 6+ PlatformAdmin pages. REB `routes/platform_admin.py`. Stage 17. |
| Platform tenant management | ORIG | REB | PI | REF | High | Tenants | Platform admin | ORIG `PlatformAdminTenantDetail.js`. |
| Platform analytics | ORIG | — | UNK | DEF | High | Everything | — | ORIG `PlatformAdminAnalytics.js`. |
| Platform audit logs | MVP | ORIG | WR | REF | Low | Audit | Platform admin | MVP audit collection + reader route already present. ORIG `PlatformAdminAuditLog.js`. |
| Platform email & announcements | ORIG | — | UNK | DEF | Med | Email | — | ORIG `PlatformAdminBroadcastEmail.js`. |
| Subscription plans | ORIG | REB, FEB | PI | REF | High | Stripe | Billing | ORIG `routes/plans.py`, `services/plan_configs.py`. REB `models/billing.py`. |
| Add-ons | ORIG | — | UNK | DEF | Med | Plans, Stripe | — | — |
| AI credit purchases | ORIG | — | UNK | DEF | Med | AI credits, Stripe | — | — |
| Public marketing website | ORIG | FEB | PH | DEF | Low | — | — | ORIG `LandingPage.js`, `AboutPage.js`, `FeaturesPage.js`, `ContactPage.js`. |
| Public pricing & plan selection | ORIG | FEB | PI | DEF | Low | Plans | — | ORIG `Pricing.js`, `PricingPlansV2.js`, `FoundersEditionPricing.js`. |

### Portals & public systems

| Module | Best Src | Other | Readiness | Path | Complexity | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|
| Customer portal | ORIG | FEB | PI | RB | High | Auth, Customers, Files, Approvals | Proofs, Payments | ORIG 10 Portal* pages + `routes/portal.py`. FEB 8 Portal* pages. **Duplicate implementations exist.** |
| Employee portal | ORIG | FEB | PI | RB | High | Employees, Auth | Time clock | ORIG 5 pages, FEB 4 pages. **Duplicates.** |
| Webstore owner portal | ORIG | REB | UNK | RB | High | Webstores | — | ORIG `OwnerPortal.js`, `OwnerPortalSignup.js`. |
| Webstore manager portal | REB | ORIG | UNK | RB | High | Webstores | — | REB spec-only. |
| Public storefront | ORIG | FEB | UNK | RB | High | Webstores, Public forms | — | FEB `Storefront.js`. |
| Public forms | ORIG | REB | UNK | DEF | Med | Forms | — | — |
| Public questionnaires | ORIG | REB | UNK | DEF | Med | Questionnaires | — | — |
| Public quote/intake | ORIG | — | UNK | DEF | Med | Quotes | — | Not obvious as a separate route. |

---

## Module detail sections

Detail is only provided here for modules classified **WR**, **AR**, **WMP**, **BU**, **DUP**, or **Critical complexity**. Everything else is UNK or DEF and does not warrant deeper prose without further evidence.

### Authentication & account access — WR (Best: MVP)
- **What works:** JWT + bcrypt + 60-min single-use password reset. `/api/auth/register-tenant`, `login`, `logout`, `me`, `request-password-reset`, `reset-password`, `dev-login` (bypass).
- **Files to preserve:** `backend/app/routers/auth.py`, `backend/app/core/security.py`, `backend/app/deps.py`, `frontend/src/auth/*`.
- **Files not to copy:** ORIG `routes/auth.py` — different model (`magic_links.py` + facebook auth). REB `routes/auth.py` — separate but likely equivalent to MVP.
- **Recommended path:** REF (extract REB's `AUTH_MODULE_REBUILD_DOC.md` guarantees).
- **Prereqs:** none.
- **Tests needed:** cross-tenant login sweep, password-reset expiry, dev-bypass off in prod.

### Tenants & users/roles/permissions — WR (Best: MVP)
- **What works:** single dependency `require_permission()`, role→perm map on backend, frontend fetches perm list. Cross-tenant sweep passes (see prior testing agent report).
- **Preserve:** `backend/app/core/permissions.py`, `backend/app/deps.py`.
- **Do not copy:** ORIG scatters permission checks across route files.
- **Prereqs:** none.

### File uploads, object storage, attachments — WR (Best: MVP)
- **What works:** Emergent object storage, tenant-scoped storage keys, all downloads require auth (cross-tenant sweep verified), polymorphic `attachments` table.
- **Preserve:** `backend/app/services/storage.py`, `backend/app/routers/documents.py`.
- **Do not copy:** ORIG had base64-in-Mongo patterns per the migration instructions.
- **Prereqs:** none.

### Quote-to-Order conversion — AR (Best: MVP)
- **What works:** idempotent via `find_one_and_update` claim guard + unique `converted_order_id`. Repeated clicks return same Order.
- **Preserve:** `backend/app/routers/quotes.py::convert_to_order`.
- **Prereqs:** Quotes, Orders.

### Pricing Foundation & Calculator — AR (Best: MVP)
- **What works:** starter default pack cloned per tenant, 9 canonical categories, banner wizard end-to-end, calculator returns full canonical schema.
- **Preserve:** `backend/app/services/starter_defaults.py`, `services/pricing.py`, `routers/pricing.py`, `frontend/src/pages/Pricing*.jsx`, `components/pricing/*`, `PRICING_DEFAULTS_AUDIT.md`.
- **Prereqs:** Tenants.
- **Follow-up work (not blocking reuse):** flesh out non-banner wizards; add tenant material catalog editor (ORIG had `MaterialsAdmin.js`).

### Invoices & Payments — PI in MVP, high-value donor in FEB (**highest-priority migration target**)
- **What works in MVP:** one-invoice-per-order (unique index), manual line items, payments w/ Idempotency-Key, auto status derivation (`partially_paid`/`paid`).
- **Gap vs Stage 6 spec (per migration doc):** MVP has a single `status` on Invoice; the spec requires **independent `document_status` (draft/sent/viewed/void) and `financial_status` (unpaid/partial/paid/refunded)**. MVP does not yet support void-with-reason or Stripe-payment restrictions. There is no reconciliation service.
- **Best donor:** `signguy-ai-feb22/backend/services/invoice_service.py` + `payment_service.py`.
- **Do not copy:** any of feb22's `Job`/`JobTicket` references; migrate to `Order` + `OrderItem`.
- **Required data migration:** existing `invoices.status` string → split into `document_status` + `financial_status`. Existing `payments` records → add `void_at`, `void_reason`, `void_actor` fields (nullable).
- **Tests needed:** partial-then-full payment status progression, void with restriction on Stripe payments, reconciliation service outputs match invoice.balance_due independently.

### DocuLink / Document library — PH (Best: REB specs; no working code)
- **What works:** MVP has a shared file/attachment system, but no template library, no generated documents, no share-link concept.
- **Best donor for concept:** REB `ORDER_PORTAL_*` specs + `services/doculink_bridge.py` + `services/doculink_storage.py`.
- **Do not copy:** ORIG `Documents/Documents.js` — likely presumes ORIG's file model.
- **Path:** RB (build fresh on MVP shared files). Complexity: High. Stage 8.

### Customer Portal — PI (**Duplicate implementations exist**: ORIG + FEB)
- **ORIG:** 10 pages (`PortalDashboard`, `PortalDocuments`, `PortalForms`, `PortalLogin`, `PortalMessages`, `PortalOrders`, `PortalPages`, `PortalPreview`, `PortalProfile`, `PortalProofs`, `PortalWebstores`) + `routes/portal.py`.
- **FEB:** 8 pages, subset of ORIG.
- **Duplication risk:** medium — both use identical page names but different underlying data. Do not copy either wholesale.
- **Path:** RB on MVP shared foundations (Stage 10).

### Employee Portal — PI (**Duplicate implementations exist**: ORIG + FEB)
- **ORIG:** 5 pages (`EmployeePortalDashboard/Job/Login/Pay/Profile/Tasks`) + `routes/employee_portal.py`.
- **FEB:** 5 similar pages.
- **Path:** RB (Stage 14). Complexity: High.

### Webstores / Order Portal Manager — UNK (Best: REB specs, ORIG implementation)
- **REB has 8 dedicated spec MDs** (`ORDER_PORTAL_MANAGER_MASTER_SPEC.md`, `ORDER_PORTAL_OWNER_PORTAL_SPEC.md`, `ORDER_PORTAL_PUBLIC_STOREFRONT_SPEC.md`, `ORDER_PORTAL_CHECKOUT_AND_LEDGER_SPEC.md`, `ORDER_PORTAL_DATA_MODEL_SPEC.md`, `ORDER_PORTAL_MAIN_APP_INTEGRATION_SPEC.md`, `ORDER_PORTAL_AI_SPEC.md`, `ORDER_PORTAL_WORKFLOW_STATUS_SPEC.md`, `ORDER_PORTAL_RELEASE_PLAN.md`).
- **ORIG code:** `routes/webstores.py`, `routes/webstore_owners.py`, `services/stripe_service.py`, `services/multi_product_billing.py`.
- **Path:** RB per spec, code as reference. Complexity: **Critical**. Stage 15. **Do not start until Stages 3–11 are stable.**

### Wrap Lab — UNK (Best: REB code + spec, ORIG code)
- **REB:** `routes/wrap_lab.py`, `services/wrap_lab_service.py`, `models/wrap_lab.py`, `WRAP_LAB_TRANSFER_COMPLETION.md`.
- **ORIG:** `routes/wrap/*` (core, files, pdfs, portal).
- **Path:** REF/RB. Complexity: **Critical**. Stage 16.

### Notifications / Digest — UNK
- **ORIG:** `routes/digest.py`, `services/digest_scheduler.py`.
- **REB:** `routes/communications.py`, `services/communications.py`.
- **Depth unknown** — user should paste one of these files to unlock the audit for this module.

---

## Cross-module findings

- **Duplicate customer systems:** REB, FEB, ORIG all define `customers`. **MVP already implements this correctly** — donor customer models should be treated as reference only.
- **Duplicate order/quote systems:** MVP uses `Order/OrderItem`. FEB and ORIG use `Job/JobItem/JobTicket`. **Terminology conflict must be resolved during migration** — never copy the term.
- **Duplicate invoice/payment systems:** MVP (single-status), FEB (dual-status, void, reconciliation), ORIG (Job-based). FEB is the correct donor for Stage 6.
- **Duplicate document systems:** MVP has one shared attachments table. ORIG has `Documents/Documents.js` + separate wrap files + order drawings + doc templates. REB has a full DocuLink spec but only bridge/storage services.
- **Duplicate file storage systems:** MVP uses Emergent object storage. ORIG has `services/object_storage.py` + `storage_config.py`. Migration instructions explicitly warn about base64 in Mongo — verify by reading ORIG code before copying anything.
- **Duplicate settings systems:** MVP has ad-hoc (pricing_settings). REB has intentional `routes/settings.py` + `models/settings.py`.
- **Duplicate messaging systems:** ORIG `sms.py` + `facebook_messages.py` + `email_templates.py`; REB `communications.py`; MVP `emails.py`. Consolidation needed at Stage 9.
- **Duplicate form/questionnaire systems:** ORIG has both `questionnaires.py` and `signatures.py`. REB has no working equivalent.
- **Duplicate pricing systems:** MVP is definitive (per user instruction). ORIG has `routes/pricing.py` + `pricing_setup.py` + `models/pricing.py` + `pricing_core.py` + `PricingFoundation.js` + `PricingSetup.js` + `PricingSettings.js` — the giant pricing system explicitly forbidden by the migration doc.
- **Duplicate authentication/role logic:** MVP single-source; REB has a parallel version; FEB has a job-oriented version.
- **Duplicate portal implementations:** ORIG 10 pages + FEB 8 pages. Neither should be copied wholesale.
- **Duplicate AI credit logic:** ORIG only.
- **Conflicting status values:** MVP invoice has one status; FEB splits document vs financial; ORIG job_tickets uses production statuses. Adopt FEB pattern per Stage 6.
- **Conflicting terminology:** `Order`↔`Job`, `OrderItem`↔`JobItem/JobTicket`, `WorkOrder`↔`ProductionTask/JobTicket`. MVP terms win.
- **Conflicting DB ownership:** ORIG mixes tenant filtering across route files rather than a single dependency.
- **Features complete-looking but using mock data:** unknown without deeper file reads — flagged in "Missing information".
- **Frontend without working backend:** likely REB (5 frontend pages vs 18 routes) and REB spec-only Webstore/Wrap pages.
- **Backend without frontend:** likely ORIG `digest`, `workflow_templates`, some AI internals.
- **Dead routes/components/APIs:** unknown without file reads.
- **Large files containing unrelated modules:** ORIG per the migration doc had a "giant App.js" and a "giant pricing system." MVP already split these correctly.
- **Circular deps:** unknown — needs static analysis.
- **Shared systems that MUST be built before any module migration:** Settings framework, Notifications service (separate from email), Approvals + Signatures shared service, Portal shared foundation (auth + magic-link), Feature flags / entitlements service.

---

## Top-ten lists

### 10 strongest reusable systems
1. **MVP Auth / Tenants / Permissions** — single-dependency enforcement, tenant-scoped everywhere, cross-tenant tests passing.
2. **MVP Object Storage + Attachments** — private-by-default, tenant paths, polymorphic attachments.
3. **MVP Audit Helper** — non-optional actor, called from every write.
4. **MVP Idempotent Convert-to-Order** — atomic Mongo guard.
5. **MVP Pricing Foundation + Calculator** — starter defaults, per-tenant clone, wizard, canonical calc response.
6. **MVP Atomic Sequence Service** — race-safe per-tenant numbering.
7. **MVP SendGrid Service** — 5 templates, live send verified, graceful fallback.
8. **MVP Dashboard aggregation** — permission-gated single-payload summary.
9. **FEB `invoice_service.py` + `payment_service.py`** — dual-status, void-with-reason, reconciliation (needs adapting to Order/OrderItem terms).
10. **REB `memory/MODULE SPECS MDS/*` docs + Order Portal specs** — 17 module rebuild guides; higher signal than code in REB.

### 10 highest-risk systems
1. **Webstores/Order Portal** — Stripe money movement + storefront + wrap-around scope; must be gated on portal + payment maturity.
2. **Wrap Lab** — deep cross-dependency (files, approvals, portal, email, payments).
3. **Payments + Stripe Connect** — real money, refund risk; must not port ORIG code without security review.
4. **AI billing / credits** — real cost tied to LLM API usage; needs cost-cap + tenant metering before touching.
5. **Customer Portal duplicates** — two active implementations in donors; wrong choice creates data model conflict.
6. **Employee Portal duplicates** — same duplication risk.
7. **ORIG `App.js` monolith** — explicitly banned by migration doc; must not be copied.
8. **ORIG pricing system** — explicitly banned by migration doc.
9. **`Job/JobTicket` terminology in FEB and ORIG** — will silently poison MVP if any file is copied without rename.
10. **`SIGNGUY-AI-OS` mirror** — will drift from MVP the moment someone commits to it.

### 10 most important shared dependencies (build/verify BEFORE module migration)
1. Auth + Tenant middleware (done).
2. Single permission dependency (done).
3. Shared audit helper (done).
4. Object storage service + polymorphic attachments (done).
5. Atomic sequence service (done).
6. Money handling policy (integer cents in Invoices; float dollars in Pricing settings — needs an explicit doc).
7. Settings framework (REB donor).
8. Notification service (separate from email) — NOT YET BUILT.
9. Feature-flag / entitlements service — NOT YET BUILT.
10. Shared API client + error envelope on frontend (done).

### 10 areas where rewriting would waste prior work
1. Pricing Foundation & Calculator (MVP is already the intended target).
2. Quote-to-Order idempotent convert (MVP has the correct pattern).
3. SendGrid email service (working live).
4. Object storage + attachments (working + verified secure).
5. Audit helper (correct actor pattern).
6. Sequence generator (verified race-safe).
7. Customer/Order/Invoice basic CRUD + linked-records view (MVP passing tests).
8. Design guidelines (MVP has enforced light SaaS system).
9. Cross-tenant isolation infrastructure (verified).
10. Dev auth bypass (already environment-gated with warning banner).

### 10 areas where copying blindly would create unacceptable risk
1. FEB `models/jobs.py` — `Job` domain conflict with `Order`.
2. ORIG `routes/job_tickets.py` + `LegacyJobRedirect.js` — banned terminology.
3. ORIG `routes/webstores.py` full port — must be spec-driven rebuild.
4. ORIG `routes/pricing.py` / `pricing_setup.py` / `MaterialsAdmin.js` — banned giant pricing system.
5. ORIG `routes/ai.py` + credit services — cost/security risk.
6. ORIG `Documents/Documents.js` — probably assumes ORIG data model.
7. ORIG `services/multi_product_billing.py` — Stripe risk.
8. ORIG `routes/backup.py`, `routes/dev.py` — dev-only routes must not ship.
9. ORIG `PortalPreview.js` + `preview-shop` tenant headers (migration doc explicitly excludes these).
10. Anything in REB depending on undocumented local preview state (per migration doc).

---

## Missing information that must be resolved before final build plan

I cannot promote any UNK row to a confident classification without reading the actual file contents. Please provide (paste or grant access) to at least the following files so the next audit pass can lock in Best Source per module:

- `signguy-ai-feb22/backend/services/invoice_service.py`
- `signguy-ai-feb22/backend/services/payment_service.py`
- `signguy-ai-feb22/backend/models/payments.py`
- `signguyai_rebuild_version/backend/routes/settings.py` + `models/settings.py`
- `signguyai_rebuild_version/backend/services/communications.py` + `routes/communications.py`
- `signguyai_rebuild_version/backend/services/doculink_bridge.py` + `services/doculink_storage.py` + `routes/doculink.py`
- `signguyai_rebuild_version/backend/services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py`
- `signguyai_rebuild_version/memory/MODULE SPECS MDS/SALES_WORKFLOW_QUOTES_ORDERS_ORDER_ITEMS_REBUILD_DOC.md`
- `signguyai_rebuild_version/memory/MODULE SPECS MDS/EMAIL_NOTIFICATIONS_SENDGRID_REBUILD_DOC.md`
- `signguyai_rebuild_version/memory/MODULE SPECS MDS/USERS_ROLES_PERMISSIONS_ACCESS_CONTROL_REBUILD_DOC.md`
- `signguyai_rebuild_version/memory/MODULE SPECS MDS/FILE_UPLOADS_ATTACHMENTS_STORAGE_REBUILD_DOC.md`
- `signguyai_rebuild_version/memory/MODULE SPECS MDS/PLATFORM_ADMIN_IMPLEMENTATION (2).md`
- `signguyai/routes/approvals.py` + `signatures.py`
- `signguyai/routes/portal.py` + one `PortalOrders.js` and `PortalProofs.js`
- `signguyai/routes/webstores.py` + `webstore_owners.py` + `services/stripe_service.py`
- `signguyai/services/object_storage.py` (to confirm whether base64 patterns exist)
- Any migration-safety scripts in FEB `memory/FEBRUARY_BACKUP_FINANCIAL_CORRECTION_MASTER_PLAN.md`

Additionally, please confirm:
- Is `SIGNGUY-AI-OS` intended as a distinct repo, or can it be retired as an outdated mirror of SIGNGUY-MVP?
- Which stage do you want to migrate FIRST after this audit lands?
