# Pricing Engine Extraction and Licensing Readiness

**Status:** PHASE 9I-V LICENSING READINESS GATE IMPLEMENTED - READY FOR REVIEW
**Date:** 2026-07-28

## Scope

This document records the Phase 9I-V readiness gate for the extracted pricing engine. It documents whether the current pricing engine can support a future owner-approved standalone/licensed calculator checkpoint.

Phase 9I-V is documentation and readiness evidence only. It does not implement license checks, activation keys, device registration, desktop packaging, installer behavior, code signing, updater behavior, Stripe automation, production portable import/apply/save, or standalone desktop UI.

## Current Extraction Boundary

Already implemented:

- Pure calculator package: `backend/pricing_engine/`.
- SaaS compatibility boundary: `backend/app/services/pricing_engine_adapter.py`.
- SaaS configuration boundary: `backend/app/services/pricing_engine_config_adapter.py`.
- Portable configuration contract: `backend/pricing_engine/config_export.py`.
- Test-only standalone adapter harness: `backend/tests/standalone_pricing_adapter_harness.py`.
- Versioned parity fixture pack: `backend/tests/fixtures/pricing_engine/`.

The pure calculator package remains isolated from FastAPI routers, request objects, authenticated users, tenant models, Mongo clients, persistence models, frontend code, Stripe, entitlements, license validation, network services, and environment-specific application configuration.

## Category Readiness

All nine pricing categories have passed the shared fixture and extraction parity gates:

- `banners`
- `rigid_signs`
- `cut_vinyl`
- `digital_print`
- `vehicle_graphics`
- `apparel`
- `promotional`
- `services`
- `custom`

Each category has verified parity across:

- Pure line engine execution.
- SaaS runtime/configuration adapter execution.
- Legacy SaaS cents-first compatibility adapter execution.
- Standalone portable adapter harness execution.

## Money and Result Contracts

Verified readiness:

- Fixed money uses integer cents.
- High-precision rates and non-currency decimals use Decimal strings with explicit units.
- Percent and margin fields use normalized contract fields such as basis points where established.
- Results preserve engine version, formula version, rounding policy, method evidence, warning evidence, normalized inputs, and category-specific details.
- The fixture pack is the cents authority for parity tests.
- Existing legacy dollar-float snapshots remain immutable/readable and are not rewritten.

## Digital Print Minimum Boundary

Already implemented:

- Digital Print line item minimum remains line-level evidence.
- Digital Print order minimum is applied once at Quote or Order document level.
- Visible Quote/Order order-minimum adjustment evidence was completed in Phase 9I-R.

Verified readiness:

- The standalone harness does not hardcode `$20`, `$40`, `2000`, or `4000`.
- Document-level minimum behavior remains separate from line formula execution.

## Portable Configuration Boundary

Already implemented:

- Portable configuration export is read-only.
- Import behavior is preview-only.
- The portable payload excludes tenant identity, Mongo IDs, user/email data, permissions, audits, entitlements, Stripe/license data, tokens, secrets, raw Mongo settings, and unresolved live references.

Future owner-approved work still required before a real standalone product:

- Decide how portable configuration is distributed to licensed installations.
- Decide whether a production apply/save path exists, and if so how it is authenticated, audited, versioned, and rolled back.
- Decide whether pricing configuration updates are manual file import, online sync, or both.

## Licensing Boundary

Owner-approved direction already recorded:

- Future standalone calculator licensing uses a hybrid model.
- Initial activation may be online.
- A signed local license or activation lease may be stored locally.
- Offline grace is allowed.
- Periodic online revalidation may occur when connectivity is available.
- A live internet connection must not be required for each calculation.
- License checks must not live inside pricing formulas.
- License type must not change calculated pricing results.
- License enforcement belongs in a future standalone application shell.

Out of scope for Phase 9I-V:

- License checks.
- Activation keys.
- Device registration.
- Keygen or another licensing vendor.
- Stripe annual automation.
- Desktop framework selection.
- Desktop packaging or installer behavior.
- Code signing, updater, publish, or download portal.

## Remaining Follow-Ups

Preserved follow-ups:

- Identifier-only Quote/Order item update/delete tenant-authorization audit remains open.
- EC7 inventory duplicate-key setup evidence remains open/informational.
- Cloudflare R2 remains unimplemented.
- Hosted staging deployment files remain unimplemented.
- Historical Emergent cleanup remains a separate checkpoint.

## Readiness Conclusion

The extraction work is ready for owner review as the basis for a future standalone/licensing checkpoint. Phase 9I-V does not authorize or implement the standalone product. After this readiness gate is reviewed and accepted, Phase 9I can be closed for pricing extraction and money normalization, while desktop productization and licensing remain future owner-approved work.
