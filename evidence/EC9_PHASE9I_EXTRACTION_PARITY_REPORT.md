# EC9 Phase 9I-U Extraction Parity Report

**Status:** PHASE 9I-U IMPLEMENTED AND VERIFIED - READY FOR REVIEW
**Date:** 2026-07-28
**Branch:** `ec9-phase9i-u-final-extraction-verification`

## Scope Verified

Phase 9I-U adds the final all-category parity and extraction verification gate for the pricing engine extraction plan.

Verified surfaces:

- Shared Phase 9I-K fixture pack.
- Pure line engine adapter path: `pricing_engine.line_engine.calculate_line`.
- SaaS runtime configuration adapter path: `app.services.pricing.calculate_pricing` with `saas_configuration_adapter_9iq_v1` evidence.
- Legacy cents-first compatibility adapter path: `legacy_saas_cents_first_compatibility_adapter_9il_v1`.
- Standalone portable harness path: `standalone_portable_configuration_adapter_9it_v1`.

Verified categories:

- `banners`
- `rigid_signs`
- `cut_vinyl`
- `digital_print`
- `vehicle_graphics`
- `apparel`
- `promotional`
- `services`
- `custom`

## Contract Results

- Every required fixture category is discovered from the existing shared fixture pack.
- Every adapter path returns the same normalized cents-first result for every fixture.
- The selected method, canonical method, warnings, method rows, authoritative selling price cents, suggested price cents, true cost cents, profit cents, and margin evidence match the fixed fixture contract.
- Fixture engine version, formula version, and rounding policy evidence are preserved.
- No new pricing formulas, defaults, minimums, markups, discounts, taxes, or rounding rules were added or changed.
- No fixture expected money value was copied into the Phase 9I-U verification tests.
- Digital Print document-minimum behavior remains configuration/evidence driven and is not hardcoded in the Phase 9I-U gate.

## Isolation Results

- The pure pricing engine package remains free of SaaS runtime imports.
- The standalone adapter harness remains free of SaaS runtime imports.
- Verification results expose no tenant identity, database handles, request/auth objects, permission data, audit handles, entitlements, licensing fields, tokens, secrets, or API keys.
- Executions are deterministic and do not mutate fixture input, portable configuration input, or adapter configuration.
- Executions create no persistent entities.

## Explicit Exclusions

Phase 9I-U did not implement:

- Licensing checks or license packaging.
- Desktop or standalone application packaging.
- Frontend behavior.
- Quote, Order, Order Item, Work Order, saved-calculation, Webstore, or Wrap Lab behavior.
- Data migration, historical backfill, live import/apply, or persistence changes.
- Phase 9I-V or any later phase.

## Verification Commands

Focused verification:

```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_ec9_phase9iu_final_extraction_verification.py -q
```

Result:

```text
5 passed
```

Regression verification:

```text
Phase 9I-J/K: 52 passed
Phase 9I-L/M/N: 31 passed, 6 warnings
Phase 9I-O/P: 28 passed, 6 warnings
Phase 9I-Q/R: 13 passed, 6 warnings
Phase 9I-S/T: 29 passed, 6 warnings
Pricing saved-items/materials/components: 10 passed, 6 warnings
Pricing method configuration/contracts: 36 passed, 6 warnings
Quote/Order and Digital Print regressions: 66 passed, 6 warnings
Snapshot/advisory regressions: 22 passed, 6 warnings
Orders/Quotes/Work Orders regressions: 22 passed, 6 warnings
Money policy: 14 passed
Backend compile/import validation: passed
git diff --check: passed with CRLF conversion warnings only
```

## Remaining Scope

Phase 9I remains open after 9I-U. The next bounded phase is Phase 9I-V, the licensing readiness gate after extraction passes. Phase 9I-V is documentation/readiness only unless the owner separately authorizes a later licensing or standalone packaging checkpoint.
