# EC14 Webstores Runtime Contracts

**Status:** IMPLEMENTED - awaiting final CI confirmation
**Checkpoint:** EC14 Webstores
**Primary routes:** `/api/webstores`, `/api/portal/webstores`, `/api/public/webstores`

## Boundaries

Webstores are implemented as one shared core with staff, owner-portal, and public storefront adapters. The module does not implement EC15 Wrap Lab, EC16-EC18 AI/provider execution, EC19 onboarding/help, EC4 invoice/payment mutations, EC13 subscription changes, or live Stripe provider calls.

## Canonical Backend Collections

- `webstore_owners`
- `webstores`
- `webstore_product_templates`
- `webstore_products`
- `webstore_questionnaire_submissions`
- `webstore_artwork_files`
- `webstore_mockups`
- `webstore_launch_packets`
- `webstore_buyer_orders`
- `webstore_ledger_entries`
- `webstore_activity_events`
- `webstore_ai_usage_events`
- `webstore_stripe_connect_records`

All collections are tenant-scoped except public storefront lookup, which resolves a Live Webstore by slug and then enforces that only public product data is serialized.

## Money and Ledger Rules

- Product sale prices, production cost estimates, owner share, fees, shipping, donation, tax, and totals are integer cents.
- Buyer order totals are calculated server-side from current public active Webstore products.
- EC14 buyer order capture does not create or mutate EC4 invoices or payments.
- Webstore platform-fee ledger entries are immutable snapshots.
- Full or partial platform-fee refunds create separate proportional reversal rows with `reversal_of_ledger_entry_id`; the original fee row is never modified or deleted.

## Launch and Checkout Gates

Launch requires:

- Active `webstores` EC2 entitlement.
- Store is not closed or archived.
- At least one active public product with a positive integer-cent selling price.
- Public name/slug.
- Launch packet.
- Owner approval.
- Terms and fee acknowledgement.
- Webstore payment boundary marked ready.

Public checkout requires the Webstore to be Live and checkout-enabled. Archived, closed, inactive, unavailable, private, or zero-priced products are rejected server-side.

## Portal and Permission Rules

- Staff APIs require `webstore:read`, `webstore:write`, or `webstore:manage`.
- Staff APIs still reject portal tokens through the existing EC6 staff dependency.
- Webstore owner/manager portal identities extend the existing `portal_identities` collection additively.
- Webstore owner portal routes require `portal_type` of `webstore_owner` or `webstore_manager` plus Webstore portal permissions.
- Owner portal access is scoped to the identity's `webstore_owner_id`.
- Customer and employee portal identities cannot satisfy Webstore owner portal routes.

## Stripe Boundary

`webstore_stripe_connect_records` captures local-only account/onboarding/checkout boundary records. EC14 does not call Stripe APIs, create live Checkout Sessions, process webhooks, or use EC13 Stripe Billing records for Webstore buyer orders.

## Order Bridge

Buyer orders can be bridged idempotently into canonical `orders` and `order_items`. The bridge:

- Creates or reuses a buyer Customer by tenant/email.
- Creates a confirmed canonical Order.
- Creates Order Items with Webstore pricing snapshots.
- Stores `bridged_order_id` and `bridge_status` on the buyer order.
- Returns the existing bridged Order on repeat calls.
