# Record Numbering Checkpoint Preflight and Implementation Plan

Date: 2026-07-27
Branch: `main`
Starting commit: `90bfbe2c07590c0b339d0ef2cd2dac700010a3e8`
Remote gate: local `main` matched `origin/main` before implementation.

## Authorized Scope

This checkpoint implements one backend-authoritative, tenant-scoped record-numbering system and integrates it only with currently implemented business records.

Explicit exclusions:

- No Control Center numbering settings UI.
- No Platform Administration surfaces.
- No unrelated feature development.
- No pricing formula, Quote/Order business-rule, Work Order lifecycle, Webstore payout, Wrap Lab workflow, authentication, or tenant-permission redesign.
- No "job ticket" terminology.
- No commit, push, merge, pull request, or next checkpoint.

## Owner Decisions Used

- Existing approved visible numbering conventions are preserved where already present, including numeric `number` fields displayed with established prefixes such as `Q-`, `O-`, `I-`, and `W-`.
- Where no owner-approved display format exists, the checkpoint uses neutral backend defaults only as immutable allocation snapshots. These do not expose a Control Center UI or lock the future owner-facing format.
- Deleted, archived, voided, failed, or abandoned records do not authorize number reuse. Gaps are permitted when a number was allocated before a downstream failure.
- Internal database ids remain separate from customer-facing record numbers.

## Numbering Inventory

| Record type | Existing implementation | Checkpoint decision |
|---|---|---|
| Quotes | `quotes.number` via atomic `next_number(..., "quote")`; unique tenant+number index exists | Already handled; now records canonical allocation evidence through shared service |
| Orders | `orders.number` via atomic order sequence in direct create, quote conversion, and webstore bridge; unique tenant+number index exists | Already handled; now records canonical allocation evidence through shared service |
| Invoices | `invoices.number` via atomic invoice sequence; unique tenant+number index exists | Already handled; now records canonical allocation evidence through shared service |
| Payments | Implemented EC4 payment records lacked business-facing number | Integrated now with `number` and `record_number_type="payment"` |
| Refunds | Implemented as EC4 `payments` refund rows without a distinct business-facing number | Integrated now with `number` and `record_number_type="refund"` |
| Credits / credit memos | No separate implemented credit memo model found | Deferred until a credit-memo feature checkpoint exists |
| Work Orders / production | `work_orders.number` via atomic work order sequence; unique tenant+number index exists | Already handled; now records canonical allocation evidence through shared service |
| Customers | Implemented customer records lacked business-facing number | Integrated now with optional `customers.number`; legacy rows remain readable |
| Webstore orders | Implemented `webstore_buyer_orders` lacked business-facing number | Integrated now with optional `webstore_buyer_orders.number` |
| Purchase orders | `purchase_orders.number` via atomic sequence and unique tenant+number index | Already handled; now records canonical allocation evidence through shared service |
| Expenses | `expenses.number` via atomic sequence and unique tenant+number index | Already handled; now records canonical allocation evidence through shared service |
| Proofs | `proofs.number` via atomic sequence and unique tenant+number index | Already handled; now records canonical allocation evidence through shared service |
| Signature requests | `signature_requests.number` via atomic sequence and unique tenant+number index | Already handled; now records canonical allocation evidence through shared service |
| Public quote requests | `quote_requests.number` via atomic sequence and unique tenant+number index | Already handled; now records canonical allocation evidence through shared service |
| Intake submissions | `intake_submissions.intake_number` via atomic sequence and unique tenant+intake_number index | Already handled; now records canonical allocation evidence through shared service |
| Order items | No independent customer-facing document number; line position and parent order are authoritative | Not applicable |

## Shared Design

The canonical service lives in `backend/app/services/sequence.py`.

Core entities:

- `RecordNumberConfig`: tenant-scoped future configuration contract for record type, prefix, starting number, minimum digit padding, suffix, date/year component, reset policy, max number, and active state.
- `RecordNumberAllocation`: immutable issuance/audit record containing tenant, record type, sequence name, numeric number, formatted number, status, idempotency key, target entity reference, actor, reason, context, and config snapshot.
- Existing `counters`: the database-authoritative atomic counter keyed by `(tenant_id, name)`.

Allocation method:

- Normalize the requested record type through a shared registry.
- Load tenant config or neutral default.
- Initialize the counter to `starting_number - 1` only if missing.
- Atomically increment using Mongo `find_one_and_update`.
- Insert one immutable allocation row with a unique `(tenant_id, record_type, number)` constraint.
- If an idempotency key is supplied, replay the exact existing allocation instead of consuming a new number.

## Tenant and Permission Model

- No public or tenant-facing sequence-management endpoint is exposed in this checkpoint.
- Number allocation happens only inside existing create flows after those flows pass their current backend permission and tenant checks.
- Record-specific update payloads do not include authoritative number fields; manual submit/alter attempts are ignored safely by existing Pydantic payload filtering or rejected by existing validation.
- Allocation, preview, and backfill service calls are tenant-id explicit and never query counters or records without tenant scope.
- Internal sequence state is not returned through customer-facing APIs.

## Gap and Reuse Policy

- Issued numbers are permanent.
- Deleted, archived, voided, failed, abandoned, or rolled-back records do not cause reuse.
- Gaps are acceptable when a number was issued before a downstream failure, including provider failure or uniqueness collision.
- Idempotent retries with the same key return the original allocation when available.

## Migration and Backfill

Legacy rows remain readable if they lack a newly introduced optional number field.

Backfill strategy:

- Preserve valid existing numbers.
- Detect duplicate or invalid existing numbers before assigning missing numbers.
- Advance the counter to at least the highest preserved number.
- Assign missing rows deterministically by `created_at`, then `id`.
- Use tenant-scoped updates and allocation rows.
- Do not automatically run backfill at startup.

## Required Indexes

- `counters`: unique `(tenant_id, name)`.
- `record_number_configs`: unique `id`; unique `(tenant_id, record_type)`.
- `record_number_allocations`: unique `id`; unique `(tenant_id, record_type, number)`; unique partial `(tenant_id, record_type, idempotency_key)`; lookup `(tenant_id, issued_to_entity_type, issued_to_entity_id)`.
- New optional-number constraints: partial unique customer and webstore-buyer-order `(tenant_id, number)` indexes for integer numbers only.
- Payment/refund constraints: partial unique `(tenant_id, record_number_type, number)` for integer numbered payment/refund rows.
- Existing quote, order, invoice, work order, purchase order, expense, proof, signature request, quote request, and intake submission unique numbering indexes are preserved.

## Verification Plan

- Focused record-numbering tests for concurrency, tenant isolation, record-type isolation, idempotency, preview/config, exhaustion, backfill, manual renumbering attempts, payment/refund numbers, and webstore buyer-order numbers.
- Relevant Quote, Order, Invoice, Payment, Refund, Work Order, Webstore, Purchase Order, and Expense regressions.
- Complete backend test suite.
- Complete frontend test suite and production build.
- Backend compile/import validation.
- `git diff --check`.
- Protected Banner calculator files unchanged.

## Status

Implementation completed locally for review. Do not mark this checkpoint closed until review and owner approval.
