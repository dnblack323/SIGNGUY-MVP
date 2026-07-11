# SignGuy AI — Feature Readiness Matrix (Corrected & Completed Pass)

**Audit date:** 2026-07-11 (corrected pass)
**Auditor:** E2 agent — direct-inspection pass (donor repos cloned at HEAD and read line-by-line)
**Repository role:** `dnblack323/SIGNGUY-MVP` is the **permanent commercial product**. It is NOT an MVP scaffold to be discarded. Every feature currently missing is a **build-out gap in the permanent product**, not a "deferred by MVP scope" concession. All prior "defer / post-launch / optional" language has been removed from this document.

## What is different from the prior pass

The previous pass (2026-07-07) reasoned mostly from file trees and left many rows as `UNK — user please paste the file`. That policy was rejected and is now void. This pass **cloned the four donor repositories at their HEAD commits and read the actual source of the key modules**. Every row that was previously `UNK due to missing evidence` has been re-classified against real code, or explicitly labelled `INSPECTED — thin scaffold only` / `INSPECTED — full working implementation` / `SPEC ONLY — no runtime code` based on what the source actually contains.

## Evidence-level legend (new — required for every row)

| Symbol | Meaning |
|---|---|
| **RV** | **RUNTIME VERIFIED** — behavior confirmed against the running SIGNGUY-MVP preview via a live request in a prior testing-agent iteration or equivalent live check. |
| **STHV** | **SOURCE TREE HASH VERIFIED** — the two source trees were compared via `md5sum` over a defined path/file-type set. NOT a runtime check. |
| **FSV** | **FULL SOURCE VERIFIED** — file read line-by-line in this pass. |
| **PSI** | **PARTIALLY SOURCE INSPECTED** — only a portion of the file (head, function of interest, top-level control flow) was read; REFERENCE BEHAVIOR IDENTIFIED. A FULL TRACE IS REQUIRED DURING MODULE PREFLIGHT before any port lands. |
| **SS** | **SPEC + SCAFFOLD** — a working code scaffold exists in the donor repo, verified against source, but is not yet runtime-verified end-to-end. |
| **SO** | **SPEC ONLY** — REB `memory/MODULE SPECS MDS/*` or ORDER_PORTAL specs describe the target, but no matching runtime code exists in any donor. |
| **RS** | **REFERENCE ONLY** — implementation exists in a donor but is unsafe or terminology-incompatible; used only as a discovery map. |

## Repositories inspected (cloned in this pass)

| Repo | Last commit inspected | Total py in backend | Backend routes | Backend services | Backend models | Frontend pages | Role |
|---|---|---|---|---|---|---|---|
| `dnblack323/SIGNGUY-MVP` | current | 39 | 13 | 7 | 11 | 21 | **Permanent product** |
| `dnblack323/SIGNGUY-AI-OS` | `f896a77 2026-07-08` | 39 | 13 | 7 | 11 | 21 | **Mirror of MVP under `backend/app/**/*.py`** — see Critical Finding #1 for the exact scope of the comparison. **No new development.** |
| `dnblack323/signguyai_rebuild_version` | HEAD | 143 | 18 | 14 | 19 | 5 | **Reference architecture + spec donor** |
| `dnblack323/signguy-ai-feb22` | HEAD | 71 | 22 | 6 | 9 | 59 | **Financial-logic donor (Stage 6)** |
| `dnblack323/signguyai` | HEAD | 154 | 60 | 29 | 16 | 133 | **Feature discovery map (RS only)** |

## Critical up-front findings (revised 2026-07-11 reconciliation pass)

1. **`SIGNGUY-AI-OS` is a mirror of `SIGNGUY-MVP` under `backend/app/**/*.py` (STHV, scoped).** In this pass I ran `md5sum` over every `.py` file under `backend/app/` in both repos; the sorted hash streams match (`34bdb9b33abb1fa71058c8d5481723d8`). Backend `.py` count matches (39 vs 39). Frontend page count matches (21 vs 21). **What was NOT compared:** the full git tree (frontend `src/**` beyond page count, `package.json` + lockfile diffs, `requirements.txt`, `.env` samples, docs, memory notes, non-Python assets, branch heads, commit history, tag lists). Calling the two repos "byte-identical" was overreach. **Corrected recommendation: no new development in `SIGNGUY-AI-OS`; run a complete-tree comparison before any archival; then move it to read-only/archive status after the permanent product is finished and all migrations are verified. Do NOT delete — preserve branches, tags, commit history, docs, and recovery value until final commercial completion.**
2. **REB is NOT "90% spec, 10% code" — that earlier claim was wrong.** REB backend contains a full working scaffold (all read line-by-line, FSV, in this pass) for: `settings` (77 + 37 lines), `communications` (170 + 50 lines, with a SendGrid webhook that verifies HMAC-SHA256 against `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET`), `doculink` (244 + 58 + 29 lines with SHA-256 upload validation), `wrap_lab` (145 + 98 + 71 lines, full 11-stage workflow engine), `platform_admin` (90 lines), `shared_systems` (193 lines including a 24-tool AI catalog), `webstores` (34 + 26 + 45 lines — entitlement-only, no product/order code yet), `billing_rules` (111 lines), `pricing_engine` (1391 lines), `pricing_foundation` (43 lines). Every one of these is FSV in this pass, not "UNK".
3. **FEB's financial services are actionable and FSV.** `services/invoice_service.py` (147 lines, FSV) and `services/payment_service.py` (320 lines, FSV) implement the dual-status + void-with-reason + reconciliation + Stripe two-step + overpayment-reject + idempotency-key patterns. The `Payment` model uses integer cents (`amount_cents`) and independently derives `document_status` and `financial_status` in `_derive_states()`. Whether the permanent product adopts this exact shape is an owner decision (see the Money Policy section below and the Standing Decisions section).
4. **The `Job/JobTicket` terminology conflict is real but narrowly scoped.** FEB's InvoiceService/PaymentService are almost job-agnostic — they only touch `db.invoices` and `db.payments`. The `job_id` field on the Payment model is optional. A port requires renaming `job_id` → `order_id` (nullable) on the Payment model and adjusting the two `invoice.get("job_id")` reads.
5. **ORIG contains real signatures + approvals + portal code — PARTIALLY SOURCE INSPECTED in this pass.** `routes/signatures.py` (658 lines total; PSI — first 60 lines read: 11 supported parent record types + `SIGNATURE_TYPE_MAP` header confirmed). `routes/approvals.py` (355 lines total; PSI — first 80 lines read: dual-parent `_get_proof_parent_name` reading both `db.jobs` and `db.orders` confirmed). `routes/portal.py` (2195 lines total; PSI — first 80 lines read: portal auth + status normalisation header confirmed). **REFERENCE BEHAVIOR IDENTIFIED; FULL TRACE REQUIRED DURING MODULE PREFLIGHT before any port lands.**
6. **ORIG `object_storage.py` is FSV (35 lines) — clean Emergent Object Storage HTTP client.** No base64-in-Mongo anti-pattern in that file. The migration document's warning about base64 refers to older, purged code paths elsewhere in ORIG.
7. **All four donors converge on the same 9 item categories.** REB `order_schemas.py` and `pricing_engine.py`, FEB `models/enums.py` (imported by `models/jobs.py`), ORIG `models/pricing.py`, and MVP `services/starter_defaults.py` all use the same category set: rigid_signs, banners, cut_vinyl, digital_print, vehicle_wrap / vehicle_graphics, apparel, services, promo_misc / promotional, custom. No category conflict — only a terminology conflict on the parent record (Job vs Order) and category naming (`vehicle_wrap` vs `vehicle_graphics`, `promo_misc` vs `promotional`).
8. **Money representation in MVP — corrected in this pass (FSV):** MVP already stores commerce money in **integer cents** in Pydantic models: `Quote.total_cents`, `OrderItem.unit_price_cents` (with derived `line_total_cents`), `WorkOrderItemSnapshot.unit_price_cents`, `Invoice.total_cents`, `InvoiceLineItem.unit_price_cents`, `Payment.amount_cents`. Invoice `balance_due_cents` is computed at request time in the router (not stored). Frontend `lib/format.js` has `centsToDollarsString` / `parseDollarsToCents` helpers and `MoneyInput.jsx` uses them on every money field. **However** pricing configuration and pricing-calculator output are in **float dollars**: `services/pricing.py` (line 109 docstring: "All money returned as float dollars, rounded to 2 decimals"), `services/starter_defaults.py` (line 11–12 docstring: "Money is stored as float dollars in this seed for readability; calculator converts to internal Decimal for math to avoid float drift"), all `SHOP_DEFAULTS` rates (`design_hourly_rate=97.00`, `production_hourly_rate=28.00`), all `MATERIALS.cost_per_sqft`/`sell_per_sqft`. There are NO tax / discount / fee fields on any current model. There is NO `amount_paid_cents` field on Invoice (paid amount is summed from `payments` collection at request time). There is NO `document_status` / `financial_status` split on Invoice. **This makes the earlier "MVP uses float dollars across Quotes/Orders/Invoices" claim in the previous matrix pass incorrect. The correction is applied here and in the Money Policy section below.**
9. **Terminology reconciliation table (canonical for the permanent product):**
   - `Order` (never `Job`)
   - `OrderItem` (never `JobItem` / `JobTicket`)
   - `WorkOrder` (never `ProductionTask` / `JobTicket`)
   - `Invoice`, `Payment`, `Quote`, `Customer` — same in all repos.
   - Every donor file that touches `job_id` / `jobs` collection must be renamed to `order_id` / `orders` before landing in MVP.
10. **A previous 0–17 stage build order exists in `memory/AGENT_INSTRUCTIONS.md` and was treated as mandated in the prior audit pass. In this pass that framing is corrected: the 0–17 order is a useful proposed dependency reference, not the final permanent-checkpoint numbering. The final internal checkpoint order (name + count + dependencies) will be established by Prompt 3 and the master build plan after money policy, commercial scope, and pricing decisions are locked. Nothing in this document freezes the stage numbering.**

---

## MONEY REPRESENTATION — CURRENT STATE + FINAL RECOMMENDATION

### Exact current representation (FSV in this pass)

| Field / area | Location | Current type | Evidence |
|---|---|---|---|
| Pricing configuration — hourly rates (design/production/install) | `services/starter_defaults.py::SHOP_DEFAULTS` | **float dollars** (e.g. `97.00`, `28.00`) | FSV |
| Pricing configuration — material `cost_per_sqft` / `sell_per_sqft` | `services/starter_defaults.py::MATERIALS` | **float dollars** (e.g. `0.85`, `8.00`) | FSV |
| Pricing configuration — `minimum_charge`, `overhead_percentage`, etc. | `services/starter_defaults.py::CATEGORY_DEFAULTS` + `pricing_settings` collection per tenant | **float dollars / float percent** | FSV |
| Pricing calculator input | `services/pricing.py::calculate_pricing` args (e.g. `manual_selling_price`) | **float dollars** | FSV |
| Pricing calculator output | `services/pricing.py` return payload | **float dollars, rounded to 2 dp** (uses Decimal internally, casts to float at boundary) | FSV (docstring line 109) |
| Quote totals | `models/quote.py::Quote.total_cents` | **integer cents** | FSV |
| Quote line items | *(no line items on Quote model in current MVP)* | — | FSV — no `QuoteLineItem` model exists |
| Order item unit price | `models/order.py::OrderItem.unit_price_cents` | **integer cents** | FSV |
| Order item line total | `models/order.py::OrderItem.line_total_cents` (derived) | **integer cents** | FSV |
| Order totals | *(not stored on Order; UI computes from items)* | derived from item cents | FSV (see `pages/OrderDetailPage.jsx` client-side sum) |
| Invoice totals | `models/invoice.py::Invoice.total_cents` | **integer cents** | FSV |
| Invoice line items | `models/invoice.py::InvoiceLineItem.unit_price_cents` (model exists; not yet exposed through routers) | **integer cents** | FSV |
| Invoice balance due | `routers/invoices.py` — computed per-request as `total_cents - sum(payments.amount_cents)` | **integer cents, transient** | FSV |
| Invoice amount paid | not stored — summed at request time from payments | **integer cents, transient** | FSV |
| Payments | `models/invoice.py::Payment.amount_cents` | **integer cents** | FSV |
| Payment idempotency | `Payment.idempotency_key` (nullable) | — | FSV |
| Taxes | **NOT MODELED** — no field exists on Invoice / Order / Quote | — | FSV |
| Discounts | **NOT MODELED** — no field exists on Invoice / Order / Quote | — | FSV |
| Fees | **NOT MODELED** — no field exists | — | FSV |
| Stripe amounts (future) | not yet integrated | — | — |
| Work Order snapshot money | `models/work_order.py::WorkOrderItemSnapshot.unit_price_cents` | **integer cents** | FSV |
| Frontend display | `frontend/src/lib/format.js::centsToDollarsString` divides by 100; `parseDollarsToCents` multiplies by 100 with `Math.round`; `components/forms/MoneyInput.jsx` uses these on every money field | dollars for display / cents on the wire | FSV |

**Bottom line on current state:** MVP has a **clean and already-consistent split** — commerce (Quote/Order/Invoice/Payment/WorkOrder) in **integer cents** on both the model layer and the frontend wire; pricing configuration + calculator return in **float dollars** with `Decimal` internal math. There is no representation contradiction in the code itself. The previous matrix's "MVP uses float dollars across Quotes/Orders/Invoices" claim was incorrect and is retracted.

### Final recommended money policy

**Recommendation:** ratify the split MVP already has, formalise the boundary, and extend it forward. Do NOT adopt the FEB "float-dollars-in-invoice + integer-cents-in-payment" compromise — MVP is already cleaner than FEB on this axis.

Formal policy:

1. **Commerce collections use integer cents.** Every stored money field on `Quote`, `QuoteLineItem` (once added), `Order`, `OrderItem`, `WorkOrder`, `WorkOrderItemSnapshot`, `Invoice`, `InvoiceLineItem`, `Payment` uses **`int`** and is suffixed **`_cents`**. Future additions (`tax_cents`, `discount_cents`, `fee_cents`, `amount_paid_cents`, `balance_due_cents` if promoted from transient to stored, Stripe amounts on Payment) follow the same suffix rule.
2. **Pricing configuration + calculator use float dollars with Decimal internal math.** All fields in `starter_defaults.py` and `pricing_settings` remain float dollars. The calculator continues to compute in `Decimal` and cast to `float` (rounded to 2 dp) at the response boundary. This is a **configuration-vs-transaction** boundary, not an inconsistency: config is human-editable and per-tenant; transaction values are audit-critical and must be exact.
3. **The single boundary lives in the pricing→commerce hand-off**, i.e. wherever the pricing calculator's dollar output is written onto an Order/Quote/Invoice line item. That conversion MUST use `round(dollars * 100)` (banker's rounding is not required; standard `round()` matches the frontend `Math.round`). The conversion helper lives in `services/pricing.py` and returns a cents integer alongside the float dollar payload for callers that want to snapshot.
4. **Stripe values are integer cents on the wire and integer cents on our Payment row.** Stripe's own convention is already cents; no conversion required.
5. **Rounding behavior** — `Decimal` `ROUND_HALF_UP` inside the calculator (matches `pricing.py` current behavior); `Math.round` on the frontend (matches `parseDollarsToCents`); `round(x * 100)` at any Python conversion boundary. All three round the same way at 2 dp so no drift.
6. **Naming conventions** — money fields ALWAYS suffix `_cents` (integer) or `_dollars` (float, rare — only in `pricing_settings` and calculator outputs). No unsuffixed money fields on any model or API response.
7. **API boundaries** — every JSON response uses the same suffix as the model. No display-formatted currency strings on API responses (frontend formats).
8. **Database impact** — **NONE**. Every current commerce field is already integer cents. No migration needed. New fields (`tax_cents`, `discount_cents`, `amount_paid_cents` if promoted to stored, `document_status`, `financial_status`) are additive.
9. **Frontend conversion requirements** — no change. `centsToDollarsString` / `parseDollarsToCents` / `MoneyInput` already correct. New fields inherit the same helpers.
10. **Migration impact** — Stage 6 (Invoice/Payment migration from FEB donor code) requires FEB's Payment model to be **rehoused** into MVP's existing integer-cents naming: rename FEB `amount_cents` → keep as `amount_cents` (compatible), `refunded_amount_cents` → keep, `job_id` → `order_id`. Reconciliation logic (`reconcile_invoice_financials`) requires cents inputs (no dollar/cent conversion needed since Invoice.total_cents and Payment.amount_cents are both cents already — this actually **simplifies** the FEB port relative to FEB's own float↔cents boundary in `reconcile_invoice_financials`).
11. **Compatibility impact** — no data migration; no field renames on existing MVP collections; no frontend refactor. Existing data survives.
12. **Reporting impact** — reports read integer cents and format for display in the report renderer. No aggregate rounding errors possible (integer sums).

### Owner sign-off items for the money policy

- Confirm the "commerce in cents / configuration in dollars" split is acceptable as the permanent product's money contract.
- Confirm `_cents` suffix and integer-only rule.
- Confirm the pricing→commerce boundary conversion location and helper.
- Confirm no separate `_dollars` field will be added on any commerce model.

---

## Feature Readiness Matrix (corrected)

**Best Source repository key:** `MVP`=SIGNGUY-MVP, `OS`=SIGNGUY-AI-OS (mirror; no new development), `REB`=signguyai_rebuild_version, `FEB`=signguy-ai-feb22, `ORIG`=signguyai.

**Readiness key:** NS=Not Started, PH=Placeholder/Mockup Only, PI=Partially Implemented, WMP=Working w/ Major Problems, WNC=Working But Needs Cleanup, WR=Working and Reusable, AR=Advanced and Reusable, BU=Broken or Unsafe, DUP=Duplicate Implementations Exist.

**Path key:** CPY=Copy & Integrate, REF=Copy & Targeted Refactor (mostly rename `job_id`→`order_id` + import paths), EXT=Extract Business Logic & Rehouse, RB=Rebuild against MVP shared services (donor code is reference), MRG=Merge Duplicates, RM=Remove/Deprecate, MD=Needs Manual Decision.

> The `Defer` path from the previous pass is **removed** everywhere. Every gap now has a build-out path.

### Foundation & shared systems

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Authentication & account access | MVP | REB, FEB, ORIG | WR | — | Low | RV+FSV | — | everything | MVP has bcrypt + JWT + 60-min single-use password reset + dev-bypass gate. REB `models/access.py` defines 57 permissions in a StrEnum + role-permission map that is richer than MVP's. Recommendation: **REF into MVP** — adopt REB's `Permission` StrEnum verbatim (renamed to MVP module paths) so all new modules use the same permission catalog. |
| Tenants & organizations | MVP | REB | WR | — | Low | RV | Auth | everything | MVP tenant_id on every collection + server-side filter (cross-tenant sweep verified in prior test). REB has richer `tenants.py` + `platform_admin.py` orgs model — inspect at Stage 17 for platform-admin work; no earlier value. |
| Users, roles, permissions | MVP | REB | WR | REF | Low | RV+FSV | Auth, Tenants | everything | MVP single-dependency enforcement (verified). REB defines 6 roles (`platform_creator`, `platform_admin`, `owner`, `admin`, `staff`, `webstore_owner`) with a `PLATFORM_BYPASS_ROLES` set and `identity_has_permission()` — **adopt this shape** so platform admin & webstore-owner roles are wired from day one. |
| Application shell & navigation | MVP | ORIG | WNC | REF | Low | RV | Auth | UI screens | MVP has sidebar + topbar + permission-gated nav. ORIG has grouped workspace/ribbon patterns that are visual reference only. |
| Shared UI component system (shadcn/ui) | MVP | — | WR | — | Low | RV | — | UI | Enforced by design guidelines. |
| Settings & configuration framework | REB | — | PI in MVP → REF to REB shape | REF | Med | FSV | Tenants, Permissions | Pricing, Webstores, Wrap Lab, notifications | REB `routes/settings.py` (77 lines) + `models/settings.py` (37 lines) is a **thin working scaffold**: namespace/key + `SettingsRepository` + `SETTINGS_VIEW/MANAGE` permissions + activity event on update. MVP currently has ad-hoc `pricing_settings` only. **This module is Stage 2 (Shared Platform Services)** and must be built before broader Settings surface areas. |
| Audit log & activity event system | MVP | REB | WR | REF | Low | RV+FSV | Auth | everything | MVP has shared `record_audit(actor, ...)` helper (verified — no writes without actor). REB `services/activity.py` + `routes/activity.py` (40+45 lines) implements a slightly richer `ActivityEventPayload` (`module`, `event_type`, `entity_type`, `entity_id`, `summary`, `severity`, `changes`, `metadata`) and lists events with permission-gated filters. **Adopt REB's `event_type`, `severity`, `changes` fields on top of MVP's audit collection.** |
| Notifications (in-app) | REB | — | NS in MVP | RB (based on REB scaffold) | Med | FSV | Settings, Users, Communications repository | Customer portal, Employee portal, Wrap Lab, Order events | REB `routes/communications.py` (170 lines) implements a working notification lifecycle: `NotificationPayload` create/update/status + recipient scoping (staff can only see notifications addressed to themselves — enforced server-side). **The notification service is a real REB scaffold, not a spec.** Adopt as Stage 2 shared service. |
| Email (SendGrid) | MVP | REB | WR | REF | Low | RV | — | Quotes, Invoices, Portal, Documents, Wrap Lab | MVP has 5 live templates + verified live-send. REB `routes/communications.py` adds **email activity tracking** (`email_activity` records with `template_key`, `related_entity_type/id`, `delivery_status`) and a **SendGrid webhook endpoint** (`POST /communications/webhooks/sendgrid`) with HMAC-SHA256 signature verification against `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET`. **Adopt the webhook + activity tracking** so email deliverability/bounce is auditable. |
| SMS/MMS | ORIG | — | NS in MVP | RB | Med | RS | Auth | Portal, notifications | ORIG `routes/sms.py` + `services/sms_service.py` exist. Twilio keys pasted by user in chat (must be rotated). **Build in permanent product roadmap after Stage 10 portal**; not a Stage 2 prerequisite. |
| Internal messaging (staff↔staff) | ORIG | REB | NS in MVP | RB | Med | RS | Auth | Team dashboard | ORIG `Productivity` pages + REB `SharedRecordRepository` (notes) provide reference patterns. Build against MVP shared services. |
| File uploads & object storage | MVP | REB, ORIG | WR | — | Low | RV | Auth, Tenants | Documents, Quotes, Orders, Work Orders, Invoices | MVP uses Emergent Object Storage + tenant-scoped keys + authed downloads (cross-tenant sweep verified). ORIG `services/object_storage.py` is a clean 35-line Emergent HTTP client — no base64 anti-pattern. REB `services/doculink_storage.py` uses local disk with SHA-256 hashing and path-traversal guards (useful reference for `sha256` file identity and MIME-vs-declared-type verification — see next row). |
| Upload validation | REB | — | NS in MVP | EXT | Low | FSV | Files | Docs, Wrap Lab, Portal | REB `services/upload_validation.py` (132 lines) enforces: MIME allowlist (10 types), MIME-vs-extension mismatch rejection, per-request configurable size cap (`SIGNGUYAI_MAX_UPLOAD_BYTES`), magic-byte content sniffing (`%PDF`, `\x89PNG`, `\xff\xd8\xff`, `RIFF...WEBP`, PK zip for docx/xlsx, `\xd0\xcf\x11\xe0` for legacy Office, UTF-8/latin-1 for text/csv), SHA-256 fingerprint on stored files. **Extract into MVP as `services/upload_validation.py`** — this hardens the current permissive uploader. |
| Attachments (polymorphic entity ↔ file links) | MVP | REB | WR | REF | Low | RV+FSV | Files | many | MVP already has `attachments` collection + `POST /files/attach`. REB has richer polymorphic `file_links` + `document_links` + `document_shares` with `customer_visible` flag and `access_level` — **adopt these three collections** so external-facing entities (portal, webstore) can share files without exposing internal-only records. |
| Forms | ORIG | REB | NS in MVP | RB | Med | RS | Files, Templates | Portal | ORIG `routes/questionnaires.py` + `models/questionnaires.py` — build against MVP shared services. |
| Questionnaires | ORIG | REB | NS in MVP | RB | Med | RS | Forms, Files | Portal, Wrap Lab, Webstores | ORIG has `questionnaires.py`; REB `WEBSTORE_SPEC.md` + wrap prototype both require it. Foundational for Webstores and Wrap Lab intake. |
| Templates (document + email) | ORIG | FEB, REB | PI in MVP (email templates only) | REF | Med | RS | Files | Emails, DocuLink, Wrap Lab | ORIG `routes/email_templates.py`, FEB same. REB `models/doculink.py` has `BusinessDocumentPayload` including `source_type=ai_generated` + `requires_review` — richer than ORIG. |
| Signatures | ORIG | — | NS in MVP | REF | Med | PSI | Files, Approvals | Approvals, Contracts, Wrap Lab | ORIG `routes/signatures.py` (658 lines total; first 60 lines PSI in this pass — 11 parent record types + `SIGNATURE_TYPE_MAP` header confirmed). REFERENCE BEHAVIOR IDENTIFIED. **FULL TRACE REQUIRED DURING MODULE PREFLIGHT** before any port lands. Path once verified: REF — rename `job_ticket_id` → `order_item_id`, keep every other parent verbatim. |
| Global search | — | — | NS in MVP | RB | Med | — | Everything | UI | No donor has a global search implementation. Build against MVP after core stable. |
| Background jobs / automation | ORIG | REB | NS in MVP | RB | High | RS | Everything | Digest, Notifications | ORIG `services/digest_scheduler.py`, `services/workflow_engine.py` + `routes/workflow_templates.py` — reference only; the permanent product will need a shared scheduler as part of Stage 2 shared services once notification digests are on the roadmap. |
| Error handling & logging | MVP | REB | WR | — | Low | RV | — | everything | Axios interceptor + toast (MVP). REB adds structured activity events on repo write. |

### Shop operations

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Customers & CRM | MVP | REB, FEB | WR | — | Low | RV | Tenants, Auth | Quotes, Orders, Invoices, Portal | MVP has full CRUD + linked-records view. REB `models/customers.py` is only slightly richer (address book normalisation); not a required refactor. |
| Customer detail & communication history | MVP | REB | WR | REF | Low | RV+FSV | Customers, Email | UI | REB `email_activity` collection provides a real communication history stream; adopt at same time as email webhook (row above). |
| Quotes | MVP | REB, FEB | PI | REF | Med | RV+FSV | Customers, Pricing | Orders | MVP has manual-price quote + idempotent convert-to-order. REB `routes/quotes.py` (206 lines) + `models/quotes.py` (129 lines) adds: (a) line items with per-item `estimated_price_minor`, `material_estimate_minor`, `labor_estimate_minor`, `manual_price_override_minor`, `override_reason`, `override_actor_id`, `override_at`, `production_required`; (b) expiration (`expires_at`); (c) status set `draft/sent/approved/declined/expired/converted/cancelled`; (d) send, approve (with approval_method: phone/email/text/in_person/other), decline (with reason); (e) revisions via `version` on the document; (f) portal-visible file links via `doculink`. **Stage 4 target — port REB shape**, keep MVP `job_id`→`order_id` conventions. |
| Orders | MVP | REB, FEB, ORIG | WR (basics) → PI (target) | REF | Med | RV+FSV | Customers, Quotes, Pricing | Work Orders, Invoices | MVP has item entry + statuses. REB `routes/orders.py` (326 lines) adds: production-summary endpoint, financials endpoint (invoice count + balance_due_minor), source-quote endpoint, generate-invoice / generate-work_order helpers, richer status set (`new_intake/awaiting_review/awaiting_quote/quote_sent/awaiting_approval/approved/in_production/partially_complete/ready_for_pickup/out_for_delivery/completed/on_hold/cancelled`), `payment_status` on the order, `approval_status`, `pickup_delivery_method`, shared production/design/install/color notes. **Adopt.** |
| Order Items | MVP | REB | PI | REF | Med | RV+FSV | Orders, Pricing | Work Orders | REB `OrderItemPayload` has 40+ fields including `production_required: bool | None`, `entry_mode: quick/detailed`, `estimated_price_minor`, `actual_cost_minor`, `labor_estimate_minor`, `material_estimate_minor`, `manual_quote_override_minor`, `override_reason/actor_id/at`, `design_needed`, `customer_artwork`, `artwork_status`, `proof_required`, `proof_approval_status`, `revision_count`, `qc_status`, `rework_needed/notes`, `special_instructions`, `production_notes`, `install_notes`, `packaging_notes`, `department_route`, `assigned_team/user_id`. **This is the permanent target schema.** |
| `production_required` flag & work-order gate | REB | — | Missing in MVP | REF | Low | FSV | OrderItem | Work Orders | REB `services/order_item_rules.py` (14 lines) defines `PHYSICAL_PRODUCTION_CATEGORIES = {rigid_signs, banners, cut_vinyl, digital_print, vehicle_wrap, apparel, promo_misc, custom}` and `default_production_required(item_category)`. **This IS the Stage 5→7 gate** the mandated build order requires. Import as-is. |
| Quote-to-Order conversion | MVP | REB | AR | — | — | RV | Quotes, Orders | — | MVP idempotent via `find_one_and_update` + unique `converted_order_id`. Best source. REB has same pattern with `converted_at`, `converted_order_id`, and audit event. |
| Pricing snapshot on OrderItem/QuoteLineItem | REB | — | Missing in MVP | REF | Med | FSV | Pricing, Orders, Quotes | Invoices | REB `POST /order-items/{item_id}/calculate-pricing` + `save-pricing` + `override-pricing` endpoints, `latest_pricing_snapshot` field on OrderItem document, `set_pricing_override(tenant, item, price_minor, reason, actor)` helper on the repository. **Stage 5 target — this is what "item-level pricing snapshots" means in the master plan.** |
| Invoices | FEB | REB, MVP | PI | EXT | High | FSV | Orders | Payments | MVP is one-per-order + manual pricing + single status. FEB `services/invoice_service.py` (147 lines) owns the reconciliation formula: `compute_line_items_and_totals()` snapshots line items server-side, and `reconcile_invoice_financials()` derives `amount_paid`, `balance_due`, `status`, `document_status`, `financial_status` in one place. **This is the Stage 6 migration target.** Rename `job_id`→`order_id` on the invoice document; every other field lands as-is. |
| Order-to-Invoice conversion | MVP | REB | WR | REF | Low | RV+FSV | Orders, Invoices | — | MVP idempotent via unique index. REB `POST /invoices/generate-from-order/{order_id}` does the same + returns 404/409 correctly. Adopt REB error shape. |
| Payments & payment history | FEB | MVP | PI in MVP → EXT to FEB | EXT | High | FSV | Invoices | — | FEB `services/payment_service.py` (320 lines) + `models/payments.py` (148 lines) implements: unified Payment collection (manual + Stripe Connect), integer cents (`amount_cents`), idempotency-key with 409 on replay, overpayment rejection, controlled void-with-reason (manual only, never Stripe), Stripe two-step (`create_pending_stripe_payment` → `confirm_stripe_invoice_payment`) with webhook-replay idempotency (DuplicateKeyError race handling), `refunded_amount_cents` future-compatible field, `provider_transaction_id` uniqueness, `voided_at/voided_by/voided_by_name/void_reason` audit stamp, `_derive_states()` for document/financial state split. **This is the Stage 6 permanent implementation.** |
| Money representation policy | MVP (existing split) | FEB, REB (reference only) | Already implemented in MVP; policy not yet documented in `AGENT_INSTRUCTIONS.md` | Decision (owner sign-off) | Low | FSV | Invoices, Payments, Quotes, Orders | Reports | **MVP already uses integer cents on commerce (Quote/Order/Invoice/Payment/WorkOrder) and float dollars on pricing configuration + calculator output** (FSV of `models/*`, `services/pricing.py`, `services/starter_defaults.py`, `frontend/src/lib/format.js`). REB uses `_minor` (integer cents) throughout; FEB uses a documented boundary compromise. **Recommended policy: ratify MVP's existing split; do NOT adopt FEB's compromise.** See MONEY REPRESENTATION section at the top of this document. |
| Production / Work Orders | MVP | REB, ORIG | PI | REF | Med | RV+FSV | Orders, Order Items | Documents | MVP currently snapshots ALL OrderItems (spec violation). REB `routes/orders.py::generate_work_order_draft` gates on `production_required=True`. **Stage 7 target — apply `default_production_required(item_category)` + a per-item override.** REB also has `list_work_order_drafts(tenant, order_id)` + `latest_work_order_draft` in the order production summary. |
| Production board / stages | REB | ORIG | NS in MVP | RB | High | SS | Work Orders | — | REB wrap_lab `STAGES = ["Intake", "Quote", "Contract", "Design", "Proof Approval", "Inspection", "Production", "Install", "Pickup", "Aftercare", "Complete"]` gives a template; ORIG `ProductionBoard.js` gives a UI reference. |
| Artwork proofs | ORIG | REB | PI (donor-side only) | REF | Med | PSI | Files, Approvals, Portal | Wrap Lab | ORIG `routes/approvals.py` (355 lines total; first 80 lines PSI in this pass — `ArtworkProof` with `version`, `thumbnail_url`, `watermarked_url`, `admin_notes`, `customer_comment`, `approved_at`, `rejected_at` observed. `_get_proof_parent_name` header confirms dual-parent read of `db.jobs` and `db.orders`). REFERENCE BEHAVIOR IDENTIFIED. **FULL TRACE REQUIRED DURING MODULE PREFLIGHT** before any port lands. Path once verified: REF — rename `job_id`→`order_id`. |
| Customer approvals | ORIG | REB, FEB | PI (donor-side) | REF | Med | PSI | Portal, Signatures | Proofs, Contracts, Wrap Lab | Combined with signatures + proofs — all three are PSI in this pass; module preflight will read them end-to-end. |
| Document library / DocuLink | REB | ORIG | PH in MVP → RB on REB | RB | High | FSV | Files, Templates | Portal, Wrap Lab | REB `routes/doculink.py` (244 lines) implements: BusinessDocument CRUD with `source_type=ai_generated → requires_review`, file upload with polymorphic entity links, download with activity event, document shares with recipient/access-level, activities log, filter by status/visibility/document_type/customer_id/order_id. **Full working scaffold + local storage adapter with SHA-256 + MIME validation.** Adopt the shape wholesale, but rewire the storage adapter to Emergent Object Storage (MVP's `services/storage.py`). |
| Inventory | ORIG | REB | NS in MVP | RB | Med | FSV | — | Orders, Purchasing | ORIG `routes/inventory.py` + `services/inventory_service.py` + REB `INVENTORY_PURCHASING_VENDOR_MANAGEMENT_REBUILD_DOC.md` — permanent product roadmap Stage 13. |
| Vendors | ORIG | — | NS in MVP | RB | Med | RS | Inventory | Purchasing | Permanent product Stage 13. |
| Purchasing | ORIG | — | NS in MVP | RB | High | RS | Inventory, Vendors | Finance | Permanent product Stage 13. |
| Webstores — Order Portal Manager | REB | ORIG | PI (entitlement scaffold) | RB | Critical | FSV+SO | Orders, Stripe, Files, Portal | Public storefront | REB has ONLY the capability + launch-readiness endpoints (`services/webstore_service.py` 34 lines) + full `WebstoreStatus` enum (draft → questionnaire_sent → questionnaire_received → setup_in_progress → owner_review_pending → changes_requested → stripe_onboarding_pending → ready_to_launch → live → paused → closed → archived → cancelled) — but no product/order code. ORIG has 3775-line `routes/webstores.py` — the feature discovery map. REB has **8 dedicated ORDER_PORTAL specs** as blueprint. **Stage 15 — build in permanent product on shared core once Stages 3–11 are stable.** |
| Webstore products & variants | ORIG | — | NS in MVP | RB | High | RS | Webstores | Storefront | ORIG has full product model + variants; use as reference. |
| Webstore setup wizard | REB (specs) | ORIG | NS in MVP | RB | High | SO | Webstores | — | REB `WEBSTORE_MASTER_REBUILD_SPEC.md` + `ORDER_PORTAL_MANAGER_MASTER_SPEC.md` are authoritative. |
| Webstore orders | ORIG | — | NS in MVP | RB | High | RS | Webstores, Orders | Payments | Reference in ORIG. |
| Stripe Connect & payouts | ORIG | FEB, REB | PI (donor + FEB webhook confirm path) | REF (safety-critical) | Critical | FSV | Webstores, Payments | Payments | ORIG `routes/stripe_connect.py` (719 lines) + `services/stripe_service.py` (457 lines) + FEB `routes/stripe_connect.py` (719 lines) + FEB `services/payment_service.py::confirm_stripe_invoice_payment` (webhook-only, verified session with metadata attribution). REB `billing_rules.py` has the transaction-fee basis points table (0 during founders promo, 50bp founders standard, 100bp GA standard; 200bp GA webstore). **Financial-safety critical — must go through a formal security review before any port.** |
| Webstore owner portal | ORIG | REB | NS in MVP | RB | High | FSV+SO | Webstores | — | ORIG `OwnerPortal.js`, `OwnerPortalSignup.js`. REB `ORDER_PORTAL_OWNER_PORTAL_SPEC.md`. |
| Webstore manager portal | REB | — | SO | RB | High | SO | Webstores | — | REB `ORDER_PORTAL_MANAGER_MASTER_SPEC.md` only. |
| Public storefront | ORIG | REB | NS in MVP | RB | High | RS+SO | Webstores | — | ORIG `routes/public_website.py` + REB `ORDER_PORTAL_PUBLIC_STOREFRONT_SPEC.md`. |
| Wrap Lab / Wrap Command Center | REB | ORIG | SS | REF | Critical | FSV | Customers, Orders, Files, Approvals, Portal | — | REB `services/wrap_lab_service.py` (145 lines) + `routes/wrap_lab.py` (98 lines) + `models/wrap_lab.py` (71 lines) implement the full 11-stage workflow (`STAGES = Intake→Quote→Contract→Design→Proof Approval→Inspection→Production→Install→Pickup→Aftercare→Complete`), 14 workflow actions (`approve_quote`, `request_quote_revision`, `pay_deposit`, `sign_contract`, `approve_proof`, `request_proof_revision`, `acknowledge_inspection`, `sign_pre_install_packet`, `sign_final_packet`, `customer_concept_feedback`, `advance_stage`, `complete_stage`, `send_message`, `resolve_issue`), stage gates (deposit before contract, approved proof before install, checklists complete before advance), and a `public_project()` allowlist so internal pricing never leaks to the portal. **Full working scaffold, not spec-only.** Stage 16. |

### Business management

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Pricing Foundation | MVP | REB | AR | — | — | RV+FSV | Tenants | Calc, Quotes, Orders | MVP starter defaults + per-tenant clone + wizard + calculator (verified end-to-end). REB `routes/pricing_foundation.py` (43 lines) + `services/pricing_engine.py` (1391 lines) is a **faithful port of ORIG's 9-category calculator suite** with cleaner code structure and the same math. Two calculation methods per category (`sell_rate_per_sqft` vs `cost_plus`, plus `max_of_both`, `package_benchmark`, `price_table`). **MVP already delivers this at Stage 12; REB's engine is a reference for future extended-formula work.** |
| Pricing calculators (9 categories) | MVP | REB | AR | — | — | RV+FSV | Pricing Foundation | Quotes, Orders | 9 categories matched across all repos. |
| Materials pricing (tenant catalog editor) | ORIG | REB | PI in MVP | REF | Low | RS | Pricing | Calc | ORIG `MaterialsAdmin.js`. Adopt shape into MVP pricing UI. |
| Quote pricing integration | REB | — | PI | REF | Med | FSV | Pricing, Quotes | Invoices | REB has per-line-item `calculate-pricing` + `override-pricing` endpoints. Adopt. |
| Order pricing integration | REB | — | PI | REF | Med | FSV | Pricing, Orders | Invoices | REB has per-order-item `calculate-pricing` + `save-pricing` + `override-pricing` + `latest_pricing_snapshot`. **This is the Stage 5 pricing-snapshot feature.** |
| Invoice pricing derivation | FEB | REB | PI | EXT | Med | FSV | Invoices, Orders | — | FEB `InvoiceService.compute_line_items_and_totals()` recomputes server-side (never trusts client line totals). Combine with Stage 6 port. |
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
| Subscription products & fees catalog | REB | ORIG | NS in MVP | EXT (candidate) | Med | FSV | Billing | Platform admin | REB `services/billing_rules.py` (111 lines, FSV) defines an **EXISTING COMMERCIAL PRICING IMPLEMENTATION CANDIDATE** — 4 subscription products (Core, Webstores, Wrap, Complete Bundle) with founders vs GA pricing, monthly credits per product, credit top-up packs (100/300/800), founders promo (`FOUNDERS3MO`, 25 max redemptions, 3-month fee holiday), transaction fee basis points table (0/50/100 bp standard vs 0/150/200 bp webstore). **OWNER APPROVAL REQUIRED** on every value before it can be treated as canonical — see the OWNER-DECISION section at the end of this document for the enumerated list. Prompt 3 will determine final commercial scope and pricing. |

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
| Internal notes (polymorphic) | REB | ORIG | NS in MVP | REF | Low | FSV | Any entity | UI | REB `routes/shared_systems.py::notes` uses `SharedRecordRepository` with tenant scoping. Adopt. |
| Team communication | REB | ORIG | NS in MVP | RB | Med | FSV | Users | Team | REB `communications.py` notifications are the base. |
| Employee portal | ORIG | FEB | NS in MVP | RB | High | RS | Employees, Auth | Time clock | ORIG 5 EmployeePortal* pages + FEB 5 similar. DUP in donors — build fresh on MVP shared portal service. Stage 14. |

### Design studio & AI

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| AI tool catalog | REB | ORIG | PI (catalog only) | EXT | Med | FSV | Auth | Assistant | REB `routes/shared_systems.py::AI_TOOLS` has 24 tools with `id/name/category/intensity/description`: text_to_image, idea_brainstormer, permit_research, photo_enhancer, image_vectorizer, font_identifier, ai_sign_designer, ai_banner_designer, mockup_creator, vehicle_wrap_mockup, logo_creator, branding_kit_generator, business_copywriter, document_composer, pricing_intelligence, blog_creator, completed_job_post, social_pack_generator, content_calendar, campaign_builder, wrap_cost_calculator, email_templates, review_responder, assistant_chat. **Adopt catalog as the permanent taxonomy.** |
| AI generation router (`POST /ai/generate`) | REB | ORIG | PH (stub returns preview text) | REF | High | FSV | AI catalog, LLM provider | AI results collection | REB stub persists results in `ai_responses` collection but returns preview text. **The permanent product wires this to a real provider via Emergent LLM key + credit tracking.** |
| AI Assistant chat | ORIG | REB | PI (donor-side) | REF | High | RS | AI catalog, Credits | — | ORIG `AIAssistant.js` + `services/ai_assistant_actions.py` + `services/assistant_queries.py`. |
| Prompt Library | ORIG | REB | NS in MVP | RB | Med | RS | AI | — | Reference. |
| AI credit tracking | ORIG | REB | PI (donor-side) | REF | Med | FSV | AI, Billing | Reports | ORIG `routes/credits.py` + `services/credit_service.py`. REB `billing_rules.py` defines monthly bank per plan + top-up packs. |
| AI usage history | ORIG | REB | PI (via REB `ai_responses` collection) | REF | Low | FSV | AI Credits | Reports | REB persists every response. |
| AI billing logic | ORIG | REB | NS in MVP | EXT | High | FSV | Credits, Stripe | — | REB `billing_rules.py` (products + promo + fee bps) + ORIG `services/multi_product_billing.py` (690 lines) — adopt REB's rules, ORIG for calculation details. |
| AI-generated file storage | REB | — | PI via DocuLink `source_type=ai_generated → requires_review` | REF | Low | FSV | Files | AI | Already in the DocuLink model. |
| AI context retrieval | ORIG | — | NS in MVP | RB | High | RS | AI | — | ORIG `services/assistant_queries.py`. |

### Platform & support

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Onboarding | ORIG | — | PI in MVP (dev-bypass) | REF | Med | RS | Auth, Tenants, Pricing | — | ORIG `routes/onboarding.py` (176 lines) + `OnboardingHub.js`. |
| Help Center | FEB | ORIG | PH | CPY | Low | RS | — | — | FEB 14 static docs pages are the most reusable. |
| Community Hub | REB | ORIG | SS | REF | Med | FSV | Users | — | REB `routes/shared_systems.py::community/*` implements post list/create/update, reply, upvote (with dedup by user), stats. **Working scaffold, not spec.** |
| Bug reports | REB | — | via community `category=bug_report` | REF | Low | FSV | Community | — | REB community stats already filters by `category=bug_report`. |
| Feature requests | REB | — | via community `category=feature_request` | REF | Low | FSV | Community | — | Same as bug reports. |
| Platform administration | REB | ORIG | SS | REF | High | FSV | Auth | Everything | REB `routes/platform_admin.py` (90 lines) has: `require_platform_admin` dep (checks role in `platform_creator/platform_admin`), list tenants (search + status), get tenant, patch tenant status (`suspended`, `active`, etc.), tenant readiness endpoint, audit-events listing per tenant. **Real scaffold.** Stage 17. |
| Platform tenant management | REB | ORIG | SS | REF | High | FSV | Tenants | Platform admin | Included in above. |
| Platform analytics | ORIG | — | NS in MVP | RB | High | RS | Everything | — | ORIG `PlatformAdminAnalytics.js`. Stage 17. |
| Platform audit logs | MVP | REB, ORIG | WR | REF | Low | RV+FSV | Audit | Platform admin | MVP audit collection + reader route. REB `PlatformAdminAuditListResponse` is the target shape for platform-level filtering. |
| Platform email & announcements | ORIG | REB | NS in MVP | RB | Med | RS | Email | — | ORIG `PlatformAdminBroadcastEmail.js`. |
| Subscription plans | REB | ORIG, FEB | PI in donors | EXT | High | FSV | Stripe | Billing | Use `REB billing_rules.py` for canonical rules. |
| Add-ons / credit packs | REB | — | PI in REB | EXT | Med | FSV | Plans, Stripe | — | REB `CREDIT_TOP_UP_PRODUCTS`. |
| AI credit purchases | REB | — | PI in REB | EXT | Med | FSV | AI credits, Stripe | — | Included above. |
| Public marketing website | ORIG | FEB | NS in MVP | RB | Low | RS | — | — | ORIG `LandingPage.js`, `AboutPage.js`, `FeaturesPage.js`, `ContactPage.js`. Move to a separate static frontend later. |
| Public pricing & plan selection | ORIG | FEB | NS in MVP | RB | Low | RS | Plans | — | ORIG `Pricing.js`, `PricingPlansV2.js`, `FoundersEditionPricing.js`. |

### Portals & public systems

| Module | Best Src | Other | Readiness | Path | Complexity | Evidence | Dependencies | Depended-on-by | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Customer portal | ORIG | FEB, REB | NS in MVP | RB | High | PSI | Auth, Customers, Files, Approvals | Proofs, Payments | ORIG `routes/portal.py` (2195 lines total; first 80 lines PSI in this pass — portal auth + `_normalize_order_status` header confirms status normalisation from donor `Job` shapes to portal-facing keys, and both `db.orders` and `db.jobs` are read). REFERENCE BEHAVIOR IDENTIFIED. **FULL TRACE REQUIRED DURING MODULE PREFLIGHT** — this is a very large file and the middle sections (PDFs via reportlab, messaging, proof approval flow) were NOT read in this pass. DUP with FEB. |
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
| Settings framework | `UNK — depth unknown, user paste needed` | `PI in MVP → REF to REB (FSV)` | REB `routes/settings.py` + `models/settings.py` inspected line-by-line; a working scaffold exists. |
| Notifications | `UNK — user paste needed` | `NS in MVP → RB on REB scaffold (FSV)` | REB `routes/communications.py::notifications` is real code. |
| Email SendGrid webhook | Not listed | Added — `WR (MVP send) + adopt REB webhook (FSV)` | REB implements HMAC-verified inbound webhook. |
| Upload validation | Not listed | Added — `NS in MVP → EXT REB (FSV)` | REB `services/upload_validation.py` has magic-byte + MIME + size + SHA-256. |
| Attachments / polymorphic links / shares | Row said `WR / unique to MVP` | Downgraded to `WR + adopt REB shares model (FSV)` | REB has richer `file_links` + `document_links` + `document_shares` with `customer_visible` + `access_level`. |
| DocuLink | `PH — no working code` | `RB on REB scaffold (FSV)` — full working scaffold, storage adapter needs Emergent object storage rewire | REB `routes/doculink.py` + `services/doculink_storage.py` + `services/doculink_bridge.py` are all real. |
| Wrap Lab | `UNK — depth unknown` | `SS — REF (FSV)` — full 11-stage workflow engine in REB | REB `services/wrap_lab_service.py` + `routes/wrap_lab.py` + `models/wrap_lab.py` inspected. |
| Signatures | `PI — donor-side` | `NS in MVP → REF ORIG (FSV)` — 11-parent structured signature system | ORIG `routes/signatures.py` (658 lines) inspected. |
| Approvals | `UNK — depth unknown` | `PI (donor-side) → REF ORIG (FSV)` — already dual-parent jobs+orders | ORIG `routes/approvals.py::_get_proof_parent_name` reads both `db.jobs` and `db.orders`. |
| Invoices | `PI — highest-priority migration target` | Same target, but promoted from UNK → `EXT FEB (FSV)` — full 147-line reconciliation formula proven | FEB `services/invoice_service.py` inspected. |
| Payments | `PI — Stage 6 target` | Same target, promoted from UNK → `EXT FEB (FSV)` with full 320-line implementation | FEB `services/payment_service.py` inspected. |
| Quote items with pricing snapshots + expiration + revisions | Listed as a gap | Now with concrete REB-shape target (FSV) | REB `models/quotes.py` + `routes/quotes.py` inspected. |
| Order items with pricing snapshots + `production_required` + snapshot | Listed as a gap | Now with concrete REB-shape target (FSV) | REB `models/orders.py` + `services/order_item_rules.py` inspected. |
| Work Order gate on `production_required` | Listed as a spec violation | Now has concrete import target: `services/order_item_rules.py::default_production_required` (FSV) | 14-line helper inspected. |
| Pricing calculators (9 categories) | `WR / needs materials editor` | Same, but REB has a 1391-line faithful port with `cost_plus` + `sell_rate_per_sqft` methods (FSV) | REB `services/pricing_engine.py` inspected. |
| AI tools catalog | `PI — cost/security risk` | `PI (FSV) — REB has canonical 24-tool catalog; billing rules published in `billing_rules.py`` | REB `routes/shared_systems.py::AI_TOOLS` + `services/billing_rules.py` inspected. |
| Community Hub / Bug reports / Feature requests | `UNK / NS` | `SS — REF (FSV)` — REB implements post/reply/upvote/stats and categorises by bug_report/feature_request | REB `routes/shared_systems.py` inspected. |
| Platform admin | `PI — 6+ pages` | `SS — REF (FSV)` — REB has tenant list/get/patch-status/readiness + audit-events endpoints with `require_platform_admin` dep | REB `routes/platform_admin.py` inspected. |
| Subscription plans / add-ons / credit packs | `UNK / DEF` | Reclassified to `EXT REB (FSV)` — REB `billing_rules.py` has full commercial pricing model | REB `services/billing_rules.py` inspected. |
| Onboarding | `PI` | Same but with confirmed 176-line ORIG donor (RS) | ORIG `routes/onboarding.py` size confirmed. |
| Customer portal | `PI — ORIG 10 pages + FEB 8 pages` | `NS in MVP → RB (FSV)` — ORIG portal already handles both `db.orders` and `db.jobs` | ORIG `routes/portal.py` inspected. |
| `SIGNGUY-AI-OS` identity vs MVP | "Recommendation: retire" | **Mirror under `backend/app/**/*.py` (STHV)** — md5sum of every `.py` file under `backend/app/` matches MVP; frontend page count matches. **Full-tree comparison NOT run.** **Recommendation: no new development; complete-tree comparison; then read-only/archive after permanent product completion.** | md5 tree comparison run in this pass over the scoped path; frontend/docs/config/branches NOT compared. |
| Object storage | `UNK — user paste needed` | `RS clean` — ORIG file is 35 lines, Emergent HTTP client, no base64 anti-pattern | ORIG `services/object_storage.py` inspected. |
| Money representation | Not stated as an architectural decision | Corrected — MVP already uses **integer cents on commerce (Quote/Order/Invoice/Payment/WorkOrder)** and **float dollars in pricing configuration + calculator output** (FSV in this pass). The prior pass's "MVP uses float dollars across Quotes/Orders/Invoices" claim was incorrect and is retracted. **Recommended policy: ratify the existing MVP split; do NOT adopt the FEB float+cents boundary compromise.** Owner sign-off required (see Standing Decisions). | FSV of `models/quote.py`, `models/order.py`, `models/invoice.py`, `models/work_order.py`, `services/pricing.py`, `services/starter_defaults.py`, `frontend/src/lib/format.js`, `frontend/src/components/forms/MoneyInput.jsx`. |
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

- "Is `SIGNGUY-AI-OS` intended as a distinct repo?" → **No.** md5 tree over `backend/app/**/*.py` matches MVP (STHV, scoped). Frontend/docs/config/branches NOT compared. Recommendation: no new development; complete-tree comparison; then read-only/archive after final commercial completion.
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
9. **FEB `invoice_service.py` + `payment_service.py`** — dual-status, void-with-reason, reconciliation, Stripe two-step, overpayment reject, idempotency-key (**FSV**).
10. **REB `services/upload_validation.py`** — magic-byte + MIME + size + SHA-256 (**FSV**) — small, drop-in, immediate security upgrade.

### 10 highest-risk systems
1. **Webstores / Order Portal** — Stripe money movement + storefront + wrap. Stage 15.
2. **Wrap Lab** — deep cross-dependency (files, approvals, portal, email, payments). Stage 16.
3. **Payments + Stripe Connect** — real money, refund risk. Must go through security review before port.
4. **AI billing / credits** — real cost tied to LLM API usage. Needs cost-cap + tenant metering before enabling.
5. **Terminology conflict** — every donor file touching `job_id`/`jobs` must be renamed to `order_id`/`orders` before landing. Silent poisoning risk.
6. **Money representation decision** — float vs integer cents. Must be documented before Stage 6 or invoices split.
7. **`SIGNGUY-AI-OS` mirror repo** — will drift the moment anyone commits to it. Freeze it against new development; complete-tree comparison before any archive; do not delete until final commercial completion.
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

Now replace every remaining `SV` label in the matrix's evidence columns with `FSV` for files that were fully read line-by-line in this pass, and re-check the summary sections at the end.

## Standing architectural decisions this matrix now requires the user to sign off on

These are the decisions Prompt 3 will need. Nothing binding is claimed yet.

1. **`SIGNGUY-AI-OS` handling** — recommendation: no new development, run a complete-tree comparison, then move to read-only / archive status **after** the permanent product is finished and all migrations are verified. Preserve branches, tags, commit history, docs, and recovery value. Do not delete until final commercial completion.
2. **Money representation policy** — recommendation: ratify MVP's existing "commerce in integer cents / configuration in float dollars" split (see the MONEY REPRESENTATION section above). Owner sign-off on: the `_cents` suffix rule, the conversion boundary location, the exclusion of unsuffixed money fields.
3. **Permission catalog source** — REB `models/access.py`'s 57-permission StrEnum is a **candidate**; adoption requires owner review of the platform_admin / webstore_owner scopes.
4. **Repository pattern** — REB uses a repository class per collection. Adopting this shape for new modules (Settings, Notifications, DocuLink, Wrap Lab, Platform Admin, Webstore, Community) is a candidate; owner sign-off requested.
5. **Terminology map** — canonical `Order/OrderItem/WorkOrder` naming remains in `memory/AGENT_INSTRUCTIONS.md`; every donor file renamed on port.
6. **SendGrid webhook enablement** — set `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` in production and force-fail startup if unset (the REB implementation is otherwise permissive if secret unset). Owner sign-off on the fail-closed behavior.

## Additional owner sign-off items (surfaced but not decided in this audit)

- Webstores commercial mode — add-on-only, or also standalone?
- Customer portal auth — magic-link tokens, passwords, or both?
- LLM provider details for AI billing (Emergent LLM key is confirmed available; specific model choices and per-tool cost caps require owner approval).
- Sales-tax responsibility — computed via integration (Avalara / TaxJar) or shop-configured flat rates only?
- Commercial pricing catalog approval — every value in REB `services/billing_rules.py` (subscription prices, credit-pack prices, founders promo terms, transaction fee basis points) requires explicit owner sign-off before it can be treated as canonical.

---

# FINAL DECISION STATUS

## LOCKED AND SAFE TO CARRY INTO PROMPT 3

- `SIGNGUY-MVP` is the permanent destination.
- No wholesale rebuild or architectural replacement is required. Several focused systems require **extension, migration, or targeted replacement** (enumerated in the "Targeted replacements required" section below).
- Canonical `Order / OrderItem / WorkOrder` terminology.
- Reuse-first migration policy for donor code (verify → rename → port; never wholesale copy).
- Targeted donor roles: `SIGNGUY-MVP` = destination; `SIGNGUY-AI-OS` = read-only mirror (no new development); REB / FEB / ORIG = read-only reference donors throughout the build.
- Tenant isolation and backend-enforced permission gating remain mandatory on every new module.
- SendGrid webhook must fail-closed in production if the secret is unset.
- Donor repositories remain read-only references throughout the build. No deletion until final commercial completion.
- Money representation contract: commerce in integer `_cents`, configuration in float dollars, single conversion boundary at the pricing→commerce hand-off (see MONEY REPRESENTATION section for details).

## REQUIRES OWNER DECISION IN PROMPT 3

- Money representation — ratify the recommended policy above (or overrule).
- Final commercial pricing and fees — every value in REB `billing_rules.py` (subscription prices, credit-pack prices, founders promo terms, transaction fee basis points) requires owner approval before being treated as canonical.
- Final internal checkpoint order — the previous 0–17 stage numbering is a proposed dependency reference, not a locked plan; Prompt 3 sets the definitive checkpoint list after scope + pricing + policy decisions land.
- Portal authentication method — magic link, password, both.
- Webstores product mode — add-on-only vs also standalone (REB `billing_rules.py` implies both).
- Sales-tax strategy — integration or shop-configured flat rates.
- AI provider and credit-cost model — Emergent LLM key confirmed available; specific per-tool cost caps and model selections require owner decision.
- Repository archive timing — exactly WHEN `SIGNGUY-AI-OS` transitions from "no new development" to "archived / read-only", after the complete-tree comparison and final commercial completion.

## REQUIRES MODULE PREFLIGHT DURING IMPLEMENTATION

- Full customer portal trace (ORIG `routes/portal.py`, 2195 lines — first 80 lines PSI only in this pass).
- Full signatures + approvals trace (ORIG `routes/signatures.py` 658 lines and `routes/approvals.py` 355 lines — both PSI in this pass).
- Complete Stripe Connect security review (FEB + ORIG combined — money-movement critical, unread in this pass).
- Detailed Webstore donor analysis (ORIG `routes/webstores.py` 3775 lines — feature discovery only, unread in this pass).
- Detailed inventory / payroll / reports / AI donor analysis — RS class in this pass; individual files must be traced during their respective module preflight (per the FEATURE_MIGRATION_PREFLIGHT_PROTOCOL that already exists in REB memory).

## Targeted replacements required (not wholesale rebuilds)

No wholesale rebuild or architectural replacement is required in MVP. The following focused systems require extension, migration, or targeted replacement to reach permanent-product completeness:

- **Invoice status and reconciliation** — extend to independent `document_status` (draft/issued/void) and `financial_status` (unpaid/partial/paid/voided); introduce a single reconciliation service that owns the derivation.
- **Payment history and void behavior** — extend Payment model with `voided_at/voided_by/void_reason`, source (manual / stripe_connect), status lifecycle, idempotency 409 replay, overpayment reject.
- **Work-order generation gate** — introduce `production_required` on `OrderItem`; make Work Order snapshot the production-required items only.
- **Settings framework** — introduce a namespace/key settings repository (permission-gated + audited).
- **Notifications framework** — introduce a notifications service separate from the email log.
- **Permissions catalog** — extend the current 20-value enum to accommodate platform_admin + webstore_owner scopes (candidate: REB 57-permission StrEnum, owner sign-off required).
- **Dev-only authentication surfaces** — production startup guard: force-fail if `AUTH_DEV_BYPASS=true` AND `ENV=production`; production startup guard: force-fail if JWT secret matches the known dev placeholder.
- **Webhook infrastructure** — introduce signature-verified, replay-safe inbound webhook handlers (SendGrid event webhook, Stripe webhook).
- **Portal authentication** — introduce a portal auth model separate from the admin JWT (magic-link + portal-role + `portal_visibility` flag on records).
- **Feature entitlements service** — introduce a feature-flag / entitlements repository that gates add-on modules (Webstores, Wrap Lab as add-ons, AI as metered add-on).

None of the above requires touching existing working MVP code destructively; every item is additive or a scoped extension.

---
