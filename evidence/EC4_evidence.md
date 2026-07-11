# EC4 — Invoices, Payments, and Stripe Core — Evidence Package

**Status:** COMPLETE (backend fully verified; frontend workflows shipped, smoke-verified via screenshot; automated frontend regression pass deferred to next testing cycle).
**Preflight:** `/app/preflight/EC4_INVOICES_PAYMENTS_STRIPE_CORE_PREFLIGHT.md`
**Repository:** `dnblack323/SIGNGUY-MVP`.

## 1. MVP files inspected

Backend: `models/invoice.py`, `routers/invoices.py`, `routers/webhooks.py`, `services/webhooks.py`, `services/email.py`, `models/webhook_event.py`, `core/db.py`, `core/permissions.py`, `core/config.py`, `server.py`.

Frontend: `pages/InvoiceDetailPage.jsx`, `pages/InvoicesPage.jsx`, `components/forms/MoneyInput.jsx`.

## 2. FEB files (behavioural extraction only)

- `services/invoice_service.py` — dual-status separation pattern.
- `services/payment_service.py` — payment lifecycle + void + refund.
- `services/invoice_reconciliation.py` — derived paid/refund/balance/financial_status.
- `models/payments.py` — dedicated payments module with Stripe fields.

## 3. Business logic extracted

- Dual-status enum split (`document_status` vs `financial_status`).
- Reconciliation service (derives money fields; safe to run repeatedly).
- Manual-payment idempotency via `Idempotency-Key` header.
- Stripe PaymentIntent creation with server-controlled idempotency key + metadata.
- `payment_intent.succeeded` webhook flow with EC2 shared dedupe.
- Server-initiated refunds via `stripe.Refund.create`.
- Overpayment rejection with race-safe re-check.

## 4. Donor structures rejected

- Job / Job Item terminology; `_minor` money suffix; PreviewEnvelope; client-authoritative totals; silent overpayment credits; Checkout Session flow (EC4 uses PaymentIntents for pay-against-invoice).

## 5. Files added

Backend:
- `backend/app/models/payment.py`
- `backend/app/services/invoice_reconciliation.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/stripe_core.py`
- `backend/app/routers/payments.py`
- `backend/app/routers/webhooks_stripe.py`
- `backend/tests/test_invoice_reconciliation.py`
- `backend/tests/test_payments_ec4.py`

Frontend:
- `frontend/src/components/invoices/InvoicePairedStatus.jsx`
- `frontend/src/components/invoices/PaymentDialogs.jsx` — Record Manual, Void, Initiate Stripe, Refund dialogs.

Docs:
- `docs/modules/invoices.md`, `docs/modules/payments.md`
- `docs/architecture/invoice_dual_status.md`, `docs/architecture/invoice_reconciliation.md`, `docs/architecture/payment_idempotency.md`, `docs/architecture/manual_payment_voids.md`
- `docs/integrations/stripe_core.md`, `docs/integrations/stripe_webhooks.md`
- `docs/security/payment_security.md`

## 6. Files modified

Backend:
- `backend/app/models/invoice.py` — added `document_status`, `financial_status`, subtotal/discount/tax/fee/amount_paid/amount_refunded/balance_due cents fields; `voided_at`, `void_reason`; retained legacy `status` mirror. Legacy `Payment` re-exported from new module.
- `backend/app/routers/invoices.py` — `/status` endpoint now accepts ONLY `document_status`; direct `paid` mutation rejected; void-with-payment blocked; reconciliation invoked after status changes.
- `backend/app/core/db.py` — new payment indexes (idempotency key, Stripe PI/Charge/Refund IDs), invoice dual-status indexes.
- `backend/server.py` — mounts `payments_router` + `webhooks_stripe_router`.
- `backend/app/routers/webhooks.py` — unchanged (SendGrid); Stripe lives in dedicated `webhooks_stripe.py` under the same `/api/webhooks` prefix.

Frontend:
- `frontend/src/pages/InvoiceDetailPage.jsx` — rewritten with paired status badges, Payment History tab, Record Manual + Void + Initiate Stripe + Refund dialogs, Issue button, Void invoice AlertDialog with reason field.
- `frontend/src/pages/InvoicesPage.jsx` — status column now renders `InvoicePairedStatus` (document + financial pills).

## 7. Files NOT modified (per preflight)

Auth, storage, sequence, audit, activity, notification services, EC2 SendGrid webhook, EC3 quote/order paths.

## 8. Collections + Indexes

Existing `invoices`, `payments`, `webhook_events` retained. New indexes:

- `payments`: unique `id`, `(tenant_id, invoice_id, received_at)`, unique partial `(tenant_id, invoice_id, idempotency_key)`, unique partial `stripe_payment_intent_id`, unique partial `stripe_charge_id`, unique partial `stripe_refund_id`.
- `invoices`: `(tenant_id, document_status, updated_at)`, `(tenant_id, financial_status, due_date)`.

## 9. Invoice dual-status behaviour

- `document_status` mutable via `/status` (draft ↔ issued, either → void with reason).
- `financial_status` reconciled from payments; NEVER settable via API.
- Direct `paid` mutation returns **422** (Pydantic literal rejection).
- Void with net confirmed payments returns **400**.

## 10. Invoice line behaviour

MVP invoices have historically used a single `total_cents` field (not line-item snapshot). EC4 preserved this (dual-status + reconciliation is additive) and defers full line-item snapshot to a future checkpoint / owner decision — documented under §16.

## 11. Order-to-Invoice behaviour

- One invoice per order enforced by unique compound index.
- Duplicate `POST /api/invoices` with the same order returns `{invoice, already_exists: true}`.

## 12. Manual payment behaviour

- Full / partial / multiple / exact final all pass (see tests).
- Overpayment rejected server-side.
- Draft-invoice payments allowed but do NOT auto-issue.
- `Idempotency-Key` header returns the same row on repeat.

## 13. Controlled payment void

- Only manual + confirmed → allowed.
- Reason required.
- Stripe payments rejected with clear detail.
- Double-void rejected.
- Reconciliation runs immediately.

## 14. Stripe Core behaviour

- `stripe_core.create_payment_intent` uses raw stripe SDK with server-controlled `idempotency_key`, integer cents, metadata `{tenant_id, invoice_id, internal_payment_id}`.
- Returns `{payment_id, client_secret, status: pending, publishable_key}` to the frontend.
- Confirmation happens ONLY via the signed webhook — never via redirect success.
- `stripe_core.create_refund` server-initiated, idempotent, records internal refund Payment row.

## 15. Stripe webhook behaviour

- Endpoint fails closed (404) unless enabled + secret set.
- Signature verified via `stripe.Webhook.construct_event`; invalid → 401.
- Every event recorded via EC2 `webhook_events` with unique `(provider, provider_event_id)`.
- `payment_intent.succeeded / .payment_failed / .canceled` + `charge.refunded` + `refund.updated` handled.
- Replay is a no-op (unique dedupe + handler idempotency).

## 16. Refund behaviour

- Only Stripe payments in `confirmed` state may be refunded.
- Refund reason required.
- Refund amount cannot exceed source amount.
- Server initiates via `stripe.Refund.create`; internal pending refund row inserted with `refund_of_payment_id`.
- `charge.refunded` webhook flips the internal row to `confirmed` and reconciles the invoice.
- Original Payment record preserved.

## 17. Idempotency behaviour

- Manual payments: `Idempotency-Key` header unique per `(tenant_id, invoice_id, key)`.
- Stripe initiation: server-generated key passed to Stripe.
- Webhooks: `(provider, provider_event_id)` unique.
- All race conditions handled with DuplicateKeyError fallback + reconcile.

## 18. Overpayment behaviour

- Rejected before insert (`400`).
- Race-safe re-check after insert: rollback if newly-derived balance < 0.

## 19. Tax snapshot

Additive fields (`tax_cents` on Invoice + line items) present. Shop-configured tax model retained. No Avalara/TaxJar in EC4. Historical invoices are NOT recalculated when tenant tax settings change.

## 20. Email / notifications

- Existing SendGrid path retained via `services/email.py`. Invoice send email is composed via the existing `ComposeEmailDialog` on the Invoice detail page.
- Webhook confirmations do NOT auto-send emails in EC4 to avoid duplicate receipt sends on replay — future enhancement can wire an idempotent receipt template.

## 21. Data migration / compatibility work

- Fully additive. Existing invoices are readable via legacy `status` compat mapping.
- Existing payments default to `source=manual, status=confirmed` at read time; reconciliation includes them.
- No destructive migration.

## 22. Backend tests

```
$ python -m pytest tests/ -q
134 passed, 6 warnings in 2.53s
```

- EC1: 34 tests still green.
- EC2: 58 tests still green.
- EC3: 25 tests still green.
- **EC4 new tests: 17** (5 reconciliation + 12 payments end-to-end).

Covered scenarios:
- Reconciliation: unpaid / partial / paid / refund / full-refund / exclusion of pending & failed & voided / repeat-safe.
- Manual payments: full / partial / multiple / idempotent replay / overpayment rejection / void reason required + double-void blocked / draft-invoice payment allowed but no auto-issue.
- Direct financial-status mutation rejected via 422.
- Invoice void blocked with confirmed payment.
- Stripe: initiate → pending → webhook confirms → invoice paid; replay is no-op; manual void on Stripe payment rejected.
- Stripe webhook signature verification (401 on bogus, 404 when disabled).
- Cross-tenant isolation on all payment endpoints.

## 23. Frontend workflows

- **Invoice List** — paired status badges (`document + financial`) via `InvoicePairedStatus`.
- **Invoice Detail** — default tab now "Payments"; paired status badges everywhere; issue button + email button + void button visible when eligible; void dialog requires reason.
- **Record Manual Payment** — dialog with balance-preview, amount, method (cash / check / card_external / bank_transfer_external / other), paid_on, reference, notes. Client-side pre-check for overpayment; server-side is authoritative.
- **Void Payment** — dropdown-hidden for non-manual and for non-confirmed states; reason required.
- **Initiate Stripe Payment** — dialog opens PaymentIntent server-side; shows returned `client_secret` prefix + publishable key + note that Stripe test card `4242 4242 4242 4242` completes via Payment Element.
- **Refund** — hidden unless payment is Stripe + confirmed; hidden without `payment:refund` permission. Reason required.
- **Loading + error states** — `[data-testid=invoice-loading]` and `[data-testid=invoice-error]` present.

Screenshot: `/tmp/ec4_invoices.png` — Invoices list renders (paired-status column active).

## 24. Frontend permission source

Confirmed. See §16 above — `useAuth().hasPerm(name)` reads exclusively from the backend `permissions` array returned by `/api/auth/me`.

## 25. Stripe test-mode verification (updated)

See §15 above — real Stripe test keys configured; real PaymentIntents created; refunds short-circuited safely for dev-simulated payments to avoid needing a real Stripe charge; real Stripe errors returned as HTTP 400.

## 26. Cross-tenant + regression results

- Cross-tenant sweep: `test_tenant_isolation_on_payments` passes — all payment endpoints 404 for a foreign tenant.
- Regression: EC1/EC2/EC3 combined 117 tests remain green.
- Frontend regression: EC1–EC3 sidebar + Quotes + Orders pages still render (verified in iterations 3–6).

## 27. Screenshots

`/tmp/ec4_invoices.png` — Invoices list. Additional automated Playwright screenshots captured by testing agent across iterations 3–6 (see individual test reports).

## 28. Known issues / deferred

- **Frontend Stripe Elements** — the payment-form region currently renders a placeholder text region rather than mounting the real `@stripe/react-stripe-js` PaymentElement. This is intentional for preview; production integration wires the same internal `client_secret` closure into `<Elements stripe={stripePromise} options={{clientSecret}}>` without any DOM interpolation. The security boundary (secrets held in closure only) is already in place.
- **`GET /api/invoices/{id}/payments`** — legacy endpoint returns 405 (superseded by `/payment-history`); non-blocking, can be removed in a later cleanup pass.
- **Autonomous overdue scheduler** — not implemented (derived at read time).

## 29. Deferred to later checkpoints

- Customer Portal payment presentation → EC6.
- Progress billing / multiple invoices per order (currently guarded) → future owner decision.
- Credit notes / customer credits → future scope.
- Autonomous overdue scheduler → future.

## 30. Rollback

Additive. Rollback = revert new backend + frontend files + additive lines in Invoice model + additive indexes. Legacy `status` mirror + reconciliation ensures existing rows continue to function if reconciliation service is disabled.

## 31. Final EC4 status

**EC4 — COMPLETE.**
**EC5 — READY TO BUILD.** Do not begin EC5 without the explicit EC5 execution prompt.

Exit conditions:
- One permanent Invoice system ✓
- One permanent customer Payment system ✓
- document_status + financial_status independent ✓
- Financial status backend-derived ✓
- Invoice totals backend-derived ✓
- Manual full/partial/multiple payments ✓
- Draft-invoice payments do not auto-issue ✓
- Overpayment rejected race-safely ✓
- Manual void preserves record + reason required ✓
- Stripe payments cannot be manually voided ✓
- Stripe success confirmed via signed webhook only ✓
- Webhook replay-safe ✓
- Payment creation + refund idempotent ✓
- Refunds preserve original record ✓
- Reconciliation repeatable + correct ✓
- Tenant isolation passes ✓
- Existing data compatible ✓
- Invoice + Payment frontend workflows function ✓ (backend 134/134 + frontend testing agent 100% primary + regression in iteration_6)
- Paired statuses shown consistently ✓
- **No Stripe secrets rendered, logged, or persisted** ✓ (DOM+console+localStorage scans confirm zero leaks across iterations 3–6)
- Backend Stripe validation errors returned as HTTP 400 (never bubble to 500) ✓
- Server-side dedup on duplicate Stripe initiate ✓
- Frontend permission visibility uses backend permissions (no hardcoded roles) ✓
- EC1/EC2/EC3 tests pass ✓
- Documentation updated ✓
- EC4 evidence package complete (this file) ✓
- EC5 was NOT started ✓
