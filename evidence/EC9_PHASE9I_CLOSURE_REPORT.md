# EC9 Phase 9I Closure Evidence

**Status:** PHASE 9I-I REVIEW PASSED - COMPLETE; PHASE 9I REMAINS OPEN
**Date:** 2026-07-27
**Branch:** `main`
**Starting commit:** `911394e40de94a6a439263ba9de85b9f4b199d34`

## Scope

Phase 9I-I implements the remaining approved Digital Print item/order minimum behavior and reconciles Phase 9I for review. It does not begin Control Center, Platform Administration, UX completion, Advanced Onboarding, public signup, release hardening, Record Numbering backfill, Webstore workflow changes, Wrap Lab workflow changes, or any later checkpoint.

## Phase 9I Inventory

| Subphase | Status | Evidence |
|---|---|---|
| 9I-A | Complete and reviewed | Shared contracts and registry committed before this checkpoint. |
| 9I-B | Complete and reviewed | Tenant method configuration foundation committed before this checkpoint. |
| 9I-C | Corrected; re-review passed | `PHASE 9I-C RE-REVIEW PASSED`. |
| 9I-D | Corrected; re-review passed | `PHASE 9I-D RE-REVIEW PASSED`. |
| 9I-E | Review passed and committed | Dedicated calculator workspace committed before this checkpoint. |
| 9I-F | Review passed and committed | Quote/Order dialog parity committed before this checkpoint. |
| 9I-G | Review passed and committed | Saved Calculation Library committed before this checkpoint. |
| 9I-H | Review passed and committed | Direct consumer contracts committed before this checkpoint. |
| 9I-I | Review passed; complete | Independent focused read-only review passed. Digital Print item/order minimum enforcement is safe to commit. |

## Digital Print Rule

Digital Print now uses tenant pricing defaults for separate `item_minimum` and `order_minimum` values. Starter defaults are `$20` per produced item/unit and `$40` per Quote or Order document, matching the recorded owner-approved repository decision.

The previous 9I-I review failed because the first implementation enforced the `$40` order minimum inside each individual Digital Print calculator invocation. This correction removes that rejected behavior.

The standalone Digital Print calculator now applies only the line-item floor:

```text
item_minimum * quantity
```

It returns the calculated line result and displays the `$40` order minimum only as document-level context.

Quote and Order pricing orchestration aggregate eligible Digital Print line subtotals after line-item minimum enforcement. Non-Digital-Print line items are excluded. If the eligible Digital Print subtotal is below the configured `$40` order minimum, the backend applies one document-level `digital_print_order_minimum_adjustment_cents` before existing discounts and tax. The adjustment is applied once per Quote or Order and is not duplicated for multiple Digital Print line items.

Manual overrides preserve the requested manual line price and existing override-reason enforcement. The document-level Digital Print minimum still evaluates against the selected stored line subtotal. Quote revisions persist the current document-level evidence, Quote-to-Order conversion copies the accepted Quote evidence without recalculating, and historical line snapshots remain unchanged when defaults change.

## Files Changed

- `backend/app/services/starter_defaults.py`
- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_method_outputs.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/order_pricing.py`
- `backend/app/services/quote_conversion.py`
- `backend/app/services/quote_revisions.py`
- `backend/app/routers/quotes.py`
- `backend/app/routers/orders.py`
- `backend/tests/test_ec9_phase9ii_digital_print_order_minimum.py`
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/__tests__/PricingCalculatorPage.test.jsx`
- `frontend/src/__tests__/LineItemDialogPricingParity.test.jsx`
- `docs/architecture/pricing_snapshots.md`
- `preflight/EC9_PHASE9I_SHARED_PRICING_CALCULATOR_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/PRD.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `memory/owner_specification_hold_register.md`
- `evidence/EC9_PHASE9I_CLOSURE_REPORT.md`

## Verification

- Focused corrected Digital Print document-minimum backend tests: `31 passed, 6 warnings`.
- Focused Quote/Order dialog and dedicated Pricing Calculator frontend tests: `21 passed`.
- Combined Phase 9I-A/B/C/D/F/G/H/I backend regressions: `163 passed, 6 warnings`.
- Quote/Order/Work Order/pricing-snapshot regressions: `115 passed, 6 warnings`.
- Category/Banner/snapshot regressions: `85 passed, 6 warnings`.
- Complete backend suite: `879 passed, 3 skipped, 6 warnings`.
- Complete frontend suite: `72 passed`.
- Frontend production build: compiled successfully.
- Backend compile/import validation: `405` Python files compiled successfully.
- `git diff --check`: passed with CRLF conversion warnings only.

## Independent Review Acceptance

The focused read-only re-review verified:

- The rejected per-calculator `$40 order_minimum` behavior was removed.
- Digital Print item minimum is `item_minimum * quantity`.
- Digital Print order minimum is applied once per Quote or Order.
- The document adjustment is `max(order_minimum - eligible_digital_print_subtotal, 0)`.
- Eligible subtotal uses authoritative stored Digital Print line subtotals after line-item minimum enforcement.
- Banner and all other categories are excluded.
- Pricing order is line pricing, Digital Print document adjustment, existing document discount, then existing tax.
- Backend recomputes authoritative totals and ignores forged client totals and adjustment values.
- Tenant-specific settings are used.
- New persisted document-adjustment fields use integer cents.
- Quote and Order use shared logic in `backend/app/services/order_pricing.py`.
- Manual-price override reasons remain required.
- Quote revisions and Quote-to-Order conversion preserve accepted historical evidence.
- Legacy records without the new fields remain readable.
- Banner output remains unchanged.
- Full backend, frontend, build, compile, and focused regression verification passed.

## Protected And Deferred Scope

- Banner pricing behavior remains protected and was verified through owner-decision regression tests.
- Record Numbering files and backfill execution are out of scope.
- Existing pricing snapshots are not rewritten.
- Quote-to-Order conversion preserves stored snapshot behavior.
- Webstore, Wrap Lab, customer portal, Control Center pricing configuration screens, Platform Administration, public signup, and later checkpoints remain deferred.

## Closure Evaluation

Phase 9I-I satisfies implementation exit criteria, passed independent focused read-only review, and is complete. All of Phase 9I remains open and must not be formally closed until the separate `Calculator Extraction, Money Normalization, and Standalone Licensing Readiness Audit` is completed and its required corrections are resolved.

Preserved non-blocking follow-ups:

1. Add a dedicated visible `Digital Print order minimum adjustment` breakdown row to applicable Quote and Order detail surfaces.
2. Audit pre-existing Quote and Order item mutation paths that perform identifier-only updates or deletes after tenant-scoped authorization lookups.
3. Record the one-off duplicate-key setup failure in `tests/test_ec7_inventory.py` as informational test-reliability evidence; the immediate full-suite rerun passed.
