# EC15 Wrap Lab Runtime Contracts

**Status:** COMPLETE - CLOSED
**Checkpoint:** EC15 Wrap Lab
**Primary route:** `/api/wrap-lab`
**Implementation commit:** `d67414907c48f83186d6f48cf2ccbda79f39f659`
**GitHub CI:** `29678805230` passed

## Boundaries

Wrap Lab is implemented as a tenant-scoped shared core for staff workflows. It does not implement EC16-EC18 AI/provider execution, AI credits, generated asset billing, live VIN/vision lookup, EC19 onboarding/help, live Stripe calls, Checkout Sessions, subscription changes, Billing Portal sessions, Stripe webhooks, EC4 invoice/payment mutations, or EC14 Webstore payout changes.

## Canonical Backend Collections

- `wrap_vehicles`
- `wrap_projects`
- `wrap_coverage_plans`
- `wrap_inspections`
- `wrap_design_scenes`
- `wrap_panel_plans`
- `wrap_packets`
- `wrap_schedules`
- `wrap_warranties`
- `wrap_activity_events`

Every collection is tenant-scoped. Repositories filter by `tenant_id` on reads and updates.

## Workflow Contracts

Wrap projects progress through:

`lead_intake -> vehicle_recorded -> measurement_planning -> estimate_ready -> quote_linked -> contract_deposit_pending -> pre_install_ready -> pre_install_signed -> design_in_progress -> proof_ready -> proof_approved -> panel_plan_ready -> production_ready -> install_scheduled -> installing -> completion_packet_ready -> completed -> warranty_active -> archived`

Normal advancement is one step at a time and requires `wrap_lab:advance_stage`. Archived projects are read-only.

## Vector and Logo Rules

- `wrap_design_scenes` store the production vector scene contract.
- Logo layers must preserve original `source_file_id`/asset identity.
- AI-generated logo replacement, font substitution, and silent redrawing are rejected by the preflight contract.
- Locked layers cannot be edited until explicitly unlocked by an authorized staff actor.
- Vehicle templates, scale, groups, artboard, and layer metadata are stored independently from any future AI/provider workflow.

## Packet Rules

`wrap_packets` are immutable generated snapshots. New packet generation creates a new revision rather than modifying an earlier packet. The layout contract preserves the EC15 binding packet structure: clean white card sections, strong headers, two-column summaries, coverage/damage tables, vehicle diagram area, checklist hierarchy, financial summary, proof/timeline blocks, and completion/warranty sections.

## Money Rules

All Wrap Lab money fields use integer cents:

- `estimate_total_cents`
- `deposit_required_cents`
- `material_estimate_cents`
- `labor_estimate_cents`
- `material_cost_cents`
- `labor_cost_cents`
- `warranty_value_cents`

EC15 does not create invoices, payments, checkout sessions, subscription rows, or Webstore buyer orders.

## Shared-Core Reuse

The runtime is independent of purchase source. It can later be entitled through Founder, Core add-on, Complete Bundle, or standalone commercial products without separate runtime systems. Standalone annual pricing remains unavailable and no public standalone purchase flow is implemented in EC15.

## Permission Rules

- Reads require `wrap_lab:read`.
- Writes require `wrap_lab:write`.
- Lifecycle advancement requires `wrap_lab:advance_stage`.
- Staff routes use the staff auth dependency, so portal tokens are rejected before route logic.
- Frontend permission checks only control visibility; backend enforcement is authoritative.

## Indexes

EC15 adds indexes for vehicle/customer lookup, project lifecycle queues, linked quote/order/work-order references, coverage/inspection/design/panel/packet/schedule/warranty project lookup, sparse VIN/calendar references, immutable revision identity, and activity feeds.
