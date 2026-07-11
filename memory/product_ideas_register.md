# Product Ideas & Future Feature Register

This file holds product ideas that are **NOT** committed to any current execution checkpoint. Each idea listed here requires its own later scope decision, dependency review, and preflight before it enters the master plan.

Owner-approved rules:
- Do not schedule any idea from this file into an active checkpoint without explicit owner instruction.
- Do not implement an idea from this file as a "small side task" or as opening work of another checkpoint.
- Ideas here may accumulate without a size or priority limit — this is a backlog, not a plan.

---

## Reusable Quote and Order Templates

**Recorded:** 2026-02 — after EC3 corrections were accepted.
**Origin:** Suggestion floated during EC3 close-out. Owner declined to schedule it and directed it here.

**Purpose:**
- Save a Quote or an Order item bundle as a reusable template.
- Reuse common product mixes (e.g. "Real estate yard sign kit", "Vehicle door lettering pair", "Trade-show booth package").
- Reduce repetitive item entry for shops that ship the same product configurations frequently.
- Support future reorder and upsell analysis (which templates convert, which drive repeat business, etc.).

**Explicit non-status:**
- Not part of EC3.
- Not part of EC4 (Invoices, Payments, and Stripe Core).
- Not part of the opening work of EC5 (Production and Work Orders).
- Requires its own later scope decision and a full dependency review before any implementation is scheduled.

**Open questions to resolve at that later decision:**
- Where do templates live in the data model (own collection vs derived from a starred Quote/Order)?
- Do templates capture pricing snapshots (frozen prices) or re-price against current shop defaults on apply?
- Tenant scope vs shared "marketplace" templates?
- Permissions model — who can create / update / retire templates?
- Interaction with the Approvals + Portal work (EC6) and the Reporting work (EC7).

---

## Production Board Live Refresh

**Recorded:** 2026-02 — after EC5 frontend corrections were accepted.
**Origin:** Suggestion floated during EC5 close-out. Owner declined to schedule it and directed it here.

**Purpose:**
- Keep multiple production-floor screens synchronized.
- Refresh Work Order card positions, assignments, priorities, and statuses.
- Reduce stale board state across simultaneous users.

**Explicit non-status:**
- Not part of EC5.
- Not part of EC6.
- Not to be added as an EC5.1 increment or as opening work of any other checkpoint.
- Requires its own later scope decision, dependency review, and preflight before any implementation is scheduled.

**Future scope must decide:**
- polling versus WebSocket/SSE
- refresh interval
- conflict handling during drag-and-drop
- stale-card reconciliation
- notification behavior
- infrastructure and connection cost
- offline/reconnect behavior

---
