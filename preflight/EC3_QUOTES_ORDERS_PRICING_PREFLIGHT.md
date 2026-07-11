# EC3 — Quotes, Orders, Order Items, and Pricing Snapshots — PREFLIGHT

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` (owner-approved).
**Prerequisite checkpoints:** EC0, EC1, EC2 — COMPLETE. Do not reopen.
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent product). Donor repos are read-only.

---

## 1. MVP files inspected

Quotes / Orders / Work Orders / Pricing:
- `backend/app/models/quote.py`
- `backend/app/models/order.py` (contains `Order` + `OrderItem`)
- `backend/app/models/work_order.py` (contains `WorkOrder` + `WorkOrderItemSnapshot`)
- `backend/app/models/invoice.py` (compat — EC4 will refactor)
- `backend/app/routers/quotes.py`
- `backend/app/routers/orders.py`
- `backend/app/routers/work_orders.py`
- `backend/app/services/pricing.py` (canonical calculator + tenant settings)
- `backend/app/services/starter_defaults.py` (9 categories, materials, shop defaults)
- `backend/app/services/audit.py` + `services/activity.py`
- `backend/app/core/db.py` (indexes)
- `backend/app/core/permissions.py`
- `backend/app/deps.py`
- `backend/server.py`
- `frontend/src/pages/QuotesPage.jsx`, `QuoteDetailPage.jsx`
- `frontend/src/pages/OrdersPage.jsx`, `OrderDetailPage.jsx`

## 2. Existing MVP behaviour (RV)

- **Quote (RV):** `Quote{id, tenant_id, number, customer_id, job_name, notes, total_cents, status(draft|sent|approved|declined|converted), converted_order_id, converted_at, created_by}`. Router owns `POST /quotes`, `GET /quotes`, `GET /quotes/{id}`, `PATCH /quotes/{id}`, `POST /quotes/{id}/status`, `POST /quotes/{id}/convert-to-order` (idempotent via `find_one_and_update` on `converted_order_id == None`).
- **Order (RV):** `Order{id, tenant_id, number, customer_id, quote_id, job_name, notes, status(draft|confirmed|in_production|completed|cancelled), created_by}`. `OrderItem{id, tenant_id, order_id, description, quantity, unit_price_cents, position}` with derived `line_total_cents`. Backend derives totals per request (never trusts client).
- **Work Order (RV):** currently snapshots ALL order items (violates `production_required` rule). Uses `items_snapshot: list[dict]`.
- **Pricing (RV):** `services/pricing.calculate_pricing(...)` returns float dollars + Decimal-internal math; per-tenant settings auto-cloned from starter pack.
- **Existing collections:** `quotes`, `orders`, `order_items`, `work_orders`, `pricing_settings`, plus EC2 collections.
- **Existing indexes:** `(tenant_id, number)` unique on quotes/orders/work_orders/invoices; `id` unique everywhere; polymorphic `attachments`.

## 3. Donor logic approved for reuse (behavioural evidence only — no wholesale copy)

- REB `services/order_item_rules.py` — `default_production_required(category)` and `PHYSICAL_PRODUCTION_CATEGORIES`. **BEHAVIOUR EXTRACTED** to `backend/app/services/order_item_rules.py`.
- REB `models/quotes.py` — line-item shape + expiration + revision + approval fields. **BEHAVIOUR EXTRACTED** into MVP `models/quote.py` extensions.
- REB `models/orders.py` — rich OrderItem field groups. **BEHAVIOUR EXTRACTED** into MVP `models/order.py` extensions (subset — see §7).
- REB `services/pricing_engine.py` — pricing snapshot shape. **BEHAVIOUR EXTRACTED** into `services/pricing_snapshot.py`.

## 4. Donor logic REJECTED

- REB `PreviewEnvelope`, header-based tenant impersonation, unresolved `core_runtime` imports.
- REB `_minor` naming — MVP uses `_cents`.
- REB whole-file router copies (routers stay thin; MVP shape preserved).
- Any Job/JobItem/JobTicket terminology from any donor.
- REB approvals sub-router — will be delivered by a later checkpoint (EC4 shared Approvals system). EC3 records approval-state fields on the Quote itself.

## 5. Classification of every donor element

| Donor element | Classification |
|---|---|
| REB `order_item_rules.py::default_production_required` | EXTRACT BUSINESS LOGIC |
| REB `models/quotes.py` line item + revision + expiration | COPY AND TARGETED REFACTOR (into MVP `models/quote.py`) |
| REB `models/orders.py` rich OrderItem | COPY AND TARGETED REFACTOR (subset) |
| REB `services/pricing_engine.py` snapshot shape | EXTRACT BUSINESS LOGIC |
| REB `routes/quotes.py` router | REBUILD AGAINST MVP SERVICES (extend MVP router; do NOT clone) |
| REB `routes/orders.py` router | REBUILD AGAINST MVP SERVICES |
| REB `_minor` money suffix | REJECT (MVP uses `_cents`) |
| REB PreviewEnvelope + preview auth | REJECT |
| ORIG monolithic App.js | REJECT |

## 6. Schema differences

| Field | MVP today | EC3 target | Migration |
|---|---|---|---|
| `Quote.subtotal_cents / discount_cents / tax_cents / total_cents` | only `total_cents` | full 4-field set, derived from line items | derived; existing `total_cents` retained |
| `Quote.expires_at` | absent | new `str | None` (ISO) | additive |
| `Quote.revision_number` | absent | int, default 1 | additive; default 1 on read |
| `Quote.sent_at / approved_at / declined_at / viewed_at` | absent | new (ISO) | additive |
| `Quote.notes_internal / notes_customer` | `notes` only | keep `notes`; add both new fields | additive |
| `QuoteLineItem` | absent | new collection `quote_line_items` | additive |
| `QuoteRevision` | absent | new collection `quote_revisions` | additive |
| `Quote.status` | `draft/sent/approved/declined/converted` | add `viewed`, `expired`, `void` | additive; existing values still valid |
| `Order.subtotal_cents / discount_cents / tax_cents / total_cents` | absent | derived; stored for reporting | additive; recomputed on write |
| `Order.source_quote_id / source_quote_revision` | `quote_id` only | keep `quote_id` (compat); add `source_quote_revision` | additive |
| `OrderItem.category / product_type` | absent | new; nullable | additive |
| `OrderItem.width_inches / height_inches / unit_of_measure` | absent | new; nullable | additive |
| `OrderItem.production_required` | absent | new bool; category-defaulted | additive |
| `OrderItem.pricing_snapshot` | absent | dict | additive |
| `OrderItem.manual_override_reason / manual_override_actor_id / manual_override_at` | absent | new | additive |
| `OrderItem.line_subtotal_cents / discount_cents / tax_cents / line_total_cents` | derived only | stored derived; snapshot-safe | additive |
| `WorkOrder.items_snapshot` gate | snapshots ALL items | filter by `production_required=True` | change router logic; no data migration |

## 7. Files to add / modify / not to modify

**Add:**
- `backend/app/models/quote_line_item.py`
- `backend/app/models/quote_revision.py`
- `backend/app/services/order_item_rules.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/commerce_totals.py`
- `backend/app/services/quote_conversion.py`
- `backend/app/services/quote_revisions.py`
- `backend/app/routers/quote_revisions.py` (mounted under `/quotes/{id}/revisions`)
- `backend/tests/test_quote_line_items.py`
- `backend/tests/test_quote_revisions.py`
- `backend/tests/test_quote_expiration.py`
- `backend/tests/test_quote_conversion_ec3.py`
- `backend/tests/test_order_items_ec3.py`
- `backend/tests/test_pricing_snapshot.py`
- `backend/tests/test_production_required.py`
- `backend/tests/test_commerce_totals.py`
- Frontend: extend `QuoteDetailPage.jsx`, `OrderDetailPage.jsx` (line items, revisions, override, production toggle).
- Docs: `docs/modules/quotes.md`, `docs/modules/orders.md`, `docs/modules/order_items.md`, `docs/architecture/quote_revisions.md`, `docs/architecture/quote_to_order_conversion.md`, `docs/architecture/pricing_snapshots.md`, `docs/architecture/commerce_totals.md`, `docs/architecture/order_item_rules.md`.

**Modify:**
- `backend/app/models/quote.py` — extend with new fields (backwards compatible).
- `backend/app/models/order.py` — extend `Order` + `OrderItem` (backwards compatible; new fields optional).
- `backend/app/routers/quotes.py` — extend routes: line items, revisions, expiration, approval-state fields; keep existing routes.
- `backend/app/routers/orders.py` — extend routes: rich item add/update, recalculate totals, override.
- `backend/app/routers/work_orders.py` — filter snapshot by `production_required=True`.
- `backend/server.py` — mount new router.
- `backend/app/core/db.py` — add EC3 indexes.
- `backend/app/core/permissions.py` — already covers EC3 permissions (added in EC1).

**Do NOT modify:**
- `backend/app/core/security.py`, `services/audit.py`, `services/sequence.py`, `services/storage.py`, `services/email.py`.
- Existing EC1/EC2 code paths beyond additive extensions.
- Pricing configuration (`services/starter_defaults.py`, `services/pricing.py`).

## 8. Compatibility plan for existing MVP data

- All new fields are optional / defaulted at read time via Pydantic `default=`.
- Existing quotes with only `total_cents` still work: `subtotal_cents = total_cents`, others zero.
- Existing orders without stored totals: totals derived at read time.
- Existing order items without `production_required`: derived from `category` (nullable) via `default_production_required(category)`, else `True` when category is unknown (safe default — items still show up on work orders).
- No destructive migration. No renames. No collection drops.

## 9. Test plan (per EC3 §29)

- **Quote:** create, add/update/remove line items, backend-derived totals, sent-quote edit creates revision, expired quote conversion rejected, approve/decline transitions, invalid transition rejected, tenant isolation.
- **Quote-to-Order:** successful conversion copies line items → order items, preserves pricing snapshots + source revision, idempotent, cross-tenant rejection, declined quote rejection, audit events written.
- **Order:** create direct, add/update rich order item, recompute totals, reject client totals, invalid financial status rejected, tenant isolation.
- **Pricing:** integer cents rounding, snapshot preserved after settings change, manual override requires reason, negative values rejected.
- **production_required:** category default, manual override with reason, work-order snapshot filters correctly.
- **File-link:** covered by EC2 tests.
- **Regression:** all EC1 (34) + EC2 (58) tests remain green.

## 10. Rollback plan

Additive-only design → rollback = revert new files + revert additive lines in existing files. No data migration to reverse.

## 11. Preflight sign-off

- Preflight complete. Proceeding directly to implementation per EC3 §4.
