# Pricing Engine Consumer

SIGNGUY-MVP consumes the shared private pricing engine as the pinned package `signguy-pricing-engine==0.1.0`.

## Current Lock

- Engine repository: `dnblack323/SIGNGUY-PRICING-ENGINE`
- Release tag: `v0.1.0`
- Source extraction commit: `0cd5908a34c92da59c141bb80f18628760900ed3`
- Wheel: `signguy_pricing_engine-0.1.0-py3-none-any.whl`
- SHA256: `E374C967CF45164F1C37910E03A29CF1D76C47D0414ACEB6240FB071BAF11106`
- Lock file: `backend/pricing_engine_package.lock.json`

## Local Installation

Authorized developers install normal backend dependencies first, then install the pinned private wheel:

```powershell
cd backend
python -m pip install -r requirements.txt
python scripts/install_pricing_engine.py
```

The installer downloads the release asset through the GitHub API, verifies the SHA256 from the lock file, installs the wheel, and confirms `pricing_engine` imports from the active environment instead of the MVP source tree.

For local use, either authenticate GitHub CLI as an account with read access to `dnblack323/SIGNGUY-PRICING-ENGINE`, or set `PRICING_ENGINE_READ_TOKEN` for the current shell. Do not commit tokens, authenticated URLs, downloaded wheels, or local package copies.

## GitHub Actions

The backend CI job installs public backend dependencies, then runs:

```bash
python backend/scripts/install_pricing_engine.py
```

CI requires an Actions secret named `PRICING_ENGINE_READ_TOKEN` on `dnblack323/SIGNGUY-MVP`. The token must be a fine-grained GitHub token with read-only Contents access limited to the private `dnblack323/SIGNGUY-PRICING-ENGINE` repository.

## Updating the Engine

Pricing behavior changes must be made in `dnblack323/SIGNGUY-PRICING-ENGINE` first, released as a new version, and then adopted here by updating `backend/pricing_engine_package.lock.json`.

For every future update:

1. Publish the new engine release and wheel from the engine repository.
2. Update the package version, tag, asset filename, source commit, and SHA256 in the lock file.
3. Run the installer in a clean environment and confirm import source is external.
4. Run the pricing parity/contract suites and full backend suite.
5. Do not update expected pricing fixtures to hide behavior drift.
