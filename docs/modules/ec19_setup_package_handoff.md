# EC19 Setup Package Handoff

EC19 reads EC13 setup-package purchase records and stores onboarding handoff status. It does not create or change checkout sessions.

## Source Of Truth

- EC13 `setup_package_purchases` remains authoritative for package key, amount, currency, payment/waiver/refund/fulfillment state, and checkout linkage.
- EC19 only updates `ec19_handoff_status` and `ec19_handoff_notes`.

## Supported Handoff States

- `not_started`
- `ready_for_intake`
- `in_progress`
- `blocked`
- `complete`

## Boundaries

- No Stripe API calls.
- No checkout sessions.
- No setup-package pricing changes.
- No subscription, billing portal, webhook, or invoice/payment mutation.
- No EC20 platform support-console work.

## Frontend

The onboarding dashboard shows the latest setup-package handoff state and lets owner/admin users mark a paid or waived setup package ready for onboarding intake.
