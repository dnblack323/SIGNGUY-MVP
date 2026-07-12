# EC7 — Inventory, Purchasing, Finance, and Reporting — PREFLIGHT

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` §§ EC7 (base) + Appendix A (owner-locked A.1 EC6.3, A.2 EC3.1 remain visible + pending).
**Prereqs:** EC0–EC6 COMPLETE. EC3.1 and EC6.3 must NOT be absorbed.
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent). No donor repo modified.

---

## 1. MVP files inspected (read-only for preflight)

**Existing backend surface EC7 will extend without duplicating.**
- `backend/app/models/` — 33 model files. Notable pre-EC7 items EC7 must integrate with, not duplicate:
  - `pricing_material.py` — the existing pricing-material record used by EC3 calculators.
  - `settings.py` — tenant settings + tax jurisdiction config (EC2).
  - `attachment.py`, `file.py`, `file_link.py`, `document.py` (EC1/EC2/EC6) — reuse for receipts + PO attachments + report exports.
  - `order.py`, `order_item.py`, `invoice.py`, `payment.py`, `quote.py` — sources for revenue, tax collected, receivables, sales.
  - `email.py`, `notification.py` (EC2) — reuse for low-stock + PO alerts.
  - `activity.py`, `audit_log.py` (EC1/EC2) — reuse for all EC7 events.
- `backend/app/services/` — `payment_service.py`, `invoice_reconciliation.py`, `audit.py`, `notifications.py`, `sequence.py`, `settings.py`, `storage.py`. Reuse for revenue + receivables aggregation, PO number sequences, receipt storage.
- `backend/app/routers/` — no `inventory.py`, `purchase_orders.py`, `expenses.py`, `finance.py`, `reports.py` yet. New routers land under standard `/api/*` prefix.
- `backend/app/core/permissions.py` — enumerate the `INVENTORY_*`, `VENDOR_*`, `PURCHASE_ORDER_*`, `EXPENSE_*`, `FINANCE_*`, `REPORT_*` permissions. Verify EC1 catalog and extend only where a permission is missing.
- `backend/app/core/db.py::ensure_indexes` — extension point for new indexes.
- `backend/app/deps.py` + `deps_portal.py` — staff `require_permission` reused; portal not extended (EC7 is staff-only).

**Existing frontend**
- `frontend/src/pages/DashboardPage.jsx` — reuse layout patterns.
- `frontend/src/pages/DocumentsPage.jsx` — receipt/attachment upload pattern to reuse.
- `frontend/src/lib/navigation.js` — extend with new EC7 nav areas (Inventory, Purchasing, Finance, Reports).
- `frontend/src/components/ui/*` — shadcn components reused.

**Existing MVP inventory / material / vendor / expense**
Grep across `backend/app/models` and `backend/app/routers` shows **no pre-existing** `inventory_items`, `inventory_movements`, `vendors`, `purchase_orders`, `expenses`, `saved_reports` collections. EC7 is a greenfield build on top of EC0–EC6 shared services. `pricing_material.py` is the only pricing-material record and remains **KEEP MVP**.

## 2. Legacy job-ticket / bad-terminology behavior found
**None.** Terminology guard passes. EC7 never uses "job".

## 3. Donor evidence
Behavioral references only — no wholesale copy.
- **REB** — inventory + purchasing + expense + finance summary + report filters + tax reporting behavior. Rejected: donor auth, donor tenant helpers, permissive routes, float money, hardcoded categories, giant routers.
- **ORIG** — material + inventory workflow + purchasing + receiving + shop expense + financial dashboard + report categories + tax reporting behavior. Rejected: duplicate finance dashboards, client-derived totals, weak tenant filtering, hardcoded queries, legacy nav.

## 4. Classification
| Element | Class |
|---|---|
| `pricing_material` (EC3) | KEEP MVP |
| Settings framework (EC2) | KEEP MVP + extend |
| Files/Attachments (EC1/EC2/EC6) | KEEP MVP + reuse |
| Audit + Activity + Notifications | KEEP MVP + reuse |
| Materials collection (physical) | REBUILD AGAINST MVP SERVICES — separate `materials` from `pricing_material` |
| Inventory items / locations / movements / reservations | REBUILD AGAINST MVP SERVICES |
| Vendors, Vendor-Materials | REBUILD |
| Purchase Orders + Lines + Receiving | REBUILD |
| Expenses + Categories | REBUILD |
| Finance metrics + Reports | REBUILD using aggregations over Orders/Invoices/Payments/Expenses |
| Custom Report Builder | REBUILD (curated semantic catalog) |
| Payroll / Bank feeds / QuickBooks / TaxJar | REJECT (out of scope) |

## 5. Schema additions (additive; no destructive changes)

**Collections (all tenant-scoped):**
- `materials` — Material definition (identity, purchase config, cost, inventory behavior, pricing integration ref).
- `inventory_locations` — locations per tenant (main shop, production, install vehicle, warehouse, overflow, ...).
- `inventory_items` — unique `(tenant_id, material_id, location_id)`; `quantity_on_hand`, `quantity_reserved`, derived `quantity_available`, `reorder_point`, `reorder_quantity`.
- `inventory_movements` — immutable ledger; enumerated `movement_type`; `before_quantity` + `after_quantity`; idempotency key where applicable.
- `inventory_reservations` — link reservation → Order/OrderItem/WorkOrder; reduces `quantity_available`.
- `vendors` — tenant-scoped vendor records (no User overlap).
- `vendor_materials` — Material↔Vendor with vendor-specific cost, MOQ, lead time, cost history.
- `purchase_orders` — Identity + lifecycle + amounts (cents) + snapshot of Vendor.
- `purchase_order_lines` — line items; backend-derived totals; `quantity_received` + `quantity_remaining`.
- `receiving_records` — one row per receiving action; idempotency-key-unique.
- `expenses` — operational expenses (integer cents; receipt via `file_id`).
- `saved_reports` — tenant-scoped saved report definitions (semantic domain + curated fields + filters).

**Indexes** (registered in `ensure_indexes`):
- Materials: unique `(tenant_id, sku)` sparse; `(tenant_id, category, active)`; `(tenant_id, name)`.
- Inventory Items: **unique `(tenant_id, material_id, location_id)`**; `(tenant_id, quantity_available)`; `(tenant_id, reorder_point)`.
- Inventory Movements: `(tenant_id, material_id, created_at)`; `(tenant_id, location_id, created_at)`; `(tenant_id, source_entity_type, source_entity_id)`; **unique `idempotency_key` sparse**.
- Vendors: `(tenant_id, name)`; `(tenant_id, active)`.
- Vendor-Materials: unique `(tenant_id, vendor_id, material_id)`.
- Purchase Orders: **unique `(tenant_id, number)`**; `(tenant_id, vendor_id, created_at)`; `(tenant_id, status, expected_at)`.
- PO Lines: `(tenant_id, purchase_order_id, sort_order)`; `(tenant_id, material_id)`.
- Receiving Records: **unique `idempotency_key`**; `(tenant_id, purchase_order_id, created_at)`.
- Expenses: `(tenant_id, date)`; `(tenant_id, category, date)`; `(tenant_id, vendor_id, date)`.
- Saved Reports: `(tenant_id, created_by, updated_at)`; `(tenant_id, shared, name)`.

## 6. Files to add / modify

**Backend — add**
- `models/material.py`, `inventory.py` (item + location + movement + reservation), `vendor.py`, `purchase_order.py`, `expense.py`, `report_definition.py`.
- `services/inventory_service.py`, `inventory_movements.py`, `unit_conversion.py`, `purchasing_service.py`, `receiving_service.py`, `finance_service.py`, `tax_reporting.py`, `report_service.py`, `report_export.py`.
- `routers/materials.py`, `inventory.py`, `vendors.py`, `purchase_orders.py`, `expenses.py`, `finance.py`, `reports.py`.
- `tests/test_ec7_inventory.py`, `test_ec7_purchasing.py`, `test_ec7_expenses.py`, `test_ec7_finance.py`, `test_ec7_reports.py`, `test_ec7_cross_tenant.py`.

**Backend — modify**
- `server.py` (register routers).
- `core/db.py::ensure_indexes` (extend).
- `core/permissions.py` (add any missing EC7 perms; verify existing).

**Frontend — add**
- Pages: `InventoryOverviewPage.jsx`, `MaterialsPage.jsx`, `MaterialDetailPage.jsx`, `InventoryAdjustmentsPage.jsx`, `LocationsPage.jsx`, `VendorsPage.jsx`, `VendorDetailPage.jsx`, `PurchaseOrdersPage.jsx`, `PurchaseOrderDetailPage.jsx`, `PurchaseOrderEditor.jsx`, `ReceivingDialog.jsx`, `FinanceDashboardPage.jsx`, `ExpensesPage.jsx`, `TaxSummaryPage.jsx`, `ReportsHomePage.jsx`, `ReportViewerPage.jsx`, `SavedReportsPage.jsx`, `CustomReportBuilderPage.jsx`.
- `lib/navigation.js` — new nav areas.

## 7. Rules (LOCKED)
- **One Inventory system.** No parallel stock balances. Future modules consume/reserve via `inventory_service`.
- **Immutable movements.** Every stock change writes an `inventory_movements` row; balance mutations happen only via the service and are race-safe (find-and-modify with expected quantity check).
- **Integer cents everywhere on money.** Decimal permitted for fractional quantities where units support it (square feet, linear feet).
- **Backend-derived totals.** PO + line totals + finance metrics NEVER trust client input.
- **Idempotent receiving.** `Idempotency-Key` header (or system-generated key) is unique on `receiving_records`; replay is a no-op.
- **Material cost history preserved.** Never rewrite historical Quote/Order/Invoice pricing snapshots when cost changes.
- **Finance metrics labeled.** Every metric declares its date basis (cash vs invoice) and its collection source in the API response and in the UI.
- **Report Builder is curated.** No raw Mongo queries; no arbitrary field paths; server-side field catalog is authoritative. Row limits + timeouts enforced.
- **Terminology.** No "Job Ticket" / "Production Ticket".
- **EC3.1 and EC6.3 boundaries.** EC7 preserves and exposes Material data required by pricing, but category formulas remain owned by EC3.1. EC7 does NOT implement in-person signature capture on Order intake — that's EC6.3.

## 8. Test plan
Backend suites:
- Inventory CRUD + tenant isolation + cost-permission masking + movement immutability + physical count + transfer + negative-stock rejection + unit conversion + low-stock state + reservation + release + concurrent adjustment + idempotency.
- Vendors CRUD + tenant isolation + Material relationship + cost history.
- Purchase Orders: draft + line totals + submit + partial receive + full receive + receive-idempotency + double-receive prevention + cost-history update + cancel-with-reason + invalid-transition + tenant isolation + permission.
- Expenses CRUD + attachment + integer cents + tenant + permission.
- Finance metrics: revenue basis (invoice vs cash) + Payments received + refunds + outstanding + expenses + tax collected + incomplete-cost warning + date-range + tenant.
- Reports: curated + filters + grouping + aggregation + permissions + row limit + timeout handling + CSV export + saved reports + forbidden fields rejected + cross-tenant rejected.

Frontend (via `testing_agent_v3_fork`):
- Inventory Overview / Materials / Adjustments / Transfers / Low-stock / Vendors / POs / Receiving / Expenses / Finance Dashboard / Tax Summary / Reports Home / Report Viewer / Custom Report Builder foundation / loading + empty + error + permission states.

Regression: all EC1–EC6 tests + tenant sweep + permission matrix.

## 9. Compatibility & migration
No existing MVP data touched. `pricing_material` remains authoritative for EC3.1 formula work; EC7 `materials` is a new physical-material record. A future pass may attach `pricing_material_id` to `materials` where semantically equivalent, but no destructive migration is required in EC7.

## 10. Rollback
Additive. Drop new collections + remove new routers + remove new frontend routes.

## 11. Delivery integrity note (raised to owner)
EC7 as scoped is the largest single checkpoint in the plan — roughly 12 backend routers, 9 services, 6 model families, ~15 frontend pages, ~150 pytest scenarios, plus documentation and evidence. Prior fork sessions produced ~1000 lines of production code per session before context exhaustion. **Owner acknowledgment requested before code starts** — see §12.

## 12. Owner acknowledgment gate

### 12A. Supplier Catalog, Price Comparison & Integrated Purchasing (LOCKED — added to EC7)

Per master plan Appendix A.3. Authoritative for EC7. Not optional.

**Delivered inside EC7:**
- Normalized supplier-product model (supplier, product_id, manufacturer, brand, family, SKU, UPC, description, category, variant attributes, pkg qty, purchase unit, warehouse, available qty, account price in **cents**, list price, effective_at, lead time, MOQ, freight class, active state, source + sync timestamps). Raw supplier identifiers preserved + mapped to internal Materials.
- Reusable **supplier connector interface** with per-connector capability advertisement. Interface operations: `search_catalog`, `get_product`, `get_variants`, `get_account_price`, `get_inventory`, `get_shipping_quote`, `create_supplier_order`, `retrieve_supplier_order`, `retrieve_tracking`, `cancel_order`.
- Three connection tiers:
  - **Direct API / EDI** (full catalog + account pricing + inventory + submission + acknowledgement + tracking).
  - **Catalog feed** (CSV / XML / JSON / SFTP, scheduled sync; PO creation only, no electronic submission).
  - **Manual supplier** (URL + prepared PO + authorized vendor-site handoff).
- Catalog import + sync foundation; category-aware variant support (apparel size/color; vinyl width/length/finish/adhesive; substrates thickness/sheet dims; hardware SKU). Never force apparel + non-apparel into one variant structure.
- Vendor-to-Material mapping (extends the EC7 `vendor_materials` collection).
- **Shortage calculation** from Order Items vs current Inventory (batched, tenant-scoped, cost-aware).
- **Purchasing recommendation service** with priorities: lowest delivered cost / fastest arrival / preferred supplier / fewest warehouse splits / all-items-available / best combined score. Comparison uses **delivered cost** (item + breaks + account pricing + package qty + shipping + freight + handling + MOQ surcharge + warehouse split + expected arrival + tax where relevant). Estimates labeled when live freight is unavailable.
- **Supply Center** staff UI (supplier comparison + purchasing cart + draft-PO flow).
- Secure connection settings via EC2 integration-secret storage (no credential ever reaches the frontend).
- **Idempotent supplier-order submission** — Idempotency-Key required on every `create_supplier_order` call; replay never places a duplicate order.
- Full audit of every supplier order (actor + supplier + products + amount + timestamp + request_id + response status).
- At least **one realistic end-to-end connector OR deterministic supplier test adapter** demonstrating catalog search → variant → price → availability → shortage recommendation → PO creation → idempotent submission → receiving into inventory. Static mock cards alone do NOT satisfy EC7.

**LOCKED rules:**
- Supplier account credentials use EC2 integration-secret storage. Never exposed to frontend.
- Cross-tenant supplier pricing leakage forbidden.
- Explicit user confirmation on every electronic submission.
- No card storage; use supplier account terms, hosted checkout, or tokenized providers.
- No supplier scraping; no automated checkout unless the vendor explicitly authorizes it.
- Never silently substitute apparel brand/style/color/size.
- Never compare incompatible products as equivalent (vinyl cast vs calendared, adhesive types, etc.).

**Required EC7 preflight artifact — Supplier Integration Inventory.** Owner must supply the vendor list. For each supplier the preflight will document: categories carried, API availability, EDI availability, catalog-feed availability, account-pricing availability, inventory availability, order-submission availability, auth method, approval / partnership requirements, rate limits, ToS restrictions, and fallback integration method. Every capability marked **verified / unavailable / pending vendor confirmation** — no guessing.

**Files to add during EC7 (in addition to §6 above):**
- `backend/app/models/supplier.py` — `Supplier`, `SupplierProduct`, `SupplierWarehouse`, `SupplierOrderLog`.
- `backend/app/services/supplier_connectors/` — `base.py` (ABC), `manual.py`, `feed_csv.py`, plus one seeded test adapter (`test_adapter.py`).
- `backend/app/services/supplier_catalog.py` — catalog import + sync.
- `backend/app/services/shortage_service.py` — Order-Items vs Inventory shortage calculation.
- `backend/app/services/purchasing_recommendation.py` — comparison + priority-driven recommendation.
- `backend/app/routers/supply_center.py` — staff routes for catalog search, recommend, cart, submit.
- Frontend: `SupplyCenterPage.jsx`, `SupplierComparisonView.jsx`, `PurchasingCartPage.jsx`, `SupplierConnectionsPage.jsx`.

**Phase mapping:** this requirement lands inside **phase 7b (Vendors + Purchasing)** and extends into **phase 7d (evidence)**. Phases stay four total.

---


Per the "unless a genuine conflict is found" clause, I raise **one** integrity concern before writing any code:

**Delivery reality.** EC5 and EC6 were both rejected by you the first time because the agent over-marked completion when frontend or E2E was incomplete. EC7's scope is larger than EC5 + EC6 combined. To keep EC7 to the same integrity bar you enforced, I plan to deliver it in **four internal implementation phases inside this single execution checkpoint** (no sub-checkpointing; EC7 stays one checkpoint):

- **7a — Inventory foundation.** Models + services (unit_conversion, inventory_service, inventory_movements, reservations, low-stock). Materials + Locations + Movements + Adjustments + Count + Transfer + Reservation. Backend + pytest + Inventory Overview + Materials List/Detail + Adjustments UI. Concurrency + idempotency tests.
- **7b — Purchasing + Vendors + Receiving.** Vendors, Vendor-Materials, PurchaseOrders, PO Lines, ReceivingRecords, Purchase Order Editor + Receiving Dialog + Vendors pages. Cost-history update. Receive-idempotency + cancel-with-reason + double-receive prevention. Backend + pytest + UI.
- **7c — Expenses + Finance dashboard + Tax summary.** Expenses CRUD (with receipt attachment), Finance Dashboard metrics with labeled basis, Tax Summary. Backend + pytest + UI.
- **7d — Reports.** Curated reports (Sales, Orders, Invoices, Payments, Inventory, Purchasing, Expenses, Finance). Custom Report Builder foundation with curated field catalog + saved reports + CSV export + row limit + timeout. Backend + pytest + UI + `testing_agent_v3_fork` full frontend regression + evidence + registers + docs.

Between 7a→7d I run pytest after each phase; the final `testing_agent_v3_fork` runs at 7d close. EC7 is marked COMPLETE **only** at 7d close.

If context runs low mid-phase, I will honestly declare **EC7 — IN PROGRESS (phase N delivered)** rather than falsely mark it COMPLETE. That is exactly the same discipline the master plan and your prior directives enforce.

**No design or scope change is being requested.** Every EC7 requirement in your prompt stays authoritative. The phasing is purely internal execution ordering; the exit conditions and evidence package remain as specified. If you approve, I begin phase 7a immediately without further pausing. If you want a different ordering (e.g., start with Finance Dashboard first, or split at different boundaries), name it and I follow.
