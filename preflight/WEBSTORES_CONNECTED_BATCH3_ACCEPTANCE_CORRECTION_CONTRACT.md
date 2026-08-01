# Webstores Connected Batch 3 Acceptance Correction Contract

Status: Stripe-ready foundation correction implemented for independent re-audit. Live Stripe integration remains deferred by owner decision.

## Starting state

- Repository: `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP`
- Starting commit: `1e5f61cfc5d208e1d703cf752e07259bd47d91d8`
- Correction branch: `fix/webstores-batch-3-acceptance`
- Existing untracked files preserved and excluded from this correction:
  - `preflight/WEBSTORES_STAGE3_BRANDING_IMPLEMENTATION_CONTRACT.md`
  - `runtime-backend.log`
  - `runtime-frontend.log`

## Findings corrected

The formal Batch 3 audit found a local-only checkout, development-only webhook authority, stored payment-readiness claims, live-launch risk, incomplete provider reconciliation, fake-provider conversion risk, and missing provider-ready handoff evidence. This correction removes the local checkout authority and makes every provider-dependent path fail closed while preserving setup, catalog, branding, packet, approval, Terms, preview, and canonical-entity boundaries.

## Authority

Found:

- `specs_pack/extracted/EC14_Webstores_Master_Specification.docx`
- `preflight/EC14_WEBSTORES_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `docs/modules/ec14_webstores.md`
- `evidence/EC14_IMPLEMENTATION_COMPLETION_REPORT.md`
- `C:\Users\thesi\OneDrive\ORGANIZED SIGNGUYAI\SignGuy_AI_Webstores_Final_Consolidated_Specification.docx`
- `C:\Users\thesi\OneDrive\ORGANIZED SIGNGUYAI\SignGuy_AI_Phase_6_Webstores_Add_On_Specification.docx`

Still missing and not reconstructed:

- `WEBSTORES_REUSE_INVESTIGATION_REPORT.md`
- `WEBSTORES_PORT_SOURCE_DECISION_CONTRACT.md`
- The original Connected Batch 3 implementation contract.

## Owner decision relied upon

The owner authorized a Stripe-ready foundation and explicitly deferred the real Stripe integration until the application is otherwise complete and returned to Emergent. The final Stripe charge model remains deferred; this branch must not select direct charges, destination charges, or separate charges and transfers.

Locked decisions retained here:

- Webstore Owners or clients will eventually receive their appropriate share through Stripe Connect.
- The sign shop must not become an informal payment middleman.
- SignGuy AI must not invent or maintain a private stored-money balance.
- Production allocation, owner/fundraiser share, platform fee, taxes, refunds, and related amounts remain explicit immutable integer-cent snapshots.
- The version-one SignGuy transaction-fee default is 0%.
- Optional shop-created Webstore management fees remain separate from SignGuy platform fees.

## Authorized architecture

This branch adds one provider boundary with a typed disabled implementation. The provider boundary owns future onboarding, account status, readiness synchronization, Checkout Session creation/retrieval, payment verification, webhook verification/parsing, refunds, transfers/payouts, disputes, and provider-event reconciliation. Typed provider-authoritative fixtures are accepted only by internal service injection for tests; no deployed route can select them. The disabled implementation returns `PAYMENT_PROVIDER_NOT_CONFIGURED` and performs no network call or database money mutation.

Stored Webstore flags never establish provider-authoritative readiness. Public checkout and live launch remain unavailable while `STRIPE_ENABLED=false`, the charge model is `deferred`, credentials are incomplete, or the provider adapter is absent.

## Boundaries

- No live Stripe SDK/API call.
- No Stripe credential requirement.
- No provider-specific charge routing selected.
- No fake checkout session, fake payment, fake webhook authority, or fake paid Order.
- No second Customer, Order, Payment, ledger, refund, or Production system.
- No private balance or withdrawable-balance behavior.
- Existing EC4 Stripe Core remains separate.
- Existing Webstore setup/catalog/branding/packet/approval/Terms/preview behavior remains available.

## Persistence

Existing Mongo documents receive additive provider, readiness, checkout-attempt, reconciliation, recovery, allocation-snapshot, provider-event sequence, and allowlisted provider-reference fields through the existing model/index path. No destructive migration or applied migration edit is required. Raw provider payload retention remains outside this foundation; payment events persist no raw payload from the provider boundary.

## Stop conditions

Stop without claiming commerce readiness if the future implementation would require choosing the deferred charge model, enabling live money movement, treating a database flag as provider authority, creating fake paid records, introducing a duplicate commerce system, or changing canonical Orders, Payments, or Production.

## Verification and acceptance

Required verification includes focused Webstore/provider/configuration tests, existing Webstore setup and preview tests, existing non-Webstore payment/order tests, frontend Webstore tests, backend compile/import validation, frontend production build, secret/generated-file scans, and diff review. The original 80 connected-payment browser checks are intentionally deferred and must be rerun only after Emergent supplies the approved Stripe adapter and test-mode acceptance environment.

This branch is not accepted production commerce and must not be merged into `main` until the later Stripe integration and separate acceptance pass.
