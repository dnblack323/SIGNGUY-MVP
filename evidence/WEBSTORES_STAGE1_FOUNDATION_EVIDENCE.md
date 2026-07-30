# Webstores Stage 1 Foundation Evidence

Status: ACCEPTANCE REVIEW CORRECTION APPLIED

Branch: `feature/webstores-phase-6`

## Owner Decisions Applied

- New public purchases create `webstore_purchase_intents`, not unpaid `webstore_buyer_orders`.
- Existing `webstore_buyer_orders` are legacy compatibility records and cannot bridge to canonical Orders without verified payment evidence.
- `public_slug` is globally unique and separate from the tenant-local internal `slug`.
- Donations are disabled during Stage 1.
- Verified-payment processing is internal, provider-neutral, idempotent, and has no public fake-payment route.
- Payment readiness is computed and remains false until a real verified provider connection exists.
- Official Webstore types are `B2B`, `Fundraiser`, `Event`, `Promotional`, `Employee`, and `General`.

## Implemented Contracts

- Public storefront lookup uses `public_slug` and does not use tenant-local `slug`.
- Public purchase-intent totals are calculated server-side from active public products.
- Public buyer-supplied shipping, tax, discounts, donations, fees, subtotals, or final totals are rejected by the service contract or safely ignored at the public request schema.
- Purchase-intent creation does not create canonical Customers, Orders, Order Items, Payments, buyer orders, or ledger rows.
- Verified internal payment events create or reuse the canonical Customer, then create the canonical Order, Order Items, and Payment exactly once.
- Duplicate verified events and duplicate provider payment references return already-processed canonical record references.
- Webstore-created canonical Orders and Order Items carry stable `source_type` and `source_id` fields, with unique tenant-scoped partial indexes preventing duplicate canonical records for one purchase intent.
- Amount or currency mismatch records a failed event and creates no canonical commerce records.
- Store Owner portal access remains owner-scoped; Store Manager portal access requires an assigned Webstore and is limited to that Webstore.
- Public and Store Owner responses use explicit allowlists to avoid exposing tenant data, production costs, margins, supplier notes, staff notes, or platform-only fields.
- Lifecycle updates validate allowed state transitions.
- Placeholder checkout URLs and manual payment-readiness controls are disabled or removed.

## Deferred

- Real Stripe Checkout Sessions.
- Stripe webhook signature verification.
- Stripe Connect payouts, disputes, refunds, and payout reporting.
- Donation eligibility, limits, increments, and provider-backed collection.
- Storefront cart redesign, branding builder, setup wizard, Launch Packet expansion, catalog improvements, AI actions, Webstore payout analytics, and later Webstores stages.
- Automatic migration or deletion of legacy `webstore_buyer_orders`.

## Verification

- Stage 1 backend tests: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_webstores_stage1_foundation.py -q` -> `9 passed, 6 warnings`.
- Combined affected backend regressions: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_webstores_stage1_foundation.py backend/tests/test_ec14_webstores.py backend/tests/test_record_numbering_checkpoint.py backend/tests/test_entitlements.py backend/tests/test_ec2_permissions.py backend/tests/test_permissions_scope.py backend/tests/test_report_builder_complete_system.py -q` -> `48 passed, 6 warnings`.
- Focused frontend tests: `npm.cmd test -- --runTestsByPath src/__tests__/WebstoresStage1.test.jsx src/__tests__/ReportsPageComplete.test.jsx --watchAll=false` -> `2 suites passed, 7 tests passed`.
- Frontend production build: `npm.cmd run build` -> compiled successfully.
- Backend compile/import validation: `backend/.venv/Scripts/python.exe -m compileall -q backend/app backend/tests/test_webstores_stage1_foundation.py` -> passed.
- `git diff --check` -> passed with CRLF conversion warnings only.
