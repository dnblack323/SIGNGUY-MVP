<!-- headroom:rtk-instructions -->
# RTK (Rust Token Killer) - Token-Optimized Commands

When running shell commands, **always prefix with `rtk`**. This reduces context
usage by 60-90% with zero behavior change. If rtk has no filter for a command,
it passes through unchanged — so it is always safe to use.

## Key Commands
```bash
# Git (59-80% savings)
rtk git status          rtk git diff            rtk git log

# Files & Search (60-75% savings)
rtk ls <path>           rtk read <file>         rtk grep <pattern>
rtk find <pattern>      rtk diff <file>

# Test (90-99% savings) — shows failures only
rtk pytest tests/       rtk cargo test          rtk test <cmd>

# Build & Lint (80-90% savings) — shows errors only
rtk tsc                 rtk lint                rtk cargo build
rtk prettier --check    rtk mypy                rtk ruff check

# Analysis (70-90% savings)
rtk err <cmd>           rtk log <file>          rtk json <file>
rtk summary <cmd>       rtk deps                rtk env

# GitHub (26-87% savings)
rtk gh pr view <n>      rtk gh run list         rtk gh issue list

# Infrastructure (85% savings)
rtk docker ps           rtk kubectl get         rtk docker logs <c>

# Package managers (70-90% savings)
rtk pip list            rtk pnpm install        rtk npm run <script>
```

## Rules
- In command chains, prefix each segment: `rtk git add . && rtk git commit -m "msg"`
- For debugging, use raw command without rtk prefix
- `rtk proxy <cmd>` runs command without filtering but tracks usage
<!-- /headroom:rtk-instructions -->

# SIGNGUY-MVP — Root Agent Instructions

**Product:** SignGuy AI, the online multi-tenant SaaS for sign shops. **Permanent repository:** `dnblack323/SIGNGUY-MVP`. **Goal:** get a secure, usable, sellable Core V1 online and earning subscription revenue, then ship one completed feature update at a time.

## Read order

1. This file.
2. `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md` — the owner-approved launch order, blockers and the current feature. **Work only on the feature it names as current.**
3. `docs/MVP_BUILD_PLAYBOOK.md` — operating process and verification classes.
4. `memory/AGENT_INSTRUCTIONS.md` — permanent LOCKED implementation rules. **Binding. Not restated here; that file wins.**
5. `memory/documentation_authority_register.md` and `memory/owner_specification_hold_register.md` — precedence and owner holds.
6. Only the audit rows and source files for the current feature (see "Audits" below).

Historical plans use `/app/...` paths from the old hosted environment. Resolve them relative to this checkout.

## Mode

`MODE = BUILD`, scoped to **one** owner-approved feature from the launch plan. Do not start the next feature on your own. Explicit owner instructions such as `READ ONLY`, `PLAN ONLY`, `DRAFT PR`, `DO NOT MERGE` and active holds override ordinary merge habits. Never deploy to production, enable live billing, change paid entitlements or migrate live records without explicit release authorization.

**Feature loop:** read the feature's audit rows → inspect only the relevant implementation → keep what works → complete or correct the gap → reuse superior Price Lab / original SignGuy AI behavior where the plan allows → remove obsolete or duplicate code inside that feature only → verify the real customer workflow → focused tests + required CI → PR → merge only with owner authorization → report → STOP.

## Audits are complete — do not repeat them

The one-time baseline is done. Do **not** run another general code, feature or architecture audit.

- `docs/audits/MVP_BASELINE_AUDIT_2026-10-10.md` — feature/workflow audit.
- `docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv` — the authoritative 124-row findings register (row numbers are used by the launch plan). Do not edit findings; record status changes in the launch plan.
- `docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md` — code-health audit (cleanup IDs `CH-01`…`CH-23`).
- `memory/code_issue_register.md` — open correctness defects (`CIR-…`).

Inspect additional code only when a specific finding needs clarification for the current feature.

## Binding contracts (reminder only — full text in `memory/AGENT_INSTRUCTIONS.md`)

Tenant filters on every tenant-owned query; backend-enforced permissions in three disjoint scopes; integer `_cents` commerce money with the single conversion boundary; backend-authoritative totals; immutable quote revisions and snapshots; canonical **Order / Work Order** terminology (never `Job` as a persisted model); approved navigation; verified, idempotent Stripe webhooks; no production dev bypass; no parallel Customer/Order/Invoice/Payment/File/Audit stores; no AI before credit metering and cost controls; no wholesale donor copies. If a new instruction conflicts with one of these or with an owner hold, name the exact conflict before changing behavior.

## Sources: reuse, do not copy blindly

- **SIGNGUY-MVP** is authoritative for data, auth, roles, routing, records and SaaS behavior. Reuse existing MVP services and components first.
- **Price Lab** (`dnblack323/Signguy-AI-Pricing-Lab`) is the **reference implementation for MVP's Pricing Foundation and all nine category calculators** (pre-launch Track 2, milestones P1–P6, launch plan §E; starts only when its stability gate opens): recreate its approved functionality and layouts inside MVP's shell and tenant architecture, keeping MVP's Quote/Order records. Treat an unfinished Price Lab category as a gap, not as approved. Read its merged `origin/main` with `git show origin/main:<path>`; never check out, reset or edit the local Price Lab working tree (it holds unfinished branch work). Do not import Electron, SQLite, sidecar IPC, licensing, installer code or `Job` persistence.
- **SIGNGUY-PRICING-ENGINE** is the single pricing formula authority; MVP supplies tenant data through its own adapters and never adds a second calculation engine. MVP is pinned to **0.1.0** (`backend/pricing_engine_package.lock.json`); Price Lab and Engine `main` are at **0.15.0** (2026-10-14). Upgrade only in milestone P1 with parity evidence; never recalculate historical quotes, orders, invoices or snapshots.
- Legacy donors (`SIGNGUY-AI-OS`, `signguyai_rebuild_version`, `signguy-ai-feb22`, `signguyai`) are read-only behavior references.

## Repository safety

Check `git status` before changing anything. Preserve untracked owner files and existing stashes. Never `reset --hard`, `clean`, force-push, or overwrite uncommitted work. Branch from current `origin/main`; one feature per branch/PR.

## Verification classes

- **Class A** — docs, labels, simple visuals: verify the exact surface; no general suites.
- **Class B** — forms, UI state, nonfinancial workflows: affected tests + browser smoke of the workflow.
- **Class C** — pricing, money, payments, billing/entitlements, tenant/auth, snapshots, migrations, deployment: focused correctness, tenant-boundary and compatibility tests, required CI, critical-path smoke.

No broad suites per commit, no reruns of unchanged failures, no repeated audits. Never report skipped or unrun tests as passing. Required CI and release gates are never waived for token savings.

## Optional subagents (read-only)

| Role | Claude Code | Codex | Use only when |
|---|---|---|---|
| Token Optimizer | `.claude/agents/token-optimizer.md` | `.codex/agents/token-optimizer.toml` | a large search/context task where savings exceed the delegation cost |
| Test Gatekeeper | `.claude/agents/test-gatekeeper.md` | `.codex/agents/test-gatekeeper.toml` | the minimum test scope for a change is genuinely unclear |
| Review Gatekeeper | `.claude/agents/review-gatekeeper.md` | `.codex/agents/review-gatekeeper.toml` | one focused review of a consequential completed change |

The primary agent can apply this guidance itself. Do not invoke all three by default or chain them. They never edit files, run tests, merge or deploy.

**RTK** is installed on the owner's machine; use the block above for compact command output, raw commands for debugging. Never invent savings figures (`rtk gain` measures them).

## Reporting

Brief plain English for a nondeveloper: `STATUS`, `WHAT WORKS (verified)`, `WHAT DOES NOT`, `NEXT FEATURE`, `RISKS / OWNER DECISIONS`, `PR + TEST STATUS`. No command diaries.
