# EC13 Founder Test-Slot Isolation Recovery

**Date:** 2026-08-18

**Scope:** Baseline recovery only for `backend/tests/test_ec13_phase13a_commercial_catalog.py::test_entitlement_contracts_founder_preservation_and_tenant_isolation`.

## Root Cause

The Phase 13A Founder preservation test selected a globally unused Founder slot from the persistent local MongoDB collection. Prior test executions left 25 `t-13a-*` Founder contracts in `signguy_local`, occupying every slot from 1 through 25. The test then failed before exercising the intended entitlement, Founder preservation, and tenant-isolation assertions.

No production database cleanup was performed. The local database was confirmed to be `signguy_local` with `MONGO_URL=mongodb://localhost:27017`, so stale records were not deleted or reset.

## Fix

Only the test-owned Founder contract collection access was isolated for the affected tests. The test now substitutes an in-memory Founder contract collection for the service and module-level test helper while preserving real access to all other collections.

The substitute mirrors the production duplicate-key behavior relevant to the test:

- unique Founder contract id
- one active/pending/grace Founder contract per tenant
- globally unique numeric Founder slot

The production service, model, route, database indexes, pricing code, Webstore code, and release/cutover files were not changed.

## Regression Coverage

Added `test_founder_contract_test_isolation_does_not_consume_persistent_slots`, which verifies that creating a Founder contract through the route in this test isolation does not change the persistent `founder_tenant_contracts` count.

## Verification

- Reproduced pre-change failure: `AssertionError: No unused Founder test slot available`
- Focused repaired test, five separate runs: `1 passed` each run
- Phase 13A commercial catalog file: `5 passed, 11 warnings`
- All EC13 backend tests: `9 passed, 16 warnings`
- Relevant entitlement/tenant-isolation/commercial-catalog cross-check: `18 passed, 16 warnings`
- Compile/import check: `import ok`
- Complete backend suite run 1: `1213 passed, 3 skipped, 265 warnings`
- Complete backend suite run 2: `1213 passed, 3 skipped, 265 warnings`

## Explicit Non-Scope

- No pricing-engine consumer cutover work started.
- No pricing formula/default/rounding/warning behavior changed.
- No Webstore branch files changed in this recovery worktree.
- No stash entries changed.
- No database collection or database reset was performed.
