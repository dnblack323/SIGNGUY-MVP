# SignGuy AI MVP — Commercial V1 Launch Plan

**Prepared:** 2026-10-14 from the completed audits (no new general audit was performed).
**Status:** PROPOSED — becomes the working order once the owner approves this PR.
**Current feature:** none yet. On approval, **F1 — Subscription access control** becomes CURRENT.

**Sources used:** `docs/audits/MVP_BASELINE_AUDIT_2026-10-10.md`, `docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv` (124 rows, cited below as `#n`), `docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md` (`CH-n`), `memory/code_issue_register.md` (`CIR-n`), `memory/owner_specification_hold_register.md`, plus five targeted source checks recorded in §B where an audit row needed clarification.

---

## A. Current functional baseline

**Honest summary:** the audit runtime-verified **0 of 124** features. 95 are connected end-to-end in code (screen → API → tenant-scoped database) with focused tests; 19 are partial. "Built and wired" is not yet "proven working for a paying customer."

What MVP already has, in code and tests:

| Area | What exists |
|---|---|
| Accounts | Shop registration, tenant-scoped login, roles and three separate permission scopes, password reset, account suspension, production startup guards that refuse a dev bypass or placeholder secrets |
| Shop setup | Company settings, Pricing Foundation, guided pricing setup, onboarding checklist and Help Center (EC19 foundation) |
| Sales | Customers (with merge), staff intake, quotes with immutable revisions, line-item pricing through the private Pricing Engine 0.1.0, idempotent quote → order conversion |
| Fulfilment | Orders, Work Orders, production stages, timeline, board and kiosk; order completion packets |
| Money | One invoice per order, backend-calculated totals in integer cents, manual payment recording (concurrent overpayment defect CIR-001 fixed) |
| Subscription business | Stripe subscription checkout, billing portal, 48-hour and 7-day trials, setup packages, day-based dunning, platform-fee ledger (EC13 and EC20 closed), platform admin console |
| Quality gates | GitHub CI runs backend tests, frontend tests and a production build on every branch; 24 of 32 code-issue-register defects fixed and verified; Shop Operations section reviewed and corrected end-to-end |

Also built but **not** V1 material: Webstores, Wrap Lab, Team/payroll, inventory/purchasing, AI Studio/Assistant (local mocks only, no real AI provider).

## B. Launch blockers

These stop a shop from **registering, paying, and safely using** MVP. B1, B2, B4 and B5 were confirmed by direct source checks on 2026-10-14; the rest come from the audits.

| # | Blocker | Evidence |
|---|---|---|
| **B1** | **Not paying does not lock anything.** Entitlements are calculated but no API route enforces them: `require_entitlement` (`backend/app/deps.py:83`) has zero callers. Trials expire only when a platform admin manually calls `POST /api/billing/platform/trials/expire`. Billing suspension writes `tenant_billing_accounts.status`, while the login/request gate checks only `tenants.is_active` (`deps.py:41`, `tenant_billing.py:562`). A shop that never pays keeps full access. | Source check; refines `#100`, `#101` |
| **B2** | **Signup is not connected to a plan.** Registration (`backend/app/routers/auth.py`) creates the shop but never creates a billing account or starts a trial. No public plan/pricing page exists (EC21 not started). There are no Terms of Service or Privacy pages for a paid product. | Source check; `#2`, `#101` |
| **B3** | **No production deployment exists.** `docker-compose.yml` is development-only: `ENV=development`, `AUTH_DEV_BYPASS=true`, placeholder JWT secret, MongoDB port published, HTTP only (no TLS), filesystem file storage, and no database or file backups. There is no error monitoring. | Source check; audit §10–11 |
| **B4** | **Online invoice payments would send shop money to SignGuy's Stripe account.** `stripe_core.create_payment_intent` charges the platform account with no connected shop account, using the same `STRIPE_API_KEY` that subscription billing needs. Turning on subscriptions therefore also turns on invoice card payments that land in the wrong account. They must stay off until moved to Stripe Connect (post-launch U2). | Source check; `#29` |
| **B5** | **Email is unproven.** Password reset and any registration emails depend on SendGrid; none was exercised. A locked-out paying customer cannot recover access. | `#2`, `#4`, `#31` |
| **B6** | **The core workflow was never run end-to-end.** Customer → quote → order → work order → production → invoice → payment, plus two-tenant isolation, needs one real run on a disposable tenant, fixing whatever fails. | `#11`–`#28`, `#42`–`#52`; audit §4 |
| **B7** | **Open data-integrity defects inside V1 workflows.** CIR-031 (production timers and stage moves can double-record), CIR-025 (customer merge can split records; any staff user can merge). | `memory/code_issue_register.md` |
| **B8** | **Unfinished modules must not be sold.** Webstores (CIR-026/027 launch blockers), AI (mock only, hold H7), and customer-facing public links (CIR-005/030/032) must be switched off for V1 shops. B1's enforcement is the switch. | Audit §3, §8; CIR register |

**Owner decisions needed** (needed by F1/F5, not before approving this plan):

1. **Re-sequence the locked order.** The hold register's H1 order is UX1 → Advanced Onboarding → EC19 close → EC21 → EC22. This plan pulls minimal EC21 (signup/plan page) and EC22 (release hardening) pieces ahead of UX1 and Advanced Onboarding. Approving this PR approves that re-sequencing. Nothing in UX1/Advanced Onboarding is removed; it moves to post-launch (U10).
2. **V1 offer.** Which approved EC13 price launches first (recommended: the Founder offer on the Core plan for the first 25 shops), and which feature keys Core grants. Only owner-approved prices may reach Stripe (EC13 decision 4).
3. **Trial start.** Recommended: start the approved 48-hour free trial automatically at registration.
4. **Hosting provider and domain** for production (F6).

## C. First release scope — "Core V1"

The smallest complete, honest, sellable product:

**Included:** signup → free trial → Core subscription purchase (Stripe) → company settings and Pricing Foundation → staff users and roles → customers → quotes priced by the calculator → staff-recorded quote approval → quote-to-order → work orders and production board → invoices → manual payment recording (cash, check, card terminal, bank) → billing portal, dunning and suspension → onboarding checklist, Help Center and support email.

**Switched off for V1 shops (entitlements), not deleted:** online card payment of invoices, customer portal and public approval links, Webstores, Wrap Lab, AI tools and Assistant, inventory/purchasing, team time clock/payroll/employee portal, decision rooms and proofs, intake forms. Every one stays on the roadmap below.

## D. Development priority

One feature at a time, each on its own branch and PR, merged only with owner approval.

**Required before first paid launch**

| Feature | Scope | Rows / IDs | Class |
|---|---|---|---|
| **F1 Subscription access control** | Enforce entitlements on staff API routes; automatic trial start and expiry; billing suspension blocks access; 402 handling routes the user to Billing; unentitled modules hidden and blocked | B1, B8; `#5 #7 #100 #101` | C |
| **F2 Shop setup and pricing** | New shop can complete company settings, invite staff with roles, finish guided pricing setup and price a line item that matches the Engine | `#48 #49 #50 #52 #66 #97 #98 #104` | C |
| **F3 Sales to cash** | Customer → quote → approval → order → invoice → manual payment on a disposable tenant with a second tenant proving isolation; fix CIR-025 (merge restricted to managers and made safe) | B6, B7; `#8 #11–#13 #18–#28 #30`; CIR-025 | C |
| **F4 Production** | Order → work orders → stages, timers, board → completion; fix CIR-031 | B6, B7; `#42–#46`; CIR-031 | C |
| **F5 Signup and plan purchase** | Minimal public plan page (approved price only), Terms and Privacy pages, registration → trial → Stripe test-mode checkout → webhook → entitlements; password reset via SendGrid; invoice card payments confirmed off | B2, B4, B5; `#1 #2 #4` | C |
| **F6 Production deployment** | Hosted production stack: TLS, real secrets, `ENV=production`, private database, automated database and file backups with a tested restore, error monitoring, health checks, staging copy | B3; re-verify `#6` | C |
| **F7 Launch candidate** | Full critical-path smoke on staging, platform admin check, truthful plan copy, owner visual review, live Stripe keys switched on, first Founder shop onboarded | `#108` | C |

**First feature updates after launch** (order by customer value; owner may reorder)

| Update | Scope | Rows / IDs |
|---|---|---|
| U1 Customer approvals and portal | Fix CIR-005, CIR-030, CIR-032; then enable public quote/proof/completion links, decision rooms, customer portal, email history | `#31–#38 #109 #111 #112 #118` |
| U2 Online invoice payments | Move invoice card payments to Stripe Connect (shop's own account), then enable | `#29 #110` |
| U3 Pricing Engine upgrade and calculator refresh | CH-02/CH-03 resolver consolidation first, then Engine 0.1.0 → 0.14.0 with parity evidence, then selected Price Lab calculator/Foundation UX | `#51`; CH-02 to CH-05, CH-20 |
| U4 Intake and lead capture | Staff intake, public inquiry → intake conversion, forms and templates | `#14–#17 #39–#41 #120` |
| U5 Team, schedule and production floor | Time clock, timesheets, schedules (CIR-028), tasks, training, employee portal, kiosk | `#47 #65 #67–#76 #78 #113–#117` |
| U6 Webstores add-on | Fix CIR-026, CIR-027; canonical order and production handoff | `#79–#86 #119 #124` |
| U7 Wrap Lab add-on | Runtime-verify and enable | `#87–#90` |
| U8 Inventory and purchasing | Materials, stock, reorder, purchase orders, receiving | `#54–#59` |
| U9 Finance reports | Expenses, finance dashboard, tax reports | `#61–#63` |
| U10 Experience polish | UX1 visual system, Advanced Onboarding, help topic pages, Google sign-in, integrations and security views, community | `#3 #9 #10 #99 #103 #105–#107` |

**Later expansion** (permanent roadmap, not dropped): real AI provider, Studio, Business Assistant and voice after the H7 cost audit (`#92–#96 #102`); pricing advisory (`#53`); live supplier connectors (`#60`); reporting rebuilds and payouts (`#64`); statutory payroll (`#77`); Wrap Lab post-install reports (`#91`); SMS.

## E. Price Lab and original SignGuy AI integration

**Before launch:** none required. MVP's own Pricing Foundation and calculator on Engine 0.1.0 support V1. Copying Price Lab code now would add risk without unblocking a sale. One conditional exception: if F3 finds MVP's customer-facing quote/invoice output unusable, Price Lab's branded quote/invoice output (Phase 5C) is the reference to recreate inside MVP's existing templates.

**Pricing Engine version dependency (documented, not upgraded):**

| | Version | Where |
|---|---|---|
| MVP | 0.1.0 | `backend/pricing_engine_package.lock.json` (tag `v0.1.0`, SHA-256 pinned) |
| Price Lab `origin/main` | 0.14.0 | `electron/packageScripts.test.js` version assertion |
| Engine repository `main` | 0.14.0 | `pyproject.toml` |

Price Lab's newer calculators (banner linear-foot, rigid signs, cut vinyl, vehicle graphics, services) depend on 0.14.0 method outputs. Any calculator reuse therefore waits for U3, which must first consolidate MVP's duplicated quote/order pricing resolver (CH-02/03), then upgrade with parity evidence against `backend/tests/fixtures/pricing_engine/` and keep legacy snapshot readers working.

**After launch, assess in this order:** Pricing Review Center with "Show the Math" provenance; Guided Pricing Interview feeding one Draft with Active-vs-Draft comparison; Quick Prices; Saved Products/Package Builder; compact app shell and home widgets (with UX1). Original SignGuy AI stays a donor for proofs/markup, portals and AI growth tools in U1, U10 and later expansion only.

## F. First implementation task

**F1 — Subscription access control.** It is first because:

- It is the difference between a demo and a business: without it nobody has a reason to pay (B1).
- It is the switch that hides every unfinished module from V1 shops (B8), which makes the smaller launch scope honest.
- It is backend-contained and builds on EC13/EC20 code that already exists, so it is completion, not a rebuild.

**Definition of done:**

1. Every staff API router for an entitlement-gated module rejects unentitled shops with `402` (backend-enforced; frontend hiding alone does not count).
2. A new registration starts the approved trial and projects entitlements (subject to owner decision 3).
3. Expired trials and billing-suspended or past-grace subscriptions lose gated access automatically, without a manual admin call.
4. The frontend sends a blocked user to the Billing page with a clear message; platform admins are not locked out.
5. Focused tests: entitlement allowed/denied per gated router family, trial expiry, dunning suspension, two-tenant isolation of entitlements; required CI green.
6. One PR, owner-approved before merge.

## G. Audit findings map (all 124 rows)

Each row appears exactly once. Findings in the CSV are unchanged; this is their launch disposition.

**Launch blockers — verified and fixed inside F1–F7 (37):**
`#1 #2 #4 #5 #7 #8 #11 #12 #13 #18 #19 #20 #21 #22 #23 #24 #25 #26 #27 #28 #30 #42 #43 #44 #45 #46 #48 #49 #50 #52 #66 #97 #98 #100 #101 #104 #108`
(`#20` and `#25` cover the staff-side actions; their customer-facing halves are in U1. `#22` is verified for parity in F3; its duplicated resolver is consolidated in U3.)

**First feature updates after launch — switched off for V1 shops until their update (72):**
`#3 #9 #10 #14 #15 #16 #17 #29 #31 #32 #33 #34 #35 #36 #37 #38 #39 #40 #41 #47 #51 #54 #55 #56 #57 #58 #59 #61 #62 #63 #65 #67 #68 #69 #70 #71 #72 #73 #74 #75 #76 #78 #79 #80 #81 #82 #83 #84 #85 #86 #87 #88 #89 #90 #99 #103 #105 #106 #107 #109 #110 #111 #112 #113 #114 #115 #116 #117 #118 #119 #120 #124`

**Later expansion (11):**
`#53 #60 #64 #77 #91 #92 #93 #94 #95 #96 #102`

**Obsolete / cleanup only (3):** `#121` and `#122` are dead declarations (CH-01; remove when their file is next touched). `#123` duplicates `#106` (same help-alias defect, fixed in U10).

**Already resolved (1):** `#6` dev login is refused in production by `backend/app/core/security_guards.py` (dev bypass blocked when `ENV=production`; hosted deployments must run `ENV=production`). Re-verify on the real deployment in F6.

No other row changed since the audit: the four commits merged after it (`MY_DOCUMENTS` owner documents and reproducible private-engine setup) touched no audited feature.
