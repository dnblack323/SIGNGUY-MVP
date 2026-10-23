# SignGuy AI MVP — Commercial V1 Launch Plan

**Current owner authorization, October 22, 2026:** Stages B and D engineering/mock verification are accepted; Stage C engineering remains the voice foundation, with commercially cleared previews still required for release. Stage E controlled actions and approved private memory are implemented for owner review in the existing Business Assistant worktree/branch and draft PR #63. See docs/BUSINESS_ASSISTANT_V1_STAGE_E_REVIEW.md (repository-relative). This supersedes historical B-pending, D-pending and E-prohibited wording below only for the authorized scope. No paid calls, preview generation, Stage F, merge or deployment are authorized. Unrelated feature holds remain unchanged.

**Current owner decision, October 21, 2026:** Stage B is ACCEPTED for its approved scope. Stage C voice selection, prerecorded preview and microphone/interface readiness is authorized and implemented for review. The original C/D split applies; complete Realtime remains D. This supersedes historical B-pending/C-unstarted or combined-C/D statements below. No paid evaluation, D–F implementation, merge or deployment is authorized. See [Stage C report](../evidence/EC18_STAGE_C_EVIDENCE.md). Unrelated features, including postponed onboarding/Help Center, remain outside this work.

**Prepared:** 2026-10-14 from the completed audits (no new general audit was performed).
**Revised:** 2026-10-21 — Business Assistant V1 required for initial release; Stage A APPROVED; Stage B implemented with mocks, awaiting owner acceptance. The October 14 tracks and unrelated work are preserved: **Track 1** independent MVP features; **Track 2** pricing integration when its gate opens; **Track 3** launch completion. BA1 is required before launch; C–F remains held.
**Status:** APPROVED by the owner 2026-10-14 (three-track strategy and order). Each feature and each stage still needs separate owner authorization and its own PR. Business decisions in §B remain open.
**Current authorized feature (owner, 2026-10-21): Business Assistant V1 Stage B implementation, now awaiting owner acceptance.** [Stage A](BUSINESS_ASSISTANT_V1_STAGE_A_REVIEW.md) is APPROVED with recommended launch scope/architecture and user-private conversations/memory. Business Assistant is **REQUIRED for initial release**, including real text, shared tools/context, memory, authorized actions, voice and five personalities. See [Stage B review](BUSINESS_ASSISTANT_V1_STAGE_B_REVIEW.md) and [implementation plan](BUSINESS_ASSISTANT_V1_IMPLEMENTATION_PLAN.md). **Stage B was implemented and tested with mocks; C–F, paid evaluations and merge are not authorized.** Preserve unfinished F3 and other work; unrelated ordering is unchanged. Historical F1/F2 completion (#42/#43) remains; the original checkout's F3/launch-plan WIP is not overwritten.

**Sources used:** `docs/audits/MVP_BASELINE_AUDIT_2026-10-10.md`, `docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv` (124 rows, cited below as `#n`), `docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md` (`CH-n`), `memory/code_issue_register.md` (`CIR-n`), `memory/owner_specification_hold_register.md`, targeted source checks recorded in §B, and Price Lab `origin/main` merge history (read-only).

---

## A. Current functional baseline

**Honest summary:** the audit runtime-verified **0 of 124** features. 95 are connected end-to-end in code (screen → API → tenant-scoped database) with focused tests; 19 are partial. "Built and wired" is not yet "proven working for a paying customer."

| Area | What exists in code and tests |
|---|---|
| Accounts | Shop registration, tenant-scoped login, roles and three separate permission scopes, password reset, account suspension, production startup guards that refuse a dev bypass or placeholder secrets |
| Shop setup | Company settings, an older Pricing Foundation and guided setup (to be replaced by Price Lab's in Track 2), onboarding checklist and Help Center (EC19 foundation) |
| Sales | Customers (with merge), staff intake, quotes with immutable revisions, line-item pricing through the private Pricing Engine 0.1.0, idempotent quote → order conversion |
| Fulfilment | Orders, Work Orders, production stages, timeline, board and kiosk; Shop Schedule; order completion packets |
| Money | One invoice per order, backend-calculated totals in integer cents, manual payment recording (concurrent overpayment defect CIR-001 fixed) |
| Subscription business | Stripe subscription checkout, billing portal, 48-hour and 7-day trials, setup packages, day-based dunning, platform-fee ledger (EC13 and EC20 closed), platform admin console |
| Quality gates | GitHub CI runs backend tests, frontend tests and a production build on every branch; 24 of 32 code-issue-register defects fixed and verified; Shop Operations section reviewed and corrected end-to-end |

Also built but outside the currently approved first-release implementation scope: Webstores, Wrap Lab, Team/payroll, inventory/purchasing and AI Studio. **Business Assistant V1 is required before launch** (owner, 2026-10-21); its current deterministic/local text foundation is not release acceptance, and the provider, shared text/voice tools, cost controls and real workflow evidence must be completed.

## B. Launch blockers

B1, B2, B4 and B5 were confirmed by direct source checks on 2026-10-14; B9 is owner direction; the rest come from the audits.

| # | Blocker | Evidence |
|---|---|---|
| **B1** | **Not paying does not lock anything.** `require_entitlement` (`backend/app/deps.py:83`) has zero callers. Trials expire only when a platform admin calls `POST /api/billing/platform/trials/expire`. Billing suspension writes `tenant_billing_accounts.status`, while the request gate checks only `tenants.is_active` (`deps.py:41`, `tenant_billing.py:562`). | Source check; refines `#100`, `#101` |
| **B2** | **Signup is not connected to a plan.** Registration (`backend/app/routers/auth.py`) creates no billing account and starts no trial. Since F1, shops with no trial or subscription history remain **temporarily unrestricted during development**; L3 must close this before launch (trial duration and automatic enrollment are open owner decisions). No public plan page, Terms of Service or Privacy page exists (EC21 not started). | Source check; `#2`, `#101` |
| **B3** | **No production deployment.** `docker-compose.yml` is development-only: `ENV=development`, `AUTH_DEV_BYPASS=true`, placeholder JWT secret, published MongoDB port, HTTP only, filesystem storage, no backups, no error monitoring. | Source check; audit §10–11 |
| **B4** | **Online invoice payments would send shop money to SignGuy's Stripe account.** `stripe_core.create_payment_intent` charges the platform account using the same `STRIPE_API_KEY` that subscriptions need. Must stay off until moved to Stripe Connect (U2). | Source check; `#29` |
| **B5** | **Email is unproven** (password reset, registration). | `#2`, `#4`, `#31` |
| **B6** | **The core workflow was never run end-to-end** with two-tenant isolation. | `#11`–`#28`, `#42`–`#52`; audit §4 |
| **B7** | **Open data-integrity defects in V1 workflows:** CIR-025 (customer merge), CIR-028 (Shop Schedule conflicts), CIR-031 (production timers/stage moves). | `memory/code_issue_register.md` |
| **B8** | **Unfinished modules must not be sold:** Webstores (CIR-026/027), AI (mock only, hold H7), customer-facing public links (CIR-005/030/032). B1 enforcement is the switch. | Audit §3, §8; CIR register |
| **B9** | **MVP pricing does not match the approved Price Lab pricing.** MVP runs Engine 0.1.0 and an older Pricing Foundation and calculators. Price Lab's Foundation, nine calculators and newer Engine are required before launch. | Owner direction 2026-10-14; `#48`–`#52` |
| **B10** | **Required Business Assistant V1 is not launch-ready.** Real text conversation, bounded history/memory, correct permitted shop-data tools, safe task/note/draft actions, shared Realtime behavior, five personalities and trustworthy usage/cost enforcement need implementation and acceptance. | Owner direction 2026-10-21; [Stage A review](BUSINESS_ASSISTANT_V1_STAGE_A_REVIEW.md); `#93–#96`; H7 remains a release gate, not permission to defer this feature |

**Owner decisions:**

1. **Development strategy — DECIDED 2026-10-14.** Two tracks as in §D, recorded in `memory/owner_specification_hold_register.md`. UX1 Dashboard Customizer (Track 1 F2) and Shop Schedule UI modernization (F3) are pulled ahead of the rest of UX1; nothing is removed from the roadmap.
2. **Pricing gate opening** — the owner declares when Price Lab's V1 pricing contracts are stable (§E criteria).
3. **Subscription prices and Founder offer — OPEN, owner decision.** Final V1 prices, Founder offer details and which feature keys Core grants are not approved by this plan. Only owner-approved prices may reach Stripe (EC13 decision 4). Needed by F1 and L3.
4. **Trial duration and automatic activation — OPEN, owner decision.** Not approved by this plan. F1 implements whichever trial policy the owner decides. Needed by F1.
5. **Hosting provider and domain — OPEN, owner decision.** Needed by L4.
6. **Material and Resource ownership** — Price Lab's Materials/Equipment/Hardware Resources must map onto MVP's existing material and equipment records rather than become a second catalog (locked "no parallel stores" rule). Decided at the start of P2.
7. **Wrap Lab included in Core — DECIDED 2026-10-14.** Wrap Lab is not a paid add-on; Webstores is the only separately purchased feature add-on. Older separate Wrap Lab add-on/standalone pricing is superseded (see owner register).
8. **AI included in the standard subscription — DECIDED 2026-10-14.** Existing EC17/EC18 code still checks the `ai_studio` / `business_assistant` entitlement keys; the standard plan's catalog rules must grant both keys when commercial values are finalized (catalog configuration, not new code). Credit allowances and pack prices are unchanged and finalized separately.

## C. First release scope — "Core V1"

**Included:** signup → trial (per owner trial decision) → Core subscription purchase → company settings → **Price Lab Pricing Foundation** → staff users and roles → customizable Home dashboard → customers → quotes priced with the **Price Lab category calculators** (all nine, full-page and order overlay) → staff-recorded quote approval → quote-to-order → work orders, production board and Shop Schedule → invoices → manual payment recording → billing portal, dunning and suspension → onboarding checklist, Help Center and support email → **Business Assistant V1 with real text and voice, shared permitted shop tools, bounded conversational context/memory, confirmed actions and all five personalities** (owner, 2026-10-21; launch boundary proposed in the Stage A review).

**Commercial rules (owner, 2026-10-14):** Core includes all standard business-management modules, including Wrap Lab, AI Studio and the AI Business Assistant when released; AI usage draws on monthly included credits and optional purchased packs (§E-AI). **Webstores is the only separately purchased feature add-on**: publishing is enforced by the `webstores` entitlement in the backend, and the module is also marked not yet released for V1. Technical entitlement keys may remain for backend authorization, but Core-included features never require a separate purchase. Release availability is separate from commercial entitlement: unreleased features stay unavailable until approved. Online card payment of invoices stays off until Stripe Connect (U2). **Open owner decision:** whether unfinished Core modules (inventory/purchasing, team time clock/payroll/employee portal, decision rooms and proofs, intake forms, customer portal and public approval links) are hidden at V1 launch (release availability, not a tier).

## D. Development order

One feature at a time, each on its own branch and PR, each started only with owner authorization. All three tracks and **BA1 Business Assistant V1** are **required before the first paid launch**; Track 2 starts only when its gate opens. Business Assistant Stage A is APPROVED; Stage B implementation is delivered for owner acceptance, and C–F remains held. Its launch requirement supersedes earlier AI deferral without changing unrelated feature priorities or authorizing live provider/commercial activation. If Track 1 finishes first, separately authorized Track 3 items that do not depend on pricing (L3, L4) may proceed.

**Track 1 — Independent MVP features (now, while Price Lab finishes its categories)**

Preserve MVP backend business logic, tenant isolation, permissions and Order/Work Order terminology. Use approved Price Lab layouts and interaction patterns as references where applicable (Price Lab `src/features/home`, `operations`, `customers`, `team` on `origin/main`); no SQLite, Electron or desktop code; do not overwrite working MVP features.

| Feature | Scope | Rows / IDs | Class |
|---|---|---|---|
| **F1 Subscription access control** — ✅ COMPLETE (PR #42) | Enforce entitlements on staff API routes; automatic trial start and expiry; billing suspension blocks access; 402 → Billing page; unentitled modules hidden and blocked | B1, B8; `#5 #7 #100 #101` | C |
| **F2 Customizable Home dashboard widgets** — ✅ COMPLETE (PR #43) | One Home dashboard with nonduplicate, user-arrangeable widgets over existing dashboard/summary APIs; respects permissions and entitlements (UX1C scope) | `#8 #9 #10` | B |
| **F3 Shop Schedule UI modernization** | Modernized schedule views over the existing schedule service; fix CIR-028 conflict/duplicate enforcement since the surface is being made V1-ready | `#74`; CIR-028 | B (C for CIR-028) |
| **F4 Production Board improvements** | Board usability and status visibility over existing Work Order stages; no change to stage rules | `#44` | B |
| **F5 Customer interface improvements** | Customer list/detail usability; make merge safe and manager-only (CIR-025) | `#11 #12 #13`; CIR-025 | B (C for CIR-025) |

**Track 2 — Price Lab pricing integration (required before launch; starts when the §E gate opens)**

| Milestone | Scope | Rows / IDs | Class |
|---|---|---|---|
| **P1 Shared Engine upgrade and compatibility** | Pin a published, tested Engine release; consolidate the duplicated quote/order pricing resolver first (CH-02, CH-03); legacy snapshots readable; no historical recalculation | `#22 #52`; CH-02, CH-03 | C |
| **P2 Pricing Foundation modernization** | Price Lab Foundation structure, shared systems and Resources (§E); retire replaced MVP Foundation screens | `#48` | C |
| **P3 Category Defaults and Guided Setup** | Category Catalog, Category Defaults, Direct and Guided Setup, shared Draft, Review and Activate, Active-vs-Draft benchmarks, Reset to Starter | `#49` | C |
| **P4 Nine calculator implementations** | One category per stage (§E order): category settings + shared full-page/overlay calculator; material selling-rate rules | `#50 #51`; CH-04, CH-05, CH-20 | C |
| **P5 Pricing-to-Quote/Order integration** | Add to Quote/Order for all nine categories; snapshots immutable; backend cents totals | `#21` | C |
| **P6 Complete pricing workflow verification** | New shop → Foundation → each category → quote → order, on a disposable tenant; historical records unchanged | — | C |

**Track 3 — Launch completion (after Tracks 1–2, except L3/L4 which may start earlier)**

| Feature | Scope | Rows / IDs | Class |
|---|---|---|---|
| **L1 Customer → Quote → Order → Invoice → Payment** | Run the workflow with a second tenant proving isolation; fix what fails | B6; `#18 #19 #20 #23–#28 #30 #66 #97 #98` | C |
| **L2 Production workflow completion** | Order → work orders → stages, timers → completion; fix CIR-031 | B6, B7; `#42 #43 #45 #46`; CIR-031 | C |
| **L3 Signup, subscription purchase and email** | Minimal public plan page (approved price only), Terms and Privacy, registration → trial → Stripe test-mode checkout → webhook → entitlements; password reset via SendGrid; invoice card payments confirmed off | B2, B4, B5; `#1 #2 #4 #104` | C |
| **L4 Secure production deployment** | TLS, real secrets, `ENV=production`, private database, automated database and file backups with tested restore, error monitoring, health checks, staging copy | B3; re-verify `#6` | C |
| **BA1 Business Assistant V1 — REQUIRED BEFORE LAUNCH** | Complete the canonical assistant with the approved Stage A launch scope/architecture and user-private conversations/memory. Stage A APPROVED; Stage B IMPLEMENTED with mocks, owner acceptance pending; C–F NOT STARTED. Text/voice, safe actions, five personalities and real usage/cost controls remain required. No paid tests without a separate cap. | B10; `#93–#96`; H7; [Stage B review](BUSINESS_ASSISTANT_V1_STAGE_B_REVIEW.md) | C |
| **L5 Complete workflow verification and commercial launch** | Full critical-path run on staging, platform admin check, truthful plan copy, owner visual review, live Stripe keys, first Founder shops | `#108` | C |

**First feature updates after launch** (owner may reorder)

| Update | Scope | Rows / IDs |
|---|---|---|
| U1 Customer approvals and portal | Fix CIR-005, CIR-030, CIR-032; enable public quote/proof/completion links, decision rooms, customer portal, email history | `#31–#38 #109 #111 #112 #118` |
| U2 Online invoice payments | Move invoice card payments to Stripe Connect (shop's own account), then enable | `#29 #110` |
| U3 Intake and lead capture | Staff intake, public inquiry → intake conversion, forms and templates | `#14–#17 #39–#41 #120` |
| U4 Team and production floor | Time clock, timesheets, team schedule, tasks, training, employee portal, kiosk | `#47 #65 #67–#73 #75 #76 #78 #113–#117` |
| U5 Webstores add-on | Fix CIR-026, CIR-027; canonical order and production handoff | `#79–#86 #119 #124` |
| U6 Wrap Lab (Core module) | Runtime-verify and enable | `#87–#90` |
| U7 Inventory and purchasing | Materials, stock, reorder, purchase orders, receiving | `#54–#59` |
| U8 Finance reports | Expenses, finance dashboard, tax reports | `#61–#63` |
| U9 Experience polish | Rest of UX1 (visual system, ribbons/sidebar), Advanced Onboarding, help topic pages, Google sign-in, integrations and security views, community | `#3 #99 #103 #105–#107` |

**Later expansion** (permanent roadmap, not dropped): AI Studio and other AI capabilities outside the required Business Assistant V1 (`#92 #102`), subject to their own approvals and H7; pricing advisory (`#53`); live supplier connectors (`#60`); reporting rebuilds and payouts (`#64`); statutory payroll (`#77`); Wrap Lab post-install reports (`#91`); SMS. **Business Assistant, its real text provider integration and voice are initial-release requirements, not later expansion** (owner, 2026-10-21). Proposed later assistant enhancements are separated in the Stage A review and require owner acceptance.

## E. Price Lab pricing integration (Track 2)

**Gate — when Track 2 may start.** Stable V1 pricing contracts, not cosmetic perfection or final demo data:

1. All nine categories are merged in Price Lab `origin/main` as functional V1 (category settings, methods, calculator inputs and saved evidence no longer changing).
2. A selected, stable Engine release, published as a GitHub Release with a wheel asset (MVP's installer verifies a release asset by SHA-256). This is a P1 requirement only; Track 1 features do not need it.
3. Verified compatibility of that release with Price Lab.
4. No known blocking defects affecting the required V1 pricing contracts.
5. An approved migration and compatibility plan for P1.
6. Explicit owner authorization to begin P1.

Future Engine changes do not automatically block the MVP migration. MVP and Price Lab may run different verified Engine versions during controlled upgrades.

**Price Lab status at 2026-10-14** (from merge history, read-only):

| Category | Price Lab status |
|---|---|
| Banner | V1 complete (batches 1–3, workflow verification) |
| Rigid Signs & Panels | V1 merged (#111) |
| Cut Vinyl | V1 completion merged (#108) |
| Services | V1 completion + stage 3 merged (#109, #110) |
| Vehicle Graphics | V1 merged (#85, 2026-10-04); confirm against current approved package |
| Digital Print | V1 functional implementation complete and merged (#105, 2026-10-11); owner visual review pending |
| Apparel | In active development, not merged |
| Promotional Products | Early baseline only (Phase 4E) |
| Custom / Miscellaneous | Early baseline only (Phase 4F) |

**Engine versions:** MVP 0.1.0 (`backend/pricing_engine_package.lock.json`, tag `v0.1.0`, SHA-256 pinned); Price Lab `origin/main` and Engine `main` 0.15.0; the only published Engine GitHub Release is `v0.1.0` (latest git tag `v0.12.1`). Re-confirm all versions when the gate opens.

**Principles.** Price Lab `origin/main` is the reference implementation: its code, approved Master Packages, UI specifications and screenshots. MVP recreates that functionality and those layouts, as closely as practical, inside its own shell, navigation, authentication and tenant architecture, keeping Quote/Order records. Replaced MVP pricing screens are removed, not kept alongside. One authoritative Engine owns formulas; each application pins its own verified release. MVP supplies tenant data through its own adapters (`backend/app/services/pricing_engine_adapter.py`) and never adds a second calculation engine. Existing quotes, orders, invoices and pricing snapshots are never automatically recalculated; legacy snapshot readers keep working. Parity evidence uses `backend/tests/fixtures/pricing_engine/` without regenerating expected values.

**P2/P3 Foundation scope:** Foundation overview and navigation; Shop Basics; Labor Roles and labor costs; Production Operations and Master Tasks; Shop Rate Determination; Pricing Baselines; Materials, Equipment and Hardware Resources; Outside Services; Category Catalog; Category Defaults; Direct Setup; Guided Setup; shared Draft editing; Review and Activate; Active-versus-Draft live benchmarks; Reset to Starter defaults; readiness and missing-input indicators.

**Material selling rates (P2, applied per category in P4).** Editable suggested Starter selling rates per square foot or per linear foot by the material's unit, separate from purchase cost, category-specific where production methods differ, from documented Starter rules and approved values, never presented as verified market averages. Cost Plus and Target Margin stay independent. Labor or production already included in a selling rate is never charged twice. A rule the Engine does not support becomes an Engine producer change, not MVP-local math.

**P4 per category.** Each stage delivers that category's settings and methods plus the calculator in both forms (full-page and New Order overlay sharing one calculation and configuration path) with the approved controls: quantity/dimensions, material and resource selection, conditional options and add-ons, artwork and production settings, installation and travel, rush and finishing, available methods, Live Estimate, Quick Prices, Show the Math, Save Calculation, Add to Quote/Order, cost/margin/evidence, missing-cost and unavailable-method safeguards. Order follows the status table above. Staging follows Price Lab's policy: one branch and draft PR, stop after each authorized stage, one combined verification at the end.

**MVP components reused (per the audits):** Engine adapter and financial-unit boundary (`pricing_engine_adapter.py`, `core/money.py`, `services/commerce_totals.py`); immutable pricing snapshots and legacy readers (`#52`); quote/order line-item pricing and conversion (`#21`, `#22`, after CH-02/03); saved calculations (`#51`); engine contract fixtures and EC9 quote/order financial integration tests; app shell, navigation, permission gates, design system and `MoneyInput`. Calculator draft/payload logic in `LineItemDialog`, `PricingCalculatorPage` and `CategorySpecificFields` is kept where it matches (CH-04, CH-05, CH-20); old layouts are replaced. `wizardConfigs.js` is replaced by Price Lab Guided Setup where Price Lab covers the category.

**Original SignGuy AI** supplies read-only assistant/personality/history/recorded-voice behavior references for required first-release Business Assistant V1. Proofs/markup, portals and broader AI growth tools remain separately scheduled; no wholesale donor import is authorized.

## E-AI. AI credit model reference (owner direction 2026-10-14)

Reference for AI credit integration; **not implemented in F1**. Required Business Assistant V1 must use and complete the existing EC16 usage/cost/credit/governance boundary before first release; broader AI Studio activation remains separately governed. Behavior comes from the original `dnblack323/signguyai` (`backend/services/founders_config.py`, `credit_service.py`, `models/credits.py`, `routes/credits.py`, `frontend/src/components/founders/CreditMeter.js`, `frontend/src/components/credits/`). Reuse MVP's EC16 AI Gateway (credit accounts, reserve/commit/release, credit ledger, provider-cost ledger); do not copy the legacy wallet. H7's final commercial/provider values remain gated and need an owner-approved pre-launch validation path; no prices or allowances are finalized here.

| Original behavior to preserve | Original implementation | EC16 starting point |
|---|---|---|
| AI tools included with the main subscription | Founders plan with `ai_credits_monthly` | Plan catalog rules grant `ai_studio` / `business_assistant`; credits limit use |
| Credit cost per AI action | `AI_CREDIT_COSTS`: 1-credit (short text), 2-credit (blog/SEO/proposals), 3-credit (image/mockup) tool tiers | Capability credit cost on `AICapability` |
| Monthly included allowance; expires at period end | `monthly_credits`, refill with `monthly_expire` + `monthly_grant` transactions | `AICreditAccount.included_balance_credits` (grant/expiry cycle to confirm at integration) |
| Purchased credits separate, never expire | `purchased_credits` | `purchased_balance_credits` |
| Monthly consumed before purchased | `build_credit_preview` uses monthly first | Ledger `included_credits_delta` / `purchased_credits_delta` |
| Charge only after success; failures logged free | preflight → `deduct_credits_after_success`; `log_failed_ai_usage` | Reserve → commit on success / release on failure |
| Visible balance, days until refill, low-credit warning, Buy Credits | `CreditMeter.js`, `CreditBalance.js`, threshold `low_credits_threshold` | Frontend to build on existing AI credits page |
| Cost shown and confirmed before an AI action; insufficient-credit state | `AICreditConfirmationDialog.js`, `POST /credits/preflight` | Gateway reservation preflight |
| Purchase additional credits | `POST /credits/purchase` + Stripe webhook | EC13 credit-pack checkout type (`credit_pack`) |
| Transaction and usage history | `credit_transactions`, `GET /credits/history` | `AICreditLedgerEntry`, usage ledger |

**Do not carry over** the original pack prices ($10/$25/$60), monthly amount (150) or trial credits (50): current approved values (EC13/C3 packs 100/$19, 300/$45, 800/$99, subject to H7) stay until finalized separately.

## F. First implementation task

**F1 — Subscription access control.** It makes paying necessary (B1), is the switch that hides unfinished modules from V1 shops (B8), and is independent of Price Lab pricing.

**Definition of done:**

1. Every staff API router for an entitlement-gated module rejects unentitled shops with `402` (backend-enforced; frontend hiding alone does not count).
2. A new registration applies the owner-decided trial policy (§B decision 4) and projects entitlements.
3. Expired trials and billing-suspended or past-grace subscriptions lose gated access automatically, without a manual admin call.
4. The frontend sends a blocked user to the Billing page with a clear message; platform admins are not locked out.
5. Focused tests: entitlement allowed/denied per gated router family, trial expiry, dunning suspension, two-tenant isolation of entitlements; required CI green.
6. One PR, owner-approved before merge.

## G. Audit findings map (all 124 rows)

Each row appears exactly once. Findings in the CSV are unchanged; this is their launch disposition.

**Launch blockers — completed inside Tracks 1–3 (41):**
`#1 #2 #4 #5 #7 #8 #9 #10 #11 #12 #13 #18 #19 #20 #21 #22 #23 #24 #25 #26 #27 #28 #30 #42 #43 #44 #45 #46 #48 #49 #50 #51 #52 #66 #74 #97 #98 #100 #101 #104 #108`
(Track 1: `#5 #7 #8–#13 #44 #74 #100 #101`. Track 2: `#21 #22 #48–#52`. Track 3: the rest. `#20` and `#25` cover staff-side actions; their customer-facing halves are in U1.)

**First feature updates after launch — switched off for V1 shops until their update (68):**
`#3 #14 #15 #16 #17 #29 #31 #32 #33 #34 #35 #36 #37 #38 #39 #40 #41 #47 #54 #55 #56 #57 #58 #59 #61 #62 #63 #65 #67 #68 #69 #70 #71 #72 #73 #75 #76 #78 #79 #80 #81 #82 #83 #84 #85 #86 #87 #88 #89 #90 #99 #103 #105 #106 #107 #109 #110 #111 #112 #113 #114 #115 #116 #117 #118 #119 #120 #124`

**Later expansion (11):**
`#53 #60 #64 #77 #91 #92 #93 #94 #95 #96 #102`

**Obsolete / cleanup only (3):** `#121` (removed during P4 calculator work) and `#122` are dead declarations (CH-01). `#123` duplicates `#106` (same help-alias defect, fixed in U9).

**Already resolved (1):** `#6` dev login is refused in production by `backend/app/core/security_guards.py`. Re-verify on the real deployment in L4.

No other row changed since the audit: the four commits merged after it touched no audited feature.
