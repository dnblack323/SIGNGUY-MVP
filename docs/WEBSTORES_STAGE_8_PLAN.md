# Webstores Stage 8 Plan

Status: Stage 8A through 8E implemented locally on `feature/webstores-stage-8-orders-production-reports-relaunch`; checkpoint commit pending separate instruction.

Repository: `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP`

Primary specification: `C:\Users\thesi\OneDrive\ORGANIZED SIGNGUYAI\SignGuy_AI_Phase_6_Webstores_Add_On_Specification.docx`

Stage 8 scope: Orders, Production, reports, and relaunch behavior for Webstores.

Current checkpoint: All Stage 8 checkpoints are implemented locally. The branch
is ready for focused verification and a separate Stage 8 checkpoint review.

This plan follows the Phase 6 Webstores add-on specification and keeps the MVP as
the implementation authority. It does not authorize Stage 9 work, a new order
system, a second production system, or any product-facing "Order Portal"
terminology.

## Current checkpoint

The current checkout is `feature/webstores-stage-8-orders-production-reports-relaunch`
with local, uncommitted Stage 8 changes. Stage 7 was integrated before this
branch began. This planning document does not stage, commit, or modify those
changes.

Stage 7 already provides the relevant handoff records and provider evidence:

- `WebstorePurchaseIntent` contains the immutable checkout snapshot and links to
  canonical Customer, Order, and Payment records when downstream creation is
  enabled.
- `WebstorePaymentEvent` preserves verified provider evidence and processing
  state.
- `WebstorePurchaseIntent` also carries `production_bridge_status` and
  `work_order_id` for the production handoff.
- `WebstoreBuyerOrder` remains a legacy compatibility record. Stage 8 must not
  make it a second order authority.

## Authority and reuse rules

### Current MVP: implementation authority

Reuse and extend these existing contracts in place:

- `backend/app/models/order.py` for canonical `Order` and `OrderItem` records.
- `backend/app/models/payment.py` and `backend/app/services/payment_service.py`
  for canonical payment and refund behavior.
- `backend/app/models/work_order.py` and
  `backend/app/services/work_order_service.py` for Work Orders, immutable item
  snapshots, versioning, transitions, assignments, and audit records.
- `backend/app/services/production_board_service.py`,
  `backend/app/services/production_stage_service.py`, and the existing
  production routers for employee and shop production views.
- `backend/app/services/reports_service.py` and
  `backend/app/services/report_export.py` for tenant-scoped reporting and
  exports.
- `backend/app/models/webstore.py`, `backend/app/services/webstores.py`,
  `backend/app/services/webstore_payments.py`, and the existing Webstore
  routers for purchase-intent, lifecycle, payment-event, activity, and
  Webstore scope.
- Existing Customer, tenant permission, Notifications, Activity/Audit, DocuLink,
  and Settings services.

No second Customer, Order, Order Item, Payment, refund, Work Order, production,
reporting, document, notification, or permission system is permitted.

### Original repository: read-only evidence

Inspected donor files:

- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\stripe_connect.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\services\stripe_service.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\webstore_owners.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\webstores.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\models\orders.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\models\webstores.py`

Reuse decision:

- Reuse the provider interaction concepts: Connect onboarding, refresh/login
  behavior, owner-facing status, and clear separation between provider state
  and application state.
- Reuse terminology or UX ideas only where they fit the current MVP contracts.
- Do not copy code or records from `webstores_v2`, legacy buyer-order flows,
  legacy payout counters, job-ticket data, or legacy production collections.
- Do not copy the donor's owner or Stripe authorization assumptions. The MVP's
  tenant permissions, provider authority checks, and server-side scopes remain
  authoritative.

### Rebuild repository: read-only evidence

Inspected donor files:

- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\backend\models\orders.py`
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\backend\repositories\orders.py`
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\backend\routes\orders.py`
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\backend\models\webstores.py`
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\backend\services\webstore_service.py`
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version\frontend\src\components\webstores\WebstoresWorkspace.js`

Reuse decision:

- Reuse generic workflow ideas for order lists, order-item production details,
  production summaries, event history, and operational dashboard grouping only
  after mapping them to the MVP's canonical records.
- Use the rebuild repository's order repository as a comparison checklist for
  missing read models, not as an implementation donor.
- Do not copy its preview-only launch readiness, standalone capability model,
  `work_order_drafts`, or in-memory/legacy order projections into the MVP.
- Do not copy its "Order Portal" naming. The product name is Webstores.

## Phase 6 requirements carried into Stage 8

The specification requires:

- A successful, verified provider event creates or reuses exactly one canonical
  Customer, one canonical Order, and canonical Order Items through one
  controlled bridge. A browser success redirect never creates an Order.
- Each Order Item stores an immutable checkout snapshot: Webstore, product and
  variant identity, public title, selected options, quantity, public price,
  discounts/tax allocation, image reference, and production mapping.
- Public shoppers see only public storefront, cart, checkout, and their own
  safe confirmation. They never see costs, margins, supplier costs, internal
  notes, production instructions, owner share, or Stripe account details.
- Production receives Webstore-originated Order Items through the existing
  canonical Work Order and production services.
- Closing a Webstore stops new checkout but preserves prior orders and safe
  confirmation access. Archive hides internal lists without deleting history.
- Relaunch is a validated lifecycle action. It must re-check current catalog,
  branding, owner approval, payment authority, dates/deadlines, and any changed
  post-approval material. It must not silently rewrite prior orders.
- Material order, payment, refund, fulfillment, lifecycle, payout, and launch
  actions emit Activity/Audit records.
- Store-type behavior remains configuration-driven. Stage 8 does not create
  separate implementations for B2B, Fundraiser, Event, Promotional, Employee,
  or General Webstores.

## Stage 8 sequence

### 8A. Canonical paid Webstore-to-Order bridge

Goal: make the verified-payment handoff complete, replay-safe, and canonical.

Work:

- Use the existing `WebstorePurchaseIntent` as the handoff key and its
  immutable snapshot as the only source for Order totals and line items.
- Upsert the Customer by tenant and normalized customer identity without
  creating duplicate customers on webhook replay.
- Create or reuse the canonical Order and Order Items by purchase intent and
  provider payment identity. Never create a separate Webstore Order.
- Copy public checkout data into immutable Order Item snapshots. Keep production
  mapping and internal instructions server-controlled.
- Create or reconcile the canonical Payment only after verified provider
  evidence. Preserve failed and late provider events.
- Make the bridge resumable when payment processing fails after one downstream
  record is created. A retry must finish the missing records rather than create
  another graph.
- Store the canonical IDs back on the purchase intent and payment event.
- Add a controlled internal recovery/replay action with permission and audit
  evidence; it must not trust browser success state.

Acceptance gate:

- Duplicate browser attempts, duplicate webhooks, delayed webhooks, and retries
  produce one Customer, one Order, one set of Order Items, and one Payment.
- Historical snapshots remain unchanged after a product, variant, price,
  promotion, or Webstore setting changes.
- Tenant and Webstore scope is checked on every lookup and mutation.

### 8B. Webstore Orders projection and staff/owner views

Goal: expose Webstore orders without introducing a Webstore-specific order model.

Work:

- Add the Webstore order view under `/api/webstores/:storeId/orders` as a
  filtered projection of canonical Orders, Order Items, Payments, and safe
  Webstore metadata.
- Add the Webstore detail Orders view using the existing four-tab Webstore
  navigation pattern. Do not add a second top-level workspace.
- Show staff the operational fields required to process the order, including
  item snapshots, fulfillment choice, customer contact, payment state, and
  production state.
- Show owners only permitted sales, refund, fee, and payout status summaries.
  Do not expose internal cost, margin, supplier, production, or Stripe account
  details.
- Keep customer confirmation access limited to the confirmation token/reference
  for that purchase; never allow an arbitrary Order ID to be used as a public
  lookup.
- Enforce Webstore assignment and restricted-store permissions server-side.

Acceptance gate:

- Staff can locate only orders for stores they can access.
- Owners cannot change or read another owner's store.
- Public responses contain only the safe receipt/confirmation DTO.

### 8C. Production and fulfillment handoff

Goal: route Webstore Order Items into the existing production workflow.

Work:

- Use `work_order_service.generate` for production-required Order Items and
  preserve the Work Order item snapshot.
- Use the existing Work Order lifecycle, production board, production stages,
  assignment, notifications, and DocuLink attachment links.
- Attach Webstore, canonical Order, and Order Item references to the existing
  Work Order metadata or snapshot fields; do not add a Webstore-only production
  collection.
- Carry only server-approved production mappings, quantities, artwork references,
  and production notes from the immutable checkout/product snapshot.
- Make generation idempotent and concurrency-safe so one paid Order cannot
  create multiple current Work Orders.
- Define deliberate behavior for non-production items, unavailable products,
  late deadlines, cancellations, refunds, and partial fulfillment.

Acceptance gate:

- Production sees Webstore-originated Order Items in the existing production
  board and can progress them through the existing Work Order states.
- A deleted or edited product cannot rewrite an existing Work Order snapshot.
- A refund or cancellation does not delete production history; it creates the
  required status transition and audit record.

### 8D. Operational reports and payout projections

Goal: add Webstore filters and safe projections to existing reports.

Work:

- Extend `reports_service` queries to filter canonical Orders, Order Items,
  Payments, refunds, production status, and Webstore IDs.
- Provide manager metrics for order count, paid/failed/refunded totals,
  fulfillment status, production load, product quantities, and deadline risk.
- Provide owner-safe gross, refunds, provider fees, and payout pending/status
  values from provider-authoritative records. Do not invent a local payout
  balance or profit value.
- Retain the existing distinction between actual financial records and estimated
  production cost/margin fields. Label estimates clearly if displayed internally.
- Keep report exports tenant-scoped, Webstore-scoped, and permission-checked.
- Project payout and transfer status from verified Stripe events and existing
  financial records; preserve event history for failures and disputes.

Acceptance gate:

- A report can be reconciled to canonical Orders, Payments, refunds, and
  provider events.
- Owner views do not expose protected shop or production data.
- Failed financial records remain available for audit and reporting.

### 8E. Close, archive, and relaunch

Goal: make the post-launch lifecycle safe and reversible without rewriting history.

Work:

- Enforce the Phase 6 lifecycle transitions and computed readiness checks for
  close, archive, pause, and relaunch.
- Closing/pausing blocks new checkout and new purchase intents while preserving
  existing orders, payment records, Work Orders, messages, and confirmation
  references.
- Define the deadline rule for carts, checkout sessions, late provider events,
  and already-paid orders.
- Archive only removes the Webstore from applicable internal active lists; it
  does not delete financial, order, production, form, or audit history.
- Relaunch creates a new audited lifecycle event and re-evaluates catalog
  completeness, owner approval/version, branding, payment authority, dates, and
  public visibility. It does not silently relaunch an unapproved changed
  catalog.
- Revoke or rotate public QR/links only through the existing Webstore lifecycle
  and public-link controls; do not break safe historical confirmations.

Acceptance gate:

- Closed and archived stores cannot accept new checkout.
- Existing customers can still reach the safe confirmation for their own paid
  purchase when policy allows.
- Relaunch is blocked until the current readiness evidence passes and is audited.

## Dependencies and issue-register gates

These existing issues must be resolved or explicitly gated before the affected
Stage 8 checkpoint. This plan does not silently close them:

- CIR-002: incomplete Stripe webhook reconciliation. Gate 8A and 8D.
- CIR-003: quote total/item disagreement. Gate any path that reuses quote
  conversion or reports quote-derived totals.
- CIR-004: failure-unsafe quote conversion. Do not use quote conversion as a
  Webstore bridge until its transaction boundary is safe.
- CIR-006: financial edits to completed/cancelled Orders. Gate order/refund
  actions and historical snapshot protection.
- CIR-007: duplicate current Work Orders under concurrency. Gate 8C.
- CIR-008: missing restricted-store access enforcement. Gate 8B and public
  confirmation access.
- CIR-009: manufactured lifecycle milestone states. Gate 8E.
- CIR-013: deleted financial failure records instead of preserved audit history.
  Gate 8A and 8D.
- CIR-011: oversized Webstores files is a maintainability risk. Do not perform
  an unrelated refactor during Stage 8; split only when a touched boundary needs
  it and preserve behavior.

The Stage 7 local checkpoint must also be committed separately before Stage 8
implementation begins. No Stage 8 work should be mixed into that commit.

## Focused verification strategy

No full repository suite is planned. Each implementation checkpoint gets only
the focused tests needed for its changed contracts:

- 8A backend: duplicate/replayed webhook, partial failure recovery, immutable
  Order Item snapshot, Customer/Order/Payment linkage, amount/currency/provider
  authority, tenant isolation, and preserved financial failure records.
- 8B backend/frontend: Webstore order projection, assignment permissions,
  owner-safe fields, public confirmation scope, and four-tab navigation.
- 8C backend: one current Work Order under concurrency, production-required item
  selection, snapshot preservation, refund/cancellation behavior, and existing
  production board visibility.
- 8D backend/frontend: Webstore filters, report-to-canonical-record
  reconciliation, owner-safe payout fields, and export scope.
- 8E backend/frontend: close/pause/archive checkout blocking, historical
  confirmation access, deadline handling, relaunch readiness, and lifecycle
  activity records.

For each checkpoint, run the focused backend tests, the affected focused
frontend tests, a touched-module compile/build check where applicable, and
`git diff --check`. Do not run broad tests merely because a Webstore file was
touched.

## Explicit non-goals

- No new Webstore Order, Buyer Order, payout ledger, customer, invoice, or
  production model.
- No copying or modifying donor repositories.
- No Client Design or Training form adapters; the shared Form Maker remains the
  existing canonical system for those future consumers.
- No public exposure of costs, margins, supplier data, internal notes,
  production instructions, owner share, or Stripe account details.
- No automatic product, pricing, catalog, or branding changes during relaunch.
- No use of "Order Portal" as a product name or user-facing label.
- No Stage 9 features beyond the Phase 6 Webstores requirements.

## Proposed checkpoint order

1. 8A: canonical paid Webstore-to-Order bridge and recovery.
2. 8B: Webstore Orders projection and access-safe views.
3. 8C: Work Order and production handoff.
4. 8D: Webstore operational reports and payout projections.
5. 8E: close, archive, deadline, and relaunch behavior.

Each checkpoint is reviewed and committed separately. Stage 8 is complete only
when all five gates pass and the Phase 6 acceptance scenarios for tenant
isolation, duplicate checkout, historical snapshots, production visibility,
refunds, closed stores, owner privacy, and relaunch are proven by focused tests.
