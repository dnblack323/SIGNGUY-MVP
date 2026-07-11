# Quote Revisions (EC3)

Editing a **sent** (or later) quote's customer-visible commercial fields (job name, expiration, customer-facing notes, totals, or any line-item mutation) captures the pre-change state into `quote_revisions`, then bumps the quote's `revision_number`, then rolls all current `quote_line_items` forward to the new revision.

## Storage

`backend/app/models/quote_revision.py::QuoteRevision` — one row per (`tenant_id`, `quote_id`, `revision_number`). Enforced by a unique compound index.

Each revision captures:
- Header snapshot (job_name, notes_internal, notes_customer, expires_at).
- Full line items array (denormalized).
- Full totals (subtotal_cents, discount_cents, tax_cents, total_cents).
- Provenance (actor_user_id, actor_email, reason).

## Rules

- Draft edits do NOT create a revision.
- Once a quote reaches `sent`, ANY commercial mutation creates a revision.
- Revisions are immutable. `PATCH /revisions/{n}` is not exposed.
- `quotes.approved_revision`, `quotes.converted_revision` reference the exact revision they applied.
- Historical revisions remain readable via `GET /api/quotes/{id}/revisions[/{n}]`.

## Choice: separate collection vs embedded snapshots

We chose a **dedicated `quote_revisions` collection**. Rationale:
- Denormalized line items can be inspected directly without walking the quote row.
- Compound unique index guarantees per-quote monotonic revision numbers.
- Simple to add a later "compare revisions" UI.
