# SIGNGUY-MVP | Project Operating Playbook

**Prepared:** October 13, 2026  
**Scope:** `dnblack323/SIGNGUY-MVP`, the permanent SignGuy AI online product.  
**Current mode (updated 2026-10-14):** the one-time baseline is COMPLETE (see §5). Work now follows `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md`, one owner-approved feature at a time. This document sets process; it does not by itself authorize implementation or deployment.

## 1. Vision and commercial objective

Build an online, multi-tenant subscription application that a real sign shop can sign up for, configure, use to quote and manage a job/order, and pay for. Launch a credible **sellable core** as soon as it is secure and actually usable. Continue shipping opt-in feature improvements afterward. Do not wait for advanced AI, portals, webstores, Wrap Lab, or every conceivable workflow to be perfect before selling a clearly scoped core tier, unless a binding dependency or approved commercial policy requires it. Never claim an unfinished capability is included in a sold plan.

The application should unify shop setup and pricing, customer relationships, sales documents, production, scheduling, employees, payments, business operations, webstores, and later AI-enabled features. Favor compact, practical interfaces for working sign-shop staff, not decorative dashboards or sprawling multi-step forms.

**Success metric:** a new tenant can sign up, configure enough real shop data, create a customer and accurate quote, convert it into an Order/Work Order, track production, invoice and record payment, without cross-tenant exposure or corrupted totals; a buyer can understand the plan, start paying and receive appropriate entitlements/support. Some steps may be released in phases only if the marketed capabilities remain truthful.

## 2. Repositories and reuse boundaries

| Repository | Role | Allowed reuse |
|---|---|---|
| `dnblack323/SIGNGUY-MVP` | Permanent commercial SaaS | Target for all new product implementation; protect its live interfaces and storage |
| `dnblack323/Signguy-AI-Pricing-Lab` | Windows offline Price Lab | Approved UI patterns, category setup/calculator specifications, pricing workflows, demo design, tests and interaction evidence |
| `dnblack323/SIGNGUY-PRICING-ENGINE` | Portable pricing engine | Validated pure pricing formulas, method results, provenance, completeness and fixtures through a compatible pinned release |
| `SIGNGUY-AI-OS`, `signguyai_rebuild_version`, `signguy-ai-feb22`, `signguyai` | Legacy design/feature donors | Compare behavior and extract good ideas only, never wholesale import |

**Critical constraint:** do not copy desktop Electron wrappers, SQLite persistence, offline licensing, installer behavior, Price Lab's `Job` persistence terminology, or Python sidecar IPC into a MongoDB/FastAPI SaaS. Recreate the useful UX/logic at MVP's existing API, entity and shared-engine boundaries. The existing MVP commercial domain is authoritative.

**Pricing-engine version gap to investigate:** Price Lab merged Engine 0.14.0 during Services work, while SIGNGUY-MVP's current README mentions an earlier pinned wheel/version in its setup/history. Read MVP's *actual* package lock, installed wheel, integrations, current engine API and pinned hashes before proposing an update. Never equate 'latest' with 'compatible' or change formulas without parity evidence.

**Confirmed 2026-10-14:** MVP pins `signguy-pricing-engine` **0.1.0** (`backend/pricing_engine_package.lock.json`, tag `v0.1.0`, SHA-256 verified by `backend/scripts/install_pricing_engine.py`). Price Lab `origin/main` and the Engine repository `main` are at **0.15.0**; the Engine's only published GitHub Release is `v0.1.0`, so a release for the target version must be published before MVP can pin it. The upgrade is the **pre-launch** feature F2 (Stage A) in the launch plan §E, followed by Pricing Foundation (F3) and per-category calculator modernization (F4) using Price Lab as the reference implementation.

## 3. Repository facts established before this handoff

Repository `main` has `backend/`, `frontend/`, `docs/`, `memory/`, `specs_pack/`, `evidence/`, `tests/`, `docker-compose.yml`, `nginx/`, and `scripts/`.

- Backend: FastAPI, Python, MongoDB/Motor, `/api` routes. Existing code is structured around app models, services, routers, core and (for new modules) repositories.
- Frontend: React with Create React App/CRACO, shadcn/ui, Tailwind, app-shell/navigation, pages and auth guards; frontend uses Yarn 1.x. Check actual dependencies: the README says React 18 but current `frontend/package.json` lists React 19. This is a documentation/version inconsistency to reconcile, not a reason for an unsolicited framework migration.
- Multi-tenant login, permission scopes, billing, payment, pricing snapshots and workflow boundaries are covered by existing code/specifications. Completion register statements are **claims requiring current validation**.
- `memory/AGENT_INSTRUCTIONS.md` already states immutable money/security/terminology/business contracts. Do not supersede it with generic new-agents boilerplate.
- Original plan and checkpoint docs are extensive and may conflict by age. `memory/documentation_authority_register.md` gives the controlling precedence, and `memory/owner_specification_hold_register.md` contains approvals required before certain work.
- Some historical plans use `/app/...` paths from hosted environments. Resolve those references relative to this Git checkout; do not assume the present machine has `/app`.

## 4. Specification authority and owner decisions

Read only the relevant slices in this order:

1. The owner's newest explicit approved scope for the task, respecting explicit existing holds and external contract obligations.
2. `memory/documentation_authority_register.md` and `memory/owner_specification_hold_register.md`.
3. Relevant checkpoint specification under `specs_pack/extracted/` (EC09–EC22 where applicable).
4. Existing locked MVP contracts in `memory/AGENT_INSTRUCTIONS.md` plus relevant `docs/architecture/` and `docs/security/`.
5. Current backend/frontend source and runtime evidence, current PRs, current tests.
6. Older master plans/registers and donor repos as historical evidence.

When a current UI preference conflicts with an existing terminology/navigation/data contract, note that conflict precisely rather than changing the persisted model as a side effect of styling. Respect signed-off pricing/business rules. Ask only for an unresolved material owner choice, not routine implementation details.

## 5. One-time baseline audit: what to inspect

> **STATUS: COMPLETE — do not repeat.** Results: `docs/audits/MVP_BASELINE_AUDIT_2026-10-10.md`, `docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv` (124 rows, authoritative) and `docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md`. Their mapping to launch work is in `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md` §G. This section is kept as the record of what the baseline covered.

**Purpose:** learn what actually works and select a single best path to a sellable release; not generate another endless review cycle. Keep this read-only and bounded. First read existing readiness/source registers, compare with current main and changed commits, then inspect enough source, routes, tests and running behavior to validate each claim. The one-time baseline may span the whole product; subsequent feature reviews are scoped.

| Area | Evidence to collect | Critical question |
|---|---|---|
| App shell, home, navigation | live routes, guards, responsive UI | Can intended roles reach active screens without duplicate/blank routes? |
| Identity, tenants, onboarding | backend tenancy/security + login demo | Can a new shop sign up safely and maintain isolated data? |
| Shop setup and Pricing Foundation | setup, draft/active defaults, guided flows | Can a shop enter required actual costs/rates and activate valid defaults? |
| Material/Equipment/Staff Resources | canonical catalogs and CRUD | Are records reusable, tenant-scoped, correctly priced? |
| All calculator categories | category screen/API/Engine parity | Which categories really quote, save, and surface unavailable inputs? |
| Customers/Leads | CRUD and conversion | Can actual sales start with a customer? |
| Quotes/Orders/Work Orders | revision/snapshot, handoffs, production | Can a quote become an order and be fulfilled without recalculating history? |
| Invoice/Payment/Stripe | totals, invoice state, idempotency | Can customer pay and shop reconcile correctly? |
| Production/Schedule/Team | real task routes, timers and calendar | What part is usable vs an attractive placeholder? |
| Webstores/Portal | roles, authentication, permissions, payments | What is truly production-capable versus staged? |
| AI/Studio/Assistant/Wrap Lab | real provider/config/usage cost gates | Which features work and which should be disabled or unmarketed at launch? |
| Subscription commercialization | registration, trial, tiers, entitlements, checkout, webhooks | Can a customer buy and access the correct plan? |
| Deployability/operations | Docker, nginx, CI, env, migrations, backup, logging, email, support | Can a tenant be onboarded and serviced online reliably? |

**Test standard:** `WORKING` only when an end-to-end path has been observed with isolated/nonproduction data and the tested environment/date is recorded. `PRESENT-UNVERIFIED` when only code/tests/older reports exist. No blanket "complete" claims. For discovered dead code mark `OBSOLETE-CANDIDATE` pending reference/data/entry-point proof; do not delete during audit.

### Required baseline output (one concise report)

1. **Architecture map:** frontend routes, backend domain modules/APIs, storage ownership, engine boundary, deployment/CI; highlight only high-impact duplications or monoliths.
2. **Feature matrix:** one row per major page/workflow with `status`, `UI/API paths`, `evidence` (RUNTIME, TEST, SOURCE or HISTORICAL), `customer impact`, `best donor`, `blocker`, `next action`.
3. **Launch readiness:** true blockers vs post-launch improvements; flag tenant/data/payment/security prerequisites first.
4. **Reuse shortlist:** precise feature or component from Price Lab/original SignGuy AI, source file, target MVP architecture and migration risk. Propose before copying.
5. **Next ONE feature:** smallest high-value vertical slice toward first sellable tenant; its definition of done and necessary owner decision.

Keep final report short enough for a nondeveloper. Detailed findings can use one audit artifact if necessary; do not spawn standalone reports for each subsystem or perform fixes while auditing.

## 6. Development workflow AFTER the audit

**One feature at a time, guided by the owner.** A feature is a customer-visible vertical slice, not a file, isolated component or unrelated batch. For each feature:

1. Identify what exists and which code is already used. Inspect one corresponding Price Lab/original SignGuy AI implementation only when it provides a demonstrated improvement.
2. Define customer action and exit condition: e.g., quote → save → convert → production → invoice. The release slice may be smaller when clearly disclosed.
3. Make focused implementation on an isolated branch/PR. Reuse current MVP services, app shell, components, records and shared engine; never create a second authority for the same data.
4. Test the affected tenant, calculation, snapshot, permissions, stored data, and UI paths. Use a real browser/runtime demo with isolated demo tenant and screenshots for significant UI changes.
5. Perform one focused review, resolve real blocking findings, finish required current-head CI, merge only with authorization; do not auto-deploy.
6. Confirm the merged change runs on the intended integration environment. Mark `FUNCTIONAL BASELINE — OWNER VISUAL REVIEW PENDING` when appropriate; do not confuse agent checks with owner sign-off.
7. Return the next single feature recommendation and STOP. No autonomous queue of ten features.

### Verification tiers

- Class A: docs/UI labels/simple visual. Direct surface verification + relevant lint/config if needed.
- Class B: form/workflow and nonfinancial data. Relevant frontend/backend tests and browser smoke.
- Class C: money, pricing, snapshots, tenant/security, payments, billing, migrations, release. Contract/authorization/integrity tests, correct CI, migration/rollback proof where applicable, actual critical-path smoke.

Do not run the whole test suite at every intermediate checkpoint. But do not skip mandatory production/release gates. Use RTK where available to avoid verbose command output, and check savings rather than assuming them.

## 7. Commercial launch path (validate, don't assume complete)

**A candidate minimum sellable tier** requires: authenticated tenant onboarding; plan/trial/payment-to-entitlement flow; foundational settings and usable pricing; Customer/Quote/Order/Work Order pipeline; Invoice/Payment workflows that work within advertised scope; reliable backups and tenant isolation; deployment/health/error monitoring; and basic support/onboarding. Whether some components belong in an entry tier is an owner decision governed by actual EC13/EC19/EC21 terms.

The approved sequencing of this path lives in `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md`.

Do not silently discard unreleased functionality from the permanent roadmap. Separate `MUST WORK FOR FIRST PAID CUSTOMER`, `LATER PAID FEATURE UPDATE`, and `WAITING FOR OWNER/CONTRACT` so a small commercial V1 can launch safely. Be honest in plan descriptions and marketing about what exists.

Do not initiate AI/voice/tool actions, production Stripe writes, customer migrations or live launch in discovery. Monetization policies, entitlement names and amounts must come from current approved commerce specs, not guesses.

## 8. UX and domain reuse targets (not preapproved code moves)

> **Owner direction 2026-10-14:** the Price Lab Pricing Foundation and all nine category calculators (layouts and behavior) are approved **pre-launch** targets, implemented one stage at a time per launch plan §E (Stage A Engine → B Foundation → C one category per stage → D pricing-to-Quote/Order verification). Each stage still needs separate owner authorization. Other patterns below remain assess-first.

**Price Lab patterns worth assessing:** compact petrol-teal app header, icon-collapsed charcoal sidebar, single Home dashboard with customizable nonduplicate widgets, inline Foundation cards + Draft/Review/Activate, real Active-versus-Draft benchmark, Guided Setup feeding one Draft, canonical Resources, matching full-page/overlay calculator, live multi-method estimate, Quick Prices, Show the Math and saved pricing evidence, production task timing, financial document/record-payment integration, scheduling, and readable help/onboarding. Actual MVP navigation/terminology authorities must be preserved unless explicitly changed.

**Original SignGuy AI:** examine approved design/spec behavior for sales intake, graphical markup/proofs, work orders, employee/customer portals, webstores, AI growth tools and other owner-prioritized features. These are donor references, not current MVP completion proofs.

Recreate a *workflow*, not a screenshot alone. When different repositories implement competing solutions, document a short side-by-side comparison, choose one authoritative target in MVP and remove duplication only when proved unused and authorized.

## 9. Agent and tooling map

Two equivalent homes for the same three optional read-only specialists:

| Specialist | Work | Invocation threshold |
|---|---|---|
| Token Optimizer | narrow repo/context searches; RTK output compacting; prompt focus | only for genuinely context-heavy tasks |
| Test Gatekeeper | select smallest suite with meaningful coverage | scoped changes with ambiguous test scope |
| Review Gatekeeper | review concrete architecture/money/tenant boundary | potentially consequential changed boundary |

In Codex use `.codex/agents/*.toml`; in Claude Code use `.claude/agents/*.md`. The assistant may perform these jobs itself. Do not delegate orchestration to a subagent. These roles do NOT have write, testing, merge or deployment authority. The primary implementer alone owns the final decision and evidence.

**Tool economy:** use targeted `rg`, relevant paths, small file windows and Git diff; avoid rescanning large plans repeatedly. Run `rtk --version` first; only use `rtk` if present. Never run a potentially destructive cleanup on a dirty worktree; preserve untracked owner artifacts. No imaginary token saving claims.

## 10. Ready-to-send kickoff for Claude Code or Codex (one feature)

The original read-only baseline kickoff has been used and is retired. For each approved feature send:

> SIGNGUY-MVP — FEATURE `<F#> <name>` from `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md`. Read root AGENTS.md, the launch plan entry for this feature (scope, inventory rows, CIR/CH IDs, definition of done) and memory/AGENT_INSTRUCTIONS.md. Do NOT run a general audit. Branch from current origin/main. Inspect only the listed rows' Relevant Files and their direct dependencies; keep what works, complete the gap, remove obsolete code inside this feature only. Verify the real customer workflow on an isolated demo tenant, run the focused tests for the feature's verification class plus required CI, open ONE PR, and STOP with a plain-English report. Do not merge or deploy without owner approval. Do not start the next feature.

## 11. Owner working preferences

Challenge plans that waste effort or create redundant systems. Keep instructions specific and brief. Explain real risks early, rather than agreeing and uncovering the obvious flaw after hours of work. Use one Codex/Claude Code prompt per feature/stage, reuse prior decisions, minimize repeated CI and token cost, and preserve owner visibility over milestone choices. Prefer measured completed workflows over audit volume, agent count, document count or percentage-complete guesses. Owner reviews final visuals by annotating screenshots after functional baselines exist; this does NOT defer security, pricing or data-integrity defects.
