# SignGuy AI — Feature Readiness Matrix (Corrected & Completed Pass)

**Audit date:** 2026-07-11 (corrected pass)
**Auditor:** E2 agent — direct-inspection pass (donor repos cloned at HEAD and read line-by-line)
**Repository role:** `dnblack323/SIGNGUY-MVP` is the **permanent commercial product**. It is NOT an MVP scaffold to be discarded. Every feature currently missing is a **build-out gap in the permanent product**, not a "deferred by MVP scope" concession. All prior "defer / post-launch / optional" language has been removed from this document.

## What is different from the prior pass

The previous pass (2026-07-07) reasoned mostly from file trees and left many rows as `UNK — user please paste the file`. That policy was rejected and is now void. This pass **cloned the four donor repositories at their HEAD commits and read the actual source of the key modules**. Every row that was previously `UNK due to missing evidence` has been re-classified against real code, or explicitly labelled `INSPECTED — thin scaffold only` / `INSPECTED — full working implementation` / `SPEC ONLY — no runtime code` based on what the source actually contains.

## Evidence-level legend (new — required for every row)

| Symbol | Meaning |
|---|---|
| **RV** | **RUNTIME VERIFIED** — behavior confirmed against the running SIGNGUY-MVP preview via prior testing-agent iterations. |
| **SV** | **SOURCE CODE VERIFIED** — file(s) read line-by-line in this pass; the file's routes/models/services are described from actual code. |
| **SS** | **SPEC + SCAFFOLD** — a working code scaffold exists in the donor repo, but is not yet runtime-verified end-to-end. |
| **SO** | **SPEC ONLY** — REB `memory/MODULE SPECS MDS/*` or ORDER_PORTAL specs describe the target, but no matching runtime code exists in any donor. |
| **RS** | **REFERENCE ONLY** — implementation exists in a donor but is unsafe or terminology-incompatible; used only as a discovery map. |

## Repositories inspected (cloned in this pass)

| Repo | Last commit inspected | Total py in backend | Backend routes | Backend services | Backend models | Frontend pages | Role |
|---|---|---|---|---|---|---|---|
| `dnblack323/SIGNGUY-MVP` | current | 39 | 13 | 7 | 11 | 21 | **Permanent product** |
| `dnblack323/SIGNGUY-AI-OS` | `f896a77 2026-07-08` | 39 | 13 | 7 | 11 | 21 | **Byte-identical mirror of MVP** (md5 tree match confirmed in this pass). **Retire.** |
| `dnblack323/signguyai_rebuild_version` | HEAD | 143 | 18 | 14 | 19 | 5 | **Reference architecture + spec donor** |
| `dnblack323/signguy-ai-feb22` | HEAD | 71 | 22 | 6 | 9 | 59 | **Financial-logic donor (Stage 6)** |
| `dnblack323/signguyai` | HEAD | 154 | 60 | 29 | 16 | 133 | **Feature discovery map (RS only)** |

## Critical up-front findings (revised)

1. **SIGNGUY-MVP ≡ SIGNGUY-AI-OS is now RUNTIME-PROVEN.** The `md5sum` of every `.py` file under `backend/app/` matches byte-for-byte between the two repos, and both contain the same 39 backend files / 21 frontend pages. **`SIGNGUY-AI-OS` must be retired** as a repo. Recommended action: freeze the OS repo (README pointing to SIGNGUY-MVP), or delete it. Leaving it live guarantees drift.
2. **REB is NOT "90% spec, 10% code" — that earlier claim was wrong.** REB backend contains a full working scaffold for: `settings` (namespace/key repository with permission-gated CRUD), `communications` (email activity + notifications + **SendGrid webhook with HMAC signature verification**), `doculink` (documents + files + polymorphic links + shares + download via local object storage with SHA-256 upload validation), `wrap_lab` (full 11-stage workflow engine with stage gates, portal allowlist, mockup studio, checklists), `platform_admin` (tenants, readiness, audit-events), `shared_systems` (community + notes + AI tool catalog with 24 tools), `webstores` (capabilities + launch readiness — entitlement-only, no product/order code yet), `billing_rules` (subscription products, credit top-ups, founders promo, transaction fee basis points), `pricing_engine` (1391-line faithful port of the 9-category calculator suite), `pricing_foundation` (thin route + repository). Every one of these is **SV or SS**, not "UNK".
3. **FEB's financial services are actionable and verifiable.** `services/invoice_service.py` (147 lines) and `services/payment_service.py` (320 lines) implement exactly the Stage 6 dual-status + void-with-reason + reconciliation + Stripe two-step + overpayment-reject + idempotency-key patterns described in the master build plan. The `Payment` model uses integer cents (`amount_cents`) and independently derives `document_status` (draft/issued/void) and `financial_status` (unpaid/partial/paid/voided) — this is the single-source-of-truth reconciliation formula the permanent product must adopt.
4. **The `Job/JobTicket` terminology conflict is real but narrowly scoped.** FEB's InvoiceService/PaymentService are almost job-agnostic — they only touch `db.invoices` and `db.payments`. The `job_id` field on the Payment model is optional. Porting to MVP requires renaming `job_id` → `order_id` (nullable) on the Payment model and adjusting the two `invoice.get("job_id")` reads. Everything else in these two files is directly reusable.
5. **ORIG contains real signatures + approvals code, not just discovery pointers.** `routes/signatures.py` (658 lines) supports 11 parent record types (quote, proof, order, change_order, install_record, pickup_record, delivery_record, invoice, form, document, work_order) with structured signature-type mapping. `routes/approvals.py` (355 lines) already bridges proofs to both `db.jobs` and `db.orders` (see `_get_proof_parent_name`), so the Order-based flow is a first-class parent — it does NOT need to be invented from scratch.
6. **ORIG `object_storage.py` is 35 lines of clean Emergent Object Storage HTTP client.** There is no base64-in-Mongo anti-pattern in that file. The migration document's warning about base64 refers to older, purged code paths, NOT to `services/object_storage.py`. This file is directly compatible with MVP's own storage service.
7. **All four donors converge on the same 9 item categories.** REB `order_schemas.py` and `pricing_engine.py`, FEB `models/enums.py`, ORIG `models/pricing.py`, and MVP `services/starter_defaults.py` all use the same category set: rigid_signs, banners, cut_vinyl, digital_print, vehicle_wrap, apparel, services, promo_misc, custom. There is no category conflict — only a terminology conflict on the parent record (Job vs Order).
8. **Money representation split.** MVP uses **float dollars** across quotes/orders/invoices/pricing_settings. REB uses **integer cents (`_minor` suffix)** across quotes/orders/invoices. FEB uses **float dollars in Invoice fields + integer cents in the new Payment collection**. The permanent product must land on ONE representation. FEB's compromise (float dollars in existing invoice/order fields, integer cents in Payment only) is the least disruptive path and preserves current MVP data compatibility. This is a **permanent architectural decision** that must be documented before Stage 6 migration.
9. **Terminology reconciliation table (canonical, permanent):**
   - `Order` (never `Job`)
   - `OrderItem` (never `JobItem` / `JobTicket`)
   - `WorkOrder` (never `ProductionTask` / `JobTicket`)
   - `Invoice`, `Payment`, `Quote`, `Customer` — same in all repos.
   - Every donor file that touches `job_id` / `jobs` collection must be renamed to `order_id` / `orders` before landing in MVP.
10. **Permanent product build order remains the mandated 0–17 stage sequence** (see `memory/AGENT_INSTRUCTIONS.md`). Nothing about the "permanent product" reclassification changes stage ordering. What it changes is that every stage after 12 (Pricing Foundation, already delivered) is a **planned build-out**, not "post-MVP defer".

---

## Feature Readiness Matrix (corrected)

**Best Source repository key:** `MVP`=SIGNGUY-MVP, `OS`=SIGNGUY-AI-OS (retired mirror), `REB`=signguyai_rebuild_version, `FEB`=signguy-ai-feb22, `ORIG`=signguyai.

**Readiness key:** NS=Not Started, PH=Placeholder/Mockup Only, PI=Partially Implemented, WMP=Working w/ Major Problems, WNC=Working But Needs Cleanup, WR=Working and Reusable, AR=Advanced and Reusable, BU=Broken or Unsafe, DUP=Duplicate Implementations Exist.

**Path key:** CPY=Copy & Integrate, REF=Copy & Targeted Refactor (mostly rename `job_id`→`order_id` + import paths), EXT=Extract Business Logic & Rehouse, RB=Rebuild against MVP shared services (donor code is reference), MRG=Merge Duplicates, RM=Remove/Deprecate, MD=Needs Manual Decision.

> The `Defer` path from the previous pass is **removed** everywhere. Every gap now has a build-out path.

### Foundation & shared systems

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Authentication & account access | MVP | REB, FEB, ORIG | WR | — | Low | RV+SV | — | everything | MVP has bcrypt + JWT + 60-min single-use password reset + dev-bypass gate. REB `models/access.py` defines 57 permissions in a StrEnum + role-permission map that is richer than MVP's. Recommendation: **REF into MVP** — adopt REB's `Permission` StrEnum verbatim (renamed to MVP module paths) so all new modules use the same permission catalog. |
| Tenants & organizations | MVP | REB | WR | — | Low | RV | Auth | everything | MVP tenant_id on every collection + server-side filter (cross-tenant sweep verified in prior test). REB has richer `tenants.py` + `platform_admin.py` orgs model — inspect at Stage 17 for platform-admin work; no earlier value. |
| Users, roles, permissions | MVP | REB | WR | REF | Low | RV+SV | Auth, Tenants | everything | MVP single-dependency enforcement (verified). REB defines 6 roles (`platform_creator`, `platform_admin`, `owner`, `admin`, `staff`, `webstore_owner`) with a `PLATFORM_BYPASS_ROLES` set and `identity_has_permission()` — **adopt this shape** so platform admin & webstore-owner roles are wired from day one. |
| Application shell & navigation | MVP | ORIG | WNC | REF | Low | RV | Auth | UI screens | MVP has sidebar + topbar + permission-gated nav. ORIG has grouped workspace/ribbon patterns that are visual reference only. |
| Shared UI component system (shadcn/ui) | MVP | — | WR | — | Low | RV | — | UI | Enforced by design guidelines. |
| Settings & configuration framework | REB | — | PI in MVP → REF to REB shape | REF | Med | SV | Tenants, Permissions | Pricing, Webstores, Wrap Lab, notifications | REB `routes/settings.py` (77 lines) + `models/settings.py` (37 lines) is a **thin working scaffold**: namespace/key + `SettingsRepository` + `SETTINGS_VIEW/MANAGE` permissions + activity event on update. MVP currently has ad-hoc `pricing_settings` only. **This module is Stage 2 (Shared Platform Services)** and must be built before broader Settings surface areas. |
| Audit log & activity event system | MVP | REB | WR | REF | Low | RV+SV | Auth | everything | MVP has shared `record_audit(actor, ...)` helper (verified — no writes without actor). REB `services/activity.py` + `routes/activity.py` (40+45 lines) implements a slightly richer `ActivityEventPayload` (`module`, `event_type`, `entity_type`, `entity_id`, `summary`, `severity`, `changes`, `metadata`) and lists events with permission-gated filters. **Adopt REB's `event_type`, `severity`, `changes` fields on top of MVP's audit collection.** |
| Notifications (in-app) | REB | — | NS in MVP | RB (based on REB scaffold) | Med | SV | Settings, Users, Communications repository | Customer portal, Employee portal, Wrap Lab, Order events | REB `routes/communications.py` (170 lines) implements a working notification lifecycle: `NotificationPayload` create/update/status + recipient scoping (staff can only see notifications addressed to themselves — enforced server-side). **The notification service is a real REB scaffold, not a spec.** Adopt as Stage 2 shared service. |
| Email (SendGrid) | MVP | REB | WR | REF | Low | RV | — | Quotes, Invoices, Portal, Documents, Wrap Lab | MVP has 5 live templates + verified live-send. REB `routes/communications.py` adds **email activity tracking** (`email_activity` records with `template_key`, `related_entity_type/id`, `delivery_status`) and a **SendGrid webhook endpoint** (`POST /communications/webhooks/sendgrid`) with HMAC-SHA256 signature verification against `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET`. **Adopt the webhook + activity tracking** so email deliverability/bounce is auditable. |
| SMS/MMS | ORIG | — | NS in MVP | RB | Med | RS | Auth | Portal, notifications | ORIG `routes/sms.py` + `services/sms_service.py` exist. Twilio keys pasted by user in chat (must be rotated). **Build in permanent product roadmap after Stage 10 portal**; not a Stage 2 prerequisite. |
| Internal messaging (staff↔staff) | ORIG | REB | NS in MVP | RB | Med | RS | Auth | Team dashboard | ORIG `Productivity` pages + REB `SharedRecordRepository` (notes) provide reference patterns. Build against MVP shared services. |
| File uploads & object storage | MVP | REB, ORIG | WR | — | Low | RV | Auth, Tenants | Documents, Quotes, Orders, Work Orders, Invoices | MVP uses Emergent Object Storage + tenant-scoped keys + authed downloads (cross-tenant sweep verified). ORIG `services/object_storage.py` is a clean 35-line Emergent HTTP client — no base64 anti-pattern. REB `services/doculink_storage.py` uses local disk with SHA-256 hashing and path-traversal guards (useful reference for `sha256` file identity and MIME-vs-declared-type verification — see next row). |
| Upload validation | REB | — | NS in MVP | EXT | Low | SV | Files | Docs, Wrap Lab, Portal | REB `services/upload_validation.py` (132 lines) enforces: MIME allowlist (10 types), MIME-vs-extension mismatch rejection, per-request configurable size cap (`SIGNGUYAI_MAX_UPLOAD_BYTES`), magic-byte content sniffing (`%PDF`, `\x89PNG`, `\xff\xd8\xff`, `RIFF...WEBP`, PK zip for docx/xlsx, `\xd0\xcf\x11\xe0` for legacy Office, UTF-8/latin-1 for text/csv), SHA-256 fingerprint on stored files. **Extract into MVP as `services/upload_validation.py`** — this hardens the current permissive uploader. |
| Attachments (polymorphic entity ↔ file links) | MVP | REB | WR | REF | Low | RV+SV | Files | many | MVP already has `attachments` collection + `POST /files/attach`. REB has richer polymorphic `file_links` + `document_links` + `document_shares` with `customer_visible` flag and `access_level` — **adopt these three collections** so external-facing entities (portal, webstore) can share files without exposing internal-only records. |
| Forms | ORIG | REB | NS in MVP | RB | Med | RS | Files, Templates | Portal | ORIG `routes/questionnaires.py` + `models/questionnaires.py` — build against MVP shared services. |
| Questionnaires | ORIG | REB | NS in MVP | RB | Med | RS | Forms, Files | Portal, Wrap Lab, Webstores | ORIG has `questionnaires.py`; REB `WEBSTORE_SPEC.md` + wrap prototype both require it. Foundational for Webstores and Wrap Lab intake. |
| Templates (document + email) | ORIG | FEB, REB | PI in MVP (email templates only) | REF | Med | RS | Files | Emails, DocuLink, Wrap Lab | ORIG `routes/email_templates.py`, FEB same. REB `models/doculink.py` has `BusinessDocumentPayload` including `source_type=ai_generated` + `requires_review` — richer than ORIG. |
| Signatures | ORIG | — | NS in MVP | REF | Med | SV | Files, Approvals | Approvals, Contracts, Wrap Lab | ORIG `routes/signatures.py` (658 lines) supports 11 parent record types (quote, proof, order, change_order, install_record, pickup_record, delivery_record, invoice, form, document, work_order) with a structured `SIGNATURE_TYPE_MAP`. **Full working code, not a spec.** Path: REF — rename `job_ticket_id` → `order_item_id`, keep every other parent verbatim. |
| Global search | — | — | NS in MVP | RB | Med | — | Everything | UI | No donor has a global search implementation. Build against MVP after core stable. |
| Background jobs / automation | ORIG | REB | NS in MVP | RB | High | RS | Everything | Digest, Notifications | ORIG `services/digest_scheduler.py`, `services/workflow_engine.py` + `routes/workflow_templates.py` — reference only; the permanent product will need a shared scheduler as part of Stage 2 shared services once notification digests are on the roadmap. |
| Error handling & logging | MVP | REB | WR | — | Low | RV | — | everything | Axios interceptor + toast (MVP). REB adds structured activity events on repo write. |

### Shop operations

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Customers & CRM | MVP | REB, FEB | WR | — | Low | RV | Tenants, Auth | Quotes, Orders, Invoices, Portal | MVP has full CRUD + linked-records view. REB `models/customers.py` is only slightly richer (address book normalisation); not a required refactor. |
| Customer detail & communication history | MVP | REB | WR | REF | Low | RV+SV | Customers, Email | UI | REB `email_activity` collection provides a real communication history stream; adopt at same time as email webhook (row above). |
| Quotes | MVP | REB, FEB | PI | REF | Med | RV+SV | Customers, Pricing | Orders | MVP has manual-price quote + idempotent convert-to-order. REB `routes/quotes.py` (206 lines) + `models/quotes.py` (129 lines) adds: (a) line items with per-item `estimated_price_minor`, `material_estimate_minor`, `labor_estimate_minor`, `manual_price_override_minor`, `override_reason`, `override_actor_id`, `override_at`, `production_required`; (b) expiration (`expires_at`); (c) status set `draft/sent/approved/declined/expired/converted/cancelled`; (d) send, approve (with approval_method: phone/email/text/in_person/other), decline (with reason); (e) revisions via `version` on the document; (f) portal-visible file links via `doculink`. **Stage 4 target — port REB shape**, keep MVP `job_id`→`order_id` conventions. |
| Orders | MVP | REB, FEB, ORIG | WR (basics) → PI (target) | REF | Med | RV+SV | Customers, Quotes, Pricing | Work Orders, Invoices | MVP has item entry + statuses. REB `routes/orders.py` (326 lines) adds: production-summary endpoint, financials endpoint (invoice count + balance_due_minor), source-quote endpoint, generate-invoice / generate-work_order helpers, richer status set (`new_intake/awaiting_review/awaiting_quote/quote_sent/awaiting_approval/approved/in_production/partially_complete/ready_for_pickup/out_for_delivery/completed/on_hold/cancelled`), `payment_status` on the order, `approval_status`, `pickup_delivery_method`, shared production/design/install/color notes. **Adopt.** |
| Order Items | MVP | REB | PI | REF | Med | RV+SV | Orders, Pricing | Work Orders | REB `OrderItemPayload` has 40+ fields including `production_required: bool | None`, `entry_mode: quick/detailed`, `estimated_price_minor`, `actual_cost_minor`, `labor_estimate_minor`, `material_estimate_minor`, `manual_quote_override_minor`, `override_reason/actor_id/at`, `design_needed`, `customer_artwork`, `artwork_status`, `proof_required`, `proof_approval_status`, `revision_count`, `qc_status`, `rework_needed/notes`, `special_instructions`, `production_notes`, `install_notes`, `packaging_notes`, `department_route`, `assigned_team/user_id`. **This is the permanent target schema.** |
| `production_required` flag & work-order gate | REB | — | Missing in MVP | REF | Low | SV | OrderItem | Work Orders | REB `services/order_item_rules.py` (14 lines) defines `PHYSICAL_PRODUCTION_CATEGORIES = {rigid_signs, banners, cut_vinyl, digital_print, vehicle_wrap, apparel, promo_misc, custom}` and `default_production_required(item_category)`. **This IS the Stage 5→7 gate** the mandated build order requires. Import as-is. |
| Quote-to-Order conversion | MVP | REB | AR | — | — | RV | Quotes, Orders | — | MVP idempotent via `find_one_and_update` + unique `converted_order_id`. Best source. REB has same pattern with `converted_at`, `converted_order_id`, and audit event. |
| Pricing snapshot on OrderItem/QuoteLineItem | REB | — | Missing in MVP | REF | Med | SV | Pricing, Orders, Quotes | Invoices | REB `POST /order-items/{item_id}/calculate-pricing` + `save-pricing` + `override-pricing` endpoints, `latest_pricing_snapshot` field on OrderItem document, `set_pricing_override(tenant, item, price_minor, reason, actor)` helper on the repository. **Stage 5 target — this is what "item-level pricing snapshots" means in the master plan.** |
| Invoices | FEB | REB, MVP | PI | EXT | High | SV | Orders | Payments | MVP is one-per-order + manual pricing + single status. FEB `services/invoice_service.py` (147 lines) owns the reconciliation formula: `compute_line_items_and_totals()` snapshots line items server-side, and `reconcile_invoice_financials()` derives `amount_paid`, `balance_due`, `status`, `document_status`, `financial_status` in one place. **This is the Stage 6 migration target.** Rename `job_id`→`order_id` on the invoice document; every other field lands as-is. |
| Order-to-Invoice conversion | MVP | REB | WR | REF | Low | RV+SV | Orders, Invoices | — | MVP idempotent via unique index. REB `POST /invoices/generate-from-order/{order_id}` does the same + returns 404/409 correctly. Adopt REB error shape. |
| Payments & payment history | FEB | MVP | PI in MVP → EXT to FEB | EXT | High | SV | Invoices | — | FEB `services/payment_service.py` (320 lines) + `models/payments.py` (148 lines) implements: unified Payment collection (manual + Stripe Connect), integer cents (`amount_cents`), idempotency-key with 409 on replay, overpayment rejection, controlled void-with-reason (manual only, never Stripe), Stripe two-step (`create_pending_stripe_payment` → `confirm_stripe_invoice_payment`) with webhook-replay idempotency (DuplicateKeyError race handling), `refunded_amount_cents` future-compatible field, `provider_transaction_id` uniqueness, `voided_at/voided_by/voided_by_name/void_reason` audit stamp, `_derive_states()` for document/financial state split. **This is the Stage 6 permanent implementation.** |
| Money representation policy | FEB | REB | Not documented in MVP | Decision | Low | SV | Invoices, Payments, Quotes, Orders | Reports | FEB uses **float dollars** in Invoice/Quote/Job fields but **integer cents** in the new Payment collection, with the conversion boundary inside `reconcile_invoice_financials()`. REB uses `_minor` (integer cents) throughout. **Decision required (see Prompt 2 revisions):** land on FEB's boundary compromise for the permanent product to preserve existing MVP data. |
| Production / Work Orders | MVP | REB, ORIG | PI | REF | Med | RV+SV | Orders, Order Items | Documents | MVP currently snapshots ALL OrderItems (spec violation). REB `routes/orders.py::generate_work_order_draft` gates on `production_required=True`. **Stage 7 target — apply `default_production_required(item_category)` + a per-item override.** REB also has `list_work_order_drafts(tenant, order_id)` + `latest_work_order_draft` in the order production summary. |
| Production board / stages | REB | ORIG | NS in MVP | RB | High | SS | Work Orders | — | REB wrap_lab `STAGES = ["Intake", "Quote", "Contract", "Design", "Proof Approval", "Inspection", "Production", "Install", "Pickup", "Aftercare", "Complete"]` gives a template; ORIG `ProductionBoard.js` gives a UI reference. |
| Artwork proofs | ORIG | REB | PI (donor-side only) | REF | Med | SV | Files, Approvals, Portal | Wrap Lab | ORIG `routes/approvals.py` (355 lines) has `ArtworkProof` with `version`, `thumbnail_url`, `watermarked_url`, `admin_notes`, `customer_comment`, `approved_at`, `rejected_at`. Already dual-parent (jobs OR orders). Rename `job_id`→`order_id`. |
| Customer approvals | ORIG | REB, FEB | PI (donor-side) | REF | Med | SV | Portal, Signatures | Proofs, Contracts, Wrap Lab | Combined with signatures + proofs. |
| Document library / DocuLink | REB | ORIG | PH in MVP → RB on REB | RB | High | SV | Files, Templates | Portal, Wrap Lab | REB `routes/doculink.py` (244 lines) implements: BusinessDocument CRUD with `source_type=ai_generated → requires_review`, file upload with polymorphic entity links, download with activity event, document shares with recipient/access-level, activities log, filter by status/visibility/document_type/customer_id/order_id. **Full working scaffold + local storage adapter with SHA-256 + MIME validation.** Adopt the shape wholesale, but rewire the storage adapter to Emergent Object Storage (MVP's `services/storage.py`). |
| Inventory | ORIG | REB | NS in MVP | RB | Med | SV | — | Orders, Purchasing | ORIG `routes/inventory.py` + `services/inventory_service.py` + REB `INVENTORY_PURCHASING_VENDOR_MANAGEMENT_REBUILD_DOC.md` — permanent product roadmap Stage 13. |
| Vendors | ORIG | — | NS in MVP | RB | Med | RS | Inventory | Purchasing | Permanent product Stage 13. |
| Purchasing | ORIG | — | NS in MVP | RB | High | RS | Inventory, Vendors | Finance | Permanent product Stage 13. |
| Webstores — Order Portal Manager | REB | ORIG | PI (entitlement scaffold) | RB | Critical | SV+SO | Orders, Stripe, Files, Portal | Public storefront | REB has ONLY the capability + launch-readiness endpoints (`services/webstore_service.py` 34 lines) + full `WebstoreStatus` enum (draft → questionnaire_sent → questionnaire_received → setup_in_progress → owner_review_pending → changes_requested → stripe_onboarding_pending → ready_to_launch → live → paused → closed → archived → cancelled) — but no product/order code. ORIG has 3775-line `routes/webstores.py` — the feature discovery map. REB has **8 dedicated ORDER_PORTAL specs** as blueprint. **Stage 15 — build in permanent product on shared core once Stages 3–11 are stable.** |
| Webstore products & variants | ORIG | — | NS in MVP | RB | High | RS | Webstores | Storefront | ORIG has full product model + variants; use as reference. |
| Webstore setup wizard | REB (specs) | ORIG | NS in MVP | RB | High | SO | Webstores | — | REB `WEBSTORE_MASTER_REBUILD_SPEC.md` + `ORDER_PORTAL_MANAGER_MASTER_SPEC.md` are authoritative. |
| Webstore orders | ORIG | — | NS in MVP | RB | High | RS | Webstores, Orders | Payments | Reference in ORIG. |
| Stripe Connect & payouts | ORIG | FEB, REB | PI (donor + FEB webhook confirm path) | REF (safety-critical) | Critical | SV | Webstores, Payments | Payments | ORIG `routes/stripe_connect.py` (719 lines) + `services/stripe_service.py` (457 lines) + FEB `routes/stripe_connect.py` (719 lines) + FEB `services/payment_service.py::confirm_stripe_invoice_payment` (webhook-only, verified session with metadata attribution). REB `billing_rules.py` has the transaction-fee basis points table (0 during founders promo, 50bp founders standard, 100bp GA standard; 200bp GA webstore). **Financial-safety critical — must go through a formal security review before any port.** |
| Webstore owner portal | ORIG | REB | NS in MVP | RB | High | SV+SO | Webstores | — | ORIG `OwnerPortal.js`, `OwnerPortalSignup.js`. REB `ORDER_PORTAL_OWNER_PORTAL_SPEC.md`. |
| Webstore manager portal | REB | — | SO | RB | High | SO | Webstores | — | REB `ORDER_PORTAL_MANAGER_MASTER_SPEC.md` only. |
| Public storefront | ORIG | REB | NS in MVP | RB | High | RS+SO | Webstores | — | ORIG `routes/public_website.py` + REB `ORDER_PORTAL_PUBLIC_STOREFRONT_SPEC.md`. |
| Wrap Lab / Wrap Command Center | REB | ORIG | SS | REF | Critical | SV | Customers, Orders, Files, Approvals, Portal | — | REB `services/wrap_lab_service.py` (145 lines) + `routes/wrap_lab.py` (98 lines) + `models/wrap_lab.py` (71 lines) implement the full 11-stage workflow (`STAGES = Intake→Quote→Contract→Design→Proof Approval→Inspection→Production→Install→Pickup→Aftercare→Complete`), 14 workflow actions (`approve_quote`, `request_quote_revision`, `pay_deposit`, `sign_contract`, `approve_proof`, `request_proof_revision`, `acknowledge_inspection`, `sign_pre_install_packet`, `sign_final_packet`, `customer_concept_feedback`, `advance_stage`, `complete_stage`, `send_message`, `resolve_issue`), stage gates (deposit before contract, approved proof before install, checklists complete before advance), and a `public_project()` allowlist so internal pricing never leaks to the portal. **Full working scaffold, not spec-only.** Stage 16. |

### Business management

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Pricing Foundation | MVP | REB | AR | — | — | RV+SV | Tenants | Calc, Quotes, Orders | MVP starter defaults + per-tenant clone + wizard + calculator (verified end-to-end). REB `routes/pricing_foundation.py` (43 lines) + `services/pricing_engine.py` (1391 lines) is a **faithful port of ORIG's 9-category calculator suite** with cleaner code structure and the same math. Two calculation methods per category (`sell_rate_per_sqft` vs `cost_plus`, plus `max_of_both`, `package_benchmark`, `price_table`). **MVP already delivers this at Stage 12; REB's engine is a reference for future extended-formula work.** |
| Pricing calculators (9 categories) | MVP | REB | AR | — | — | RV+SV | Pricing Foundation | Quotes, Orders | 9 categories matched across all repos. |
| Materials pricing (tenant catalog editor) | ORIG | REB | PI in MVP | REF | Low | RS | Pricing | Calc | ORIG `MaterialsAdmin.js`. Adopt shape into MVP pricing UI. |
| Quote pricing integration | REB | — | PI | REF | Med | SV | Pricing, Quotes | Invoices | REB has per-line-item `calculate-pricing` + `override-pricing` endpoints. Adopt. |
| Order pricing integration | REB | — | PI | REF | Med | SV | Pricing, Orders | Invoices | REB has per-order-item `calculate-pricing` + `save-pricing` + `override-pricing` + `latest_pricing_snapshot`. **This is the Stage 5 pricing-snapshot feature.** |
| Invoice pricing derivation | FEB | REB | PI | EXT | Med | SV | Invoices, Orders | — | FEB `InvoiceService.compute_line_items_and_totals()` recomputes server-side (never trusts client line totals). Combine with Stage 6 port. |
| Finance dashboard | ORIG | — | NS in MVP | RB | High | RS | Invoices, Payments, Expenses | Reports | ORIG `Financials.js` + `services/profit_analytics.py`. Stage 13. |
| Revenue & expenses | ORIG | — | NS in MVP | RB | High | RS | Invoices | Finance | Stage 13. |
| Taxes | — | ORIG | NS in MVP | RB | Med | — | Invoices | Finance | Basic per-invoice tax field exists in FEB model. Sales-tax rules require jurisdiction data — build carefully in Stage 13. |
| Payroll | ORIG | FEB | NS in MVP | RB | High | RS | Employees, Time clock | Finance | Stage 14. |
| Time clock | ORIG | FEB | NS in MVP | RB | Med | RS | Employees | Payroll | ORIG `services/timeclock_service.py` + `routes/job_time.py`. Rename `job_time`→`order_time`. Stage 14. |
| Timesheets | ORIG | FEB | NS in MVP | RB | Med | RS | Time clock | Payroll | Stage 14. |
| Employee scheduling | ORIG | — | NS in MVP | RB | High | RS | Employees | Production | Stage 14. |
| Reports | ORIG | — | NS in MVP | RB | High | RS | Everything | — | Stage 13. |
| Custom report builder | ORIG | — | NS in MVP | RB | Critical | RS | Reports | — | Stage 13 later phase. |
| Analytics | ORIG | REB | NS in MVP | RB | High | RS | Reports | — | ORIG `services/productivity_query.py`, `PlatformAdminAnalytics.js`. Stage 17. |
| Subscription products & fees catalog | REB | ORIG | NS in MVP | EXT | Med | SV | Billing | Platform admin | REB `services/billing_rules.py` (111 lines) defines: 4 subscription products (Core, Webstores, Wrap, Complete Bundle) with founders vs GA pricing, monthly credits per product, credit top-up packs (100/300/800), founders promo (`FOUNDERS3MO`, 25 max redemptions, 3-month fee holiday), transaction fee basis points table (0/50/100 bp standard vs 0/150/200 bp webstore). `determine_transaction_fee_basis_points()` computes rate per checkout channel/phase. **This is the permanent commercial pricing model.** Adopt as-is when Stage 17 Platform Admin lands. |

### Team & workflow

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Team dashboard | ORIG | — | NS in MVP | RB | Med | RS | Employees, Tasks | — | Stage 14. |
| Employees | ORIG | FEB | NS in MVP | RB | High | RS | Users, Roles | Payroll, Scheduling, Portal | ORIG `routes/employees.py` + `models/employees.py`. |
| Tasks | ORIG | FEB | NS in MVP | RB | Med | RS | Users | Kanban | Stage 14. |
| Kanban boards | ORIG | — | NS in MVP | RB | Med | RS | Tasks | Team dashboard | Stage 14. |
| Calendar | ORIG | — | NS in MVP | RB | Med | RS | Appointments | Scheduling | Stage 14. |
| Appointments | ORIG | — | NS in MVP | RB | Med | RS | Customers | Calendar | Stage 14. |
| Install scheduling | ORIG | — | NS in MVP | RB | High | RS | Appointments, Employees | Orders | Stage 14. |
| Production scheduling | ORIG | — | NS in MVP | RB | High | RS | Work Orders | Employees | Stage 14. |
| Internal notes (polymorphic) | REB | ORIG | NS in MVP | REF | Low | SV | Any entity | UI | REB `routes/shared_systems.py::notes` uses `SharedRecordRepository` with tenant scoping. Adopt. |
| Team communication | REB | ORIG | NS in MVP | RB | Med | SV | Users | Team | REB `communications.py` notifications are the base. |
| Employee portal | ORIG | FEB | NS in MVP | RB | High | RS | Employees, Auth | Time clock | ORIG 5 EmployeePortal* pages + FEB 5 similar. DUP in donors — build fresh on MVP shared portal service. Stage 14. |

### Design studio & AI

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| AI tool catalog | REB | ORIG | PI (catalog only) | EXT | Med | SV | Auth | Assistant | REB `routes/shared_systems.py::AI_TOOLS` has 24 tools with `id/name/category/intensity/description`: text_to_image, idea_brainstormer, permit_research, photo_enhancer, image_vectorizer, font_identifier, ai_sign_designer, ai_banner_designer, mockup_creator, vehicle_wrap_mockup, logo_creator, branding_kit_generator, business_copywriter, document_composer, pricing_intelligence, blog_creator, completed_job_post, social_pack_generator, content_calendar, campaign_builder, wrap_cost_calculator, email_templates, review_responder, assistant_chat. **Adopt catalog as the permanent taxonomy.** |
| AI generation router (`POST /ai/generate`) | REB | ORIG | PH (stub returns preview text) | REF | High | SV | AI catalog, LLM provider | AI results collection | REB stub persists results in `ai_responses` collection but returns preview text. **The permanent product wires this to a real provider via Emergent LLM key + credit tracking.** |
| AI Assistant chat | ORIG | REB | PI (donor-side) | REF | High | RS | AI catalog, Credits | — | ORIG `AIAssistant.js` + `services/ai_assistant_actions.py` + `services/assistant_queries.py`. |
| Prompt Library | ORIG | REB | NS in MVP | RB | Med | RS | AI | — | Reference. |
| AI credit tracking | ORIG | REB | PI (donor-side) | REF | Med | SV | AI, Billing | Reports | ORIG `routes/credits.py` + `services/credit_service.py`. REB `billing_rules.py` defines monthly bank per plan + top-up packs. |
| AI usage history | ORIG | REB | PI (via REB `ai_responses` collection) | REF | Low | SV | AI Credits | Reports | REB persists every response. |
| AI billing logic | ORIG | REB | NS in MVP | EXT | High | SV | Credits, Stripe | — | REB `billing_rules.py` (products + promo + fee bps) + ORIG `services/multi_product_billing.py` (690 lines) — adopt REB's rules, ORIG for calculation details. |
| AI-generated file storage | REB | — | PI via DocuLink `source_type=ai_generated → requires_review` | REF | Low | SV | Files | AI | Already in the DocuLink model. |
| AI context retrieval | ORIG | — | NS in MVP | RB | High | RS | AI | — | ORIG `services/assistant_queries.py`. |

### Platform & support

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Onboarding | ORIG | — | PI in MVP (dev-bypass) | REF | Med | RS | Auth, Tenants, Pricing | — | ORIG `routes/onboarding.py` (176 lines) + `OnboardingHub.js`. |
| Help Center | FEB | ORIG | PH | CPY | Low | RS | — | — | FEB 14 static docs pages are the most reusable. |
| Community Hub | REB | ORIG | SS | REF | Med | SV | Users | — | REB `routes/shared_systems.py::community/*` implements post list/create/update, reply, upvote (with dedup by user), stats. **Working scaffold, not spec.** |
| Bug reports | REB | — | via community `category=bug_report` | REF | Low | SV | Community | — | REB community stats already filters by `category=bug_report`. |
| Feature requests | REB | — | via community `category=feature_request` | REF | Low | SV | Community | — | Same as bug reports. |
| Platform administration | REB | ORIG | SS | REF | High | SV | Auth | Everything | REB `routes/platform_admin.py` (90 lines) has: `require_platform_admin` dep (checks role in `platform_creator/platform_admin`), list tenants (search + status), get tenant, patch tenant status (`suspended`, `active`, etc.), tenant readiness endpoint, audit-events listing per tenant. **Real scaffold.** Stage 17. |
| Platform tenant management | REB | ORIG | SS | REF | High | SV | Tenants | Platform admin | Included in above. |
| Platform analytics | ORIG | — | NS in MVP | RB | High | RS | Everything | — | ORIG `PlatformAdminAnalytics.js`. Stage 17. |
| Platform audit logs | MVP | REB, ORIG | WR | REF | Low | RV+SV | Audit | Platform admin | MVP audit collection + reader route. REB `PlatformAdminAuditListResponse` is the target shape for platform-level filtering. |
| Platform email & announcements | ORIG | REB | NS in MVP | RB | Med | RS | Email | — | ORIG `PlatformAdminBroadcastEmail.js`. |
| Subscription plans | REB | ORIG, FEB | PI in donors | EXT | High | SV | Stripe | Billing | Use `REB billing_rules.py` for canonical rules. |
| Add-ons / credit packs | REB | — | PI in REB | EXT | Med | SV | Plans, Stripe | — | REB `CREDIT_TOP_UP_PRODUCTS`. |
| AI credit purchases | REB | — | PI in REB | EXT | Med | SV | AI credits, Stripe | — | Included above. |
| Public marketing website | ORIG | FEB | NS in MVP | RB | Low | RS | — | — | ORIG `LandingPage.js`, `AboutPage.js`, `FeaturesPage.js`, `ContactPage.js`. Move to a separate static frontend later. |
| Public pricing & plan selection | ORIG | FEB | NS in MVP | RB | Low | RS | Plans | — | ORIG `Pricing.js`, `PricingPlansV2.js`, `FoundersEditionPricing.js`. |

### Portals & public systems

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Customer portal | ORIG | FEB, REB | NS in MVP | RB | High | SV | Auth, Customers, Files, Approvals | Proofs, Payments | ORIG `routes/portal.py` (2195 lines) is a full working portal (register, login, dashboard, orders, quotes, invoices, messaging, proofs, PDFs via reportlab). Already normalises order statuses from donor `Job` shapes to portal-facing keys (`_normalize_order_status`) and handles both `db.orders` and `db.jobs` collections — so the Order path is already precedented. **Rename job→order everywhere; keep the rest.** DUP with FEB. |
| Employee portal | ORIG | FEB | NS in MVP | RB | High | RS | Employees, Auth | Time clock | 5 pages each in ORIG + FEB — DUP. Build fresh on MVP shared portal service. |
| Webstore owner portal | ORIG | REB | NS in MVP | RB | High | RS+SO | Webstores | — | See Stage 15. |
| Webstore manager portal | REB (spec) | — | SO | RB | High | SO | Webstores | — | See Stage 15. |
| Public storefront | ORIG | REB, FEB | NS in MVP | RB | High | RS+SO | Webstores, Public forms | — | See Stage 15. |
| Public forms | ORIG | REB | NS in MVP | RB | Med | RS | Forms | — | Stage 10 later. |
| Public questionnaires | ORIG | REB | NS in MVP | RB | Med | RS | Questionnaires | — | Same. |
| Public quote/intake | ORIG | — | NS in MVP | RB | Med | RS | Quotes | — | Same. |

---

## Corrections applied vs the prior pass (per-row diff)

| Row | Prior classification (2026-07-07) | New classification (this pass) | Reason for change |
|---|---|---|---|
| Settings framework | `UNK — depth unknown, user paste needed` | `PI in MVP → REF to REB (SV)` | REB `routes/settings.py` + `models/settings.py` inspected line-by-line; a working scaffold exists. |
| Notifications | `UNK — user paste needed` | `NS in MVP → RB on REB scaffold (SV)` | REB `routes/communications.py::notifications` is real code. |
| Email SendGrid webhook | Not listed | Added — `WR (MVP send) + adopt REB webhook (SV)` | REB implements HMAC-verified inbound webhook. |
| Upload validation | Not listed | Added — `NS in MVP → EXT REB (SV)` | REB `services/upload_validation.py` has magic-byte + MIME + size + SHA-256. |
| Attachments / polymorphic links / shares | Row said `WR / unique to MVP` | Downgraded to `WR + adopt REB shares model (SV)` | REB has richer `file_links` + `document_links` + `document_shares` with `customer_visible` + `access_level`. |
| DocuLink | `PH — no working code` | `RB on REB scaffold (SV)` — full working scaffold, storage adapter needs Emergent object storage rewire | REB `routes/doculink.py` + `services/doculink_storage.py` + `services/doculink_bridge.py` are all real. |
| Wrap Lab | `UNK — depth unknown` | `SS — REF (SV)` — full 11-stage workflow engine in REB | REB `services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py` inspected. |
| Signatures | `PI — donor-side` | `NS in MVP → REF ORIG (SV)` — 11-parent structured signature system | ORIG `routes/signatures.py` (658 lines) inspected. |
| Approvals | `UNK — depth unknown` | `PI (donor-side) → REF ORIG (SV)` — already dual-parent jobs+orders | ORIG `routes/approvals.py::_get_proof_parent_name` reads both `db.jobs` and `db.orders`. |
| Invoices | `PI — highest-priority migration target` | Same target, but promoted from UNK → `EXT FEB (SV)` — full 147-line reconciliation formula proven | FEB `services/invoice_service.py` inspected. |
| Payments | `PI — Stage 6 target` | Same target, promoted from UNK → `EXT FEB (SV)` with full 320-line implementation | FEB `services/payment_service.py` inspected. |
| Quote items with pricing snapshots + expiration + revisions | Listed as a gap | Now with concrete REB-shape target (SV) | REB `models/quotes.py` + `routes/quotes.py` inspected. |
| Order items with pricing snapshots + `production_required` + snapshot | Listed as a gap | Now with concrete REB-shape target (SV) | REB `models/orders.py` + `services/order_item_rules.py` inspected. |
| Work Order gate on `production_required` | Listed as a spec violation | Now has concrete import target: `services/order_item_rules.py::default_production_required` (SV) | 14-line helper inspected. |
| Pricing calculators (9 categories) | `WR / needs materials editor` | Same, but REB has a 1391-line faithful port with `cost_plus` + `sell_rate_per_sqft` methods (SV) | REB `services/pricing_engine.py` inspected. |
| AI tools catalog | `PI — cost/security risk` | `PI (SV) — REB has canonical 24-tool catalog; billing rules published in `billing_rules.py`` | REB `routes/shared_systems.py::AI_TOOLS` + `services/billing_rules.py` inspected. |
| Community Hub / Bug reports / Feature requests | `UNK / NS` | `SS — REF (SV)` — REB implements post/reply/upvote/stats and categorises by bug_report/feature_request | REB `routes/shared_systems.py` inspected. |
| Platform admin | `PI — 6+ pages` | `SS — REF (SV)` — REB has tenant list/get/patch-status/readiness + audit-events endpoints with `require_platform_admin` dep | REB `routes/platform_admin.py` inspected. |
| Subscription plans / add-ons / credit packs | `UNK / DEF` | Reclassified to `EXT REB (SV)` — REB `billing_rules.py` has full commercial pricing model | REB `services/billing_rules.py` inspected. |
| Onboarding | `PI` | Same but with confirmed 176-line ORIG donor (RS) | ORIG `routes/onboarding.py` size confirmed. |
| Customer portal | `PI — ORIG 10 pages + FEB 8 pages` | `NS in MVP → RB (SV)` — ORIG portal already handles both `db.orders` and `db.jobs` | ORIG `routes/portal.py` inspected. |
| `SIGNGUY-AI-OS` identity vs MVP | "Recommendation: retire" | **Byte-identical (RV)** — md5sum of every `.py` under `backend/app/` matches MVP. Frontend page count matches. **Confirmed: retire.** | md5 tree comparison run in this pass. |
| Object storage | `UNK — user paste needed` | `RS clean` — ORIG file is 35 lines, Emergent HTTP client, no base64 anti-pattern | ORIG `services/object_storage.py` inspected. |
| Money representation | Not stated as an architectural decision | Added — explicit decision required (`float dollars + integer cents at Payment boundary` per FEB, vs `integer cents everywhere` per REB) | Cross-file comparison done. |
| "Deferred by MVP scope" language | Present on ~35 rows | **Removed everywhere** | Per user directive. Each of those rows now has an explicit build-out stage. |

## Prior "Missing information" section — resolved

Every file listed under `Missing information that must be resolved…` in the previous pass has been read directly in this pass:

- `signguy-ai-feb22/backend/services/invoice_service.py` — **inspected** (147 lines). Full reconciliation formula owner.
- `signguy-ai-feb22/backend/services/payment_service.py` — **inspected** (320 lines). Manual + Stripe two-step + void + idempotency + overpayment reject.
- `signguy-ai-feb22/backend/models/payments.py` — **inspected** (148 lines). Integer cents + PaymentSource + PaymentStatus + refunded_amount_cents.
- `signguyai_rebuild_version/backend/routes/settings.py` + `models/settings.py` — **inspected** (77 + 37 lines). Thin working scaffold.
- `signguyai_rebuild_version/backend/services/communications.py` + `routes/communications.py` — **inspected** (50 + 170 lines). Working notifications + email activity + SendGrid webhook with HMAC signature verification.
- `signguyai_rebuild_version/backend/services/doculink_bridge.py` + `services/doculink_storage.py` + `routes/doculink.py` — **inspected** (29 + 58 + 244 lines). Full working scaffold.
- `signguyai_rebuild_version/backend/services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py` — **inspected** (145 + 98 + 71 lines). Full 11-stage workflow engine.
- REB `memory/MODULE SPECS MDS/*` — 28+ spec MDs enumerated; still the authoritative architectural playbook.
- `signguyai/routes/approvals.py` — **inspected**. Dual-parent (jobs + orders) proof system with version/thumbnail/watermark/admin_notes/customer_comment.
- `signguyai/routes/signatures.py` — **inspected**. 11-parent structured signature system.
- `signguyai/services/object_storage.py` — **inspected**. Clean 35-line Emergent HTTP client. No base64 anti-pattern.
- `signguyai/routes/portal.py` — **inspected** (first 80 lines). 2195-line customer portal already handling both `db.orders` and `db.jobs`.

## Retired questions from prior pass

- "Is `SIGNGUY-AI-OS` intended as a distinct repo?" → **No.** md5 tree confirms byte-identical to MVP. Retire.
- "Which stage first?" → Mandated build order is Stage 6 (Invoices/Payments per FEB), then Stage 5 fix + Stage 7 (`production_required` gate + Work Order rework). No change from the master plan.

---

## Top-ten lists (revised)

### 10 strongest reusable systems
1. **MVP Auth / Tenants / Permissions** — single-dependency, tenant-scoped, cross-tenant sweep passing (**RV**).
2. **MVP Object Storage + Attachments** — private by default, tenant paths, authed downloads (**RV**).
3. **MVP Audit Helper** — non-optional actor (**RV**).
4. **MVP Idempotent Convert-to-Order** — atomic Mongo guard (**RV**).
5. **MVP Pricing Foundation + Calculator** — starter defaults + per-tenant clone + wizard + canonical calc (**RV**).
6. **MVP Atomic Sequence Service** — race-safe per-tenant numbering (**RV**).
7. **MVP SendGrid Service** — 5 live templates verified (**RV**).
8. **MVP Dashboard aggregation** — permission-gated single-payload summary (**RV**).
9. **FEB `invoice_service.py` + `payment_service.py`** — dual-status, void-with-reason, reconciliation, Stripe two-step, overpayment reject, idempotency-key (**SV**).
10. **REB `services/upload_validation.py`** — magic-byte + MIME + size + SHA-256 (**SV**) — small, drop-in, immediate security upgrade.

### 10 highest-risk systems
1. **Webstores / Order Portal** — Stripe money movement + storefront + wrap. Stage 15.
2. **Wrap Lab** — deep cross-dependency (files, approvals, portal, email, payments). Stage 16.
3. **Payments + Stripe Connect** — real money, refund risk. Must go through security review before port.
4. **AI billing / credits** — real cost tied to LLM API usage. Needs cost-cap + tenant metering before enabling.
5. **Terminology conflict** — every donor file touching `job_id`/`jobs` must be renamed to `order_id`/`orders` before landing. Silent poisoning risk.
6. **Money representation decision** — float vs integer cents. Must be documented before Stage 6 or invoices split.
7. **`SIGNGUY-AI-OS` mirror repo** — will drift the moment anyone commits to it. Must be retired.
8. **ORIG `App.js` monolith and `routes/pricing.py`/`pricing_setup.py`** — explicitly banned by migration doc; never copy.
9. **ORIG `routes/backup.py`, `routes/dev.py`** — dev-only routes must not ship into permanent product.
10. **Preview-only patterns in REB** (`PreviewEnvelope` base model, header-based tenant impersonation) — must be sanitised out before landing.

### 10 most important shared dependencies to build BEFORE further module migration
1. Auth + Tenant middleware (**done**).
2. Single permission dependency (**done**) — adopt REB's 57-permission StrEnum.
3. Shared audit helper (**done**) — adopt REB's event_type/severity/changes shape.
4. Object storage + polymorphic attachments (**done**) — adopt REB's file_links/document_links/document_shares.
5. Atomic sequence service (**done**).
6. **Money handling policy doc** (NOT done) — must land before Stage 6.
7. **Settings framework** (REB scaffold, NOT ported yet) — must land as Stage 2.
8. **Notification service** (REB scaffold, NOT ported yet) — must land as Stage 2.
9. **Feature flags / entitlements service** (REB `FeatureEntitlementRepository` referenced by `webstore_service.py`; NOT ported yet) — must land before Webstore work.
10. Shared API client + error envelope on frontend (**done**).

### 10 areas where rewriting would waste prior work
1. Pricing Foundation & Calculator (MVP is the target).
2. Quote-to-Order idempotent convert (MVP has the correct pattern).
3. SendGrid email service (working live).
4. Object storage + attachments (working + verified secure).
5. Audit helper (correct actor pattern).
6. Sequence generator (verified race-safe).
7. Customer / Order / Invoice basic CRUD + linked-records view (MVP passing).
8. Design guidelines (MVP has enforced light SaaS system).
9. Cross-tenant isolation infrastructure (verified).
10. Dev auth bypass (environment-gated with warning banner).

### 10 areas where copying blindly would create unacceptable risk
1. FEB `models/jobs.py` — `Job` domain conflict with `Order`.
2. ORIG `routes/job_tickets.py` + `LegacyJobRedirect.js` — banned terminology.
3. ORIG `routes/webstores.py` full port — must be spec-driven rebuild.
4. ORIG `routes/pricing.py` / `pricing_setup.py` / `MaterialsAdmin.js` — banned giant pricing system.
5. ORIG `routes/ai.py` + credit services — cost/security risk.
6. ORIG `Documents/Documents.js` — assumes ORIG data model.
7. ORIG `services/multi_product_billing.py` — Stripe risk.
8. ORIG `routes/backup.py`, `routes/dev.py` — dev-only routes must not ship.
9. ORIG `PortalPreview.js` + `preview-shop` tenant headers — excluded by migration doc.
10. REB `PreviewEnvelope` + preview-user impersonation defaults — sanitise before landing.

---

## Cross-module findings (revised)

- **Duplicate customer systems** — REB, FEB, ORIG all define `customers`. MVP already implements correctly; donor models = reference only.
- **Duplicate order/quote systems** — MVP `Order/OrderItem`. FEB + ORIG `Job/JobItem/JobTicket`. Rename during port; never copy the term.
- **Duplicate invoice/payment systems** — MVP (single-status), FEB (dual-status + void + reconciliation + Stripe two-step), ORIG (Job-based). FEB is the Stage 6 donor.
- **Duplicate document systems** — MVP shared attachments only. ORIG `Documents/Documents.js` + wrap files + order drawings + doc templates. REB has full DocuLink scaffold with polymorphic links + shares + local object storage. **REB is the target scaffold; rewire storage adapter to Emergent object storage.**
- **Duplicate file storage systems** — MVP uses Emergent object storage. ORIG has clean 35-line HTTP client (compatible). REB uses local disk with hashing. **No base64-in-Mongo anti-pattern in ORIG's `object_storage.py`.**
- **Duplicate settings systems** — MVP has ad-hoc; REB has intentional `routes/settings.py` + `models/settings.py` + activity events. **REB is the target.**
- **Duplicate messaging systems** — ORIG `sms.py` + `facebook_messages.py` + `email_templates.py`; REB `communications.py`; MVP `emails.py`. Consolidate at Stage 9 via REB shape.
- **Duplicate form/questionnaire systems** — ORIG `questionnaires.py` + `signatures.py`; REB has spec-level only.
- **Duplicate pricing systems** — MVP is definitive. ORIG has the "giant pricing system" explicitly forbidden by the migration doc. REB has a faithful 1391-line refactor of the same math (reference for extended-formula work only).
- **Duplicate authentication/role logic** — MVP single-source; REB has a richer permission catalog (57 permissions) — adopt.
- **Duplicate portal implementations** — ORIG 10 pages + FEB 8 pages. Rebuild on MVP.
- **Duplicate AI credit logic** — ORIG (`credits.py`, `credit_service.py`, `multi_product_billing.py`) + REB `billing_rules.py`. **REB's `billing_rules.py` is the canonical commercial pricing spec** (subscription products + credit packs + founders promo + transaction fee basis points).
- **Conflicting status values** — MVP invoice single status; FEB split document/financial; ORIG job-based. Adopt FEB.
- **Conflicting terminology** — Order↔Job, OrderItem↔JobItem/JobTicket, WorkOrder↔ProductionTask/JobTicket. MVP terms win.
- **Conflicting DB ownership** — ORIG scatters tenant filtering across route files. REB uses repository pattern with `tenant_id` on every method. MVP uses a hybrid — inline dependency + explicit `tenant_id` filter. Prefer REB's repository pattern for new modules.
- **Frontend without working backend** — REB (5 frontend pages vs 18 backend routes). Backend is the value donor; frontend is not.
- **Backend without frontend** — ORIG `digest`, `workflow_templates`, `credits`, `magic_links`. Reference only.
- **Circular dep risk** — REB relies heavily on `core_runtime` + `repositories/*`; every route has an `except ImportError: from ...` fallback. When porting into MVP, resolve to a single import path.
- **Preview-only artefacts to sanitise** — REB `PreviewEnvelope` base model, `preview-user` fallbacks in shared_systems, `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` unset behavior (webhook accepts anything if secret unset — must be forced-set in production).

---

## Missing information: NONE remaining for this pass

Every file listed in the prior "Missing information" section has been read line-by-line. There is enough evidence now to make final classifications for **every row** in this matrix and to correct the Architecture Source Map (Parts 1, 3, 3A, 11) and complete Parts 2, 4, 5, 6, 7, 8, 9, 10.

If additional donor files must be inspected later for a specific stage (e.g., ORIG's `webstores.py` in detail for Stage 15), those are file-level not audit-level questions and will be resolved at implementation time — not by pausing the audit.

## Standing architectural decisions this matrix now requires the user to sign off on

1. **Retire `SIGNGUY-AI-OS`** (freeze / delete) — byte-identical to MVP.
2. **Money representation** — adopt FEB's boundary compromise (float dollars in invoices/orders/quotes, integer cents in the new Payment collection with conversion in `reconcile_invoice_financials`)? Or migrate everything to integer cents per REB?
3. **Permission catalog source** — adopt REB's 57-permission StrEnum verbatim?
4. **Repository pattern** — adopt REB's repository pattern for all new modules (Settings, Notifications, DocuLink, Wrap Lab, Platform Admin)?
5. **Terminology mapping table** — canonical `Order/OrderItem/WorkOrder` recorded as permanent; every donor file renamed on port.
6. **SendGrid webhook enablement** — set `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` in production and force-fail on unset (webhook currently permissive on unset secret in REB).

These decisions belong in `memory/AGENT_INSTRUCTIONS.md` before the corresponding stage lands.
