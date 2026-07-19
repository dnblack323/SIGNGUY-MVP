# EC14 Webstores Implementation Report

**Status:** IMPLEMENTED - awaiting GitHub CI before checkpoint closure
**Date:** 2026-07-19
**Branch:** `CODEX-EC14-BRANCH`
**Documentation preflight commit:** `1acb3a711505a563e94e8f4b9812760787815560`

## Implemented

- Canonical Webstores backend models, repository helpers, services, and routes.
- Webstore owner portal identity extensions over the existing EC6 Portal Identity system.
- Staff Webstores manager APIs and frontend workspace.
- Webstore owner portal routes and frontend page.
- Public storefront and buyer-order capture.
- Integer-cent buyer totals and Webstore ledger entries.
- Immutable Webstore platform-fee snapshot and proportional reversal contract.
- Local-only Stripe Connect boundary records.
- Idempotent bridge from Webstore buyer orders to canonical Orders/Order Items.
- EC14 Mongo indexes.
- Targeted EC14 backend tests.
- Webstores navigation enablement.

## Explicitly Not Started

- EC15 Wrap Lab.
- EC16-EC18 live AI/provider execution, AI gateway, AI credits, or generated asset billing.
- EC19 onboarding/help.
- Live Stripe Connect provider calls, webhooks, billing portal, or Checkout Sessions.
- EC4 customer invoice/payment changes.
- EC13 subscription entitlement mutation changes.
- Webstore payout execution beyond ledger contract records.

## Local Verification

- Backend compile: `python -m compileall backend/app backend/tests/test_ec14_webstores.py` passed with bundled Python runtime.
- Backend import: `import server` passed with test env vars.
- Frontend production build: `npm.cmd run build` passed.
- Targeted pytest command was attempted with bundled Python and repo-local `--basetemp`; collection reached Mongo setup but local MongoDB was not running on `localhost:27017`, so tests could not execute locally in this shell.

## Pending Closure Gate

EC14 must not be marked COMPLETE - CLOSED until the implementation commit is pushed and GitHub CI passes.
