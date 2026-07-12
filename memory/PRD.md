# SignGuy AI — PRD

**Product:** SignGuy AI — the permanent commercial business-management platform for sign, graphics, wrap, print, and apparel shops.
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent product). Donor repos are read-only reference material.
**Stack:** FARM (FastAPI + React + MongoDB).

## Original problem statement

Owner is building SignGuy AI as a permanent commercial application (not an MVP scaffold). Execution proceeds through numbered checkpoints (EC0 → EC14) defined in `SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`. Each checkpoint requires a preflight, code, tests, evidence package, and explicit stop before the next checkpoint.

Constraints:
- No `Job / Job Item / Job Ticket / Production Ticket / Job Ticket Summary` terminology.
- Commerce values stored as integer cents with `_cents` suffix; pricing configuration remains float dollars.
- Fail-closed production guards enforced by `security_guards.py`.
- Strict tenant isolation on every read/write.
- Backend enforcement is authoritative for permissions.
- No wholesale donor copies.

## Checkpoint status (2026-02)

| Checkpoint | Status | Evidence |
|---|---|---|
| EC0 — Owner Decisions | COMPLETE | Baked into master plan §4 |
| EC1 — Security & Guardrails | COMPLETE | `/app/evidence/EC1_evidence.md` |
| EC2 — Shared Platform Services | COMPLETE | `/app/evidence/EC2_evidence.md` |
| EC3 — Quotes, Orders, Order Items, Pricing Snapshots | COMPLETE | `/app/evidence/EC3_evidence.md` |
| EC4 — Invoices, Payments, and Stripe Core | COMPLETE | `/app/evidence/EC4_evidence.md` |
| EC5 — Production and Work Orders | COMPLETE | `/app/evidence/EC5_evidence.md` |
| **EC6 — Asset Library, Proofs, Signatures, Customer Portal** | **COMPLETE** | `/app/evidence/EC6_evidence.md` — 161/161 backend + `testing_agent_v3_fork` iteration 9 100% pass |
| **EC3.1 — Pricing Foundation Verification & Full Calculator Category Coverage** | **REQUIRED — SCHEDULED (permanent scope)** | Master plan Appendix A.2 — every calculator category, formulas, shop rate/labor/materials/waste/markup/margin/minimums/complexity/add-ons/templates, snapshots, tests. Must land before EC14. |
| **EC6.3 — Order Intake Capture & Visual Markup** | **REQUIRED — SCHEDULED (permanent scope)** | Master plan Appendix A.1 — image + camera + PDF uploads, drawing on images + blank canvas, version history, attach to Proofs/WOs/WOSummaries, controlled portal visibility, in-person signature capture bound to exact target with immutable audit. Reuses EC2 + EC6, no parallel system. Must land before EC14. |
| EC6.2 — Signed PDF Composite Rendering | DEFERRED (unscheduled) | `/app/memory/product_ideas_register.md` — reconsider during EC14 Final Hardening, or earlier only on a verified customer/compliance/operational requirement. Do NOT schedule during EC7. |
| **EC7 — Inventory, Purchasing, Finance, Reporting** | **COMPLETE** (all phases 7a+7b+7c+7d delivered; frontend closure workflows landed; `testing_agent_v3_fork` regression PASS) | `/app/evidence/EC7_evidence.md` + `/app/docs/modules/EC7_INVENTORY_PURCHASING_FINANCE.md`. Backend 215/215 green. Frontend Jest 25/25 green. Regression report `/app/test_reports/iteration_10.json`. |
| **EC8 — Team, Scheduling, Time, Payroll, Employee Portal, Equipment Training & Certification** | **DELIVERED / CLOSED — all phases 8a–8f complete.** | `/app/evidence/EC8_evidence.md`. Employee CRUD + status transitions, Announcements, Team Dashboard (8a) + Time Clock + Timesheets (8b) + Scheduling & Employee Portal (8c) + Payroll (8d) + Equipment/Training/Certification + Work Order enforcement (8e) + final closure regression (8f) — 312/312 full backend pytest green + terminology guard OK. Phase 8f ran the first full frontend regression covering Phase 8e (`testing_agent_v4` iteration_15): found 3 Phase-8e-only defects (critical quiz-submission 500; medium Certifications Matrix stale-dialog; low a11y DialogTitle warning), all fixed and confirmed via a focused retest (iteration_16, 100% pass, 0 open defects). Zero regressions in EC0-EC7 or Phase 8a-8d. EC8 formally closed. |
| EC9–EC14 | NOT STARTED | dependency-ordered per master plan |

## Completed capabilities

- Auth / Tenants / Users / Permissions (staff + platform + portal scopes) — EC1.
- Startup guards, terminology guard, money helpers, LOCKED navigation shell — EC1.
- Settings / Activity / Notifications / SendGrid webhook / Upload validation / File+Document links / Feature entitlements / Integration status — EC2.
- Quote line items + revisions + expiration + approval-state foundation — EC3.
- Rich Order Item schema with backend-derived totals, pricing snapshots, manual override with reason — EC3.
- `production_required` rule + override + reason — EC3.
- Idempotent race-safe Quote-to-Order conversion copying line items + snapshots + source revision — EC3.
- Work Order snapshot filters by `production_required` — EC3.
- **Functional frontend Quote/Order editors:** quick + detailed entry modes, calculator integration, override-reason validation, production-required switch, revision-warning dialog, expired-quote convert-with-override UX, source-quote link on Orders — EC3 (v2 corrections).
- Invoice dual-status (`document_status` + `financial_status`), reconciliation, `_cents` money, immutable snapshots — EC4.
- Payments: record / void / refund with idempotency; Stripe Core integration (test adapter, publishable-key + client_secret never leak to DOM/console) — EC4.
- **Work Order lifecycle (EC5):** 9-state enum, priority + due dates, immutable snapshots, versioned regenerate/supersede with reason, controlled transitions coordinating Order operational status, cross-tenant-safe assignment with in-app notifications, printable summary gated by `invoice:read`, `/api/production/board` view — EC5.
- **Production frontend (EC5):** Production Board (Kanban + HTML5 drag-drop + reason-required modal), rebuilt Work Order Detail (version banners, priority/due, allowed-transitions sidebar, assign dialog, in-page Print Summary), Generate WO dialog on Order Detail, Regenerate on both Order + WO detail, 9-state WO list filters + current-version toggle, Production Board sidebar link, all controls permission-gated via `/auth/me`.
- **Asset Library + Portal (EC6):** Documents metadata + versioning layered over existing FileRecord; scoped public-action tokens (single-purpose, expiring, revocable, hashed at rest); magic-link portal login (hashed, single-use, audience-scoped); portal JWT separation (`sub_scope="portal"`, disjoint dependency graph); Portal Identity n:1 mapping to Customer with 5 backend-authoritative permission-bundle presets; staff surfaces for Proofs (create/version/transition), Approvals (dual-parent incl. WOS), Signature Requests + Signatures; Public single-action endpoints (proof approve, sign, quote_view, invoice_view, public quote request, customer intake with staged-changes review); Portal customer routes (Quotes/Orders/Invoices/Documents/Proofs/Messages/Profile) with tenant+customer scope on every query; Portal messages via existing email service (no new messaging schema); Portal shell + login/magic-link/verify + list pages at `/portal/*` and public token pages at `/p/*`, both mounted OUTSIDE the staff `<AppShell>`.

- **Scheduling + Employee Portal (EC8 Phase 8c):** `Schedule`/`Shift` models (one Schedule per tenant per Sat–Fri week), manager Team Schedule builder (add/edit/cancel/copy shift/copy day/copy week/assign multiple/publish/republish), hard conflict blocks (duplicate/overlap/invalid/inactive/cross-tenant) + soft availability-warning with authorized override (audited). Employee Portal is additive on EC6's `PortalIdentity` (new `portal_type` discriminator — no second identity/token system) covering Dashboard, Time Clock (reused from 8b, zero duplicated logic), My Schedule (published-only, self-scoped), My Timesheet (self, payroll-rate-derived fields stripped), Announcements (audience/target-filtered), Profile — with a documented "My Tasks" boundary placeholder (no Task system exists). Separate `/portal/employee/*` shell + `sg_employee_portal_token` localStorage key from the Customer Portal.

- **Payroll (EC8 Phase 8d, 2026-07):** Internal gross-pay ledger only — NOT payroll-processing/tax-filing/banking (no ACH, no bank/SSN storage, no tax withholding, no W-2/1099). `PayPeriod` (one per tenant per Sat–Fri week, Friday payday, structurally overlap-free via unique `(tenant_id, start_date)` index) with statuses `open→review→approved→partially_paid→paid→closed` (+`voided`) — `partially_paid`/`paid` are ALWAYS derived from the append-only `PayrollTransaction` ledger (`_refresh_period_financial_status`), never directly settable. `PayrollSnapshot` is a pure read-model recomputed from the ledger (`_sum_ledger`/`_money_totals`); recalculation while open/review is idempotent (never duplicates `earning`/`overtime_earning` rows — only regenerates when the computed amount changes) and freezes on approval (reopen requires `payroll:manage` + a mandatory audited reason). Blocking-warning gate (`missing_rate`/`timesheet_not_approved`/`open_time_entries`/`overlapping_entries`/`not_recalculated`) on approve/close, overridable with a required reason (audited). Overtime: 40hr/week + 1.5x tenant default via the existing Settings `payroll` namespace, with per-Employee override. Carryover on close: immediate `carryover_in` if the next Pay Period exists, else a `payroll_carryovers` pending record that auto-links (idempotent, no duplicate creation) when that period is later created. Manual ledger entry types exposed to managers: `adjustment`/`advance`/`advance_repayment`/`payment` (idempotency-key support); voids/corrections always append an offsetting `void` row, never mutate history. Reuses EC7 Reports registry + generic CSV export for 2 new report keys (`payroll.by_period`, `payroll.by_employee`) — no parallel export system. Employee Portal "My Pay" added to the existing `portal_employee.py` router (no new router file) with a strict field allow-list (never other employees/manager notes/audit internals/bank/tax data). Manager UI: `/team/payroll` (Pay Periods / Employee Ledger / Settings tabs), Payroll tab on Employee Detail, Payroll card on Team Dashboard. 13 targeted backend pytest tests (`tests/test_ec8d_payroll.py`) + 60-test regression, all green.

- **Equipment, Training & Certification + Work Order enforcement (EC8 Phase 8e, 2026-07):** `Equipment` (category/access_policy/safety_sensitive/status), `TrainingDefinition` (reading/video/sop_review/quiz/practical_demonstration/manager_signoff/retraining, optional quiz authoring + `passing_score`, optional `practical_signoff_required`), `TrainingAssignment` lifecycle (`assign→start→complete|quiz→(pending_signoff)→signoff|fail|cancel`, quiz attempt history preserved, retry-after-fail correctly re-opens the assignment), `Certification` (issue/renew/revoke with permanent history, auto-expiry, `expires_soon` window). Work Order `assign()` runs `certification_service.check_work_order_assignment` against every proposed assignee's Certification for each of the Work Order's `required_equipment_ids`: `no_required`/`recommended` never block; `required_no_override` + no valid Certification → hard `409 assignment_blocked` (not overridable); `required_override_allowed` + no valid Certification → `409 assignment_warning_override_required`, assignable only with a non-empty `override_reason`; `required_role` mismatch is advisory-only (never blocks). The frontend `AssignDialog` renders the backend's `check.results` verbatim (block=rose/non-overridable, warning=amber/override-gated) — the enforcement rule is never re-implemented client-side. Manager UI: Equipment list/detail (`/team/equipment`), Training Definitions+Assignments incl. quiz builder (`/team/training`), Certification Matrix + All Certifications with issue/renew/revoke (`/team/certifications`), Work Order "Assignment requirements" card + edit dialog. Employee Portal: My Training (list + quiz-taking assignment detail) and My Certifications (read-only, renewal-needed flag), both strictly self-scoped (never accepts an Employee ID from the client, never exposes quiz answer keys/manager notes/override audit detail to the portal). Two real bugs found and fixed this phase: a quiz-retry-after-fail 409 caused by `complete_assignment`'s terminal-status guard firing on a legitimate passing retry; and pre-existing Employee Portal identities missing the new Training/Certification permissions (re-invite now re-syncs permissions, no separate migration needed). 15 targeted backend pytest tests (`tests/test_ec8e_equipment_training.py`), plus live curl verification of both the hard-block and warning-override Work Order assignment paths.

- **EC8 Phase 8f — Final closure (2026-07):** First full backend (312/312 pytest) + full frontend (`testing_agent_v4`) regression across EC0–EC8. Found and fixed 3 Phase 8e-only defects: quiz-submission 500 (schema-less quiz question dicts lacked a stable `id`; fixed via server-side backfill on create/update + defensive lookup), Certifications Matrix stale-dialog-after-issue (decoupled dialog state), and a missing-DialogTitle a11y warning. Confirmed via retest: 100% pass, 0 open defects. EC8 formally closed.

## Testing

- Backend: `cd /app/backend && python -m pytest tests/ -q` → **215 passed** (through EC7 phase 7d).
- Frontend Jest: `cd /app/frontend && CI=true yarn test --watchAll=false` → **6 suites / 25 tests passed** (EC7 closure — Physical Count, Transfer, Material Detail, Vendor Detail, PO Detail, EC7 smoke).
- Frontend E2E: `testing_agent_v3_fork` iteration 10 (EC7 closure) → **PASS** — all newly-added flows verified, zero regressions on `/supply-center`, `/purchase-orders`, `/expenses`, `/finance`, `/tax`, `/reports`. Prior iteration 9 (EC6 corrections): 100% pass. Iteration 8 (EC5): 100% pass.

## Test credentials

`AUTH_DEV_BYPASS=true` in development; dev-bypass banner visible in UI. No production credentials exist in `.env`.

## Priority backlog (P0/P1/P2)

### P0 — Immediate next checkpoint
- EC8 is DELIVERED / CLOSED (all phases 8a–8f complete, full regression passed). Per explicit owner instruction, no new checkpoint (EC9 or otherwise) begins until the owner explicitly authorizes it.

### P1 — EC8 (all phases 8a–8f complete)
- Phase 8a — Employees & Team Foundation ✅ DONE
- Phase 8b — Time Clock & Timesheets ✅ DONE
- Phase 8c — Scheduling & Employee Portal ✅ DONE
- Phase 8d — Payroll (pay periods, transactions ledger, advances/payments/carryover, My Pay, exports) ✅ DONE
- Phase 8e — Equipment, Training & Certification + Work Order assignment enforcement ✅ DONE
- Phase 8f — Full EC8 frontend regression, full backend regression, closure evidence ✅ DONE

### Permanent scope — REQUIRED before EC14 Final Hardening (owner-locked)
- **EC3.1 Pricing Foundation Verification & Full Calculator Category Coverage** — every calculator category + formulas, shop rate/labor/materials/waste/markup/margin/minimum charges/complexity/add-ons/templates, snapshots, and pytest coverage with known expected pricing examples. Reuses EC3 pricing services; no parallel pricing system. Master plan Appendix A.2.
- **EC6.3 Order Intake Capture & Visual Markup** — image + camera + PDF uploads bound to Customer/Quote/Order/Order Item, drawing on image + blank canvas, versioned annotations, attach approved markups to Proofs/Work Orders/Work Order Summaries, controlled portal visibility, **in-person customer signature capture** bound to exact Order/Order Item/drawing/image version/measurement/approval content with immutable audit. Reuses EC2 files/links/storage/audit + EC6 Proof/Approval/SignatureRequest/Signature; no parallel file/drawing/approval/signature system. Master plan Appendix A.1.
- **EC7 A.3 Supplier Catalog, Price Comparison & Integrated Purchasing** — normalized supplier-product model, reusable connector interface (search_catalog/get_product/get_variants/get_account_price/get_inventory/get_shipping_quote/create_supplier_order/retrieve_supplier_order/retrieve_tracking/cancel_order), three connection tiers (API/EDI, catalog feed, manual+handoff), shortage calc, purchasing recommendation with delivered-cost comparison, Supply Center staff UI, idempotent supplier-order submission via EC2 integration-secret storage, at least one realistic end-to-end connector or deterministic test adapter demonstrating catalog→variant→price→availability→shortage→PO→submission→receiving. Master plan Appendix A.3. **Assigned to and delivered inside EC7.**

### P1 — After EC8
- EC9 Webstores + Stripe Connect (add-on + standalone shell).
- EC10 Wrap Lab.

### P2 — Later (LOCKED per master plan Appendix A.4 — REVISED 2026-07)
- **EC11 — AI Credits and Usage Ledger** — usage ledger, provider/model cost tracking, included monthly balances (reset), top-up balances (persistent while account active), monthly resets, purchased-credit retention, refunds and adjustments, **configurable, plan-aware** launch guardrails (NOT hardcoded permanent limits), low-credit warnings, zero-balance blocking, provisional credit packs, cost-audit gate.
- **EC12 — Onboarding, Documentation, Help, and Governance UX** — Quick Setup + Advanced Setup wizards, mini quizzes, setup readiness, documentation registry, module documentation, Help Center, documentation-grounded AI Help, support escalation, documentation-gap reporting, **failed-subscription warning + restriction UX**. May display subscription state but does NOT own billing truth. DIY wizard must work without a paid package. Paid setup purchases must not create a parallel onboarding system.
- **EC13 — Commercial Billing and Marketing** — Founder eligibility (first 25 shops), $119 for first 3 paid months, $189 Founder monthly renewal, $1,890 Founder annual, Core $149/$1,490, Webstores $89/$890, Wrap $119/$1,190, Complete $279/$2,790, trials, paid extended trial + $20 conversion credit, setup products + add-ons, annual billing, platform fees, Stripe products/prices/coupons, entitlements, grace periods, continuous-active Founder enforcement, public pricing page, marketing website, signup + conversion flows.
- **EC14 — Final Integration & Hardening** — closes only after EC11 / EC12 / EC13 are COMPLETE.

### Commercial pricing source of truth (LOCKED)

Master plan **Appendix A.4** and `/app/docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` are the commercial source of truth. All Stripe product setup, marketing copy, entitlement rules, onboarding packages, and billing tests must match A.4. **None of A.4 is implemented during EC7.**

### Permanent future-scope register — configurable paid add-ons

- **Advanced Production Tracking & Bottleneck Analytics Add-On** (owner-locked, added 2026-07 during EC8 Phase 8c) — Production Stage Timer tracking Employee time against Work Order/Order Item/production stage/Equipment, distinct from and never merged with EC8's Payroll Time Clock. Append-only timer sessions/events, duplicate-timer/overlap/cross-tenant/unauthorized-WO prevention, no silent historical edits, no automatic production-time→payroll-time conversion without an explicit policy. Required analytics: estimated vs actual, average time by stage/category/employee, wait time, WIP age, queue length, stalled WOs, bottleneck stages, rework frequency, first-pass completion rate, equipment delays, throughput trends. Employee Portal integration reserves `/portal/employee/production` (not built, not wired into nav/routes). Gated through the shared plan/feature-entitlement system — **never** hardcoded as always-on. Full boundary contract documented at `/app/docs/production_stage_timer_boundary.md`. **NOT scheduled for implementation during EC8** — no code, routes, models, or placeholder data exist.

## Known deferred items (from EC3)

- Sales-tax provider integration (accepted as pass-through data).
- Assigned-team / install-notes / packaging-notes fields on OrderItem → owning module checkpoints (Team & Workflow, Wrap Lab).
- Public/portal quote approval → EC6 shared Approvals system.

## Authority references

- `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`
- `/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`
- `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`
- `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`
- `/app/memory/AGENT_INSTRUCTIONS.md`
- `/app/memory/progress_register.md`
