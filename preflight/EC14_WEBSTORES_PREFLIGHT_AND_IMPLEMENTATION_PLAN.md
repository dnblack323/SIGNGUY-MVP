# EC14 Webstores Preflight and Implementation Plan

**Status:** PREFLIGHT COMPLETE - IMPLEMENTATION AUTHORIZED  
**Date:** 2026-07-19  
**Branch:** `CODEX-EC14-BRANCH`  
**Starting commit:** `83f51010200e50f04d2c202d2cbc20543ebae6df`  
**EC13 closed ancestor:** `b76512e0fa907e2ede1b448fcabab3d85336da56`

## Starting Point Verification

- Working tree was clean before EC14 preflight documentation began.
- Current branch is `CODEX-EC14-BRANCH`, tracking `origin/CODEX-EC14-BRANCH`.
- Completed EC13 head `b76512e0fa907e2ede1b448fcabab3d85336da56` is an ancestor of the EC14 branch head.
- EC13 is recorded as COMPLETE - CLOSED in the checkpoint registers.

## Authority and Scope

The current owner prompt explicitly authorizes EC14 Webstores after EC13 closure. This lifts hold H1/H2 for EC14 only. H3-H8 remain active for EC15, EC16, EC17, EC18, and AI/provider-cost work.

Authoritative sources:

1. Current owner prompt authorizing EC14 continuation on `CODEX-ec14-branch`.
2. `00_Master_Index_and_Owner_Decision_Register.docx`.
3. `EC14_Webstores_Master_Specification.docx`.
4. `memory/AGENT_INSTRUCTIONS.md`.
5. `memory/documentation_authority_register.md`.
6. EC13 commercial billing contracts and completion records.

Naming rule: Webstores is the final product name. Existing "Order Portal" references are historical source terminology or compatibility references only.

## Authorized EC14 Scope

EC14 implements Webstores as one shared core with:

- Staff Webstores manager.
- Webstore owner portal.
- Public storefront and buyer checkout preparation.
- Per-Webstore product catalog copied from reusable templates.
- Artwork and mockup records with original artwork preservation.
- Human-reviewed AI suggestion records only; no live AI calls.
- Launch packets, launch gates, owner approval, and activity/audit trails.
- Buyer order capture, integer-cent totals, ledger snapshots, and idempotent bridge contract to canonical Orders/Order Items.
- Stripe Connect boundary records and development-safe checkout/session placeholders, with no provider calls unless explicitly configured in a later approved scope.
- Reporting projections over Webstore buyer orders and ledger records.
- Main-app navigation and frontend surfaces for staff, owner portal, and public storefront.

## Explicitly Excluded

- EC15 Wrap Lab.
- EC16-EC18 AI gateway, AI credit ledger, live model/provider use, or generated asset billing.
- EC19 onboarding/help work.
- Unapproved standalone annual Webstores pricing.
- Placeholder zero-priced commercial products.
- EC4 invoice/payment mutation for buyer checkout.
- Webstore payout execution outside Webstore ledger records.
- Broad legacy route renames without compatibility handling.

## Phase Plan

### Phase 14A - Webstores Foundation

Create canonical models, repositories, services, indexes, routes, permissions, and audit contracts for:

- Webstore owners.
- Webstores.
- Product templates.
- Portal products.
- Questionnaire submissions.
- Artwork files.
- Mockups.
- Launch packets.
- Activity records.

Acceptance:

- Tenant-scoped CRUD works for staff users with `webstore:*` permissions.
- Staff permissions remain separate from portal permissions.
- Product templates copy into Webstore products; later template edits do not mutate copied products.
- Internal cost fields are excluded from owner/public views.
- Status changes write activity/audit records.

### Phase 14B - Owner Portal and Launch Workflow

Extend the existing Portal Identity system additively for Webstore owner/manager portal identities and implement owner-facing questionnaire, approval, and launch-packet actions.

Acceptance:

- Portal tokens still never authorize staff routes.
- Customer and employee portal routes remain isolated.
- Webstore owner identities can access only Webstores linked to their owner record and tenant.
- Launch gates are enforced server-side.
- Owner approval and change requests are audited.

### Phase 14C - Public Storefront and Buyer Orders

Implement public storefront read models and buyer order capture using backend-derived integer-cent totals.

Acceptance:

- Only Live Webstores with checkout enabled can accept buyer orders.
- Inactive/unavailable/private products cannot be purchased.
- Buyer totals are calculated server-side from current portal product records.
- Ledger entries snapshot buyer payment, subtotal, donation, shipping, tax, processing fee placeholder, platform usage fee, owner/fundraiser share, production cost estimate, and shop gross estimate.
- Buyer orders do not create EC4 invoices/payments.

### Phase 14D - Stripe Connect Boundary and Order Bridge

Add Webstores-specific Stripe boundary records and idempotent bridge behavior to canonical Orders/Order Items without invoking live Stripe APIs.

Acceptance:

- Stripe Connect account/onboarding/session records remain Webstore-scoped and separate from EC4 and EC13 Stripe Billing.
- Checkout/session creation is a local contract only in EC14.
- Buyer order bridge is idempotent and records `bridged_order_id`/bridge status.
- Repeated bridge requests do not duplicate canonical Orders/Order Items.

### Phase 14E - Frontend Surfaces

Enable the Webstores navigation item and add:

- Staff Webstores workspace.
- Webstore detail workflow.
- Owner portal Webstore page.
- Public storefront page.

Acceptance:

- Staff surfaces use backend APIs and role/permission visibility.
- Owner portal surfaces use portal APIs only.
- Public storefront hides internal costs/margins and fails closed when unavailable.
- Text and controls fit across desktop/mobile constraints.

### Phase 14F - Reporting, Documentation, and Closure

Add reporting endpoints, targeted tests, completion documentation, and final CI validation.

Acceptance:

- Sales, product, fundraiser/donation, ledger, and launch-readiness reports are available.
- Targeted backend tests cover permission, tenant isolation, launch gates, buyer order ledger behavior, owner portal isolation, and order bridge idempotency.
- Directly affected tests, compile checks, and `git diff --check` pass locally.
- GitHub CI passes before EC14 is marked complete.

## Canonical Entities and Relationships

- `webstore_owners`: tenant-scoped external owner/fundraiser/contact account; may link to one portal identity and multiple Webstores.
- `webstores`: tenant-scoped store record linked to one Webstore owner and containing status, slug, branding, checkout, launch, payout-readiness, and approval state.
- `webstore_product_templates`: tenant-scoped reusable product templates used by shop staff to seed Webstore products.
- `webstore_products`: per-Webstore sale products copied from templates or created directly; stores public sale price and private production-cost estimate in integer cents.
- `webstore_questionnaire_submissions`: owner inputs and setup answers tied to one Webstore/owner.
- `webstore_artwork_files`: original and processed artwork references; original is never overwritten.
- `webstore_mockups`: human-reviewable mockup records linked to Webstore, product, and/or artwork.
- `webstore_launch_packets`: immutable-ish approval snapshot of launch copy, products, pricing, gates, and owner decision.
- `webstore_buyer_orders`: public buyer order record for storefront commerce; separate from EC4 invoices/payments.
- `webstore_ledger_entries`: Webstore commerce ledger rows with immutable transaction snapshots and refund/reversal support.
- `webstore_activity_events`: Webstores-specific activity stream paired with EC2 audit/activity.
- `webstore_ai_usage_events`: reviewable AI suggestion/action contract records only; no provider execution in EC14.

## Lifecycle and Status Contracts

Webstores use the EC14 status vocabulary:

`draft`, `questionnaire_sent`, `waiting_on_store_owner`, `questionnaire_submitted`, `ai_setup_ready`, `ai_product_suggestions_ready`, `artwork_needs_review`, `mockups_generated`, `mockups_approved`, `products_selected`, `store_packet_generated`, `sent_for_approval`, `changes_requested`, `approved`, `live`, `closing_soon`, `closed`, `in_production`, `completed`, `relaunch_ready`, `archived`.

Rules:

- Launch is only allowed after server-side readiness checks pass.
- Checkout requires `live`, entitlement, active public products with integer-cent prices, owner approval, fee acknowledgement, launch packet, and payment readiness.
- Closed/archived/unavailable stores cannot accept checkout.
- Product sale price and production cost are integer cents.
- Internal production cost/margin is staff-only.
- Platform-fee rows are immutable snapshots; refunds create separate proportional reversal entries.

## Permission Model

- Staff routes require `webstore:read`, `webstore:write`, or `webstore:manage`.
- Staff permissions never authorize portal routes.
- Portal routes require `portal:webstore_owner_admin` or `portal:webstore_manager_ops` on a portal identity of type `webstore_owner` or `webstore_manager`.
- Portal identities are tenant-scoped and Webstore-owner scoped.
- Public storefront routes never expose internal cost, margin, staff notes, or non-public products.
- All repository/service writes include `tenant_id` filters.

## Stripe Boundaries

EC14 may create local Stripe Connect boundary records and test/dev checkout contract records, but must not make live provider calls in this phase.

Boundaries:

- Separate from EC4 invoice/payment Stripe Core.
- Separate from EC13 subscription/setup Stripe Billing.
- No Stripe webhooks are required for EC14 completion.
- Provider identifiers, if stored, are references only and are never used to authorize client-side success.
- Checkout success remains server-confirmed.

## Entitlement Boundaries

- Launch and checkout require EC2 entitlement for `webstores`.
- EC14 derives access from existing EC2/EC13 entitlement contracts but does not mutate subscription entitlements.
- Existing explicit Founder access is preserved.
- Webstores standalone and add-on commercial availability must respect EC13 approved active price rules; unapproved standalone annual pricing remains unavailable.

## Migration Considerations

- Extend portal identity additively; do not migrate or rewrite existing customer/employee portal identities.
- Preserve any legacy route naming compatibility where needed, but present Webstores as the active product name.
- No broad codebase rename of historical "portal" terminology.
- Existing Orders/Order Items remain canonical; Webstores buyer-order bridge writes normal orders/items with explicit Webstore source metadata.
- Original artwork references remain immutable; cleaned/processed outputs use separate fields.

## Required Indexes

Create indexes for:

- `webstore_owners`: `id`, `(tenant_id, email)`, `(tenant_id, status)`, `(tenant_id, portal_identity_id)`.
- `webstores`: `id`, `(tenant_id, slug)` unique, `(tenant_id, owner_id)`, `(tenant_id, status, updated_at)`, `(tenant_id, launched_at)`.
- `webstore_product_templates`: `id`, `(tenant_id, active, product_category)`, `(tenant_id, template_name)`.
- `webstore_products`: `id`, `(tenant_id, webstore_id, status)`, `(tenant_id, webstore_id, public)`.
- `webstore_questionnaire_submissions`: `id`, `(tenant_id, webstore_id, status)`.
- `webstore_artwork_files`: `id`, `(tenant_id, webstore_id, artwork_status)`.
- `webstore_mockups`: `id`, `(tenant_id, webstore_id, status)`, `(tenant_id, product_id)`.
- `webstore_launch_packets`: `id`, `(tenant_id, webstore_id, status)`.
- `webstore_buyer_orders`: `id`, `(tenant_id, webstore_id, created_at)`, `(tenant_id, webstore_id, status)`, `(tenant_id, idempotency_key)` unique partial.
- `webstore_ledger_entries`: `id`, `(tenant_id, webstore_id, created_at)`, `(tenant_id, buyer_order_id, entry_type)`, `(tenant_id, source_type, source_id)`.
- `webstore_activity_events`: `id`, `(tenant_id, webstore_id, created_at)`, `(tenant_id, action, created_at)`.
- `webstore_ai_usage_events`: `id`, `(tenant_id, webstore_id, status)`.
- `portal_identities`: add optional Webstore owner/manager lookup indexes without changing existing uniqueness.

## Required Tests

- Staff permission gates for read/write/manage operations.
- Staff tenant isolation across Webstore, product, buyer order, and ledger queries.
- Portal identity type isolation for customer, employee, Webstore owner, and Webstore manager.
- Webstore owner can only access owned Webstores.
- Template-to-product copy does not share mutable state.
- Internal cost fields are hidden from owner/public serializers.
- Launch gates block missing entitlement, missing products, inactive products, missing prices, missing approval, missing fee acknowledgement, and payment-readiness failure.
- Live store checkout accepts only active public products.
- Buyer order totals and ledger entries use integer cents and server-side pricing.
- EC4 invoices/payments are not mutated by buyer order creation.
- Platform-fee refund reversal creates a separate proportional ledger entry and never edits original fee rows.
- Stripe boundary creates local records only and does not call provider APIs.
- Buyer order bridge creates canonical Orders/Order Items idempotently.
- `git diff --check` and Python compile checks pass.

## Expected Files to Create or Modify

Backend:

- `backend/app/models/webstore.py`
- `backend/app/repositories/webstores.py`
- `backend/app/services/webstores.py`
- `backend/app/services/webstore_stripe_connect.py`
- `backend/app/routers/webstores.py`
- `backend/app/routers/webstore_owner_portal.py`
- `backend/app/routers/public_webstores.py`
- `backend/app/models/portal_identity.py`
- `backend/app/services/portal_identity.py`
- `backend/app/deps_portal.py`
- `backend/app/core/db.py`
- `backend/server.py`

Frontend:

- `frontend/src/lib/webstores.js`
- `frontend/src/pages/WebstoresPage.jsx`
- `frontend/src/pages/WebstoreDetailPage.jsx`
- `frontend/src/pages/WebstoreOwnerPortalPage.jsx`
- `frontend/src/pages/PublicWebstorePage.jsx`
- `frontend/src/App.js`
- `frontend/src/PortalApp.jsx`
- `frontend/src/PublicApp.jsx`
- `frontend/src/lib/navigation.js`

Tests and documentation:

- `backend/tests/test_ec14_webstores.py`
- `docs/modules/ec14_webstores.md`
- `evidence/EC14_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `memory/owner_specification_hold_register.md`

## Risks and Open Questions

- Webstores has broad product scope. The implementation should bias toward complete contracts and tested server behavior over decorative UI.
- Annual standalone Webstores pricing remains unapproved and must stay unavailable.
- Live Stripe Connect provider integration may require credentials and approval outside EC14 local boundary work.
- AI suggestions are a human-reviewable contract only in EC14 because EC16/EC17 remain held.
- The public storefront route shape may require compatibility aliases if older "order portal" URLs are later found in external references.

## Stop Confirmation

This document is planning/preflight only. No EC14 implementation code is introduced by this document.
