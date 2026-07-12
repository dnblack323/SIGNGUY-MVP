# EC7 — Inventory, Purchasing, Expenses, Finance, Taxes, Reports (module bundle)

**Status:** EC7 Phase 7a + 7b + 7c + 7d delivered. **EC7 remains IN PROGRESS** until the full-stack `testing_agent_v3_fork` regression passes across every EC7 screen.

**Master-plan authority:** `SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` §12 + Appendix A.3.
**Commercial authority (LOCKED, not implemented in EC7):** `/app/docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md`.

This is one module document per master-plan module-standard convention (`docs/architecture/module_standard.md`). Every screen lives inside its parent module — we do NOT create a documentation file per route.

---

## 1. Inventory

**Purpose:** track shop-owned Materials, per-location stock (`inventory_items`), an immutable movement ledger (`inventory_movements`), reservations, adjustments, physical counts, low-stock threshold monitoring, and historical `material_cost_history`.

**Screens (frontend):** `InventoryPage` — tabbed shell with Items / Materials / Movements / Locations.

**Backend routers:** `/api/materials`, `/api/inventory/*`.

**Rules:**
- Reserved stock is NOT physically removed. Available = on_hand − reserved.
- Every stock change writes an immutable `inventory_movements` row (idempotency-key safe).
- Material cost history is append-only. Renaming a Material never rewrites past cost rows.

**Limitations:** valuation of finished goods is NOT computed here (EC3.1 owns full pricing verification).

---

## 2. Purchasing & Vendors

**Purpose:** vendor records, `VendorMaterial` links to internal Materials, PO lifecycle (Draft → Submitted → Acknowledged → Partially Received / Received / Cancelled), receiving that writes inventory movements + cost history.

**Screens:** `PurchaseOrdersPage` (list + submit dialog + cancel dialog with reason).

**Backend routers:** `/api/vendors/*`, `/api/purchase-orders/*`.

**Rules:**
- PO submission requires explicit `confirm=true` AND an `Idempotency-Key` header. Replays short-circuit.
- Cancel requires a reason (stored on audit trail).
- Receiving is idempotency-key keyed; over-quantity is rejected; each line spawns an immutable inventory movement.
- Vendor records NEVER store secrets. Credentials belong to EC2 integration-secret storage.

**Limitations:** manual + feed-csv connector tiers do NOT submit electronically — the Supply Center prints a handoff instead.

---

## 3. Supplier Catalog & Connectors

**Purpose:** normalized supplier catalog, connector interface, deterministic full-capability test adapter (~80 synthetic SKUs across 4 vendors and 8 warehouses).

**Screens:** `SupplyCenterPage` — catalog search, synthetic-data banner in dev, seed action gated on `purchasing:write` + `AUTH_DEV_BYPASS`.

**Backend:** `app/services/supplier_connectors/*` — `SupplierConnectorBase` with `ConnectorCapability` enum (SEARCH, PRODUCT, VARIANTS, ACCOUNT_PRICE, INVENTORY, SHIPPING_QUOTE, SUBMIT_ORDER, RETRIEVE_ORDER, TRACKING, CANCEL). Registry maps `connector_key` → concrete adapter.

**Rules:**
- Recommender never crosses `compatible_group` (cast wrap ≠ calendared, laminate gloss ≠ matte, etc.).
- Freight quotes are always labeled `rate_type=estimated` until a live vendor API is wired.
- Synthetic seed disabled in production (`ENV=production` → 403).

---

## 4. Purchase Orders & Receiving

Same module as (2). PO lifecycle + receiving is fully documented under Purchasing above. The frontend PO detail page (`/purchase-orders/:id`) is the primary receiving surface: it lists lines with ordered/received/remaining, hosts the Receive dialog (per-line quantities, location picker, packing-slip notes, per-click `Idempotency-Key`, `Fill remaining` shortcut) that handles both partial and complete receiving, and shows the receiving-history + supplier-submission-history tables.

---

## 5. Expenses

**Purpose:** operational shop spending (money the shop paid out). Distinct from customer Payment records; not a full A/P system.

**Screens:** `ExpensesPage` — list w/ state tabs (active / archived / voided), New expense dialog, Void dialog (reason required), Archive/Restore actions.

**Backend routers:** `/api/expense-categories/*`, `/api/expenses/*`.

**Rules:**
- 16 stable-key categories (materials, equipment, vehicle, fuel, rent, utilities, software, advertising, subcontractor, office, insurance, taxes, fees, shipping, maintenance, miscellaneous) seeded per tenant on first read.
- Category rename NEVER rewrites past Expense rows — every Expense stores a `category_label_snapshot`.
- Archive hides from picker; voided is a state, not a deletion.
- Receipts reuse EC2 `FileRecord` via `expense_attachments` link table. No parallel receipt storage.

---

## 6. Finance Dashboard

**Purpose:** canonical labeled-basis metrics. Every card / chart carries its `basis` label so Invoice-basis (accrual) and Payments-basis (cash) are never silently mixed.

**Screens:** `FinanceDashboardPage` — 8 basis-badged metric cards + 3 monthly trend charts + Top customers + Payment-method breakdown.

**Backend router:** `/api/finance/*` — 15 endpoints. Every response preserves the `basis` label.

**Rules:**
- No unlabeled "Revenue" or "Profit" cards.
- `Refunds` returned as its own metric — never silently netted against Payments.
- `estimated_gross_profit` warns on partial cost coverage (`coverage_label: partial_coverage`).
- Trends: monthly buckets, empty months returned as zero. Bounded to 24 months per call.
- Explicitly labeled "operational summary — not audited accounting output."

---

## 7. Taxes

**Purpose:** tax reporting from Invoice tax **snapshots** (historical rates preserved), TaxExemption CRUD.

**Screens:** `TaxReportsPage` — Total / Manual overrides / Exempt customers cards + 4 tabs (By jurisdiction / Exempt customers / Exemption records / Manual overrides).

**Backend router:** `/api/tax/*`.

**Rules:**
- Historical Invoice tax values use stored snapshots — current settings do NOT retroactively rewrite past invoices.
- Jurisdiction resolved via `Invoice.tax_jurisdiction_snapshot` → falls back to `Customer.state`.
- Reports are **operational summaries, not filing advice** — surfaced in the page subtitle.

---

## 8. Reports & Analytics

**Purpose:** curated reports (13) + Custom Report Builder foundation.

**Screens:** `ReportsPage` — two tabs. Curated (left rail list, filters, preview, CSV export) + Custom builder (dataset picker, field whitelist toggles, preview, CSV export).

**Backend router:** `/api/reports/*` — `GET /api/reports`, `POST /{key}/run`, `POST /{key}/export.csv`, `POST /custom/preview`, `POST /custom/export.csv`.

**Rules:**
- Every curated report declares data source, date basis, calc basis, and known limitations — the frontend displays them next to the preview.
- Custom builder is restricted to approved datasets + fields + filters + group_by + sort. No raw SQL. No arbitrary Mongo. No cross-tenant reads. No hidden internal fields.
- CSV export escapes formula-injection prefixes (`=`, `+`, `-`, `@`) with a leading single quote; money `_cents` fields are formatted to two-decimal dollars; export capped at 25 000 rows; every export writes an audit event.

**Reports delivered (13):**
- Inventory: `inventory.on_hand`, `inventory.low_stock`, `inventory.movements`, `inventory.material_cost_history`.
- Purchasing: `purchasing.pos_by_status`, `purchasing.vendor_spend`.
- Expenses: `expenses.by_category`, `expenses.by_vendor`, `expenses.all`.
- Finance: `finance.summary`, `finance.top_customers`.
- Tax: `tax.by_jurisdiction`, `tax.manual_overrides`, `tax.exempt_customers`.

---

## Permissions inventory (EC7-additions)

- `inventory:read`, `inventory:write` (added in phase 7a)
- `vendor:read`, `vendor:write`, `purchasing:read`, `purchasing:write` (phase 7b)
- `expense:read`, `expense:write`, `expense:archive`, `finance:read`, `tax_report:read`, `report:read` (phase 7c / 7d)

**Frontend rule:** unauthorized actions are hidden or disabled in the UI, but backend enforcement is authoritative. Restricted staff MUST NOT see Expenses, margins, estimated profit, tax details, vendor account pricing, or CSV exports without explicit role grants.

## Route inventory

Backend under `/api`: `materials`, `inventory/*`, `vendors`, `vendors/materials`, `vendors/seed/test-adapter`, `supply/*`, `purchase-orders/*`, `expenses`, `expense-categories`, `finance/*`, `tax/*`, `reports/*`.

Frontend routes: `/inventory`, `/materials/:id`, `/supply-center`, `/purchase-orders`, `/purchase-orders/:id`, `/vendors/:id`, `/expenses`, `/finance`, `/tax`, `/reports`.

**Phase 7d closure — frontend workflows delivered**
- `/vendors/:id` — Vendor identity, warehouses, linked materials, PO history.
- `/materials/:id` — Material metadata, per-location balances, recent movements, and an immutable **Material Cost History** drawer.
- `/inventory` — **Physical count** wizard (delta-preview, reason-required, Idempotency-Key) and **Inventory Transfer** dialog (paired transfer_out/transfer_in with Idempotency-Key).
- `/purchase-orders/:id` — vendor name links to Vendor Detail; **Inventory movements from this PO** table renders receiving-generated movements linked via `source_entity_id`.

**Frontend automated tests** — Jest (via `react-scripts`) + `@testing-library/react@16` + `@testing-library/user-event@14`. 6 suites / 25 tests cover the new workflows and smoke the remaining EC7 pages. See `/app/frontend/src/__tests__/`.

## Collection & index inventory (EC7)

`materials`, `material_cost_history`, `inventory_locations`, `inventory_items`, `inventory_movements`, `inventory_reservations`, `vendors`, `vendor_materials`, `supplier_warehouses`, `supplier_products`, `supplier_product_stock`, `supplier_order_log`, `purchase_orders`, `purchase_order_lines`, `receiving_records`, `expenses`, `expense_categories`, `expense_attachments`, `tax_exemptions`.

Every collection has an `id` unique index + one or more `(tenant_id, …)` compound indexes; see `app/core/db.py::ensure_indexes` for the exact list.
