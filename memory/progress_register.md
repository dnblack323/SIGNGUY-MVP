# SignGuy AI — Progress Register

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` (owner-approved).
**Register scope:** Execution checkpoints (EC0-EC14) and Program checkpoints (PC1-PC9).
**Status values (per plan Part 25.1):** NOT STARTED / PREFLIGHT IN PROGRESS / OWNER DECISION BLOCKED / READY TO BUILD / IN PROGRESS / TESTING / CORRECTIONS REQUIRED / COMPLETE / COMMERCIAL GATE BLOCKED.

---

## Execution Checkpoints (EC0-EC14)

| EC | Name | Status | Notes |
|---|---|---|---|
| **EC0** | Owner Decisions and Governance Lock | **COMPLETE** | All 27 owner decisions answered and baked into the owner-approved consolidated master plan (Part 4). Do not rerun. |
| **EC1** | Security and Permanent App Guardrails | **COMPLETE** | Production startup guards, dev-route protection, terminology guard, money policy contract, extended permission catalog with platform + portal scope separation, LOCKED sidebar + flyout navigation. 34/34 tests pass. Evidence: `/app/evidence/EC1_evidence.md`. |
| **EC2** | Shared Platform Foundations | **COMPLETE** | 92/92 tests pass (34 EC1 + 58 EC2). Settings framework, Activity feed, Notifications, Email Activity, SendGrid webhook (fail-closed), Upload validation, Polymorphic file/document links, Feature entitlements (tenant read + `require_entitlement` guard), Integration status. Frontend: Company Settings, Integrations, Feature Access, Data & Security pages + NotificationBell. Evidence: `/app/evidence/EC2_evidence.md`. |
| **EC3** | Quotes, Orders, and Pricing Snapshots | **COMPLETE** | Backend 117/117 tests pass. Frontend: functional Quote/Order line-item editors, convert-with-override, revision warning, source-quote link. Automated testing agent: 20/21 scenarios pass; 21st (invalid-id error state) received a code fix in `frontend/src/index.js` that was NOT re-verified via a full automated rerun. Evidence: `/app/evidence/EC3_evidence.md`. |
| **EC4** | Invoices, Payments, and Stripe Core | **COMPLETE** | Backend 134/134 tests pass. Security fix verified: Stripe publishable key + client_secret never rendered/logged/persisted (DOM+console+localStorage scans confirm zero leaks). Provider ref masked as `Stripe ····<last4>`. Frontend regression via `testing_agent_v3_fork` iterations 3–6: 100% primary + regression pass — Record/Void/Stripe-Initiate/Simulate-Confirm/Refund/Duplicate-Dedup/Overpayment/Permission-hidden/Paired-status/PageHeader-hydration all verified. Real Stripe test keys configured; dev-simulated payments short-circuit refund without outbound Stripe traffic. Evidence: `/app/evidence/EC4_evidence.md`. |
| **EC5** | Production and Work Orders | **COMPLETE** | Backend 143/143 tests pass. Frontend delivered in full: Production Board (`/work-orders/board`) with drag-drop + reason-required modal, rebuilt Work Order Detail (9-state pill, priority, due date, allowed-transitions, versioning banners, assign, print summary), Generate WO dialog on Order Detail, Regenerate/Supersede on both surfaces, WorkOrders list with 9-state filters + current-only toggle + `wo-filter-{state}` testids, sidebar Production Board link, all controls permission-gated via `/auth/me`, DialogDescription applied for a11y. Automated `testing_agent_v3_fork` iterations 7→8: 100% pass on iteration 8 (5 issues from iteration 7 fixed, including summary pricing gap + regen redirect wiring). Evidence: `/app/evidence/EC5_evidence.md`. Reports: `iteration_7.json`, `iteration_8.json`. |
| **EC6** | Asset Library, Proofs, Signatures, and Customer Portal | **COMPLETE** | Backend 161/161 tests pass (18 new EC6 including 7 portal-payment E2E + 143 EC1–EC5 regression). Corrections directive closed: Customer Portal Invoice Payment page (`/portal/invoices/:id/pay`) wired to EC4 Stripe Core (no parallel Payment system; publishable_key + client_secret never rendered as visible text; iteration-9 DOM scan verified). `testing_agent_v3_fork` iteration 9 → 100% pass (27/27 backend curl E2E + 25/25 Playwright UI, no action items, no retest). Signed-PDF boundary formally deferred to a named later checkpoint (`/app/docs/architecture/signed_pdf_boundary.md`) — signature evidence rows immutable + `signed_pdf_file_id` reserved. Staff `ProofsPanel` mounted on Order Detail (create/version/transition with reason-required modal). Evidence: `/app/evidence/EC6_evidence.md`. Report: `/app/test_reports/iteration_9.json`. |
| **EC3.1** | **Pricing Foundation Verification & Full Calculator Category Coverage** | **REQUIRED — SCHEDULED (permanent scope, unscheduled to a specific date, must land before EC14)** | Confirms the complete Pricing Foundation remains required permanent scope: every calculator category, category-specific fields + formulas, shop rate, labor, materials, waste, markup + margin, minimum charges, complexity, add-ons, templates, Quote + Order Item integration, historical pricing snapshots, and pytest coverage using known expected pricing examples for every calculator category. Reuses EC3 pricing services — no parallel pricing system. May NOT be silently absorbed into another checkpoint. Requires its own preflight, evidence, and pytest suite. Authority: master plan Appendix A.2. |
| **EC6.3** | **Order Intake Capture & Visual Markup** | **REQUIRED — SCHEDULED (permanent scope, unscheduled to a specific date, must land before EC14)** | Order-taking workflow: image + camera + PDF uploads bound to Customer/Quote/Order/Order Item; drawing on images and blank canvas (arrows, circles, boxes, text, notes, measurement labels); original preserved separately; version history; approved markups attach to Proofs/Work Orders/Work Order Summaries; controlled portal visibility; **in-person customer signature capture during Order intake** bound to the exact Order / Order Item / drawing / image version / measurement / approval content, with signer name + timestamp + actor + device metadata + immutable audit; **no silent overwrite** of signed/approved content. Reuses EC2 FileRecord + file-link + object-storage + document-share + audit + activity, and EC6 Proof/Approval/SignatureRequest/Signature/portal-visibility. NO parallel file/drawing/approval/signature system. Requires its own preflight, evidence, and pytest suite. Authority: master plan Appendix A.1. |
| **EC7** | (next per master plan) | **READY TO BUILD** | Awaiting explicit owner execution prompt. |
| **EC7** | (next per master plan) | **READY TO BUILD** | Awaiting explicit owner execution prompt. |
| EC5 | Production and Work Orders | superseded by row above | Legacy row retained for provenance |
| EC6 | Asset Library, Proofs, Signatures, and Customer Portal | superseded by row above | Legacy row retained for provenance |
| EC7 | Inventory, Purchasing, Finance, and Reporting | superseded by row above | Legacy row retained for provenance |
| **EC7** | Inventory, Purchasing, Finance, and Reporting | **COMPLETE (all phases 7a+7b+7c+7d delivered; frontend closure workflows landed; regression PASSED)** | Phase 7a-c per prior entries. Phase 7d frontend closure: Vendor Detail (`/vendors/:id`), Material Detail (`/materials/:id`) with Material Cost History drawer, Physical Count dialog wizard on Inventory page, Inventory Transfer dialog on Inventory page, and Inventory-movements-from-PO table on PO Detail. Vendor and Material names now deep-link across the module. Backend 215/215. Frontend automated tests wired via Jest + `@testing-library/react@16`: 6 suites / 25 tests green. `testing_agent_v3_fork` iteration_10 regression: **PASS** (zero UI bugs, zero integration issues, zero regressions on EC1–EC7). Evidence: `/app/evidence/EC7_evidence.md`. |
| EC8 | Wrap Lab (add-on; standalone conditional) | NOT STARTED | Standalone remains DEFERRED UNTIL MODULE PREFLIGHT. |
| EC9 | Creative Studio and AI Foundations | NOT STARTED | AI Credit Ledger must land before AI Tools. |
| EC10 | AI Tools Catalog and Assistant | NOT STARTED | Per-tool credit costs remain provisional until measured cost audit. |
| **EC11** | **AI Credits and Usage Ledger** (LOCKED per master plan Appendix A.4 — REVISED 2026-07) | NOT STARTED | Usage ledger + provider/model cost tracking + included monthly balances (reset) + top-up balances (persistent) + monthly resets + purchased-credit retention + refunds/adjustments + **configurable plan-aware** launch guardrails (NOT hardcoded) + low-credit warnings + zero-balance blocking + provisional credit packs + cost-audit gate. |
| **EC12** | **Onboarding, Documentation, Help, and Governance UX** (LOCKED per master plan Appendix A.4 — REVISED 2026-07) | NOT STARTED | Quick Setup + Advanced Setup + mini quizzes + setup readiness + documentation registry + module documentation + Help Center + documentation-grounded AI Help + support escalation + documentation-gap reporting + failed-subscription warning/restriction UX. Displays subscription state but does NOT own billing truth. DIY wizard must work without a paid package. |
| **EC13** | **Commercial Billing and Marketing** (LOCKED per master plan Appendix A.4 — REVISED 2026-07) | NOT STARTED | Founder eligibility (first 25) + $119 m1–3 + $189 m4+ + $1,890/yr + Core $149/$1,490 + Webstores $89/$890 + Wrap $119/$1,190 + Complete $279/$2,790 + trials + paid extended trial + $20 conversion credit + setup products + annual billing + platform fees (0/0 → 0.5/1.5 Founder; 1.0/2.0 GA) + Stripe products/prices/coupons + entitlements + grace periods + continuous-active Founder enforcement + public pricing page + marketing website + signup/conversion flows. |
| EC14 | Final Integration and Commercial-Release Hardening | NOT STARTED | SMS/MMS inclusion follows the owner-selected Decision 27 outcome; conditional inside EC14 scope. |

## Program Checkpoints (PC1-PC9)

| PC | Name | Status | Comprising ECs |
|---|---|---|---|
| PC1 | Product Rules and Security | COMPLETE | EC0, EC1 |
| PC2 | Shared Platform Foundations | COMPLETE | EC2 |
| PC3 | Core Money and Order Pipeline | COMPLETE | EC3 |
| PC4 | Documents, Portals, and Customer Workflow | NOT STARTED | EC4 |
| PC5 | Inventory, Finance, and Reporting | NOT STARTED | EC5 |
| PC6 | Team and Workflow | NOT STARTED | EC6 |
| PC7 | Add-ons (Webstores + Wrap Lab) | NOT STARTED | EC7, EC8 |
| PC8 | AI, Platform, and Commercial Systems | NOT STARTED | EC9, EC10, EC11, EC12, EC13 |
| PC9 | Final Integration and Commercial-Release Hardening | NOT STARTED | EC14 |

## Owner Decision Status Summary

- **Total owner decisions:** 27
- **Status:** ALL 27 recorded as OWNER APPROVED / LOCKED (or with explicit conditional handling) in the owner-approved consolidated plan Part 4.
- **Conditional (do NOT reopen EC0):**
  - Wrap Lab standalone readiness → conditional inside EC8; not an EC0 reopener.
  - AI pricing/model / per-tool cost measured audit → conditional inside EC9/EC10/EC12; not an EC0 reopener.
  - SMS/MMS commercial-release timing (Decision 27) → conditional inside EC14; not an EC0 reopener.

## Next Action

**Await the owner prompt to begin EC5** (per the authoritative master plan).

- Do NOT begin EC5 until the EC5 implementation prompt is provided.
- Do NOT invoke or rerun the EC0/EC1/EC2/EC3/EC4 implementation prompts.

---

**Register last updated:** 2026-07 — **EC7 CLOSED.** Final closure pass delivered the remaining frontend workflows: Vendor Detail, Material Detail (with immutable Cost History drawer), Physical Count wizard on Inventory, Inventory Transfer on Inventory, and Inventory-movements-from-PO on Purchase Order Detail. Vendor and Material names deep-link across the module. Frontend automated test suite wired via Jest + `@testing-library/react@16` + `@testing-library/user-event@14` (no framework migration — reuses `react-scripts`): 6 suites / 25 tests green. Backend 215/215 green. `testing_agent_v3_fork` iteration_10 regression **PASS** (zero UI bugs, zero integration issues, zero regressions on `/supply-center`, `/purchase-orders`, `/expenses`, `/finance`, `/tax`, `/reports`). Two optional polish suggestions recorded (raw location UUIDs in tables, searchable material picker) — not scope blockers. EC3.1 + EC6.3 remain visible + pending (must land before EC14). EC8 NOT started. Await explicit EC8 execution prompt.
