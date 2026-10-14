# SignGuy AI MVP — Commercial V1 Launch Plan

**Prepared:** 2026-10-14 from the completed audits (no new general audit was performed).
**Revised:** 2026-10-14 — owner correction: Price Lab pricing (Engine, Pricing Foundation, all nine calculators) is a **required pre-launch milestone**. Launch order F1–F9 below is owner-directed.
**Status:** PROPOSED — becomes the working order once the owner approves PR #41. Each feature and each stage still needs separate owner authorization.
**Current feature:** none yet. On authorization, **F1 — Subscription access control** becomes CURRENT.

**Sources used:** `docs/audits/MVP_BASELINE_AUDIT_2026-10-10.md`, `docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv` (124 rows, cited below as `#n`), `docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md` (`CH-n`), `memory/code_issue_register.md` (`CIR-n`), `memory/owner_specification_hold_register.md`, targeted source checks recorded in §B, and Price Lab `origin/main` merge history (read-only).

---

## A. Current functional baseline

**Honest summary:** the audit runtime-verified **0 of 124** features. 95 are connected end-to-end in code (screen → API → tenant-scoped database) with focused tests; 19 are partial. "Built and wired" is not yet "proven working for a paying customer."

| Area | What exists in code and tests |
|---|---|
| Accounts | Shop registration, tenant-scoped login, roles and three separate permission scopes, password reset, account suspension, production startup guards that refuse a dev bypass or placeholder secrets |
| Shop setup | Company settings, an older Pricing Foundation and guided setup (to be replaced by Price Lab's, §E), onboarding checklist and Help Center (EC19 foundation) |
| Sales | Customers (with merge), staff intake, quotes with immutable revisions, line-item pricing through the private Pricing Engine 0.1.0, idempotent quote → order conversion |
| Fulfilment | Orders, Work Orders, production stages, timeline, board and kiosk; order completion packets |
| Money | One invoice per order, backend-calculated totals in integer cents, manual payment recording (concurrent overpayment defect CIR-001 fixed) |
| Subscription business | Stripe subscription checkout, billing portal, 48-hour and 7-day trials, setup packages, day-based dunning, platform-fee ledger (EC13 and EC20 closed), platform admin console |
| Quality gates | GitHub CI runs backend tests, frontend tests and a production build on every branch; 24 of 32 code-issue-register defects fixed and verified; Shop Operations section reviewed and corrected end-to-end |

Also built but **not** V1 material: Webstores, Wrap Lab, Team/payroll, inventory/purchasing, AI Studio/Assistant (local mocks only, no real AI provider).

## B. Launch blockers

B1, B2, B4 and B5 were confirmed by direct source checks on 2026-10-14; B9 is the owner's 2026-10-14 direction; the rest come from the audits.

| # | Blocker | Evidence |
|---|---|---|
| **B1** | **Not paying does not lock anything.** `require_entitlement` (`backend/app/deps.py:83`) has zero callers. Trials expire only when a platform admin calls `POST /api/billing/platform/trials/expire`. Billing suspension writes `tenant_billing_accounts.status`, while the request gate checks only `tenants.is_active` (`deps.py:41`, `tenant_billing.py:562`). | Source check; refines `#100`, `#101` |
| **B2** | **Signup is not connected to a plan.** Registration (`backend/app/routers/auth.py`) creates no billing account and starts no trial. No public plan page, Terms of Service or Privacy page exists (EC21 not started). | Source check; `#2`, `#101` |
| **B3** | **No production deployment.** `docker-compose.yml` is development-only: `ENV=development`, `AUTH_DEV_BYPASS=true`, placeholder JWT secret, published MongoDB port, HTTP only, filesystem storage, no backups, no error monitoring. | Source check; audit §10–11 |
| **B4** | **Online invoice payments would send shop money to SignGuy's Stripe account.** `stripe_core.create_payment_intent` charges the platform account using the same `STRIPE_API_KEY` that subscriptions need. Must stay off until moved to Stripe Connect (U2). | Source check; `#29` |
| **B5** | **Email is unproven** (password reset, registration). | `#2`, `#4`, `#31` |
| **B6** | **The core workflow was never run end-to-end** with two-tenant isolation. | `#11`–`#28`, `#42`–`#52`; audit §4 |
| **B7** | **Open data-integrity defects in V1 workflows:** CIR-031 (production timers/stage moves), CIR-025 (customer merge). | `memory/code_issue_register.md` |
| **B8** | **Unfinished modules must not be sold:** Webstores (CIR-026/027), AI (mock only, hold H7), customer-facing public links (CIR-005/030/032). B1 enforcement is the switch. | Audit §3, §8; CIR register |
| **B9** | **MVP pricing does not match the approved Price Lab pricing.** MVP runs Engine 0.1.0 and an older Pricing Foundation and calculators; the owner requires Price Lab's Foundation, nine calculators and material selling-rate rules before launch. | Owner direction 2026-10-14; `#48`–`#52` |

**Owner decisions:**

1. **Launch order — DECIDED 2026-10-14.** F1–F9 below, recorded in `memory/owner_specification_hold_register.md`. UX1, Advanced Onboarding and the remainder of EC21/EC22 move after launch; nothing is removed.
2. **V1 offer** — which approved EC13 price launches first (recommended: Founder offer on Core for the first 25 shops) and which feature keys Core grants. Needed by F1/F7.
3. **Trial start** — recommended: start the approved 48-hour trial automatically at registration. Needed by F1.
4. **Hosting provider and domain.** Needed by F8.
5. **Material and Resource ownership** — Price Lab's Materials/Equipment/Hardware Resources must map onto MVP's existing material and equipment records rather than become a second catalog (locked "no parallel stores" rule). The exact mapping is decided at the start of F3 and needs owner confirmation if records must be split.

## C. First release scope — "Core V1"

**Included:** signup → free trial → Core subscription purchase → company settings → **Price Lab Pricing Foundation** (Shop Basics through Review and Activate) → staff users and roles → customers → quotes priced with the **Price Lab category calculators** (all nine, full-page and order overlay) → staff-recorded quote approval → quote-to-order → work orders and production board → invoices → manual payment recording → billing portal, dunning and suspension → onboarding checklist, Help Center and support email.

**Switched off for V1 shops (entitlements), not deleted:** online card payment of invoices, customer portal and public approval links, Webstores, Wrap Lab, AI tools and Assistant, pricing advisory, inventory/purchasing, team time clock/payroll/employee portal, decision rooms and proofs, intake forms.

## D. Development order

One feature at a time, each on its own branch and PR, each started only with owner authorization. Multi-stage features follow Price Lab's staging policy: one branch and draft PR per feature, stop after each authorized stage, one combined verification and review at the end.

**Required before first paid launch**

| Feature | Scope | Depends on | Rows / IDs | Class |
|---|---|---|---|---|
| **F1 Subscription access control** | Enforce entitlements on staff API routes; automatic trial start and expiry; billing suspension blocks access; 402 → Billing page; unentitled modules hidden and blocked | — | B1, B8; `#5 #7 #100 #101` | C |
| **F2 Shared Engine upgrade and compatibility** *(Stage A)* | See §E. Pin MVP to a published, tested Engine release (0.15.0 or the then-current merged version); consolidate the duplicated quote/order pricing resolver first (CH-02, CH-03); legacy snapshots readable; no historical recalculation | Engine release published (§E) | `#22 #52`; CH-02, CH-03 | C |
| **F3 Pricing Foundation modernization** *(Stage B)* | Recreate Price Lab's Foundation structure and shared systems inside MVP's shell (§E list); retire replaced MVP Foundation screens | F2 | `#48 #49`; owner decision 5 | C |
| **F4 Category calculator modernization** *(Stage C, then D)* | One category at a time (§E order): category Foundation settings + shared full-page/overlay calculator; final step F4-D verifies pricing → Quote/Order across all nine | F3 | `#50 #51`; CH-04, CH-05, CH-20 | C |
| **F5 Customer → Quote → Order → Invoice → Payment** | Run the workflow on a disposable tenant with a second tenant proving isolation; fix what fails; fix CIR-025 | F4 | B6, B7; `#8 #11–#13 #18–#21 #23–#28 #30 #66 #97 #98`; CIR-025 | C |
| **F6 Production workflow completion** | Order → work orders → stages, timers, board → completion; fix CIR-031 | F5 | B6, B7; `#42–#46`; CIR-031 | C |
| **F7 Signup, subscription purchase and email** | Minimal public plan page (approved price only), Terms and Privacy, registration → trial → Stripe test-mode checkout → webhook → entitlements; password reset via SendGrid; invoice card payments confirmed off | F1 | B2, B4, B5; `#1 #2 #4 #104` | C |
| **F8 Secure production deployment** | TLS, real secrets, `ENV=production`, private database, automated database and file backups with tested restore, error monitoring, health checks, staging copy | F7 | B3; re-verify `#6` | C |
| **F9 Complete workflow verification and commercial launch** | Full critical-path run on staging (signup → pricing → quote → order → production → invoice → payment → billing), platform admin check, truthful plan copy, owner visual review, live Stripe keys, first Founder shops | F1–F8 | `#108` | C |

**First feature updates after launch** (owner may reorder)

| Update | Scope | Rows / IDs |
|---|---|---|
| U1 Customer approvals and portal | Fix CIR-005, CIR-030, CIR-032; enable public quote/proof/completion links, decision rooms, customer portal, email history | `#31–#38 #109 #111 #112 #118` |
| U2 Online invoice payments | Move invoice card payments to Stripe Connect (shop's own account), then enable | `#29 #110` |
| U3 Intake and lead capture | Staff intake, public inquiry → intake conversion, forms and templates | `#14–#17 #39–#41 #120` |
| U4 Team, schedule and production floor | Time clock, timesheets, schedules (CIR-028), tasks, training, employee portal, kiosk | `#47 #65 #67–#76 #78 #113–#117` |
| U5 Webstores add-on | Fix CIR-026, CIR-027; canonical order and production handoff | `#79–#86 #119 #124` |
| U6 Wrap Lab add-on | Runtime-verify and enable | `#87–#90` |
| U7 Inventory and purchasing | Materials, stock, reorder, purchase orders, receiving | `#54–#59` |
| U8 Finance reports | Expenses, finance dashboard, tax reports | `#61–#63` |
| U9 Experience polish | UX1 visual system, Advanced Onboarding, help topic pages, Google sign-in, integrations and security views, community | `#3 #9 #10 #99 #103 #105–#107` |

**Later expansion** (permanent roadmap, not dropped): real AI provider, Studio, Business Assistant and voice after the H7 cost audit (`#92–#96 #102`); pricing advisory (`#53`); live supplier connectors (`#60`); reporting rebuilds and payouts (`#64`); statutory payroll (`#77`); Wrap Lab post-install reports (`#91`); SMS.

## E. Price Lab pricing adoption (pre-launch, F2–F4)

**Principle.** Price Lab `origin/main` is the reference implementation for MVP's pricing experience: its implemented code, approved Master Packages, UI specifications and screenshots. MVP recreates that functionality and those layouts inside its own SaaS shell, navigation, authentication and tenant architecture. Read Price Lab only from its fetched `origin/main`; never disturb its working branches or files. Do not copy Electron, SQLite, sidecar IPC, licensing or `Job` persistence. MVP keeps Quote/Order terminology and records.

**Stage A — Shared Engine (F2).**

| | Version (verified 2026-10-14) | Note |
|---|---|---|
| MVP | 0.1.0 | `backend/pricing_engine_package.lock.json`, tag `v0.1.0`, SHA-256 pinned |
| Price Lab `origin/main` | 0.15.0 | `electron/packageScripts.test.js` version assertion |
| Engine repository `main` | 0.15.0 | `pyproject.toml` |
| Engine GitHub Releases | only `v0.1.0` | latest git tag is `v0.12.1` |

- **Prerequisite:** MVP's installer downloads a published GitHub Release asset and verifies its SHA-256. A release for the target version must be published from the Engine repository before F2 can pin it.
- One authoritative Engine; formulas stay in `SIGNGUY-PRICING-ENGINE`. MVP and Price Lab may upgrade at different times, each on a tested pinned release. Confirm the current merged versions when F2 starts.
- MVP supplies tenant data through its own adapters (`backend/app/services/pricing_engine_adapter.py`): shop settings, materials and resources, labor costs and billing rates, equipment costs and speeds, category configurations, production tasks, pricing requests and saved evidence. No second calculation engine inside MVP.
- Existing quotes, orders, invoices and pricing snapshots are preserved and never automatically recalculated. Legacy snapshot readers keep working.
- Evidence: parity tests against `backend/tests/fixtures/pricing_engine/` (expected values are never regenerated to make tests pass), plus the existing quote/order integration and line-engine parity suites.

**Stage B — Pricing Foundation (F3).** Recreate, matching Price Lab's page layouts as closely as practical: Foundation overview and navigation; Shop Basics; Labor Roles and labor costs; Production Operations and Master Tasks; Shop Rate Determination; Pricing Baselines; Materials, Equipment and Hardware Resources; Outside Services; Category Catalog; Category Defaults; Direct Setup; Guided Setup; shared Draft editing; Review and Activate; Active-versus-Draft live benchmarks; Reset to Starter defaults; readiness and missing-input indicators. Replaced MVP Foundation screens are removed, not kept alongside.

**Material selling rates (F3, applied per category in F4).** Applicable materials carry editable suggested Starter selling rates per square foot or per linear foot (by the material's unit), separate from purchase cost, category-specific where production methods differ. They come from documented Starter rules and approved values and are never presented as verified market averages. Cost Plus and Target Margin stay independent. Labor or production components already included in a selling rate are never charged twice. If Engine 0.15.0 does not support a required rule, that becomes an Engine producer change, not MVP-local math.

**Stage C — Categories (F4), one category per stage.** Each category stage delivers its category Foundation settings and pricing methods plus the calculator in both forms (full-page and New Order overlay sharing one calculation and configuration path). It covers the approved controls (quantity/dimensions, material and resource selection, conditional options and add-ons, artwork and production settings, installation and travel, rush and finishing, available methods, Live Estimate, Quick Prices, Show the Math, Save Calculation, Add to Quote/Order, cost/margin/evidence, missing-cost and unavailable-method safeguards).

Order follows Price Lab completion status (from merge history, `origin/main` 2026-10-14):

| Order | Category | Price Lab status | MVP action |
|---|---|---|---|
| 1 | Banner | V1 complete (batches 1–3, workflow verification) | Ready to implement |
| 2 | Rigid Signs & Panels | V1 merged (#111) | Ready |
| 3 | Cut Vinyl | V1 completion merged (#108) | Ready |
| 4 | Services | V1 completion + stage 3 merged (#109, #110) | Ready |
| 5 | Vehicle Graphics | V1 merged (#85, 2026-10-04) | Confirm against current approved package first |
| 6 | Digital Print | Stages 1–2 merged; completion not confirmed | Wait for Price Lab completion |
| 7 | Apparel | In active development, not merged | Wait for Price Lab completion |
| 8 | Promotional Products | Early baseline only (Phase 4E) | **Gap:** needs Price Lab completion |
| 9 | Custom / Miscellaneous | Early baseline only (Phase 4F) | **Gap:** needs Price Lab completion |

An unfinished Price Lab category is not treated as approved. If categories 6–9 are not complete when MVP reaches them, the owner decides whether to wait or to launch with that category's current MVP calculator clearly labeled.

**Stage D — Pricing → Quote/Order verification (final F4 step).** All nine categories add correctly to quotes and orders, snapshots are immutable, totals are backend-authoritative in cents, and historical records are unchanged.

**MVP components reused (per the audits):** Engine adapter and financial-unit boundary (`pricing_engine_adapter.py`, `core/money.py`, `services/commerce_totals.py`); immutable pricing snapshots and legacy snapshot readers (`#52`); quote/order line-item pricing and conversion (`#21`, `#22`, after CH-02/03); saved calculations (`#51`); engine contract fixtures and the EC9 quote/order financial integration tests; app shell, navigation, permission gates, design system and `MoneyInput`. Calculator draft/payload logic in `LineItemDialog`, `PricingCalculatorPage` and `CategorySpecificFields` is extracted and kept where it matches (CH-04, CH-05, CH-20); their old layouts are replaced. `wizardConfigs.js` is replaced by Price Lab Guided Setup only where Price Lab covers the same category.

**Original SignGuy AI** remains a donor for proofs/markup, portals and AI growth tools in post-launch updates only.

## F. First implementation task

**F1 — Subscription access control** (owner-confirmed first in the F1–F9 order). It makes paying necessary (B1) and is the switch that hides unfinished modules from V1 shops (B8). It is backend-contained and completes existing EC13/EC20 code.

**Definition of done:**

1. Every staff API router for an entitlement-gated module rejects unentitled shops with `402` (backend-enforced; frontend hiding alone does not count).
2. A new registration starts the approved trial and projects entitlements (owner decision 3).
3. Expired trials and billing-suspended or past-grace subscriptions lose gated access automatically, without a manual admin call.
4. The frontend sends a blocked user to the Billing page with a clear message; platform admins are not locked out.
5. Focused tests: entitlement allowed/denied per gated router family, trial expiry, dunning suspension, two-tenant isolation of entitlements; required CI green.
6. One PR, owner-approved before merge.

## G. Audit findings map (all 124 rows)

Each row appears exactly once. Findings in the CSV are unchanged; this is their launch disposition.

**Launch blockers — verified and fixed inside F1–F9 (38):**
`#1 #2 #4 #5 #7 #8 #11 #12 #13 #18 #19 #20 #21 #22 #23 #24 #25 #26 #27 #28 #30 #42 #43 #44 #45 #46 #48 #49 #50 #51 #52 #66 #97 #98 #100 #101 #104 #108`
(`#20` and `#25` cover the staff-side actions; their customer-facing halves are in U1. `#22` and `#52` are handled in F2; `#48`, `#49` in F3; `#50`, `#51` in F4.)

**First feature updates after launch — switched off for V1 shops until their update (71):**
`#3 #9 #10 #14 #15 #16 #17 #29 #31 #32 #33 #34 #35 #36 #37 #38 #39 #40 #41 #47 #54 #55 #56 #57 #58 #59 #61 #62 #63 #65 #67 #68 #69 #70 #71 #72 #73 #74 #75 #76 #78 #79 #80 #81 #82 #83 #84 #85 #86 #87 #88 #89 #90 #99 #103 #105 #106 #107 #109 #110 #111 #112 #113 #114 #115 #116 #117 #118 #119 #120 #124`

**Later expansion (11):**
`#53 #60 #64 #77 #91 #92 #93 #94 #95 #96 #102`

**Obsolete / cleanup only (3):** `#121` (removed as part of F4's calculator work) and `#122` are dead declarations (CH-01). `#123` duplicates `#106` (same help-alias defect, fixed in U9).

**Already resolved (1):** `#6` dev login is refused in production by `backend/app/core/security_guards.py`. Re-verify on the real deployment in F8.

No other row changed since the audit: the four commits merged after it touched no audited feature.
