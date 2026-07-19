# SignGuy AI — Owner Specification Hold Register

**Purpose:** Every explicit "do not proceed without owner authorization" hold currently in force, in one place, so no hold is silently forgotten or silently cleared. Created 2026-02 during the SignGuy AI Checkpoint Specification Pack intake.

**Rule:** No checkpoint below begins — no code, no models, no routers, no pages — until its hold is explicitly lifted by the owner. Completing this documentation-only intake and delivering the Intake Report does **not** lift any hold.

## Active holds (2026-02 intake)

| # | Hold | Scope | Condition to lift | Status |
|---|---|---|---|---|
| H1 | **No checkpoint starts automatically after this documentation update.** | All of EC9–EC22 | Explicit owner "go" message naming the checkpoint to start. | ACTIVE GLOBALLY - CLOSED FOR EC18 ONLY by 2026-07-19 owner authorization on `CODEX-ec18-branch`; EC19 and later still require separate owner authorization |
| H2 | **EC14 Webstores requires separate owner authorization.** | EC14 | Owner explicitly authorizes EC14 start (separate from generic "start EC9" authorization). | CLOSED FOR EC14 - 2026-07-19 owner prompt authorized EC14 on `CODEX-EC14-BRANCH`; EC14 completed with CI `29677455165`; does not lift H3-H8 |
| H3 | **EC15 Wrap Lab requires separate owner authorization.** | EC15 | Owner explicitly authorizes EC15 start. | CLOSED FOR EC15 - 2026-07-19 owner prompt authorized EC15 on `CODEX-ec15-branch`; does not lift H4-H8 or later checkpoint holds |
| H4 | **EC16-EC18 AI work requires separate authorization.** | EC16 (Shared AI Gateway), EC17 (Studio AI Tools), EC18 (Paid Business Assistant/Voice) | Owner explicitly authorizes AI-checkpoint work to begin. | CLOSED FOR EC16, EC17, AND EC18 ONLY - 2026-07-19 owner prompts authorized EC16, EC17, and EC18. EC18 authorization applies only to `CODEX-ec18-branch` and does not lift H7 or later checkpoint holds |
| H5 | **EC17 is blocked until the owner completes the AI Tools Keep / Combine / Change / Rename / Defer / Remove review.** | EC17 specifically | Owner completes the full tool-by-tool review worksheet (28+ legacy AI tools) and assigns a final status + Final Name + Family to every tool. | CLOSED FOR EC17 - owner accepted the EC17 worksheet and supplied final tool decisions, approved capability identifiers, removed tools, EC18-only identifiers, and Meta-only identifiers on 2026-07-19 |
| H6 | Wrap Lab **standalone** activation requires a completed preflight proving shared-core reuse without duplication. | Wrap Lab standalone sale only (not Founder-included or add-on use) | Preflight completed and owner-approved (carried forward from old master plan Decision 7; still binding under EC15). | SATISFIED FOR EC15 SHARED-CORE IMPLEMENTATION - standalone annual pricing and public standalone purchase flow remain unavailable |
| H7 | AI top-up pricing, included AI-credit amounts, and AI provider/model assignments are approved **subject to a measured provider-cost audit** before live commercial activation. | EC13/EC16/EC17 commercial AI numbers | Provider-cost audit completed after 10–20 active paying shops (per rollout discipline); numbers may be adjusted before activation. | ACTIVE (carried forward from old master plan Decisions 12/13/18; reaffirmed by EC13/EC16/EC17) |
| H8 | Studio AI tool inventory must receive an owner **Keep / Change / Remove** review before EC17 implementation — no legacy tool list is automatically final. | EC17 | Same worksheet as H5 (this is the Master Index's phrasing of the same hold; tracked together with H5). | CLOSED FOR EC17 - same owner decision set as H5; removed, EC18-only, and Meta-only tools must not become active EC17 tenant tools |

## Commercial authority — confirmed scope (registered, not yet activated)

The commercial authority for EC13 (and its EC19/EC21 dependents) is confirmed to include all of the following. None of it is implemented — this is a documentation registration only:

- Subscription prices (Founder + General Availability: Core, Webstores add-on, Wrap Lab add-on, Complete Bundle)
- Annual prices ("pay 10, get 12" annual billing)
- Setup and onboarding fees (DIY $0 / Founder Kickstart $299 / Standard $499 / Full Optimization $999 / White-Glove $1,999+, plus setup add-ons)
- Trials (48-hour free trial, 7-day extended trial)
- Extended-trial credit ($20 credited toward first paid subscription if converted within 14 days)
- AI credit packs (100/$19, 300/$45, 800/$99 — provisional, subject to H7)
- Platform fees (Founder 0% → 0.5%/1.5%; GA 1.0%/2.0%)
- Add-on pricing (Webstores, Wrap Lab as Core add-ons)
- Standalone pricing (Webstores, Wrap Lab as standalone products — **see open contradiction C1 below**)
- Entitlements (feature access gated by plan/add-on/standalone status)

## EC13 post-preflight owner decisions (2026-07-18) - LOCKED before implementation

The EC13 preflight is accepted as COMPLETE. These owner decisions refine the implementation authority for EC13 and must be used before any EC13 implementation phase begins:

1. **Founder availability and scope**
   - Founder availability is the first 25 signed shops, not 50 users.
   - Founder status is assigned per tenant/shop, not per individual user.
   - Existing explicit EC12 Founder access must be preserved until the EC13 migration contract is implemented and verified.

2. **Smart Pricing**
   - Do not include Smart Pricing as a paid add-on in EC13.
   - EC13 may only ensure the commercial billing architecture can support future add-ons.
   - Smart Pricing pricing and entitlement rules remain deferred to the owning checkpoint.

3. **SMS/MMS**
   - Do not define or seed final SMS/MMS pricing in EC13.
   - EC13 may support future usage-billing hooks and categories.
   - External SMS sending, provider integration, final usage pricing, and credit rules remain deferred.

4. **Webstores and Wrap Lab pricing availability**
   - EC13 must support monthly, annual, add-on, and standalone price models.
   - Only owner-approved active prices may be published or sent to Stripe.
   - Unapproved products/prices must remain unavailable, not zero-priced or placeholder products.
   - Do not invent or seed unapproved standalone monthly or annual prices.

5. **Platform-fee refunds**
   - Store the original platform fee as an immutable transaction snapshot.
   - A full refund creates a proportional full platform-fee reversal.
   - A partial refund creates a proportional partial platform-fee reversal.
   - Stripe or provider fees are recorded separately and are not silently rewritten.
   - Manual exceptions require platform-admin permission, a reason, an audit event, and a separate adjustment record.
   - Never modify or delete the original fee transaction.

Phase 13A planning authority: `/app/preflight/EC13_PHASE13A_COMMERCIAL_BILLING_CATALOG_AND_CORE_CONTRACTS_PLAN.md`.

## Resolved contradictions (owner decisions received 2026-02) — RESOLVED, NOT open holds anymore

### C1 — RESOLVED: Standalone Webstores/Wrap Lab pricing

**Owner decision (2026-02):**

| Product | Add-on (Core) | Add-on annual | Standalone monthly | Standalone annual |
|---|---|---|---|---|
| Webstores | $89/month | $890/year | **$109/month (provisional)** | **NOT YET APPROVED — pending** |
| Wrap Lab | $119/month | $1,190/year | **$139/month (provisional)** | **NOT YET APPROVED — pending** |

Rules (owner-locked): standalone pricing is permanently a distinct figure from add-on pricing (never "same as add-on" again); standalone products include shared-platform infrastructure without requiring a Core subscription; no annual standalone price is invented — annual standalone remains explicitly pending owner approval until a future decision; EC14/EC15 must build the standalone-annual field/UI as "coming soon / not yet available," never a placeholder guess.

**Superseded by this decision:** the old master-plan Decision 10 rule and `REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` §2 rule that priced standalone = add-on price. Both are now **SUPERSEDED — HISTORICAL REFERENCE ONLY — NOT IMPLEMENTATION AUTHORITY** for standalone pricing specifically (add-on pricing and every other figure in those documents remains valid/unchanged).

### C2 — RESOLVED: Dunning and failed-payment handling

**Owner decision (2026-02) — day-based delinquency model (authoritative):**

- Days 1–7: reminder + grace period (normal access).
- Days 8–14: escalated warning (soft restriction).
- Day 15+: eligible for suspension (not automatic — "eligible," a manual/automated gate, not an instant hard block).

Rules (owner-locked): Stripe payment-failure webhook events (`invoice.payment_failed` / `invoice.payment_succeeded`) update the tenant's delinquency state; **Stripe's internal retry-attempt count is never the suspension authority** — only the day-based clock is; must support configurable grace-period extensions (admin-granted) and approved Founder exceptions (e.g., the existing 24-hour Founder Grace concept, now folded into "configurable grace extension" rather than a separate mechanism); a successful payment OR a manually-recorded/cleared payment resets the delinquency state immediately; every suspension and reactivation must be audited (actor, reason, timestamp).

**Superseded by this decision:** the EC20 "3-strikes" dunning model (`EC20_Platform_Admin_Analytics_Dunning_and_Support.docx`) is now **SUPERSEDED — HISTORICAL REFERENCE ONLY — NOT IMPLEMENTATION AUTHORITY**. The day-based model (originally old master plan Decision 26, restated in `REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` §8) is reaffirmed as authoritative, with the Day 15+ "eligible for suspension" phrasing (not an automatic hard block) and the Stripe-webhook-driven / configurable-grace / Founder-exception / reset / audit rules above layered on top as refinements.

### C3 — RESOLVED: AI subscriptions, credits, and credit packs

**Owner decision (2026-02):** no separate Starter/Growth/Power/Agency (or any other) monthly AI-subscription tier is created. The approved commercial model is:

- Monthly AI credits are included according to the tenant's approved plan (Founder/Core/Webstores/Wrap/Complete — per EC13, unchanged).
- Purchased top-up packs (one-time, unchanged from the existing commercial authority): 100 credits/$19, 300 credits/$45, 800 credits/$99.
- Studio AI Tools (EC17) are gated by plan entitlement + available credit balance — not by a separate AI subscription tier.
- The paid Business Assistant (EC18) is a separately entitled add-on, handled under EC18's own commercial terms — not part of this credit model.
- No "unlimited AI" is ever promised in marketing, UI, or copy.
- Actual provider cost (`cost_usd`, tokens, provider/model) must be tracked separately from the customer-facing credit ledger (cost ledger vs. credit ledger stay two distinct records, per EC16).

**Superseded by this decision:** the EC17 "Starter $19/Growth $49/Power $99/Agency $199" monthly AI-tier proposal (`EC17_Studio_AI_Tools_OWNER_REVIEW_REQUIRED.docx`) and any other legacy AI-subscription-tier proposal are now **SUPERSEDED — HISTORICAL RESEARCH ONLY — NOT IMPLEMENTATION AUTHORITY**. This does not lift hold H5/H8 — the owner's tool-by-tool Keep/Combine/Change/Rename/Defer/Remove review for EC17 is still required before EC17 implementation; this decision only settles the pricing-model question so that review isn't blocked on it.

## Resolved (no contradiction found)

- Founder eligibility count and pricing ($119→$189/mo, 25 shops, $1,890/yr), GA Core/Webstores-add-on/Wrap-add-on/Complete pricing, credit-pack amounts, setup-fee tiers, and trial terms in EC13 all **match** the existing `REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` exactly. (The *older* master-plan Decision 10/11 numbers — 50 shops, flat $149/mo Founder — were already superseded by that 2026-07 revision before this intake; EC13 simply reconfirms the 2026-07 revision.)
- EC19's setup-fee tier names/amounts match EC13 exactly.
- EC09's and EC19's pricing-quiz descriptions (one practical scenario question deriving labor rate/minimums/sell rate) are consistent with each other.

**2026-07-18 EC13 refinement:** only owner-approved active prices may be published or sent to Stripe. Unapproved standalone products/prices must remain unavailable; they must not be represented as zero-priced products or placeholder Stripe products. EC13 preflight is accepted COMPLETE; no EC13 implementation phase has started.

## EC14 owner authorization (2026-07-19)

The owner explicitly authorized EC14 Webstores to start on `CODEX-EC14-BRANCH` after EC13 was closed and merged. EC14 completed on 2026-07-19 at implementation commit `75c7c699b58262ed2fa550a1fd0a11e77e0f677b` with GitHub CI run `29677455165` passing. H1/H2 are closed for EC14 only.

Still held/deferred:

- EC15 public standalone sale/annual standalone pricing beyond the shared-core runtime plan.
- EC16 live commercial/provider activation under H7; EC17-EC18 AI/provider work under H4/H5/H7/H8.
- EC19 onboarding/help and later checkpoints until separately authorized.
- Webstores standalone annual pricing remains not approved and unavailable.

## EC15 owner authorization (2026-07-19)

The owner explicitly authorized continuation into EC15 Wrap Lab after EC14 was closed and merged. EC15 preflight is complete in `/app/preflight/EC15_WRAP_LAB_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`; it documents shared-core reuse, no duplicate systems, no live AI/provider execution, no live Stripe/Checkout/subscription work, no EC19 work, and no approved standalone annual Wrap Lab price.

## EC16 owner authorization (2026-07-19)

The owner explicitly authorized continuing with the next incomplete checkpoint after EC15 on `CODEX-ec16-branch`. Repository authority identifies that checkpoint as EC16 Shared AI Gateway, Usage, Cost, Credits, and Governance. H4 is closed for EC16 only. H7 remains active: AI top-up pricing, included credit amounts, provider/model assignments, and live commercial/provider activation remain subject to the measured provider-cost audit.

Still held/deferred:

- EC17 Studio AI Tools until separate H4 authorization and H5/H8 tool worksheet completion.
- EC18 Paid Business Assistant/Voice until separate H4 authorization.
- EC16 live commercial/provider activation under H7.
- EC19 onboarding/help and later checkpoints until separately authorized.

## EC17 owner authorization and tool decision closure (2026-07-19)

The owner authorized EC17 implementation on `CODEX-ec17-branch` after accepting the EC17 owner-decision worksheet. H4 is closed for EC17 only. H5/H8 are closed for EC17 only.

Required EC17 active tool families:

- Design & Image Studio
- Marketing & Brand Studio
- Business Writing & Documents
- Pricing & Profitability

Approved active EC17 capability identifiers are recorded in `/app/preflight/EC17_STUDIO_AI_TOOLS_PROMPT_LIBRARY_GENERATED_ASSETS_AND_ACTIVITY_PREFLIGHT.md`.

Removed by owner and inactive in EC17:

- `order.service_prefill`
- `studio.text.bulk_followup`

Assigned to EC18 and inactive in EC17:

- `assistant.email_draft`
- `assistant.chat`
- `assistant.action_parse`
- `assistant.voice_transcription`
- `assistant.voice_reply`
- `assistant.intent_classify`
- `assistant.navigation_classify`
- `assistant.memory_compress`

Future Meta integration only and inactive in EC17:

- `integration.facebook.message_classify`
- `integration.facebook.order_extract`

H7 remains active for EC17. EC17 must not make live external provider calls, publish final numeric credit pricing, activate production AI providers/models, implement BYOK/MCP/realtime voice, commit secrets, or start EC18/EC19/later checkpoint scope.

## EC18 Authorization - Paid Business Assistant, Actions, Intelligence, and Realtime Voice

The owner authorized full EC18 implementation on `CODEX-ec18-branch` after EC17 was merged to `main`. H1 and H4 are closed for EC18 only. OpenAI Realtime speech-to-speech is the selected EC18 voice architecture. H7 remains active for final commercial AI-credit prices, included AI-credit amounts, final production model locking, production API-key provisioning, other provider families, BYOK, MCP, and unrelated provider/commercial decisions.

EC18 may implement backend Realtime session credentials, browser WebRTC voice UI, voice/action bridge, metering hooks, assistant conversations, structured action proposals, Business Intelligence, routines, insights, memory controls, and documentation. Production activation remains config-controlled and no permanent API key or secret may be committed.

Still deferred: EC19 and later checkpoints, Meta/Facebook activation, Stripe/Checkout/subscription/billing portal/webhook changes, EC4 invoice/payment mutation, Webstore payout mutation, final AI-credit pricing, BYOK/MCP, and non-OpenAI provider decisions.

**Register last updated:** 2026-07-19 - EC18 owner authorization recorded and EC18 implementation completed pending final branch-head CI. H1/H4 are closed for EC18 only. H7 remains active. EC19 and later checkpoints remain held/deferred.
