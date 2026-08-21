# Pricing Engine v0.1.0 Consumer Cutover Evidence

**Date:** 2026-08-18

## Scope

This checkpoint moves SIGNGUY-MVP from the embedded `backend/pricing_engine` source package to the private released package `signguy-pricing-engine==0.1.0`.

No pricing formulas, defaults, fixtures, rounding, warnings, output contracts, or calculation behavior were changed. Price Lab work was not started.

## Starting State

- Starting commit: `770dcd040f8c95066682e0d903c8a6a868deb227`
- Source PR merged first: PR #31, merge commit `770dcd040f8c95066682e0d903c8a6a868deb227`
- Cutover branch: `codex/pricing-engine-v0.1.0-consumer-cutover-v2`
- Worktree: separate clean cutover worktree outside the original Webstore checkout
- Original Webstore checkout preserved on `codex/webstore-large-file-refactor`

## Engine Lock

- Engine repository: `dnblack323/SIGNGUY-PRICING-ENGINE`
- Engine release: `v0.1.0`
- Package: `signguy-pricing-engine==0.1.0`
- Source extraction commit: `0cd5908a34c92da59c141bb80f18628760900ed3`
- Wheel: `signguy_pricing_engine-0.1.0-py3-none-any.whl`
- SHA256: `E374C967CF45164F1C37910E03A29CF1D76C47D0414ACEB6240FB071BAF11106`

## Dependency Approach

The MVP records the private package pin in `backend/pricing_engine_package.lock.json`. The installer `backend/scripts/install_pricing_engine.py` downloads the release asset through the GitHub API, verifies the SHA256, installs the wheel, and fails if `pricing_engine` imports from the old embedded MVP source tree.

CI is wired to run the same installer before backend tests. GitHub Actions requires `PRICING_ENGINE_READ_TOKEN` with read-only Contents access to `dnblack323/SIGNGUY-PRICING-ENGINE`.

## Baseline Verification

Commands used `PYTHONPATH=backend`, `MONGO_URL=mongodb://localhost:27017`, and `DB_NAME=signguy_local`.

- Compile/import validation: passed
- Focused pricing baseline: `315 passed, 8 warnings`
- Full backend baseline: `1213 passed, 3 skipped, 265 warnings`

## Post-Cutover Verification

A fresh isolated `.venv` was created inside the cutover worktree. The workflow installed `backend/requirements.txt`, then installed the private engine with `backend/scripts/install_pricing_engine.py`.

- Installer proof: `signguy-pricing-engine==0.1.0`
- Import proof: `.venv\Lib\site-packages\pricing_engine\__init__.py`
- Embedded directory: `backend/pricing_engine` absent
- External-package guard test: `1 passed`
- Compile/import validation: passed
- Focused pricing/parity/regression suite: `350 passed, 8 warnings`
- Full backend suite run 1: `1214 passed, 3 skipped, 265 warnings`
- Full backend suite run 2: `1214 passed, 3 skipped, 265 warnings`
- `git diff --check`: passed
- Wheel file scan: no committed wheel files found
- Webstore diff scan: no Webstore files changed

The post-cutover full-suite count is baseline +1 because the branch adds `backend/tests/test_pricing_engine_external_package.py`.

## Secret Status

`gh secret list --repo dnblack323/SIGNGUY-MVP --app actions --json name,updatedAt` returned `[]`. `PRICING_ENGINE_READ_TOKEN` is missing, so CI backend installation is expected to wait on manual secret setup.

Required manual secret location:

`SIGNGUY-MVP -> Settings -> Secrets and variables -> Actions`

Required secret name:

`PRICING_ENGINE_READ_TOKEN`

Required minimum permissions:

Fine-grained GitHub token with read-only Contents access limited to `dnblack323/SIGNGUY-PRICING-ENGINE`.

## Rollback

Rollback is code-only: revert the consumer-cutover commit. That restores the embedded `backend/pricing_engine` package, removes the private package installer/lock/CI step, and returns imports to the embedded source package.
