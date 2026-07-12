# EC7 — Inventory, Purchasing, Finance, Reporting + Supplier Catalog — Evidence

**Status:** IN PROGRESS — Phase 7a COMPLETE. Phases 7b, 7c, 7d remain. **EC7 NOT COMPLETE.**
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

**Phase 7b — Vendors + Purchase Orders + Receiving + Supplier Catalog + Price Comparison + Supply Center + test adapter connector.** (NOT STARTED)
**Phase 7c — Expenses + Finance Dashboard (labeled metric basis) + Tax Summary.** (NOT STARTED)
**Phase 7d — Curated reports + Custom Report Builder foundation + exports + `testing_agent_v3_fork` full-frontend regression + evidence + docs.** (NOT STARTED)

## Rollback for phase 7a
Additive. Drop `materials`, `material_cost_history`, `inventory_locations`, `inventory_items`, `inventory_movements`, `inventory_reservations`. Revert `db.py`, `server.py`, and the new files listed above.

## Confirmations
- EC3.1 remains **REQUIRED — SCHEDULED (pending)**.
- EC6.3 remains **REQUIRED — SCHEDULED (pending)**.
- EC6.2 remains **DEFERRED (unscheduled)**.
- EC8 was NOT started.

## Status
**EC7 — IN PROGRESS. Phase 7a delivered. Phases 7b, 7c, 7d remain. Backend 172/172 tests green.**
