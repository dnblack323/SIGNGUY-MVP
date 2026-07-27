# Record Numbering Checkpoint Evidence

Date: 2026-07-27
Branch: `main`
Starting commit: `90bfbe2c07590c0b339d0ef2cd2dac700010a3e8`

## Starting Repository State

- Active branch: `main`.
- Local HEAD: `90bfbe2c07590c0b339d0ef2cd2dac700010a3e8`.
- `origin/main`: `90bfbe2c07590c0b339d0ef2cd2dac700010a3e8`.
- Working tree before edits: clean except ignored local runtime/environment paths.
- Ignored local paths observed: `backend/.data/`, `backend/.env`, `frontend/.env`, `frontend/build/`.

## Implemented Scope

- Added canonical tenant-scoped record-numbering contracts and allocation service.
- Preserved existing `next_number()` compatibility for existing numbered records.
- Added immutable allocation evidence for sequence issuance.
- Added optional customer, payment/refund, and webstore buyer-order record numbers.
- Added legacy-safe partial unique indexes for optional number fields.
- Added deterministic backfill helper; no automatic startup backfill is run.

## Integrated Record Types

- Already numbered, now backed by canonical allocation evidence: quotes, orders, invoices, work orders, purchase orders, expenses, proofs, signature requests, public quote requests, intake submissions.
- Newly numbered: customers, payments, refunds, webstore buyer orders.

## Deferred or Not Applicable

- Credit memos: deferred because no standalone credit memo implementation exists.
- Order items: not applicable because order-item line position and parent order remain authoritative.
- Control Center numbering configuration UI: deferred.
- Platform Administration controls: deferred.

## Verification Results

| Command | Result |
|---|---|
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_record_numbering_checkpoint.py` | `7 passed, 6 warnings` |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_record_numbering_checkpoint.py backend/tests/test_quotes_ec3.py backend/tests/test_orders_ec3.py backend/tests/test_invoice_reconciliation.py backend/tests/test_payments_ec4.py backend/tests/test_work_orders_ec5.py backend/tests/test_ec14_webstores.py backend/tests/test_ec7_expenses.py backend/tests/test_ec7_finance.py backend/tests/test_ec7_reports.py` | `71 passed, 6 warnings` |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests` | `848 passed, 3 skipped, 6 warnings` |
| `yarn.cmd test --watchAll=false` from `frontend/` | `16 passed, 16 total suites`; `70 passed, 70 total tests` |
| `yarn.cmd build` from `frontend/` | Compiled successfully; Node emitted existing `DEP0176` deprecation warning |
| `backend\.venv\Scripts\python.exe -m compileall -q backend/app` | Passed; `290` Python files counted |
| `git diff --check` | Passed with CRLF conversion warnings only |

PowerShell blocked the `yarn.ps1` shim under the local execution policy. Verification used `yarn.cmd`, which required no policy change.

## Protected File Check

Protected Banner calculator files are not part of this checkpoint and must remain unchanged:

- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/starter_defaults.py`
- `backend/tests/test_banner_pricing_owner_decisions.py`
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/components/pricing/CategorySpecificFields.jsx`
- `frontend/src/pages/PricingCalculatorPage.jsx`

`git diff --name-only -- <protected files>` returned no changed protected Banner files.

## Final Diff Scope

- `backend/app/core/db.py`
- `backend/app/models/customer.py`
- `backend/app/models/payment.py`
- `backend/app/models/record_numbering.py`
- `backend/app/models/webstore.py`
- `backend/app/routers/customers.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/sequence.py`
- `backend/app/services/webstores.py`
- `backend/tests/test_record_numbering_checkpoint.py`
- `evidence/RECORD_NUMBERING_CHECKPOINT_EVIDENCE.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/PRD.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `preflight/RECORD_NUMBERING_CHECKPOINT_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`

No frontend source files, build artifacts, runtime data, local environment files, secrets, pricing calculator files, or unrelated checkpoint files are included.

## Remaining Risks

- Existing legacy rows without optional numbers remain readable and require a deliberate owner-approved backfill run before user-facing display consistency can be guaranteed across old data.
- Owner-facing prefix, padding, suffix, date component, reset policy, and preview controls remain future Control Center work.
- Gaps are intentionally possible after a number has been issued and a downstream create fails; this is recorded as the permanent no-reuse policy.
