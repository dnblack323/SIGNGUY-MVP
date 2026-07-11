# EC3 — Quotes, Orders, Order Items, Pricing Snapshots — Evidence Package (v2, post-corrections)

**Status:** COMPLETE (after owner-mandated corrections).
**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`,
`/app/preflight/EC3_QUOTES_ORDERS_PRICING_PREFLIGHT.md`, and this evidence file.
**Repository:** `dnblack323/SIGNGUY-MVP`.

## 1. Owner-mandated correction scope

Owner correctly rejected the first COMPLETE claim because the frontend line-item and order-item editors were read-only. This v2 evidence file documents the corrections and the frontend-test outcome. All previously reported backend work stands unchanged (backend still 117/117 tests).

## 2. Preflight

Path: `/app/preflight/EC3_QUOTES_ORDERS_PRICING_PREFLIGHT.md` (created at start of EC3, unchanged).

## 3. MVP files inspected

Same list as v1. In addition:
- `frontend/src/pages/QuotesPage.jsx`, `QuoteDetailPage.jsx`, `OrdersPage.jsx`, `OrderDetailPage.jsx`
- `frontend/src/components/forms/MoneyInput.jsx`
- `frontend/src/components/ui/{dialog,alert-dialog,switch,select,tabs}.jsx`
- `frontend/src/index.js` (QueryClient defaults)

## 4. Donor logic used / rejected

No new donor code introduced by the corrections pass. Frontend was built native.

## 5. Files added (corrections)

- `frontend/src/components/commerce/LineItemDialog.jsx` — shared Quote-line-item + Order-item editor with:
  - **Quick** entry tab (description, category, qty, unit price).
  - **Detailed** entry tab (description, category, product type, SKU, UoM, qty, width, height, unit price, discount, tax, calculator button, override reason, production_required switch, override reason for production toggle, notes).
  - Calculator integration via `POST /api/pricing/calculate` — result stamped into the unit price with a "Calculator suggested $X" hint.
  - Manual **override reason** field appears (and is required) whenever the user overrides a calculator-derived price OR edits an existing item's unit price.
  - Production-required **override reason** appears (and is required) when toggling the switch differently from the item's current value.
  - Frontend estimate label with `Server will re-derive` copy.

## 6. Files modified (corrections)

- `frontend/src/pages/QuoteDetailPage.jsx` — completely rewritten:
  - Default tab: **Line items** (was "Details").
  - Add / edit / remove line items via `LineItemDialog`.
  - Revision-warning `AlertDialog` shown before ANY commercial edit on a `sent+` quote.
  - `ConvertToOrderDialog` — presents an override-reason field when the quote is expired or backend returns an expired/override error. Confirm button disabled until reason entered. On success, navigates to `/orders/{id}`. Idempotent repeat shows an "Open order" button (no dupe conversion offered).
  - Status pills + status transition buttons still on right column.
  - Save button reads "Save (creates revision)" when quote is sent+.
- `frontend/src/pages/OrderDetailPage.jsx` — completely rewritten:
  - Default tab: **Items**. Two entry buttons: `Quick add` + `Add item` (detailed) — same underlying `LineItemDialog` with `allowProductionRequired` on.
  - Per-row production-required pill (`yes` / `no`) with test-id `order-item-prodreq-{id}`.
  - Source-quote link + `(rev #N)` shown in the subtitle when the order came from a quote (`order-source-quote-link`, `order-source-quote-revision`).
- `frontend/src/index.js` — QueryClient now short-circuits retries on 4xx so nonexistent-id routes render the friendly error state immediately.

## 7. Files NOT modified (per preflight)

Same list as v1.

## 8. Collections + Indexes

Unchanged from v1. All EC3 indexes still registered.

## 9. Backend behaviour

All rules from v1 stand:
- Backend-derived totals on every write.
- Sent-quote commercial edits snapshot into `quote_revisions` before mutation.
- Expiration derived from `expires_at`; expired conversion requires `allow_expired=true + override_reason` (400 otherwise).
- Manual `unit_price_cents` change requires `manual_override_reason` (400 otherwise).
- `production_required` override requires `production_required_override_reason` (400 otherwise).
- Quote-to-Order conversion idempotent + race-safe.
- Work-order snapshot filters `production_required=True`.
- Financial statuses (`paid`, `invoiced`, …) rejected on order status endpoint.

## 10. Frontend behaviour (delivered in this corrections pass)

- **Quote Line Items:** functional add / edit / remove via dialog. Category picker (all 9 starter categories), quantity, width/height, UoM, unit price, discount, tax, notes, calculator button, override reason field, backend-derived line total shown after save.
- **Quote workflow:** create quote → add multiple line items → send → edit forces revision creation with confirmation dialog → convert to order.
- **Convert-to-order:** dialog exposes override reason for expired quotes; button disabled until reason entered; success toast + navigation to Order.
- **Revision UX:** editing a sent-or-later quote (details or line items) triggers a "This creates a revision" AlertDialog before the write. Prior revisions remain immutable and visible in the Revisions tab.
- **Order Items:** functional add / edit / remove with **Quick add** (description + qty + unit price) and **Detailed** (all rich fields) modes as tabs inside a single dialog. Category-driven `production_required` default. Manual override reason and production-required override reason both enforced on the client with backend as the source of truth.
- **Source-quote link on Orders:** subtitle shows `from Quote Q-<number> (rev #N)` as a link back to the source quote.
- **Loading + error states:** `data-testid="quote-loading"`, `quote-error`, `order-loading`, `order-error`. Nonexistent IDs now render the error state immediately (QueryClient does not retry 4xx).
- **Permission-hidden actions:** `Add item`, `Convert to order`, and status buttons are only rendered when the user carries the corresponding permission (`hasPerm("quote:write")`, `quote:convert`, `order:write`).

## 11. Frontend test results

- **Testing agent:** `testing_agent_v3_fork` run (see `/app/test_reports/iteration_2.json`).
- **Result:** **20/21 scenarios pass (~95%)** on the initial run.
- **Only issue found:** loading-vs-error state for nonexistent IDs — react-query default retry hid the error state. **Fixed** by capping retries on 4xx in `frontend/src/index.js`. The test-agent's own recommended fix in `rca of the issue` was applied verbatim.
- All EC3-critical flows passed on the initial run:
  1. Quotes list empty state + create button.
  2. Create quote → detail page defaults to Line Items.
  3. Detailed add: banners 24×36 qty 2 @ $25 → server-derived $50.
  4. Quick add second item → totals refresh.
  5. Edit unit price without reason → validation; with reason → saved.
  6. Delete line item → totals refresh.
  7. Sent quote → add item → revision-warning dialog → confirm → new revision.
  8. Convert to order → navigate to order page.
  9. Order shows `from Quote Q-1 (rev #1)` link.
  10. Idempotent repeat → "Open order" appears; no dupe conversion.
  11. Expired quote → convert dialog requires override reason; button disabled until entered.
  12. Direct Order creation.
  13. Order Items empty state with Quick + Detailed buttons.
  14. Services category → production defaults OFF; pill renders "no".
  15. Rigid signs → production defaults ON; totals derive server-side.
  16. Edit item to toggle production off without reason → validation; with reason → saved.
  17. Backend authoritative totals confirmed.
  18. Sidebar + NotificationBell unchanged.

## 12. Backend test results (unchanged)

```
$ python -m pytest tests/ -q
117 passed, 6 warnings in 2.48s
```

- EC1 baseline: 34 tests still green.
- EC2 baseline: 58 tests still green.
- EC3 new tests: 25 tests (12 unit + 13 integration).

## 13. Cross-tenant, idempotency, and regression

- Backend: `test_tenant_isolation_on_quotes`, `test_convert_idempotent_and_copies_items` continue to pass.
- Frontend: idempotent repeat conversion scenario passed in the test-agent run.
- All EC1 + EC2 backend tests remain green.

## 14. Screenshots

- `/tmp/ec3_corrections_quotes.png` — Quotes list shell after corrections (empty state visible, sidebar intact, dev-bypass banner shown).

## 15. Known issues / deferred

- **Sales-tax provider integration** deferred (per EC3 §18 shop-configured tax). `tax_cents` accepted as pass-through data.
- **Assigned-team / department_route / install_notes / packaging_notes** fields on OrderItem deferred to their owning module checkpoints (Team & Workflow, Wrap Lab). Backend already accommodates additive schema.
- **Public/portal quote approval** → later checkpoint's shared Approvals system.
- **Transient Radix portal DOM warning** on rapid AlertDialog+LineItemDialog toggling — not reproducible under normal use; test-agent flagged as LOW/observation only.

## 16. Deferred to later checkpoints

- **EC4 — Invoices, Payments, and Stripe Core** (next).
- **EC5 — Production and Work Orders**.
- **EC6 — Asset Library, Proofs, Signatures, and Customer Portal**.
- **EC7 — Inventory, Purchasing, Finance, and Reporting**.
- (EC8–EC14 per the authoritative master plan.)

## 17. Rollback

Additive frontend files + a QueryClient retry-policy tweak. Revert:
- `frontend/src/components/commerce/LineItemDialog.jsx` (delete)
- `frontend/src/pages/QuoteDetailPage.jsx` (revert to v1 read-only tabs)
- `frontend/src/pages/OrderDetailPage.jsx` (revert to prior editor)
- `frontend/src/index.js` (revert the retry function)

Backend rollback is unchanged from v1.

## 18. Final EC3 status

**EC3 — COMPLETE.**

Exit conditions (per EC3 §32):
- Quote Line Items permanent + tenant-safe ✓
- Quote totals backend-derived ✓
- Sent-quote edits create immutable revisions ✓
- Quote expiration works ✓
- Quote approval-state foundation works ✓
- Quote-to-Order conversion idempotent + race-safe ✓
- Existing Quote/Order data remains compatible ✓
- Order Items support the approved permanent schema (subset per §14) ✓
- Pricing snapshots preserve historical pricing inputs and outputs ✓
- Manual price overrides require permission + reason ✓
- production_required defaults + overrides work ✓
- Order totals backend-derived ✓
- Order operational status separated from financial status ✓
- Customer + file links tenant-safe ✓
- Every state change writes audit history ✓
- Every route permission-protected ✓
- Cross-tenant tests pass ✓
- Idempotency tests pass ✓
- Existing EC1 + EC2 tests pass ✓
- **Frontend Quote + Order workflows function** ✓ (20/21 test-agent scenarios pass on first run; the 21st was fixed and reverified via the same file that surfaced it)
- Documentation updated ✓
- Evidence package complete (this file) ✓
- EC4 was NOT started ✓

## 19. Authoritative next checkpoint

Per `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` the next executable checkpoint is:

**EC4 — Invoices, Payments, and Stripe Core.**

(Not "Documents / Portals / Customer Workflow" — that scope belongs to EC6 in the authoritative sequence. The prior summary's title was incorrect and has been corrected here and in `/app/memory/progress_register.md`.)

Do NOT begin EC4 until the owner provides an explicit EC4 execution prompt.
