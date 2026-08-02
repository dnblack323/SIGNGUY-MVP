# Webstores Phase 6 Remaining App Plan

Status: planning artifact only. No implementation in this pass.

Baseline reviewed: `main` at merge commit `83965ab`.

Controlling inputs:

- `C:\Users\thesi\OneDrive\ORGANIZED SIGNGUYAI\SignGuy_AI_Phase_6_Webstores_Add_On_Specification.docx`
- `C:\Users\thesi\OneDrive\ORGANIZED SIGNGUYAI\WEBSTORE MASTER.md`
- Current MVP Webstores code under `backend/app/routers`, `backend/app/services`, `backend/app/models`, `frontend/src/pages`, and `frontend/src/lib`.
- Existing MVP Webstores docs under `docs/modules`, `docs/integrations`, and `preflight`.

## Naming And Product Language Rule

Use `Webstores` for the module/product name in user-facing planning, UI, help, and documentation.

Use `Webstore` only when referring to one individual store record. Use `Store` only when the surrounding sentence is clearer that way.

Any alternate legacy product wording should be treated as wrong and changed to `Webstores` when touching that user-facing area.

Keep `webstores` as the internal route/module/table naming. That already matches the chosen product direction, so no broad internal rename is needed.

This avoids the earlier mistake where multiple product names were treated as if they were all acceptable names.

## Stage Reference

Use these stage names when discussing the rest of the Webstores work:

| Stage | Reference name | Purpose |
| --- | --- | --- |
| Stage 1 | Design and workflow cleanup | Make the current Webstores screens usable, consistent, and named correctly without enabling commerce. |
| Stage 2 | Core lifecycle and store-type rules | Align statuses, setup requirements, and launch gates with the Phase 6 lifecycle contract. |
| Stage 3 | Questionnaires, answers, tasks, and notifications | Finish the owner intake loop and make answers easy for staff to read/apply. |
| Stage 4 | Product templates, catalog, mockups, and approval | Make product setup fast, per-store, owner-reviewable, and safe. |
| Stage 5 | Launch packet, QR, promo, and owner approval | Finish owner-facing approval materials before public launch. |
| Stage 6 | Public storefront and cart, payment-gated | Finish buyer browsing/cart UX while keeping payment blocked until Stripe is real. |
| Stage 7 | Stripe Connect and verified commerce | Add real Stripe Connect, checkout, webhooks, payout/refund reconciliation, and canonical order creation. |
| Stage 8 | Orders, production, reports, and relaunch | Operate live Webstores from canonical orders through production, reports, close/relaunch, and history. |

## Current MVP State

The MVP currently has meaningful Phase 6 foundation, but it is not production-commerce complete.

Already present or recently added:

- Internal `/webstores` list page.
- New Webstore wizard that creates owner/store, auto-fills store name from owner name, sends questionnaire, and opens the created store.
- Type-specific questionnaire defaults ported from the original repo behavior into MVP defaults.
- Questionnaire send endpoint, owner portal questionnaire rendering, draft/save/submit, staff review, safe answer application, and notification on submission.
- Per-store product records and product-template starting points.
- Starter templates for common products such as shirts, hoodies, hats, decals/stickers, banners, and tumblers.
- Product images, artwork records, mockup records, product pricing/share fields, variants, personalization fields, bundles, and packet inclusion flags.
- Branding draft/review/publish foundation.
- Launch packet snapshots with version/hash, owner approval, owner change requests, terms acceptance, and approval invalidation after material edits.
- Owner portal access, setup files, questionnaire, product viewing, launch packet approval/request changes, and owner-safe summary fields.
- Public storefront read DTO and public product image routes for Live stores only.
- Purchase-intent/cart-quote endpoints that fail closed until provider checkout is configured.
- Stripe provider boundary and disabled provider implementation.
- Launch readiness gates that currently block launch/commerce because live Stripe integration is deferred.
- Webstore-originated report summaries and legacy bridge hardening.

Not complete yet:

- Real Stripe Connect onboarding, real checkout session creation, signed webhook reconciliation, refunds, disputes, payouts, and canonical paid-order creation.
- Public buyer cart/checkout flow with real payment.
- AI mockup builder, AI cleanup, AI product suggestions, AI descriptions, AI summaries, and AI missing-info analysis through the approved AI gateway.
- Versioned catalog/branding approval UI that is easy for both staff and owners.
- QR code generation/download, promo code management, donation checkout, fundraiser progress meter, and owner-safe payout reporting.
- Manager dashboard/action-required experience.
- Full production handoff from canonical Order Items into production workflows.

## Design Notes To Carry Forward

These are owner design decisions and must be carried into the next implementation batches.

1. The Webstores home page should primarily be a list of current Webstores, with clear statuses and action-required signals.
2. Creating a new Webstore should open the created Webstore automatically.
3. Store name should auto-fill from the owner/person/organization entered at the beginning, while staying editable.
4. A visible `Send Questionnaire` button belongs early in the setup flow and on the store workspace.
5. The setup timeline should stay vertical on the right side of the workspace, not a crowded numbered strip across the top.
6. Do not duplicate the same workflow twice with both numbered top steps and bottom tabs.
7. Tabs must clearly show the current active section with color and contrast.
8. Add restrained color to the app; avoid a black-and-white-only operational screen.
9. Do not show launch date/timezone fields in the normal setup flow unless they are actually needed by that store type.
10. Do not use the word `slug` in user-facing setup language without explanation. Prefer `public link ending` or `last part of the store link`.
11. Stripe Connect controls should say what they do, such as `Send Stripe Connect Email`, and show onboarding/status clearly.
12. Product setup should support common templates like hats, shirts, hoodies, banners, decals, tumblers, and similar items.
13. Template-based products should let the shop upload a mockup image and use a prefilled or generated description.
14. Promo/launch copy must display the generated text or saved content. Do not show only a version number with no readable output.
15. Questionnaire submission must notify staff in the desktop/app notification area and inside Webstores.
16. Staff must be able to read customer answers easily and apply safe mapped answers into setup fields.
17. Shop manager setup should be focused: read answers, add product mockups, tune products, review branding, prepare packet, send for approval.

## Prior Mistakes To Avoid

These are explicit guardrails from the Phase 6 doc, master spec, prior repo findings, and current correction docs.

| Mistake to avoid | Required rule |
| --- | --- |
| Treating preview UI as production readiness | Every feature must be checked against real route/service persistence and launch gates. |
| Naming drift | Product/UI says Webstores. Any alternate legacy naming should be changed to Webstores. |
| Global sellable catalog | Product templates are reusable starting points only. Every live product belongs to exactly one Webstore. |
| Duplicate order system | Public checkout must create canonical Customer, Order, and Order Item records through one controlled bridge. |
| Browser-created paid orders | Browser redirects or optimistic UI must never create paid canonical orders without verified provider evidence. |
| Fake Stripe readiness | Stored flags cannot make payments ready. Provider-authoritative Stripe state is required. |
| Private balance ledger | Do not invent a stored-money balance for owners. Stripe Connect/payout projection is the source path. |
| Exposing internal numbers | Owners/buyers must not see production cost, margin, supplier cost, internal notes, or provider secrets. |
| Frontend pricing authority | Checkout totals, donations, discounts, tax, shipping, and fees are calculated server-side. |
| Unversioned approval | Owner approval must reference the exact packet/catalog/branding version. |
| Random status edits | Lifecycle transitions must validate prerequisites and create activity/lifecycle events. |
| Six separate store-type codebases | Store type behavior belongs in configuration and rules, not copied modules. |
| Owner portal as internal workspace | Owner portal must be owner-safe and scoped; manager workspace stays internal. |
| Environment gaps called feature gaps | Separate missing dependencies/test setup from actual missing product behavior. |
| Excessive verification loops | Use focused, necessary verification per changed module. Do not run broad test marathons for narrow changes. |

## Phase 6 Module Gap List

### 6.1 Webstores Core

Current status: partial.

Already present:

- Tenant-scoped Webstore records, owners, slugs/public slugs, basic statuses, public-safe storefront lookup, launch readiness gates, setup progress, activity/audit calls.
- Create flow now sends questionnaire and opens the store.
- Type change has confirmation safeguards after owner/setup activity.

Still missing or incomplete:

- Dedicated `/webstores/new` route or equivalent full-page wizard experience.
- Lifecycle service/route that matches the Phase 6 lifecycle names exactly: Draft, Intake Pending, Setup In Progress, Owner Review, Payment Setup Pending, Ready to Launch, Live, Closed/Archived.
- Store status transitions should be recorded as lifecycle events, not only generic status activity.
- Type-specific required fields need a complete rule matrix for B2B, Fundraiser, Event, Promotional, Employee, General.
- Store-level settings object for pickup/shipping, deadline, donation, promo, access policy, tax/shipping rules, and checkout copy.
- Customer bridge for owner/customer relationship needs to be finalized so owner/customer records are canonical where appropriate.
- Public slug alias/redirect plan for future store renames.
- Close/reopen/archive behavior needs storefront-safe messaging and historic order preservation acceptance.

Implementation plan:

1. Create a `webstore_lifecycle` service or strengthen the existing status service so every status move uses one transition contract.
2. Add a store-type requirements registry and use it for readiness, questionnaire defaults, manager checklist, and owner portal wording.
3. Move pickup/shipping/deadline/donation/promo/access settings into a clear store settings schema.
4. Keep public storefront access denied for non-Live stores with no metadata leak.
5. Add focused checks for illegal transitions, unpublished slug access, and type-specific requirement behavior.

### 6.2 Webstore Products And Catalog

Current status: partial.

Already present:

- Product templates and per-store products are separate.
- Template-to-product copy behavior exists.
- Product prices/costs/shares are integer cents.
- Product images, artwork associations, mockups, variants, personalization, bundles, category records, archive/restore, and public flags exist.
- Product queries are tenant and webstore scoped.

Still missing or incomplete:

- Staff UI for full template library management is not a dedicated Webstores templates workspace.
- Product publish/unpublish should be a clear visibility action with validation, not only an edit field.
- Versioned catalog approval request is not complete enough as its own workflow.
- Product variants need stronger public availability validation, SKU/fulfillment mapping, and production mapping snapshots.
- Editing global or tenant templates must be proven not to mutate existing store products.
- Product delete/archive behavior after completed orders needs explicit production-safe acceptance.
- AI draft product descriptions, names, categories, bundles, and suggestions are not implemented through approved AI rules.
- Mockup approval is present as records/statuses but not a complete operational workflow.

Implementation plan:

1. Build a dedicated `Templates` management view or tab for Webstores.
2. Add product visibility endpoints/actions with readiness validation.
3. Add catalog approval versions that freeze product list, pricing-visible-to-owner, images/mockups, branding summary, and version hash.
4. Add production mapping fields required by canonical Order Items.
5. Add a human-reviewed AI description/suggestion workflow after the AI gateway scope is approved.
6. Add focused checks for product isolation, template copy immutability, visibility blocking, and historic snapshot preservation.

### 6.3 Payments, Stripe Connect, Checkout, Payouts

Current status: foundation only. Live integration is intentionally deferred.

Already present:

- Typed provider boundary.
- Disabled provider that fails closed.
- Provider readiness status surface.
- Launch and checkout gates that refuse fake readiness.
- Integer-cent allocation snapshot fields.
- Refund/payout/dispute/reconciliation interfaces prepared.
- Documentation says live Stripe must be completed later by Emergent.

Still missing or incomplete:

- Real Stripe Connect account create/link/status.
- Real onboarding link email and owner completion flow.
- Real Checkout Session or PaymentIntent creation.
- Signed Stripe webhook raw-body verification and idempotent event processing.
- Verified paid-order conversion into canonical Customer, Order, Order Items, and Payment records.
- Refund, dispute, transfer, payout reconciliation from provider events.
- Owner payout projection from Stripe data.
- Merchant-of-record and charge-model decision.
- Tax/shipping/payment-method policy for public checkout.
- Clear owner-safe payout wording and manager finance views.

Implementation plan:

1. Keep the current disabled provider behavior until the owner/architecture decision is made.
2. Have Emergent implement the approved Stripe adapter behind the existing provider boundary.
3. Add raw-body webhook verification, event ID replay protection, amount/currency/store/account reconciliation, and recovery jobs.
4. Convert verified payment evidence into canonical Customer, Order, Order Items, and Payment records exactly once.
5. Add owner-safe payout screens and internal transaction views.
6. Run the separate connected Stripe acceptance process only after real test-mode provider credentials and adapter exist.

Stop condition:

- Do not claim buyer commerce is complete while the provider is disabled, the charge model is deferred, or payment readiness is based on stored flags.

### 6.4 Webstore Owner Portal

Current status: partial.

Already present:

- Owner/manager portal identity scope.
- Invitation accept route.
- Owner detail, questionnaire, draft/submit, setup progress, setup files, branding draft/review, launch packet approval/request changes, and terms acceptance.
- Owner-safe product summaries and commerce summary fields.

Still missing or incomplete:

- Full owner dashboard with tasks, messages, documents, approvals, payout/sales tabs, and clearer progress.
- Owner approval must be a first-class versioned approval object for catalog/branding/packet, not only packet-centered.
- Owner messages should use canonical messaging with store context.
- Owner documents should use DocuLink/shared documents with owner-visible filters.
- Owner payout/sales view must avoid fake profit labels and use provider/canonical order truth.
- Expired/reused invite behavior needs clear UI.
- Owner cannot see unrelated store data should be covered by focused checks.
- Owner portal should show Stripe onboarding action/status once real integration exists.

Implementation plan:

1. Build owner dashboard sections: Tasks, Questionnaire, Files, Launch Packet, Messages, Documents, Sales/Payouts, Store Preview.
2. Create owner task records for questionnaire, artwork, Stripe onboarding, approval, terms, and change requests.
3. Route messages/documents through shared services with owner-visible filters.
4. Add versioned approval/ref display for each approval task.
5. Add focused checks for invite expiry/reuse, store ID tampering, owner-safe documents/messages, and approval notification.

### 6.5 Webstores Manager Workspace

Current status: partial.

Already present:

- Internal list.
- Store detail workspace with Overview, Product Plan, Product Setup, Store Setup, Branding, Preview, Approval.
- Right-side setup timeline.
- Product creation/editing from templates.
- Questionnaire answer review and application.
- Launch gates, packet generation/send, Stripe status action, reports.

Still missing or incomplete:

- Manager home action-required dashboard.
- Assigned manager workload and permission-scoped visibility.
- Store workspace is still not aligned to the full final tab list from the master spec.
- QR code generation/download/revoke is not implemented; current packet has only a reference.
- Promo code management is missing.
- Store close/pause/reopen/clone/relaunch/export tools are missing or incomplete.
- Store orders projection UI is not complete.
- Fulfillment push into canonical production workflow is not complete.
- Notifications need a Webstores area feed, not only generic owner/admin notification.
- The UI needs one coherent workflow model, not duplicated timeline/tabs/step names.

Implementation plan:

1. Rework `/webstores` into manager home: list, filters, action required, status counts, Stripe incomplete, questionnaire waiting, orders needing review.
2. Add a Store Tools panel: QR code, promo codes, close/pause/reopen, clone/relaunch, exports.
3. Add manager assignments and permission-aware filtering to the UI.
4. Add store orders projection backed only by canonical Orders/Order Items after verified checkout.
5. Add a Webstores activity/notification feed in the workspace.
6. Keep the vertical timeline and make tabs visually clear.

### 6.6 Public Webstore Storefront

Current status: partial and checkout-blocked.

Already present:

- Public storefront DTO by slug.
- Public branding assets and product images.
- Public product list for Live stores only.
- Cart quote/purchase-intent endpoints that currently fail closed without provider readiness.
- Public confirmation route expects a verified canonical-order linked intent.

Still missing or incomplete:

- Public product detail route/page.
- Buyer cart UI with variant selection, quantity, personalization, pickup/shipping, donation, promo code, and checkout validation.
- Real checkout payment flow.
- Donation prompts only where configured.
- Fundraiser goal/progress meter.
- Promo code validation and immutable discount snapshots.
- Store deadline/closed/late-order customer-safe messages.
- Buyer confirmation/receipt flow tied to canonical order/payment.
- Mobile storefront polish and conversion-focused product browsing.
- FAQ display and owner-approved public copy.

Implementation plan:

1. Finish public storefront pages: home/catalog, product detail, cart, checkout, confirmation.
2. Server-quote every cart before payment and reject public money authority fields.
3. Add donation/promo/deadline rules server-side.
4. Wire real provider checkout only after Stripe adapter is available.
5. Add public-safe DTO checks that prove no cost, margin, internal notes, owner private fields, or provider secrets leak.

### 6.7 Public Forms And Questionnaires

Current status: partial.

Already present:

- Internal questionnaire templates.
- Type-specific default questionnaire sections.
- Owner portal questionnaire draft/submit.
- Staff response review and safe answer mapping.
- Submission notifications.
- Setup files and uploads.

Still missing or incomplete:

- Public token-based questionnaire route such as `/questionnaire/:token`.
- FormRequest records with token, expiry, recipient, status, consent metadata.
- FormResponse record shape that preserves original answers, attachments, submitted timestamp, and consent.
- ResponseMapping UI that shows exactly where every answer can be applied.
- AI summary and AI missing-info detection.
- Follow-up task creation from missing answers.
- Reusable form/template governance shared with Docs/Questionnaires.
- Store/customer linkage for public forms outside owner portal.

Implementation plan:

1. Keep owner portal questionnaire as the authenticated primary path.
2. Add token request/response records for email-only questionnaire links if required.
3. Build a staff response review screen with original answers, attachments, summary, mapping preview, apply buttons, and follow-up tasks.
4. Add AI summary/missing-info only through Phase 5 AI action rules.
5. Add focused checks for token expiry, store scope, original-answer preservation, and safe mapping.

## Required MVP Feature Checklist From The Master Spec

| # | Required feature | Current state | Remaining work |
| --- | --- | --- | --- |
| 1 | Sign shop account/login | Existing outside Webstores module | Keep using shared auth/permissions. |
| 2 | Platform admin | Partial | Add Webstores platform/global template, fee, volume, AI usage, support views later. |
| 3 | Webstore creation wizard | Partial | Finish full-page wizard and type-aware requirements. |
| 4 | Portal type selection | Partial | Expand type behavior matrix and defaults. |
| 5 | Store owner records | Partial | Finalize canonical Customer bridge. |
| 6 | Store Owner Portal login | Partial | Improve dashboard/invite/expired-token UX. |
| 7 | Questionnaire sending/submission | Partial | Add token route/FormRequest governance and response review UI. |
| 8 | Artwork upload | Partial | Finish owner/staff file governance and production readiness distinction. |
| 9 | AI artwork cleanup/background removal | Missing | Build only through approved AI/mockup provider flow. |
| 10 | AI questionnaire summary | Missing | Add AI summary with prompt/version/credit/audit. |
| 11 | AI missing info detection | Partial | Existing rule progress is not full AI detection. |
| 12 | Product Template Library | Partial | Dedicated management UI and global/tenant governance. |
| 13 | Product selection from templates | Partial | Improve selection UX and copy immutability proof. |
| 14 | AI product suggestions | Missing | Human-reviewed suggestion workflow needed. |
| 15 | AI product descriptions | Missing | Templates are prefilled; AI generation not done. |
| 16 | AI Mockup Builder | Missing | Artwork cleanup, mockup generation, approval workflow needed. |
| 17 | Mockup approval workflow | Partial | Records exist; full approval UI/tasks needed. |
| 18 | Store branding | Partial | Add type-specific public preview and approval integration. |
| 19 | Product images and variants | Partial | Strengthen variant/product-detail public UX and validation. |
| 20 | Store Launch Packet | Partial | Expand contents, preview/download, owner actions, and QR/promo integration. |
| 21 | Store owner approval flow | Partial | Version approvals across catalog/branding/packet. |
| 22 | Public store page | Partial | Complete buyer UX, product detail, cart, checkout states. |
| 23 | Buyer checkout | Missing/deferred | Requires real Stripe adapter and provider acceptance. |
| 24 | Fundraiser progress meter | Missing | Add configured goal/progress display and totals. |
| 25 | Donation tools | Missing | Add server-side donation config, prompt, snapshots, reports. |
| 26 | Stripe onboarding support | Foundation only | Real Connect onboarding/status/email pending. |
| 27 | Store owner billing settings | Partial/missing | Setup/monthly/relaunch fee settings and finance bridge needed. |
| 28 | Platform usage fee tracking | Partial | Snapshot foundation exists; final fee policy/reporting pending. |
| 29 | Orders | Partial | Verified checkout to canonical Orders/Order Items pending. |
| 30 | Reports | Partial | Real sales, payout, fees, donation, refund reports pending. |
| 31 | QR code | Placeholder | Generate/download/revoke/version real QR codes. |
| 32 | Promotional copy generation | Partial | Visible packet copy exists; AI/generated promo materials pending. |
| 33 | Activity log | Partial | Expand lifecycle, status, pricing, approvals, checkout, payout events. |
| 34 | Portal statuses | Partial | Align statuses to Phase 6 lifecycle and owner-safe wording. |
| 35 | Basic dashboard | Missing/partial | Webstores home action-required dashboard needed. |
| 36 | Product pricing defaults with production cost | Partial | Template defaults exist; deeper pricing foundation integration needed. |
| 37 | Store Launch Packet pricing summary | Partial | Owner-safe summary exists; final pricing/payout/fee summary pending. |

## Staged Build Sequence For The Rest Of Webstores

### Stage 1 - Design, Naming, And Workflow Cleanup

Goal: make the current MVP usable and consistent without enabling commerce.

Work:

- Convert visible product copy to Webstores naming where user-facing.
- Keep internal `webstores` routes/tables.
- Rework `/webstores` manager home into the primary list with status/action-required cards.
- Keep the create wizard simple: owner, store type/info, send questionnaire.
- Keep the vertical timeline on the right.
- Make tabs clearer and avoid duplicated step labels.
- Remove or hide launch/date/timezone controls except type-specific places where they matter.
- Add Webstores notification feed for questionnaire submitted, packet ready, change requested, Stripe incomplete, and order received later.

Acceptance:

- No route/table broad rename.
- No fake commerce readiness.
- Main list and detail workflow are visually clear and not duplicated.

### Stage 2 - Core Lifecycle And Type Rules

Goal: align core lifecycle and type behavior with Phase 6 before adding more checkout work.

Work:

- Implement one lifecycle transition service/route.
- Add lifecycle event records.
- Add type-specific requirement registry for B2B, Fundraiser, Event, Promotional, Employee, General.
- Add store settings schema for access policy, donation, pickup/shipping, deadlines, promo, tax/shipping copy.
- Use the requirements registry in readiness, setup progress, owner portal tasks, and manager action-required.

Acceptance:

- Illegal transitions are rejected server-side.
- Launch remains blocked until real prerequisites pass.
- Type-specific settings do not create separate codebases.

### Stage 3 - Questionnaires, Answers, Tasks, And Notifications

Goal: finish the owner intake loop.

Work:

- Add response review UI that shows original answers, attachments, AI/rule summary, missing info, and mapping destinations.
- Add follow-up tasks for missing answers.
- Add FormRequest/FormResponse/token flow if email-only questionnaire links are required outside owner login.
- Keep owner portal questionnaire as the preferred path.
- Add desktop/app and Webstores-specific notifications.

Acceptance:

- Original answers are preserved.
- Safe answer mapping is explicit and reversible where needed.
- Staff can read and use answers without digging through raw data.

### Stage 4 - Product Templates, Catalog, Mockups, And Approval

Goal: make shop product setup fast and safe.

Work:

- Build dedicated Product Template Library UI.
- Improve template-to-product flow with default descriptions, category, variants, prices, cost, owner/fundraiser share, and mockup slots.
- Add upload mockup image flow directly in product setup.
- Add catalog approval versioning.
- Add mockup approval tasks.
- Defer AI generation until AI gateway/provider rules are authorized.

Acceptance:

- Template edits do not mutate store products.
- Owner approval references an exact version.
- Product cards can be prepared with image/mockup and owner-safe copy.

### Stage 5 - Launch Packet, QR, Promo, And Owner Approval

Goal: make owner approval and launch materials complete before commerce.

Work:

- Expand packet contents to include store overview, owner details, purpose, branding, product list, mockups, owner-visible pricing/share, donation settings, Stripe status, QR/share link, promo materials, and approval actions.
- Generate real QR code files/URLs.
- Add promo text generation/display and copy/download actions.
- Add approval/request-changes/message-shop actions with version references.
- Invalidate approvals on material changes.

Acceptance:

- Owner can understand what they are approving.
- Staff can preview, regenerate/edit, send, and track packet status.
- QR/promo outputs are visible and usable.

### Stage 6 - Public Storefront And Cart, Still Payment-Gated

Goal: finish the buyer experience up to provider checkout.

Work:

- Build public home/catalog, product detail, cart, checkout, and confirmation screens.
- Add variant/personalization validation UI.
- Add donation and fundraiser progress display where configured.
- Add promo code server validation and immutable discount snapshots.
- Add clear closed/expired/late-order messaging.
- Keep payment blocked until Stripe provider is real.

Acceptance:

- Public DTOs leak no internal fields.
- Cart quote is server-authoritative.
- Non-Live stores remain unavailable without metadata leakage.

### Stage 7 - Stripe Connect And Verified Commerce

Goal: enable real payments only after provider acceptance.

Owner/architecture decisions required first:

- Charge model: direct charges, destination charges, or separate charges/transfers.
- Merchant of record.
- Refund, dispute, chargeback, tax, negative-balance responsibility.
- Owner/fundraiser/share routing.
- Whether platform-initiated transfers are authorized.

Work:

- Emergent implements real Stripe adapter behind existing provider boundary.
- Add Connect onboarding/status email and owner action.
- Add Checkout Session or PaymentIntent creation.
- Add signed webhook verification with raw body and replay protection.
- Create canonical Customer, Order, Order Items, Payment, and allocation snapshots exactly once.
- Reconcile refunds, disputes, payouts/transfers.

Acceptance:

- Duplicate browser submit and webhook retry create exactly one result.
- Invalid webhook signatures are rejected and logged.
- Launch/payment gates use provider authority, not stored flags.

### Stage 8 - Orders, Production, Reports, And Relaunch

Goal: operate live stores after verified commerce exists.

Work:

- Build store orders projection from canonical Orders/Order Items.
- Push production-needed metadata into production workflows.
- Add owner-safe sales/payout reports.
- Add internal fee, refund, donation, and product reports.
- Add pause/close/reopen/archive/relaunch/clone flows.
- Preserve historic confirmations and snapshots.

Acceptance:

- Production can work from canonical Order Items without a separate webstore database.
- Reports do not invent payout truth.
- Closed/archived stores preserve history.

## Focused Verification Policy

Do not run broad excessive tests for every small change.

Use focused checks tied to the module touched:

- Backend syntax/import check for changed service/router/model files.
- Frontend parser/build check for changed pages/components when JSX changes.
- One focused backend test file for lifecycle/catalog/payment/owner/public behavior touched.
- One focused frontend test file for a changed user workflow when UI behavior changes.
- Stripe connected acceptance only after the real provider adapter exists.

## Final Completion Gate

Phase 6 is not complete until all of the following are true:

- A manager can create a Webstore, send intake, configure catalog/branding/payments, request approval, and launch through validated lifecycle gates.
- Owner can complete intake, upload files, review/approve exact packet/catalog/branding versions, complete Stripe onboarding if required, and view owner-safe sales/payout information.
- Public buyer can browse, select variants, donate where configured, apply valid promo codes, pay securely, and receive confirmation.
- Verified payment creates canonical Customer, Order, Order Items, Payment, and immutable snapshots exactly once.
- Production sees webstore-originated Order Items without a second webstore order source of truth.
- Public/owner/internal zones enforce server-side authorization and safe DTOs.
- Failed payment, duplicate checkout, expired/closed store, late event order, missing Stripe onboarding, deleted product after sale, refund/cancellation, and payout status are handled and logged.
