# EC15 Wrap Lab Preflight and Implementation Plan

**Status:** PREFLIGHT COMPLETE - READY TO BUILD
**Date:** 2026-07-19
**Requested branch:** `CODEX-EC15-BRANCH`
**Actual branch:** `CODEX-ec15-branch`
**Starting HEAD:** `43fe2d20a362c199a737d4f5875c5a4aa7fdd5fe`
**Remote parity:** `origin/main` and `origin/CODEX-ec15-branch` both at `43fe2d20a362c199a737d4f5875c5a4aa7fdd5fe`
**EC14 closure ancestor:** `1af626b9e3a8bf622dd714066f074e25103f668b`
**Working tree at preflight start:** clean

## Authority

- Controlling specification: `specs_pack/extracted/EC15_Wrap_Lab_Master_Specification.docx`.
- Current source precedence: `memory/documentation_authority_register.md`.
- Checkpoint tracking: `memory/checkpoint_reference_table.md`, `memory/MASTER_CHECKPOINT_CHECKLIST.md`, and `memory/progress_register.md`.
- Owner authorization: the 2026-07-19 prompt authorizes EC15 continuation after EC14 and directs implementation through completion, stopping only for defined blockers.

## Owner Decisions Recorded

- EC15 is the next authoritative incomplete checkpoint after EC14.
- Customer-facing name is **Wrap Lab**; legacy "Wrap Command Center" remains historical only.
- Wrap Lab add-on pricing remains `$119/month` and `$1,190/year`.
- Wrap Lab standalone monthly remains `$139/month` provisional.
- Wrap Lab standalone annual remains not approved and unavailable; no placeholder or zero-priced annual standalone product may be created.
- EC15 may build shared-core runtime and commercial availability hooks, but must not start EC16-EC18 AI/provider execution, EC19, or later checkpoints.

## Existing Implementation Audit

- No canonical Wrap Lab backend module exists yet.
- Navigation already reserves a disabled Wrap Lab entry at `/wrap-lab` using `wrap_lab:read`.
- `backend/app/core/permissions.py` already declares `wrap_lab:read`, `wrap_lab:write`, and `wrap_lab:advance_stage`.
- EC9 owns vehicle graphics and wrap pricing through `backend/app/services/pricing_vehicle_graphics.py`; EC15 must reuse or reference those pricing outputs instead of creating a parallel pricing calculator.
- EC10 owns intake, visual markup, decision rooms, templates, proof-adjacent authoring, and document/signature primitives.
- EC11 owns production workflow, stage, and kiosk concepts.
- EC12 owns scheduling/calendar, tasks, messages, notes, community, and explicit Founder access.
- EC13 owns commercial billing catalog, billing runtime, subscriptions, entitlements, platform-fee contracts, and Stripe Billing boundaries.
- EC14 owns Webstores, public storefront commerce, Stripe Connect boundary records, Webstore ledgers, and Webstore-to-order bridging.

## EC15 Scope

EC15 implements the tenant-scoped Wrap Lab shared core:

- Vehicle and customer-linked project records.
- Coverage and measurement plans by vehicle panel.
- Estimate, quote, order, and work-order references without mutating EC4 invoices/payments or creating duplicate quote/order systems.
- Contract/deposit boundary references without Checkout Sessions, billing portal, or live payment processing.
- Pre-install inspection, damage logs, acknowledgements, signature references, and packet snapshots.
- Vector design scene contracts with layers, locks, grouping, vehicle templates, scale metadata, logo preservation, and preflight checks.
- Panel planning, bleed, seams, overlap, print-panel manifests, material/labor summaries, and export manifests.
- Production and installation scheduling records with optional EC12 calendar references.
- Pickup/completion packets, warranty/aftercare records, history, and reporting.
- Staff frontend workspace and project detail experience at `/wrap-lab`.
- Required indexes, audit/activity events, and targeted tests.

## Explicitly Out of Scope

- EC16-EC18 live AI gateway, AI credits, provider execution, generated image billing, model selection, cost ledger, or vision/VIN/provider lookup calls.
- EC19 onboarding/help/documentation work.
- Live Stripe API calls, Checkout Sessions, subscription changes, Billing Portal sessions, Stripe webhooks, or Webstore payout changes.
- EC4 customer invoice/payment mutations.
- New commercial price seeding beyond already owner-approved EC13 catalog authority.
- Public standalone purchase flow for Wrap Lab.
- Duplicate customer, quote, order, invoice, payment, document, storage, signature, production, scheduling, entitlement, or Webstore systems.

## Canonical Entities

- `WrapVehicle`: tenant-scoped vehicle profile with customer linkage, year/make/model/trim/VIN/license/color/type, dimensions, photos, and template linkage.
- `WrapProject`: tenant-scoped job hub linked to customer, vehicle, and optional intake/quote/order/work-order records.
- `WrapCoveragePlan`: panel-level coverage, measurements, status, square footage, and installer progress.
- `WrapInspection`: pre-install or completion inspection with damage pins, damage log rows, acknowledgements, signature references, and media references.
- `WrapDesignScene`: vector layout contract with vehicle template, artboard scale, layers, locked smart-object asset references, groups, and design status.
- `WrapPanelPlan`: production geometry contract with panel split, bleed, seam, overlap, printer width, material usage, and export manifest.
- `WrapPacket`: generated packet snapshot for pre-install, work-order, completion, warranty, or aftercare packet layouts.
- `WrapSchedule`: production/install schedule reference with assignee, start/end, location, and optional EC12 calendar event reference.
- `WrapWarranty`: warranty and aftercare contract with coverage terms, expiration, care instructions, and issue references.
- `WrapActivity`: module-scoped activity trail mirrored into the global audit/activity service.

## Lifecycle Contracts

- Project statuses: `lead_intake`, `vehicle_recorded`, `measurement_planning`, `estimate_ready`, `quote_linked`, `contract_deposit_pending`, `pre_install_ready`, `pre_install_signed`, `design_in_progress`, `proof_ready`, `proof_approved`, `panel_plan_ready`, `production_ready`, `install_scheduled`, `installing`, `completion_packet_ready`, `completed`, `warranty_active`, `archived`.
- Normal status advancement requires `wrap_lab:advance_stage`; ordinary edits require `wrap_lab:write`; reads require `wrap_lab:read`.
- Archived projects are read-only except audit-preserving administrative notes.
- Packet snapshots are immutable after generation; changes create a new packet revision.
- Original uploaded logo/assets are referenced by file id/URL and must not be redrawn, substituted, or silently rasterized.
- Locked layers cannot be edited until unlocked by an authorized staff actor.
- Money summaries use integer cents only.
- Inactive/unavailable commercial products cannot be purchased; EC15 does not publish or sell standalone Wrap Lab access.

## Tenant, Permission, and Audit Rules

- Every repository read/write filters by `tenant_id`.
- Staff APIs use `get_current_user`; portal tokens cannot satisfy staff routes.
- Owner/admin roles can mutate and advance; staff can only use permissions actually granted by role maps.
- Cross-tenant IDs return not found or forbidden without leaking data.
- Every write records module activity and global audit through `record_activity_with_audit`.
- Manual exception records require actor, reason, timestamp, and linked entity id.

## Shared-Core Reuse Proof for H6

Standalone Wrap Lab activation remains unavailable commercially, but the EC15 architecture is a shared core that can later serve Core add-on, Complete Bundle, Founder-included, and standalone product entitlements without separate code paths. Runtime records stay independent from purchase source and may store only optional commercial entitlement/product references for future EC13-driven access derivation.

This satisfies the EC15 preflight requirement to prove shared-core reuse without duplication. It does not approve standalone annual pricing or create a public standalone purchase flow.

## Stripe and Commercial Boundaries

- EC15 does not import Stripe, call Stripe APIs, or create Checkout Sessions.
- EC15 stores only local references to EC13 commercial entitlement/product state when needed.
- EC13 remains the owner of subscription, entitlement derivation, dunning, trial, and setup-package billing.
- EC14 remains the owner of Webstore buyer commerce and Stripe Connect boundary records.

## Implementation Phases

1. Backend contracts: add `wrap_lab` Pydantic models, repositories, service, and staff router.
2. Indexes: register tenant-scoped indexes in `backend/app/core/db.py`.
3. Route wiring: include the Wrap Lab router in `backend/server.py`.
4. Frontend runtime: add API client helpers, `/wrap-lab` list/detail pages, vector/design and packet surfaces, and enable navigation.
5. Tests: add targeted backend tests for permissions, tenant isolation, lifecycle gates, immutability, integer cents, packet snapshots, vector preservation, scheduling, and boundary protection.
6. Documentation: add EC15 module contract and completion evidence.
7. Validation: run directly affected tests, compile checks, frontend build, `git diff --check`, push, wait for GitHub CI, and fix failures.

## Required Indexes

- `wrap_vehicles`: unique `id`; `tenant_id/customer_id`; sparse `tenant_id/vin`; sparse `tenant_id/license_plate`; `tenant_id/updated_at`.
- `wrap_projects`: unique `id`; `tenant_id/status/updated_at`; `tenant_id/customer_id/updated_at`; `tenant_id/vehicle_id`; sparse `tenant_id/order_id`; sparse `tenant_id/quote_id`; sparse `tenant_id/work_order_id`.
- `wrap_coverage_plans`: unique `id`; `tenant_id/project_id`; `tenant_id/project_id/status`.
- `wrap_inspections`: unique `id`; `tenant_id/project_id/inspection_type`; `tenant_id/project_id/status`.
- `wrap_design_scenes`: unique `id`; `tenant_id/project_id/status`; `tenant_id/project_id/revision`.
- `wrap_panel_plans`: unique `id`; `tenant_id/project_id/status`; `tenant_id/project_id/revision`.
- `wrap_packets`: unique `id`; `tenant_id/project_id/packet_type/revision`; `tenant_id/project_id/status`.
- `wrap_schedules`: unique `id`; `tenant_id/project_id/schedule_type`; `tenant_id/start_at`; sparse `tenant_id/calendar_event_id`.
- `wrap_warranties`: unique `id`; `tenant_id/project_id/status`; `tenant_id/expires_at`.
- `wrap_activity_events`: unique `id`; `tenant_id/project_id/created_at`; `tenant_id/action/created_at`.

## Required Tests

- Staff permission and portal-token rejection.
- Tenant isolation for primary reads and writes.
- Vehicle/project create/list/detail lifecycle.
- Status advancement gates and blocked invalid transitions.
- Integer-cent enforcement for material, labor, estimate, deposit, and warranty cost fields.
- Packet snapshot revision immutability.
- Locked vector layer edit rejection and original logo reference preservation.
- Panel planning geometry and export-manifest contract.
- Schedule creation with local EC12 calendar-event reference boundary.
- Completion packet and warranty/aftercare creation.
- No EC4 invoice/payment mutations.
- No EC13 entitlement mutations.
- No EC14 Webstore payout or buyer-order mutations.

## Exact Files Expected to Change

- `backend/app/models/wrap_lab.py`
- `backend/app/repositories/wrap_lab.py`
- `backend/app/services/wrap_lab.py`
- `backend/app/routers/wrap_lab.py`
- `backend/app/core/db.py`
- `backend/server.py`
- `backend/tests/test_ec15_wrap_lab.py`
- `frontend/src/lib/wrapLab.js`
- `frontend/src/pages/WrapLabPage.jsx`
- `frontend/src/pages/WrapLabDetailPage.jsx`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`
- `docs/modules/ec15_wrap_lab.md`
- `evidence/EC15_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

## Risks and Controls

- The EC15 spec includes future AI examples. Control: implement provider-neutral contracts and manual workflows only.
- Vector export depth can sprawl into a full production RIP/CAD system. Control: implement durable scene/panel/export contracts and MVP UI, not provider-grade CMYK/PDF generation.
- Wrap Lab touches quote/order/work-order/payment concepts. Control: store references and snapshots only; use existing modules for authoritative mutations.
- H6 standalone activation could be misread as commercial launch. Control: document shared-core readiness only; standalone sale remains unavailable until later approval.

## Preflight Result

EC15 is authorized, scoped, and ready to build. No implementation occurred during this preflight document update.
