# Webstores Stage 6 Implementation Plan

**Product sequence:** Webstores Stage 6
**Stage name:** Public Storefront and Server-Priced Cart
**Status:** `PLANNED - IMPLEMENTATION NOT STARTED`
**Baseline commit:** `18b8ad1946c6bfe3b8844d6ab4916ec24670f376`
**Planning branch:** `plan/webstores-stage-6-storefront-cart`

## A. Planning Identity and Authority

This document defines Webstores Stage 6 in the independent Webstores
product-stage sequence. Webstores Stage 6 is not an EC checkpoint and must not
be mapped to an older master-build stage with the same number. Webstores Stage 6
ends at a complete, server-priced cart.
Checkout, payment collection, paid order creation, payouts, Orders-module
integration, and Production handoff begin in Webstores Stage 7 or later.

Authority order for this checkpoint:

1. The locked owner decisions in the Stage 6 planning authorization.
2. This document after approval.
3. `preflight/WEBSTORES_PHASE6_REMAINING_APP_PLAN.md` for the staged Webstores roadmap.
4. `preflight/WEBSTORES_STRIPE_DEFERRED_INTEGRATION_DECISION.md` for the deferred provider boundary.
5. Current Stage 1-5 implementation, contracts, tests, and issue records.
6. Historical Webstores documents and donor repositories, used only as evidence.

Historical Webstores runtime records may remain COMPLETE/CLOSED. That
historical closure does not mark this Webstores Stage 6 plan complete or in progress.

## B. Stage Objective

Stage 6 completes this customer workflow without creating a payment or order:

1. Staff launches an owner-approved Webstore through the existing backend gates.
2. A customer visits the canonical public URL or its QR destination.
3. The customer sees published branding and welcome content.
4. The customer sees only publicly eligible, owner-approved products.
5. The customer opens a product, selects valid variants and supported options,
   and chooses an available product-level fulfillment method.
6. The customer adds, updates, and removes products in a cart.
7. Fundraiser progress, optional donations, and fixed or percentage promo codes
   are available where configured.
8. The server validates and reprices the cart authoritatively.
9. The customer reaches a complete cart summary.

The workflow stops at the cart summary. The interface must not offer an
actionable checkout control or imply that purchasing is available.

## C. Entry Conditions

The following Stage 1-5 capabilities are the starting contract:

| Capability | Entry status | Evidence |
|---|---|---|
| Store creation and setup | Accepted, with lifecycle/type corrections still needed | `backend/app/routers/webstores.py`, `backend/app/services/webstores.py` |
| Canonical Webstore types | Requires Stage 6 correction to five types | `backend/app/models/webstore.py`, `frontend/src/pages/WebstoresPage.jsx` |
| Shared questionnaires and delivery recovery | Accepted | `backend/app/routers/forms.py`, `backend/app/routers/webstores.py`, Stage 3 tests |
| Branding | Accepted | `backend/app/services/webstore_branding.py`, `frontend/src/components/webstores/WebstoreBranding.jsx` |
| Per-Webstore catalog | Accepted for Stage 4 scope | `WebstoreProduct`, `backend/app/services/webstores.py` |
| Images, variants, and pricing | Present; public fulfillment mapping is incomplete | `backend/app/models/webstore.py` |
| Owner product review | Accepted for Stage 4 scope | approval service, owner portal routes, Stage 4 tests |
| Launch packet and owner approval | Accepted for Stage 5 scope | launch packet and approval services, Stage 5 tests |
| Launch readiness | Backend gate exists; public defense-in-depth is required | `launch_readiness`, `public_webstores.py` |
| Public slug and URL preparation | Present; final public workflow is incomplete | `public_slug`, `PublicApp.jsx` |
| Tenant, auth, permissions, portals, audit, notifications | Existing shared foundations | existing platform services and Stage 1-5 tests |

Stage 6 must correct incomplete entry contracts as part of the public boundary,
without creating duplicate questionnaire, catalog, pricing, portal, auth,
notification, or order systems.

## D. Included Scope

Stage 6 includes only:

- Backend-enforced publication and launch eligibility.
- Public Webstore lookup by canonical globally unique slug.
- Published custom color, image banner, logo, and greeting/welcome content.
- Public catalog browsing and product detail.
- Explicit owner-approved and publicly eligible product filtering.
- Valid variants and existing supported personalization/customer-input fields.
- Product-level fulfillment configuration: pickup, shipping, or both.
- Client cart creation, updates, quantity changes, and item removal.
- Cart persistence compatible with the current architecture.
- Server-authoritative cart validation and repricing.
- Price-change and unavailable-item handling.
- Fundraiser goal and progress display.
- Optional customer donations.
- Fixed-amount and percentage promo-code validation and preview.
- Mobile, keyboard, screen-reader, and contrast-safe public behavior.
- Loading, empty, error, unavailable, unpublished, expired, and closed states.

The Stage 6 UI must not contain an actionable checkout button, payment form,
payment link, or order-submit action.

## E. Explicit Exclusions

The following remain outside Stage 6:

- Checkout route or checkout page.
- Payment collection or payment-provider calls.
- Stripe Connect implementation, charge-model selection, or payouts.
- Webstore order creation or paid-order confirmation.
- Main Orders integration or Production integration.
- Shipping-label purchasing and carrier-rate shopping.
- Tax remittance implementation beyond cart-total foundations needed for a
  clearly labeled pre-checkout estimate.
- New customer-account requirements.
- Post-launch analytics and financial reporting.
- Abandoned-cart automation, refunds, returns, and fulfillment operations.
- Automatic AI generation or automatic content overwrites.
- Broad Webstore administration unrelated to the public cart workflow.

## F. Supported Type Correction

The canonical newly-created Webstore types for this plan are exactly:

- `b2b` - B2B
- `fundraiser` - Fundraiser
- `event` - Event
- `promotional` - Promotional
- `general` - General

`Employee` is not a supported Webstore type. Current references that require
correction are:

| Reference | Current meaning | Stage 6 treatment |
|---|---|---|
| `backend/app/models/webstore.py:10,74` | Production enum and type literal include `employee` | Reject `employee` for new creates; preserve persisted records safely until a separately approved migration policy exists |
| `frontend/src/pages/WebstoresPage.jsx` | Create-type list includes the sixth option | Remove from new-create UI during implementation |
| `backend/app/services/reports_service.py:34,805` | Reporting allowlist treats `employee` as official | Reclassify new reporting authority to the five types; preserve legacy rows as `other_or_legacy` where required |
| `backend/app/routers/reports.py:238` | Response advertises six official types | Change the new authority response to five types |
| `backend/tests/test_report_builder_complete_system.py:131,319` | Test asserts six official types | Update the focused authority test; add persisted-legacy compatibility coverage |
| Stage 1 history and older planning notes | Historical six-type decision | Retain as historical evidence and mark superseded by this locked correction |

No existing persisted `employee` Webstore may be silently reclassified. Before
runtime changes, implementation must determine whether such records exist. If
they do, reads remain safe and tenant-scoped, new creates reject the value, and
existing records require an explicit compatibility or migration decision. New
Stage 6 tests must prove all five canonical types create successfully and
`employee` cannot be newly created.

## G. Product-Level Fulfillment Contract

The product is the fulfillment boundary. There is no single store-wide
fulfillment mode in Stage 6.

Proposed product fields, using the existing Webstore product model where safe:

```text
fulfillment_methods: ["pickup", "shipping"]
default_fulfillment_method: "pickup" | "shipping" | null
pickup_instructions: public text, optional
shipping_cost_cents: non-negative integer, optional fixed pre-checkout amount
```

If a variant has different fulfillment availability, the variant snapshot may
override `fulfillment_methods` and the effective shipping amount. Otherwise the
product-level values apply to every variant. A product with no effective method
is not publicly eligible and cannot be added to a cart.

Rules:

- Staff configure fulfillment per product and see validation errors before the
  product can be made public.
- Public product detail displays the available methods and pickup instructions
  or the fixed shipping estimate when configured.
- A cart line stores the selected method explicitly.
- If every line supports pickup, the cart defaults to pickup when configured.
- If every line supports shipping, the cart defaults to shipping when
  configured.
- Mixed carts are allowed only when every line has a compatible explicit
  selection. The cart summary groups lines by fulfillment method and explains
  the grouping.
- A line with no compatible method blocks the add/update operation with a
  customer-safe message and does not silently fall back.
- Shipping before Stage 7 is a configured fixed estimate in integer cents. It
  is not a carrier quote, label purchase, or final shipping settlement.
- Pickup instructions are informational public content; fulfillment operations
  remain deferred.

This contract gives Stage 7 explicit per-line fulfillment data without choosing
a payment, carrier, or payout architecture.

## H. Server-Priced Cart Contract

The server is authoritative for product eligibility, owner approval, variant
validity, personalization requirements, unit price, quantity, line subtotal,
promo eligibility, discount, donation, fulfillment compatibility, configured
shipping estimate, cart subtotal, and final pre-checkout total.

The browser may submit only identifiers and customer choices. It must not submit
authoritative prices, discounts, fees, taxes, donations, or totals.

Proposed request shape:

```json
{
  "webstore_id": "public-store-id",
  "currency": "usd",
  "items": [
    {
      "product_id": "public-product-id",
      "variant_id": "public-variant-id",
      "quantity": 2,
      "personalization": {"name": "Example"},
      "fulfillment_method": "pickup"
    }
  ],
  "donation_cents": 0,
  "promo_code": "TEAM10"
}
```

Proposed response shape:

```json
{
  "quote_id": "opaque-quote-id",
  "quote_version": "webstore_cart_quote_v1",
  "expires_at": "server-timestamp",
  "currency": "usd",
  "items": [],
  "fulfillment_groups": [],
  "merchandise_subtotal_cents": 0,
  "shipping_estimate_cents": 0,
  "discount_cents": 0,
  "donation_cents": 0,
  "total_cents": 0,
  "warnings": []
}
```

The quote must contain server snapshots of product, variant, fulfillment, and
price evidence. A later request must revalidate the quote. If a price changes,
a product is archived/rejected, a store closes, or a selected option becomes
unavailable, the server returns a stale or unavailable-item result with a fresh
quote rather than silently accepting old values.

Recommended behavior:

- Use a client cart for local persistence, with every meaningful change sent to
  the server quote endpoint.
- Do not create a second persistent cart or order collection unless inspection
  proves the existing architecture requires it.
- Use opaque quote identifiers, short expiration, tenant/Webstore binding, and
  a request fingerprint for safe replay.
- Use integer minor units and an explicit currency.
- Make quote creation deterministic and side-effect free; do not consume promo
  usage or count fundraising progress.
- Apply rate limits to public quote requests and normalize all public errors.
- Record audit events only for meaningful server-side cart/quote events already
  covered by the existing audit contract.

## I. Fundraiser Goal and Donation Rules

Only Fundraiser Webstores receive fundraiser-specific goal behavior.

- A fundraiser may have an optional non-negative integer-cent goal.
- The goal bar is visible only when configured and publicly approved.
- Progress is calculated from completed, authoritative paid records only.
- Stores with no completed sales show zero progress.
- Progress may display over-goal completion without capping the stored amount.
- Unpaid carts and cart donations never increase completed progress.
- An optional donation field may be enabled per Webstore and validated by the
  server with configured minimum and maximum integer-cent limits.
- Donation values must be non-negative, cannot be supplied as a negative or
  client-authoritative total, and can be removed by setting zero.
- The cart response lists donation separately from merchandise, shipping, and
  discount values.
- Stage 6 may show potential contribution in the current cart summary, but it
  must label it as unpaid and must not add it to the goal progress.
- Actual donation settlement and accounting begin with Stage 7 paid-order
  creation.

## J. Promo-Code Rules

Promo codes are owned by one Webstore and tenant. They are normalized by the
server, with whitespace removed and a case-insensitive comparison. The stored
canonical form is uppercase.

Each code may define:

- Active/inactive status.
- Start and expiration timestamps.
- Fixed integer-cent discount or percentage discount.
- Percentage constrained to `0 < percentage <= 100`.
- Optional minimum merchandise subtotal.
- Optional maximum discount cap.
- Optional product or category scope.
- Optional usage limit, validated in Stage 6 but not consumed until Stage 7.

Rules:

- A code is never read across tenant or Webstore boundaries.
- Validation uses merchandise subtotal before the discount; donations do not
  satisfy a minimum-cart requirement.
- Donations are not discounted unless a future approved contract explicitly
  says so.
- Shipping estimates are not discounted by default.
- A discount cannot reduce merchandise subtotal below zero.
- Invalid, inactive, future, expired, exhausted, cross-tenant, or inapplicable
  codes return distinct customer-safe validation messages.
- Stage 6 records the validated result in the quote snapshot but does not
  permanently redeem or increment usage.
- Stage 7 must revalidate and atomically finalize usage after successful payment.
- Code validation must be indexed by tenant, Webstore, normalized code, status,
  and validity window.

## K. Backend Implementation Plan

Prefer extending existing Webstores services, serializers, permissions, and
money helpers. Do not add a duplicate catalog, pricing, questionnaire, portal,
authentication, notification, or order system.

Likely work:

- Extend `backend/app/models/webstore.py` for the five-type authority,
  product-level fulfillment, fundraiser settings, donation limits, and promo
  definitions only where existing fields cannot safely carry the contract.
- Add request/response schemas in `backend/app/routers/public_webstores.py` or
  an existing shared schema location.
- Extend `backend/app/services/webstores.py` or a narrowly scoped cart helper
  for public eligibility, quote validation, repricing, fulfillment grouping,
  donation validation, and promo validation.
- Reuse existing pricing and integer-cent contracts; do not create a parallel
  pricing engine.
- Require live status, launch readiness, public approval, active/public
  products, and tenant/Webstore scope before public serialization.
- Add a public cart-quote route. Existing purchase-intent aliases must remain
  payment-gated and must not become the Stage 6 cart authority.
- Keep purchase intents, canonical Orders, Payments, and Work Orders outside
  this checkpoint.
- Preserve public DTO redaction for cost, margin, owner share, fees, supplier,
  internal notes, and provider details.
- Add indexes for canonical public slug, tenant/Webstore/product visibility,
  promo lookup, and any persisted quote record only if the existing design
  proves persistence is necessary.
- Preserve legacy `employee` records without silently changing their type;
  reject new values and record compatibility behavior explicitly.
- Write lifecycle, visibility, quote, and validation audit events through the
  existing activity/audit services.

## L. Frontend Implementation Plan

Reuse the existing public adapter and branding components. The public route
remains under `/p/webstores/:slug`; nested product and cart views may be added
under that route family.

Likely surfaces:

- Storefront page with branding and catalog.
- Product detail view with images, variants, personalization, and fulfillment.
- Cart panel or cart page with line-level fulfillment selections.
- Server quote refresh after every material cart change.
- Donation input only when the Webstore enables it.
- Promo-code input with clear validation feedback.
- Fundraiser goal and progress display.
- Unpublished, closed, expired, late-order, empty, unavailable, loading, and
  network-error states.

The interface must not show an actionable checkout control. A future message
may say that purchasing is unavailable while payment setup is pending, but it
must not imply that an order can be completed.

Accessibility requirements include keyboard operation, visible focus, labels
for every input, screen-reader announcements for quote changes and errors,
appropriate image alt text, contrast-safe branding fallbacks, responsive
mobile layouts, and focus management when cart or product panels open.

## M. Store-Type Behavior

| Capability | B2B | Fundraiser | Event | Promotional | General |
|---|---:|---:|---:|---:|---:|
| Public branding | Yes | Yes | Yes | Yes | Yes |
| Public catalog | Yes | Yes | Yes | Yes | Yes |
| Cart | Yes | Yes | Yes | Yes | Yes |
| Product-level pickup | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured |
| Product-level shipping | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured |
| Fundraiser goal | No | Yes, when configured | No | No | No |
| Optional donation | No by default | Yes, when configured | No by default | No by default | No by default |
| Promo codes | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured | Yes, if configured |
| Event dates or closure behavior | Not applicable unless configured | Not applicable unless configured | Yes, subject to existing deadline rules | Not applicable unless configured | Not applicable unless configured |

The table intentionally contains no Employee type. Any further type-specific
fulfillment or deadline rules require an approved contract rather than inferred
behavior.

## N. Security and Data Boundaries

- Every authenticated write remains tenant- and Webstore-scoped.
- Public slug lookup resolves only the canonical globally unique public slug.
- Non-live, unpublished, private, closed, archived, and unavailable stores
  return a safe unavailable response without metadata leakage.
- Draft, rejected, archived, non-public, and unapproved products are excluded.
- Public serializers exclude internal costs, margins, shares, fees, suppliers,
  production details, internal notes, and provider details.
- Product, variant, promo, file, and quote identifiers are rechecked against
  the resolved tenant and Webstore.
- The browser cannot set prices, discounts, donations, fees, shipping, or
  totals.
- Promo validation is normalized, tenant-scoped, rate-limited, and never
  permanently redeemed before Stage 7 payment.
- Donations are bounded, non-negative, server-calculated, and separated from
  completed fundraiser progress.
- Branding and image URLs use existing public allowlists and storage boundaries.
- Staff, owner, manager, and public access continue using separate existing
  permission and portal contracts.
- Public error responses reveal only whether the requested public resource is
  unavailable, invalid, expired, or stale; they do not reveal private state.
- Customer contact collection remains limited to fields already required by
  the accepted public Webstore contract.

## O. Focused Test Plan

Do not run tests during this documentation checkpoint. Implementation should
use focused verification only:

Existing files to extend where applicable:

- `backend/tests/test_webstores_stage1_foundation.py`
- `backend/tests/test_webstores_stage2_setup.py`
- `backend/tests/test_webstores_stage3_branding.py`
- `backend/tests/test_webstores_stage4a_product_foundation.py`
- `backend/tests/test_webstores_stage4b_owner_approval.py`
- `backend/tests/test_webstores_stage5_launch_packet_owner_approval.py`
- `backend/tests/test_ec14_webstores.py`
- `frontend/src/__tests__/WebstoresStage1.test.jsx`
- `frontend/src/__tests__/WebstoresStage3Branding.test.jsx`
- New focused public storefront/cart tests only if existing suites cannot hold
  the cases without duplication.

Required cases:

- Five canonical types are accepted for new creates.
- New `employee` creation is rejected.
- Existing `employee` records are preserved and handled safely if present.
- Canonical slug lookup is tenant-safe.
- Unpublished, non-live, closed, and unapproved stores do not leak data.
- Approved active public products are included; draft, rejected, archived, and
  unavailable products are excluded.
- Variant and personalization validation works.
- Pickup, shipping, both, no-method, and mixed-fulfillment carts behave as
  specified.
- Server prices, integer cents, quantity, repricing, stale quotes, and deleted
  products are authoritative.
- Fixed and percentage promo codes validate correctly across tenant boundaries,
  validity windows, limits, floors, and product scope.
- Donations are bounded and do not increase unpaid fundraiser progress.
- Goal display is correct with zero sales, no goal, and over-goal progress.
- Empty, closed, expired, missing, and unavailable states are safe.
- Frontend cart behavior is responsive and accessible.
- Stage 1-5 launch and owner-approval regressions remain covered.
- No checkout, payment, Webstore Order, Orders-module, or Production flow is
  introduced by Stage 6.

## P. Acceptance Criteria

### Code-complete

- A live, ready Webstore displays published branding and eligible products.
- Only the five approved types can be newly created.
- Product detail supports supported images, variants, personalization, and
  product-level fulfillment.
- Cart operations are complete and server-priced.
- Donation, fundraiser, promo, deadline, and unavailable behavior matches this
  contract.
- No actionable checkout or payment behavior exists.
- No duplicate order, pricing, catalog, or fulfillment subsystem is created.

### Focused automated verification

- Backend tests prove tenant isolation, launch-state filtering, product
  approval, fulfillment, quote authority, promos, donations, and type safety.
- Frontend tests prove public browsing, cart updates, errors, unavailable
  states, responsive structure, and absence of an actionable checkout control.
- Relevant Stage 1-5 focused tests pass when rerun for changed contracts.

### Build verification

- Changed backend files compile/import successfully.
- Changed frontend files pass the parser/build check.
- `git diff --check` passes.

### Manual/live acceptance

- Desktop and mobile browsing works for each applicable store type.
- Product selection, mixed fulfillment, donation, promo, repricing, and closed
  state messaging are understandable to a customer.
- Public output contains no internal financial or production fields.
- No payment, order, payout, or production record is created.

### Deferred gate

Stage 6 cannot be declared payment-complete. Stage 7 remains responsible for
Stripe Connect, checkout, verified payment, paid Orders, promo redemption,
payout routing, Orders integration, and Production handoff.

## Q. Proposed File Scope

Proposed production files, subject to implementation inspection:

- `backend/app/models/webstore.py`
- `backend/app/routers/public_webstores.py`
- `backend/app/routers/webstores.py`
- `backend/app/services/webstores.py`
- Existing shared pricing, audit, notification, and storage services only when
  an extension is required.
- `frontend/src/public/PublicApp.jsx`
- `frontend/src/pages/PublicWebstorePage.jsx`
- A new public product/cart component only if reuse cannot keep one storefront
  authority.

Proposed test files:

- Existing Stage 1-5 and EC14 Webstores focused suites listed above.
- One new focused public cart suite only if needed.

Possible migration work:

- A narrowly scoped compatibility migration may be required if persisted
  `employee` Webstores exist. It must preserve records and must not silently
  reclassify them.
- No migration is authorized during this planning checkpoint.

Planning/tracking files updated by this checkpoint:

- `preflight/WEBSTORES_STAGE_6_PUBLIC_STOREFRONT_AND_SERVER_PRICED_CART_PLAN.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/PRD.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`

Protected files and systems:

- No production code or tests during planning.
- No donor repository changes.
- No Stage 7 payment, checkout, order, payout, or Production implementation.
- No duplicate questionnaire, catalog, pricing, portal, auth, notification,
  or order system.

## R. Implementation Checkpoints

Use separate implementation checkpoints rather than one oversized commit.

### 1. Type and publication enforcement

- Branch: `feature/webstores-stage-6-type-publication`
- Include five-type creation authority, legacy Employee compatibility handling,
  explicit approval/publication filtering, and backend tests.
- Exclude cart, promo, donations, fulfillment, checkout, payment, and orders.
- Commit: `feat: enforce webstore stage 6 types and publication`
- Gate: focused backend tests and diff review show no public data leakage.

### 2. Public storefront and approved catalog

- Branch: `feature/webstores-stage-6-public-storefront`
- Include branding, public catalog, product detail, images, empty/loading/error
  states, and approved-product filtering.
- Exclude checkout, payment, order creation, and fulfillment operations.
- Commit: `feat: add approved public webstore storefront`
- Gate: focused public backend/frontend tests and build check pass.

### 3. Product detail and fulfillment

- Branch: `feature/webstores-stage-6-product-fulfillment`
- Include variants, personalization, product-level pickup/shipping, mixed-cart
  compatibility rules, and public instructions.
- Exclude carrier rates, labels, payment, and fulfillment operations.
- Commit: `feat: add product-level webstore fulfillment choices`
- Gate: all fulfillment and variant cases pass.

### 4. Server-priced cart

- Branch: `feature/webstores-stage-6-server-priced-cart`
- Include cart persistence compatible with the existing architecture, quote
  request/response, repricing, stale handling, and removal/update behavior.
- Exclude checkout and any order or payment side effect.
- Commit: `feat: add server-priced webstore cart`
- Gate: price-authority, tenant-isolation, and stale-cart tests pass.

### 5. Fundraiser, donation, and promo behavior

- Branch: `feature/webstores-stage-6-cart-extras`
- Include goal/progress display, optional donation validation, fixed and
  percentage promo validation, and unpaid-progress protection.
- Exclude promo redemption finalization, payment, payouts, and reports.
- Commit: `feat: add webstore cart donations and promotions`
- Gate: focused extras tests and public UI checks pass.

### 6. Final verification and live acceptance

- Branch: `feature/webstores-stage-6-public-storefront-cart`
- Include only corrections required by the completed focused verification.
- Exclude all Stage 7 and Stage 8 work.
- Commit: `docs: record webstores stage 6 acceptance` or a narrowly scoped fix
  commit as appropriate.
- Gate: manual acceptance confirms the workflow ends at the cart summary.

Each checkpoint must be reviewed before the next begins. No broad repository
test marathon is required for a narrow change; use the focused verification
policy and touched-module checks.

## S. Stage 7 Handoff Contract

Stage 6 must provide a validated cart representation containing:

- Tenant and Webstore identifiers.
- Canonical public slug evidence.
- Eligible product and variant identifiers.
- Product and variant price snapshots.
- Quantities and personalization values.
- Product-level fulfillment selections and fulfillment groups.
- Validated promo result without permanent redemption.
- Donation amount, separately represented.
- Merchandise, shipping estimate, discount, donation, and total cents.
- Currency and quote version.
- Quote expiration and integrity/replay protection.
- Warnings for stale or changed items.

Stage 7 decides and implements Stripe Connect charge model, payment
collection, checkout, successful-payment handling, Webstore Order creation,
promo redemption finalization, payout routing, Orders-module integration, and
Production handoff. Stage 6 must not depend on an unapproved charge model.

## Contradiction and Risk Review

| Risk | Severity | Resolution |
|---|---|---|
| Current code and historical records include Employee | BLOCKER for type implementation | Reject new values, preserve existing records, and handle compatibility explicitly |
| Older Stage 6 plan includes checkout screens | HIGH | This plan ends at cart summary and prohibits actionable checkout UI |
| Existing purchase-intent/cart-quote aliases overlap | HIGH | Add a true server-priced cart contract; keep purchase intents payment-gated |
| Existing public filtering does not visibly require approval status | HIGH | Add explicit owner-approved filtering before public serialization |
| Store-level fulfillment appears in older gap notes | HIGH | Use product-level fulfillment only |
| Donations and promos were previously deferred | HIGH | Include only server-priced preview behavior; no payment redemption |
| Unpaid carts could be mistaken for fundraiser revenue | HIGH | Progress uses completed paid records only |
| Historical EC14 documents describe broader commerce | MEDIUM | Treat them as historical evidence; use current Stage 6 boundary |
| Donor storefronts use incompatible auth/order/payment systems | MEDIUM | Adapt UX ideas only; do not copy donor backend |

This plan is documentation only. No Stage 6 or Stage 7 implementation has
started.
