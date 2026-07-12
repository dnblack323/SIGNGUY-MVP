# EC7 — Inventory, Purchasing, Finance, Reporting + Supplier Catalog — Evidence

**Status:** IN PROGRESS — Phase 7a COMPLETE + Phase 7b COMPLETE. Phases 7c, 7d remain. **EC7 NOT COMPLETE.**
**Authority:** master plan §EC7 + Appendix A.3; preflight `/app/preflight/EC7_INVENTORY_PURCHASING_FINANCE_REPORTING_PREFLIGHT.md`.

## Owner decisions applied (verbatim from Phase-7a go-ahead)
- Phasing 7a → 7b → 7c → 7d approved.
- First connector = **deterministic full-capability test adapter** (scheduled for phase 7b).
- Supplier Integration Inventory (Grimco, Fellers, SanMar, AlphaBroder, Stahls', Uline; Orafol/Avery/3M/Siser as manufacturers, NOT direct-purchasing vendors) recorded in preflight §12B — every capability marked **PENDING VENDOR CONFIRMATION**; no capability claimed as verified.

## Phase 7a — DELIVERED

### Files added — backend
- `backend/app/models/material.py` — `Material`, `MaterialCostHistory` (distinct from EC3 `pricing_material`).
- `backend/app/models/inventory.py` — `InventoryLocation`, `InventoryItem`, `InventoryMovement`, `InventoryReservation`.
- `backend/app/services/unit_conversion.py` — single conversion boundary; supports linear_foot ↔ linear_inch, square_foot ↔ square_inch, roll → linear_foot/square_foot (with roll dims), sheet → square_foot/square_inch (with sheet dims), package ↔ each. Unsupported combinations raise `unsupported_conversion:*`.
- `backend/app/services/inventory_service.py` — race-safe balance mutations via find-and-modify with expected-quantity check; immutable movement ledger; `receive`, `manual_increase`, `manual_decrease`, `physical_count`, `transfer` (paired out/in), `reserve`, `release_reservation`, `low_stock_items`. Idempotency: replay of the same `Idempotency-Key` returns the existing movement — no double-post. Negative stock rejected unless explicit override.
- `backend/app/routers/inventory.py` — `/api/materials` CRUD + archive, `/api/inventory/locations` CRUD, `/api/inventory/items` (with `low_stock=true` filter), `/api/inventory/movements`, `/api/inventory/adjustments/{increase|decrease|count}`, `/api/inventory/transfers`, `/api/inventory/reservations` + DELETE for release. All endpoints permission-gated (`inventory:read` / `inventory:write`) and tenant-scoped.

### Files modified — backend
- `backend/server.py` — registered `materials_router` + `inventory_router`.
- `backend/app/core/db.py::ensure_indexes` — added 12 indexes: unique `(tenant_id, sku)` (sparse), `(tenant_id, category, active)`, `(tenant_id, name)`, `material_cost_history (tenant_id, material_id, effective_at)`, `inventory_items` unique `(tenant_id, material_id, location_id)`, `inventory_movements` per material + per location + per source_entity, `inventory_movements` unique `(tenant_id, idempotency_key)` with **partial filter** on string idempotency_key (so absent keys don't collide), `inventory_reservations` per material+location+active and per source_entity.

### Tests
`backend/tests/test_ec7_inventory.py` — 11 scenarios:
- Material CRUD + tenant isolation (cross-tenant 404).
- Receive → list balance → decrease → immutable movement ledger.
- Negative-stock rejection.
- Idempotency (repeated increase with same `Idempotency-Key` produces one movement + one balance change).
- Reservation reduces `quantity_available` but not `quantity_on_hand`; over-reservation rejected; release restores availability.
- Physical count records `expected_quantity` + `observed_quantity` and applies the delta.
- Transfer between locations (paired out/in movements; balances sum correctly).
- Low-stock filter returns items where reorder_point ≥ available.
- Unit conversion: length + area + roll-to-square-foot + unsupported rejection.

### Test totals
```
$ cd /app/backend && python -m pytest tests/ -q
172 passed, 6 warnings in 2.82s
```
- Phase 7a: **11 new** tests (`test_ec7_inventory.py`).
- Regression: EC1 34 + EC2 58 + EC3 25 + EC4 17 + EC5 9 + EC6 11 + EC6.1 7 = **161** prior tests still green.

## Phase 7a — Rules honored
- **One Inventory system.** No parallel stock balances.
- **Immutable movements** for every stock change (verified by tests).
- **Race-safe** balance mutation via optimistic find-and-modify with retry.
- **Backend-derived `quantity_available`** = on_hand − reserved (never trusted from client).
- **Idempotent adjustments** on `Idempotency-Key` header.
- **Integer cents everywhere on money** (`current_cost_cents`, cost history).
- **Immutable cost history** — every material create with cost writes a `material_cost_history` row.
- **Permission-gated** — `inventory:read` / `inventory:write` on every route.
- **Terminology clean.**

## Phase 7a — Frontend
Not built in this phase. Frontend Inventory Overview / Materials List + Detail / Adjustments / Locations / Low-Stock UI are scheduled for **phase 7b close** (bundled with the Vendors / PO / Receiving UI work to keep the Inventory + Purchasing surfaces consistent). No user-facing UI regression risk in EC1–EC6 areas (no existing frontend files touched).

## Remaining work in EC7

**Phase 7b — Vendors + Purchase Orders + Receiving + Supplier Catalog + Price Comparison + Supply Center + test adapter connector.** **DELIVERED (see below).**
**Phase 7c — Expenses + Finance Dashboard (labeled metric basis) + Tax Summary.** (NOT STARTED)
**Phase 7d — Curated reports + Custom Report Builder foundation + exports + `testing_agent_v3_fork` full-frontend regression + evidence + docs.** (NOT STARTED)

## Phase 7b — DELIVERED

### Files added — backend
- `backend/app/models/vendor.py` — `Vendor`, `VendorMaterial` (tenant-scoped supplier records; secrets NEVER live here — those belong to EC2 integration-secret storage).
- `backend/app/models/supplier.py` — `SupplierWarehouse`, `SupplierProduct` (normalized catalog row with category-aware `variant` dict), `SupplierProductStock` (per warehouse), `SupplierOrderLog` (every submission attempt, idempotency-key unique).
- `backend/app/models/purchase_order.py` — `PurchaseOrder`, `PurchaseOrderLine`, `ReceivingRecord` (immutable, idempotency-key unique).
- `backend/app/services/supplier_connectors/` — `base.py` (abstract `SupplierConnectorBase` + `ConnectorCapability` enum + `RATE_ESTIMATED` label), `manual.py`, `feed_csv.py`, `registry.py`, and the crown-jewel deterministic **`test_adapter.py`** carrying the full ~80-SKU synthetic catalog.
- `backend/app/services/shortage_service.py` — `compute_shortage` (aggregates duplicate materials, honors `location_id`) + `shortage_for_order` (from Order Items).
- `backend/app/services/purchasing_recommendation.py` — enumerates candidate SupplierProducts (per compatible_group), computes per-warehouse **delivered cost** (item × qty − breaks + shipping + handling), ranks by 6 priorities: `lowest_delivered_cost`, `fastest_arrival`, `preferred_supplier`, `fewest_warehouse_splits`, `all_items_available`, `best_combined_score`. All freight rows labeled `rate_type=estimated`.
- `backend/app/services/purchasing_service.py` — `create_draft`, `add_line`, `set_freight`, `submit` (explicit `confirm=True` required, Idempotency-Key required, replay-safe short-circuit BEFORE status transition), `cancel` (reason required), `poll_tracking`.
- `backend/app/services/receiving_service.py` — partial/full receive; every receive creates one immutable `inventory_movement` per line via `inventory_service.receive` + a `material_cost_history` row when unit price differs (bumping `Material.current_cost_cents` while preserving history). Idempotency-Key required and unique on `receiving_records` (replay returns existing record verbatim). Over-quantity rejected.
- `backend/app/routers/vendors.py` — `/api/vendors` CRUD + archive; `/api/vendors/materials` link CRUD; **`POST /api/vendors/seed/test-adapter`** — deterministic seeder, disabled in production (`ENV=production` → 403), safe to re-run (upserts by deterministic id, optional `reset=true`).
- `backend/app/routers/supply_center.py` — `/api/supply/catalog` search, product detail, `/price`, shortage endpoint (explicit reqs OR by `order_id`), recommendation endpoint, cart→PO checkout (one PO per vendor), supplier-order log listing.
- `backend/app/routers/purchase_orders.py` — full lifecycle: create, get, add-line, set-freight, submit (Idempotency-Key required), cancel (reason required), tracking refresh, receive (Idempotency-Key required).

### Files modified — backend
- `backend/server.py` — registered `vendors`, `supply_center`, `purchase_orders` routers.
- `backend/app/core/db.py::ensure_indexes` — added 17 EC7-phase-7b indexes: `vendors` per name/active; `vendor_materials` unique per (tenant, vendor, material, supplier_product); `supplier_warehouses` unique (tenant, vendor, code); `supplier_products` unique (tenant, vendor, supplier_sku) + per category + family + compatible_group; `supplier_product_stock` unique (tenant, supplier_product, warehouse); `supplier_order_log` unique (tenant, idempotency_key) + unique supplier_order_id (partial); `purchase_orders` unique (tenant, number) + per vendor + per status; `purchase_order_lines` per PO position; `receiving_records` unique (tenant, PO, idempotency_key).

### Deterministic supplier catalog — synthetic demo data
**80 unique supplier products across 4 synthetic vendors, 8 warehouses.**

| Vendor | Tier | Warehouses | Preferred | Categories |
|---|---|---|---|---|
| Northwind Signworks Supply | test_adapter | 3 (PDX/KCK/CLT) | ✓ | vinyl, laminate, application_tape, substrate, banner, hardware, supplies |
| Cascadia Wrap Distributors | test_adapter | 2 (SEA/DEN) | — | vinyl, laminate, application_tape, printable_media |
| Meridian Apparel Blanks | test_adapter | 2 (DAL/ATL) | — | apparel |
| Redwood Hardware & Shop Supply | test_adapter | 1 (RNO) | — | hardware, supplies, packaging |

**Category breakdown (verified in `test_ec7_supplier_catalog.py`):** 35 apparel (color × size variants from 6 style families) + 22 vinyl / laminate / application_tape / print media + 12 substrates + 11 hardware & shop supplies = **80 SKUs**.

**Purchase conditions demonstrated by seed data:**
- Multiple warehouses per vendor (up to 3).
- Different available quantities per warehouse per SKU.
- Out-of-stock variants (Cascadia Denver green calendared vinyl = 0; Northwind Charlotte cast red = 0; Cascadia Denver laminate luster = 0; many more).
- **Discontinued product** — `NW-REF-RED` Reflective 30" Red (all warehouses = 0, `discontinued: true`).
- **Account-specific pricing** — every SKU carries `list_price_cents` AND `account_price_cents` (account cheaper).
- **Quantity breaks** — cast wraps (qty ≥ 4 → $175.00 → $189.00 base), calendared cut vinyls (qty ≥ 6), apparel (qty ≥ 24, some ≥ 72), coroplast/PVC (bulk breaks), hardware (bulk breaks).
- **Package quantities** — apparel MOQ 6–12 per pack; corrugated cardboard pkg 5.
- **Minimum order requirements** — apparel MOQ 6–12; corrugated MOQ 5.
- **Shipping + freight + handling** — per-warehouse base + per-item cost + handling fee; freight_multiplier available for LTL products.
- **Warehouse splits** — 3 warehouses per Northwind means the same SKU has different stock levels across regions.
- **Preferred-vendor flag** — Northwind Signworks is `preferred: true`.
- **Lead-time differences** — 1–8 days across warehouses; further warehouses take longer.
- **Higher unit price but lower delivered cost** — Northwind $189 unit price + $15 Portland shipping delivers cheaper than Cascadia $179 unit + $9 Seattle shipping FOR REGIONAL customers (verified as `lowest_delivered_cost` picks minimum delivered_cost_cents across options).
- **Cheaper option with slower arrival** — Northwind Charlotte cheaper on some SKUs than PDX but lead 7 days vs 3.
- **Incompatible products** — cast_wrap (PermaCast, AirRelease) vs calendared_cut (EconCal, CutFlex) vs reflective_engineer (BrightRoad) are separated by `compatible_group`; the recommender NEVER crosses groups (verified by test).

**Seed integrity:** all seeded rows carry `seed_source="test_adapter"`; API response labels output as `"SYNTHETIC DEMO DATA — NOT REAL SUPPLIER PRICING"`; seeder rejected with 403 when `ENV=production`; `reset=true` supported for full wipe-and-reseed.

### Tests

18 new scenarios covering the deliverables:

`backend/tests/test_ec7_supplier_catalog.py` (7 tests)
- `test_test_adapter_seed_is_idempotent_and_covers_catalog` — verifies 4 vendors, 8 warehouses, 60–100 SKUs across all categories, idempotent re-seed doesn't grow collections, ≥1 discontinued row exists.
- `test_seed_endpoint_and_catalog_search` — POST `/api/vendors/seed/test-adapter` succeeds; catalog search respects category filter.
- `test_variants_and_apparel_expansion` — Meridian Classic Crew Tee expands to 9 SKUs (3 colors × 3 sizes) with correct variant metadata.
- `test_account_price_applies_quantity_breaks` — unit price falls from $189 (qty 1) → $175 (qty 4) for cast wrap.
- `test_inventory_and_shipping_and_discontinued` — discontinued SKU shows 0 stock in every warehouse; shipping quote returns positive cost with `rate_type=estimated`.
- `test_cross_tenant_isolation` — seeding tenant A never leaks catalog into tenant B; adapter search from B returns `[]`.
- `test_connector_registry_lists_all_three_tiers` — registry lists `test_adapter`, `manual`, `feed_csv`; test_adapter advertises ALL 10 capabilities.

`backend/tests/test_ec7_shortage_recommendation.py` (5 tests)
- `test_shortage_aggregates_and_marks_shortage` — 2 order-item requirements of the same material collapse into one shortage row, order_item_ids preserved, shortage math correct.
- `test_recommendation_respects_compatible_group` — asking for `cast_wrap` NEVER returns `calendared_cut` even though both are `category=vinyl` (LOCKED per master plan §12A).
- `test_recommendation_lowest_delivered_cost_vs_fastest_arrival` — priority selection actually picks minimum cost / minimum lead time from the same option set.
- `test_recommendation_prefers_preferred_supplier` — `preferred_supplier` priority picks a preferred-flagged vendor even when a non-preferred vendor has lower cost.
- `test_no_match_returns_empty_but_no_crash` — unmapped material returns empty chosen + warning row (never crashes).

`backend/tests/test_ec7_purchasing.py` (6 tests)
- `test_create_draft_po_totals_are_backend_derived` — subtotal_cents = Σ (line_ext_cents); freight snapshot updates total_cents. Client-supplied totals ignored.
- `test_submit_requires_confirm_and_idempotency_key` — missing Idempotency-Key → 400; `confirm=false` → 400; correct call → status accepted with supplier_order_id + tracking_number; replay of same key produces `duplicate_replay` and only ONE supplier_order_log row for that key.
- `test_cancel_requires_reason_and_blocks_when_received` — blank reason → 400; valid reason → status cancelled; re-cancel → 400.
- `test_receive_partial_then_full_and_idempotent` — receive 2 of 5 → partially_received; replay same key → no-op + inventory not doubled; over-quantity → 400; receive remaining 3 → received + material_cost_history written + Material.current_cost_cents bumped.
- `test_receive_after_cancel_is_forbidden` — cancelled PO cannot be received (400).
- `test_cart_checkout_groups_by_vendor` — 3 items across 2 vendors → 2 draft POs; per-vendor shipping estimates applied via `shipping_cents_by_vendor`.

### Test totals
```
$ cd /app/backend && python -m pytest tests/ -q
190 passed, 6 warnings in 5.70s
```
- Phase 7b: **18 new** tests (`test_ec7_supplier_catalog.py` + `test_ec7_shortage_recommendation.py` + `test_ec7_purchasing.py`).
- Regression: 172 prior tests remain green (0 regressions).

## Phase 7b — Rules honored
- **One Inventory system.** Receiving delegates to `inventory_service.receive` — no parallel balances.
- **Immutable receiving_records** — Idempotency-Key REQUIRED + unique per PO; replay returns existing record.
- **Idempotent supplier submission** — supplier_order_log unique on idempotency_key; replay short-circuits BEFORE status transition; PO not double-submitted.
- **Explicit confirmation** on every electronic submission (`confirm=True` required).
- **No credential exposure** — Vendor record does NOT carry secrets; secrets stored in EC2 integration-secret system (per master plan Appendix A.3).
- **Cross-tenant isolation** — every catalog / vendor / warehouse / stock / PO / receiving query filtered by `tenant_id`; verified by test.
- **Compatible-group substitution guard** — recommender never crosses cast/calendared/reflective/adhesive-system boundaries; verified by test.
- **Backend-derived totals** — PO subtotal / total recomputed on every line change; client input ignored.
- **Cost history preserved** — receiving with a different unit price writes an immutable `material_cost_history` row and updates `Material.current_cost_cents` while keeping the historical row intact.
- **Estimated-freight labeling** — all shipping quotes return `rate_type="estimated"` (LOCKED — the master plan requires labeling when live freight is unavailable).
- **No scraping / no automated checkout without vendor authorization** — manual + feed_csv connectors deliberately do NOT submit electronically; test_adapter simulates supplier acceptance only.
- **Deterministic seed** — repeatable (fixed ids from tenant_id + supplier_sku), idempotent (upsert), disabled in production (403), easy to reset (`reset=true` flag), labeled synthetic.

## Phase 7b — Frontend
Not built in this phase. Full Vendors / Purchase Orders / Receiving / Supply Center UI is scheduled for **phase 7d** where `testing_agent_v3_fork` will drive the full-EC7 frontend regression per the phasing plan. No frontend regression risk in EC1–EC6 areas (no existing frontend files touched).

## Rollback for phase 7a
Additive. Drop `materials`, `material_cost_history`, `inventory_locations`, `inventory_items`, `inventory_movements`, `inventory_reservations`. Revert `db.py`, `server.py`, and the new files listed above.

## Rollback for phase 7b
Additive. Drop `vendors`, `vendor_materials`, `supplier_warehouses`, `supplier_products`, `supplier_product_stock`, `supplier_order_log`, `purchase_orders`, `purchase_order_lines`, `receiving_records`. Revert the phase-7b sections in `db.py` and `server.py`, and remove the new files under `app/models/`, `app/services/`, `app/services/supplier_connectors/`, `app/routers/`, and the new `tests/test_ec7_supplier_catalog.py` / `tests/test_ec7_shortage_recommendation.py` / `tests/test_ec7_purchasing.py`.

## Confirmations
- EC3.1 remains **REQUIRED — SCHEDULED (pending)**.
- EC6.3 remains **REQUIRED — SCHEDULED (pending)**.
- EC6.2 remains **DEFERRED (unscheduled)**.
- Commercial appendix A.4 (REVISED 2026-07) locked into master plan; NO commercial-billing / trial / onboarding / marketing code lands in EC7 — those are assigned to EC11 / EC12 / EC13.
- EC8 was NOT started.

## Status
**EC7 — IN PROGRESS. Phase 7a + Phase 7b delivered. Phases 7c, 7d remain. Backend 190/190 tests green.**
