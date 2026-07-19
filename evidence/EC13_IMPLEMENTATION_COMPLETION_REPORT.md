# EC13 Implementation Evidence

**Status:** IMPLEMENTED - PENDING GITHUB CI.
**Branch:** `CODEX-ec13-branch`
**Date:** 2026-07-19
**Phase 13A documentation commit:** `355547babe4290bfa2274e29ba018bedda66e509`
**Phase 13A implementation commit:** `d5c545fe256d66fd9d7f798e834efa895160f00e`
**Implementation commit:** pending
**GitHub CI run:** pending

## Implemented Scope

- Commercial billing catalog and core contracts from Phase 13A.
- Tenant billing account runtime.
- Tenant subscription runtime.
- Free trial and paid extended-trial billing records.
- Setup package checkout, paid state, and platform-admin waiver records.
- Checkout session idempotency records.
- Billing Portal session audit records.
- Stripe Billing boundary and separate Stripe Billing webhook route.
- EC13-derived EC2 entitlement projection.
- Day-based dunning state and platform-admin manual grace/suspension actions.
- Platform-fee assessment from EC4 payment facts into immutable EC13 fee snapshots.
- Required runtime MongoDB indexes.
- Targeted backend tests for EC13 runtime behavior.
- EC13 runtime documentation.

## Explicit Non-Scope Preserved

- No EC14 Webstore commerce, Stripe Connect, buyer order, or payout implementation.
- No EC15 Wrap Lab implementation.
- No EC16 AI usage, provider-cost, or credit ledger implementation.
- No EC19 guided onboarding/checklist/help implementation.
- No EC20 broad platform admin cockpit or analytics implementation.
- No EC21 marketing website, public pricing page, signup UI, or Founder offer page implementation.
- No mutation of EC4 customer invoice/payment semantics.
- No replacement or silent mutation of EC12 explicit Founder access.
- No external SMS/MMS sending or pricing.
- No Smart Pricing paid add-on SKU.

## Local Validation

Passed:

- `python -m compileall backend\app backend\tests\test_ec13_phase13a_commercial_catalog.py backend\tests\test_ec13_commercial_billing_rest.py`
- `python -c "import server; print('server import ok')"` from `backend/`
- `git diff --check`

Blocked locally:

- `python -m pytest backend\tests\test_ec13_phase13a_commercial_catalog.py backend\tests\test_ec13_commercial_billing_rest.py -q --basetemp=.pytest_tmp_ec13_rest`

Reason:

- Local `localhost:27017` MongoDB is not running.
- No local `mongod` executable was found.
- No local Docker executable was found.
- GitHub Actions provisions MongoDB through `.github/workflows/ci.yml`.

## CI

Pending after implementation push.

EC13 must not be marked COMPLETE until the pushed branch-head CI run passes.

