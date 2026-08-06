# Code Issue Register Fix Plan

Created: 2026-08-05
Repository: `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP`
Branch at planning time: `codex/codeReviewAfterWebstores`

This plan covers unresolved Code Issue Register items only. It does not reopen Fixed / Verified CIR entries unless a regression is found while fixing an open item.

## Current Unresolved Scope

| ID | Status | Priority | Fix grouping |
| --- | --- | --- | --- |
| CIR-003 | Fixed / Verified | P1 | Quote totals and pricing authority |
| CIR-004 | Fixed / Verified | P1 | Quote-to-Order failure safety |
| CIR-005 | Fixed / Verified | P1 | Atomic single-use token consumption |
| CIR-006 | Fixed / Verified | P2 | Terminal Order financial edit guard |
| CIR-010 | Fixed / Verified | P3 | Repository hygiene |
| CIR-011 | Fixed / Verified | P3 | Webstores maintainability split |
| CIR-012 | Fixed / Verified | P3 | Frontend documentation/dependency reconciliation |
| CIR-013 | Fixed / Verified | P2 | Financial failure history preservation |
| CIR-020 | Fixed / Verified | P2 | Webstores AI wiring through EC16/EC17 preview-confirm flow |
| CIR-023 | Fixed / Verified | P1 | Tenant-scoped mutation/reread discipline |
| CIR-024 | Fixed / Verified | P3 | Product-facing terminology cleanup |

## Stop Rules

- CIR-020 owner authorization was received after the safety-fix sequence. Keep Webstore product AI actions on the EC16/EC17 local/mock path unless a later owner decision explicitly authorizes live provider behavior.
- Do not combine the Webstores file split (CIR-011) with behavior changes. Split first with characterization tests or defer until after safety fixes.
- Do not start broad refactors of stable MVP modules just to satisfy style preferences. Fix the risk surfaces directly.
- Do not run excessive broad test suites by default. Prefer targeted backend/frontend regressions for the touched surfaces, then add broader smoke/build checks only when the touched surface is shared.

## Phase 1 - Data Integrity and Security Fixes

### CIR-023 - Tenant-scoped mutation/reread discipline

Scope:
- Add tenant filters to every tenant-owned write and post-write reread found in the review, starting with Quotes, Orders, Invoices, Documents, and Work Orders.
- Keep globally scoped/platform catalog records separate from tenant-owned records; do not blindly add tenant filters to platform-only data.

Known evidence surfaces:
- `backend/app/routers/quotes.py`
- `backend/app/routers/orders.py`
- `backend/app/routers/invoices.py`
- `backend/app/services/documents_service.py`
- `backend/app/services/work_order_service.py`

Acceptance:
- Mutating one tenant's record with another tenant's authenticated user returns 404 or 403 and does not change the source tenant record.
- Post-write rereads use the same tenant scope as the mutation.
- Focused regression tests cover update, delete, and post-write reread paths.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_quotes_ec3.py backend\tests\test_orders_ec3.py backend\tests\test_work_orders_ec5.py -q`
- Add a new focused tenant mutation test file if existing tests become too broad.

### CIR-005 - Atomic single-use token consumption

Scope:
- Consume password reset tokens with one atomic `find_one_and_update` or equivalent conditional update before applying the password change.
- Make portal magic-link consumption return failure when the conditional consume does not modify a row.
- For public write actions, claim/consume single-use tokens before side effects or use an atomic action idempotency guard that prevents duplicate writes.

Known evidence surfaces:
- `backend/app/routers/auth.py`
- `backend/app/services/portal_tokens.py`
- `backend/app/deps_portal.py`
- `backend/app/routers/public_actions.py`

Acceptance:
- Two concurrent reset requests cannot both update the password with the same token.
- Two concurrent magic-link verifications cannot both receive a valid portal session.
- Two concurrent public proof/signature write actions cannot both execute with the same single-use token.
- Multi-use view tokens remain multi-use.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_foundation_hardening.py backend\tests\test_ec6_portal_docs.py -q`
- Add focused concurrency tests for reset, magic link, and public action tokens.

### CIR-004 - Failure-safe Quote-to-Order conversion

Scope:
- Make quote conversion recoverable if order creation, item copy, snapshot creation, audit, or final quote update fails.
- Preserve the existing idempotent concurrent claim behavior.
- Prefer a transaction if the configured MongoDB environment supports it; otherwise use a recoverable conversion state with cleanup/retry semantics.

Known evidence surface:
- `backend/app/services/quote_conversion.py`

Acceptance:
- If order insert fails, quote remains convertible or records a recoverable conversion failure state.
- If item or snapshot copy fails after order insert, retry either completes the same order safely or rolls back incomplete artifacts without duplicate orders/items.
- Concurrent conversion still returns one winning order.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_quotes_ec3.py -q`
- Add failure-injection tests for each mid-conversion failure point.

### CIR-003 - Quote total/item disagreement

Scope:
- Remove or ignore client-supplied document totals on quote create/update.
- Recompute quote document totals from the current revision's line items after every line mutation.
- Preserve intentionally empty/manual draft behavior only if it has an explicit backend-owned placeholder total policy.

Known evidence surfaces:
- `backend/app/routers/quotes.py`
- `frontend/src/pages/QuotesPage.jsx`

Acceptance:
- Creating a quote with `total_cents` in the payload does not persist that client value unless backend line items support it.
- Updating a quote cannot directly alter document totals.
- Existing line-item total tests still pass.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_quotes_ec3.py backend\tests\test_ec9_phase9f_quote_order_integration.py -q`

## Phase 2 - Financial Controls

### CIR-006 - Financial edits to completed/cancelled Orders

Scope:
- Block add/update/delete/reprice operations on Order Items when the parent Order is `completed`, `cancelled`, or `archived`.
- Decide whether `ready` should allow commercial edits; default to blocking if it can affect invoices, Work Orders, or customer-facing totals.

Known evidence surface:
- `backend/app/routers/orders.py`

Acceptance:
- Terminal Orders reject item create/update/delete/reprice requests.
- Nonterminal Orders keep existing behavior.
- Work Order status transitions do not reopen commercial edit windows by accident.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_orders_ec3.py backend\tests\test_work_orders_ec5.py -q`

### CIR-013 - Preserve financial failure history

Scope:
- Replace destructive deletion of payment rows on Stripe-disabled/provider-error paths with failed/non-collectible Payment records and audit entries.
- Preserve retry-safe behavior and idempotency-key semantics.

Known evidence surface:
- `backend/app/services/payment_service.py`

Acceptance:
- A Stripe disabled/provider failure leaves a failed Payment row with failure reason, provider context when available, and no invoice paid balance impact.
- Retrying with the same idempotency key returns or reconciles the failed state intentionally.
- Existing CIR-001 rollback behavior remains intact.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_cir_001_concurrent_invoice_overpayment.py backend\tests\test_payments_ec4.py backend\tests\test_invoice_reconciliation.py -q`

## Phase 3 - Product and Repository Hygiene

### CIR-024 - Product-facing `Job` terminology

Scope:
- Replace visible UI labels such as `Job name` and `Job` with canonical terminology. Candidate labels: `Project name`, `Order name`, or `Title`; choose one and apply consistently.
- Preserve backend field names such as `job_name` only if treated as compatibility storage and not shown as product terminology.
- Expand the terminology guard or add a frontend text regression so product-facing labels do not regress.

Known evidence surfaces:
- `frontend/src/pages/QuotesPage.jsx`
- `frontend/src/pages/OrdersPage.jsx`

Acceptance:
- Product-facing quote/order screens no longer display canonical-prohibited `Job` labels.
- Tests or guard coverage fail if the old labels return in canonical UI paths.

Suggested verification:
- `npm.cmd test -- --runTestsByPath src/__tests__/AppShellNavigation.test.jsx --watchAll=false`
- Add focused frontend assertions for quote/order labels if no existing test covers them.

### CIR-010 - Committed runtime logs

Scope:
- Remove tracked runtime logs from git.
- Ensure ignore rules cover local runtime logs and preview logs.
- Do not delete user-owned logs outside the repo.

Known evidence surfaces:
- `runtime-backend.log`
- `runtime-frontend.log`
- `.gitignore`

Acceptance:
- `git ls-files` no longer includes runtime logs.
- Local runtime logs are ignored after regeneration.

Suggested verification:
- `git status --short`
- `git check-ignore runtime-backend.log runtime-frontend.log`

### CIR-012 - React documentation/dependency reconciliation

Scope:
- Update `frontend/README.md` so it reflects the actual app stack and current React dependency versions.
- Remove stale Create React App boilerplate that conflicts with the repo's actual conventions.

Known evidence surfaces:
- `frontend/package.json`
- `frontend/README.md`

Acceptance:
- Frontend docs accurately state current scripts, React version, and local preview/build commands.
- No dependency changes unless a separate compatibility issue is found.

Suggested verification:
- `npm.cmd run build`

## Phase 4 - Maintainability Split

### CIR-011 - Oversized Webstores files

Scope:
- Split Webstores code by existing behavioral boundaries after safety fixes are stable.
- Start with pure extraction of helpers/services/components without behavior changes.
- Use characterization tests before each split.

Known evidence surfaces:
- `backend/app/services/webstores.py`
- `frontend/src/pages/WebstoreDetailPage.jsx`
- `backend/app/services/webstore_setup.py`
- `backend/app/services/webstore_payments.py`

Acceptance:
- No public API or UI behavior changes during the split.
- Target files are smaller and route/service boundaries are clearer.
- Existing Stage 8 Webstores tests continue to pass.

Suggested verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_webstores_stage8a_order_bridge.py backend\tests\test_webstores_stage8b_orders_projection.py backend\tests\test_webstores_stage8c_production_handoff.py backend\tests\test_webstores_stage8d_reports.py backend\tests\test_webstores_stage8e_lifecycle.py -q`
- Focused frontend tests for the Webstores page area touched by the split.

## Final Owner-Authorized Work

### CIR-020 - Webstore product AI actions

Implemented after explicit owner authorization. The fix proves:

- AI-credit cost is shown before confirmation.
- Entitlement and permission checks are backend-authoritative.
- Generated text/mockups save as reviewable outputs and never overwrite staff work.
- Manual setup remains available.

Verification:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_webstores_cir020_ai_actions.py backend\tests\test_ec16_ai_gateway_metering.py backend\tests\test_ec17_generated_assets.py -q` (9 passed).
- `cd frontend; npm.cmd test -- --runTestsByPath src/__tests__/WebstoresStage4AProductFoundation.test.jsx --watchAll=false` (6 passed).
- `backend\.venv\Scripts\python.exe -m compileall backend\app\services\webstores.py backend\app\routers\webstores.py`.

## Recommended Implementation Order

1. CIR-023 tenant-scoped operation discipline.
2. CIR-005 atomic single-use token consumption.
3. CIR-004 failure-safe quote conversion.
4. CIR-003 backend-derived quote totals.
5. CIR-006 terminal Order edit guard.
6. CIR-013 financial failure record preservation.
7. CIR-024 terminology cleanup.
8. CIR-010 runtime log cleanup.
9. CIR-012 frontend README reconciliation.
10. CIR-011 Webstores split.
11. CIR-020 Webstore AI preview-confirm flow.

## Final Closure Criteria

- Every Open or Deferred CIR item becomes Fixed / Verified with exact test evidence, unless a later owner-approved stop rule is added.
- `memory/code_issue_register.md` is updated only after each fix is implemented and verified.
- New regression tests are focused on the corrected failure mode.
- The branch stays clean except for intentional code, test, and documentation changes.
