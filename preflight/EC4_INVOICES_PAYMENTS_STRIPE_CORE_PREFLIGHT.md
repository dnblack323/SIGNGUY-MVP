# EC4 — Invoices, Payments, and Stripe Core — PREFLIGHT

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`.
**Prerequisite:** EC0, EC1, EC2, EC3 — COMPLETE.
**Repository:** `dnblack323/SIGNGUY-MVP`.

## 1. MVP files inspected

Backend:
- `backend/app/models/invoice.py` — single `Invoice` + embedded `InvoiceLineItem` (unused) + `Payment` (embedded in the same module).
- `backend/app/routers/invoices.py` — `list / create-from-order / get / patch / status / add-payment`. Single ambiguous `status` field.
- `backend/app/routers/webhooks.py` — EC2 pattern, currently only SendGrid.
- `backend/app/services/webhooks.py` — shared `record_received / mark_verified / mark_processed / mark_failed / list_events`.
- `backend/app/services/email.py` — SendGrid wrapper.
- `backend/app/services/audit.py`, `services/activity.py`, `services/sequence.py`.
- `backend/app/models/webhook_event.py` — dedupe key `(provider, provider_event_id)`.
- `backend/app/core/db.py` — indexes.
- `backend/app/core/permissions.py` — invoice + payment perms already declared (`INVOICE_READ/WRITE/SEND/VOID`, `PAYMENT_READ/WRITE/VOID/REFUND`).
- `backend/app/core/config.py` — `stripe_api_key`, `stripe_writes_enabled`, `stripe_webhook_enabled`, `stripe_webhook_secret` env keys already scaffolded.

Frontend:
- `pages/InvoicesPage.jsx`, `pages/InvoiceDetailPage.jsx` — single-status badges, primitive payment list.

## 2. Existing MVP behaviour

- Invoice has ONE ambiguous `status` field mixing document + financial state (`draft, sent, viewed, partially_paid, paid, overdue, void`). This violates EC4 §8.
- Payments live in `payments` collection but no idempotency-key uniqueness, no Stripe fields, no void or refund lifecycle, no derived reconciliation service — reconciliation logic is inlined into `add_payment` router.
- `POST /api/invoices/{id}/payments` accepts a manual payment and derives a new `status` via `_derive_status_after_payment`. Overpayment is NOT rejected.
- Setting invoice status directly through `/status` is allowed for ANY of the enum values including `paid` — this bypasses the financial state boundary and is one of the EC4 primary bugs to fix.

## 3. FEB donor logic used (behavioural extraction only)

- `services/invoice_service.py` — dual-status separation pattern.
- `services/payment_service.py` — payment lifecycle (`pending / confirmed / voided / refunded`), void reason, Stripe-payment protection from manual void.
- `services/invoice_reconciliation.py` — derived amount_paid / balance_due / financial_status.
- `models/payments.py` — dedicated `payments.py` (separate from `invoice.py`) with Stripe fields.

**Reject from all donors:** Job terminology, `_minor` naming, preview/PreviewEnvelope, client-authoritative totals, autonomous refunds, silent overpayment credits.

## 4. Classification per donor element

| Element | Classification |
|---|---|
| FEB dual-status enum | COPY AND TARGETED REFACTOR |
| FEB `payment_service.record_manual / void_manual / initiate_stripe / apply_refund` | EXTRACT BUSINESS LOGIC AND REHOUSE |
| FEB `invoice_reconciliation.reconcile()` | EXTRACT BUSINESS LOGIC AND REHOUSE |
| FEB models/payments.py Stripe fields | COPY AND TARGETED REFACTOR |
| MVP `services/webhooks.record_received` | KEEP MVP (used for Stripe as well) |
| MVP `services/email.py` | KEEP MVP (used for receipts) |
| MVP `routers/invoices.add_payment` | REBUILD AGAINST MVP SERVICES (routes stay, logic moves to services) |
| MVP invoice single `status` | REBUILD AGAINST MVP SERVICES — split into `document_status` + `financial_status` with compat read-time mapping |
| Stripe Checkout Sessions playbook flow | REJECT (EC4 uses **Payment Intents** for pay-against-invoice, not catalog checkout) |

## 5. Schema differences + migration

| Field | MVP today | EC4 target | Migration |
|---|---|---|---|
| `Invoice.status` | mixed | keep as read-only compat mirror; new `document_status` + `financial_status` | additive; read-time derived when new fields missing |
| `Invoice.document_status` | — | `draft / issued / void` | additive |
| `Invoice.financial_status` | — | `unpaid / partial / paid / refunded / voided` | derived by reconciliation on every write |
| `Invoice.subtotal/discount/tax/fee_cents` | — | new int cents | additive; default from `total_cents` |
| `Invoice.amount_paid_cents / amount_refunded_cents / balance_due_cents` | derived | now stored (derived by reconciliation) | additive |
| `Invoice.issued_at / voided_at / void_reason` | — | new | additive |
| `Payment.status` | — | `pending / confirmed / voided / refunded / partially_refunded / failed` | additive; existing payments default to `confirmed` |
| `Payment.source` | — | `manual / stripe` | additive; existing → `manual` |
| `Payment.stripe_payment_intent_id / stripe_charge_id / stripe_refund_id` | — | new | additive |
| `Payment.voided_at / void_reason / voided_by` | — | new | additive |
| `Payment.refund_of_payment_id / refund_reason` | — | new | additive |
| `Payment.provider_event_id` | — | new | additive |

- **No destructive migration.** Existing invoices read via `_effective_document_status` / `_effective_financial_status` helpers.

## 6. Files to add / modify / not modify

**Add:**
- `backend/app/models/payment.py` (moves + extends the current `Payment` class).
- `backend/app/services/invoice_reconciliation.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/stripe_core.py`
- `backend/app/routers/payments.py` (dedicated router; existing invoice-scoped `add_payment` route retained via compat shim).
- Stripe webhook handler (extends `routers/webhooks.py`).
- Backend tests: `test_invoice_dual_status.py`, `test_payment_reconciliation.py`, `test_payment_idempotency.py`, `test_payment_void.py`, `test_stripe_core.py`, `test_stripe_webhook.py`.
- Frontend: paired status pill component, Record Payment dialog with overpayment rejection, Void Payment dialog, Initiate Stripe Payment dialog, Refund dialog.
- Docs: `docs/modules/invoices.md`, `docs/modules/payments.md`, `docs/architecture/invoice_dual_status.md`, `docs/architecture/invoice_reconciliation.md`, `docs/architecture/payment_idempotency.md`, `docs/architecture/manual_payment_voids.md`, `docs/integrations/stripe_core.md`, `docs/integrations/stripe_webhooks.md`, `docs/security/payment_security.md`.

**Modify:**
- `backend/app/models/invoice.py` — extend with new dual-status + derived money fields. Retain `Payment` class deprecation shim that re-exports from new module.
- `backend/app/routers/invoices.py` — split status endpoints (document vs financial); direct financial mutation rejected.
- `backend/app/routers/webhooks.py` — add Stripe webhook endpoint.
- `backend/app/core/db.py` — new indexes.
- `backend/server.py` — mount `payments` router.

**Do not modify:** auth, storage, sequence, audit, email, EC2 activity/notification services, EC3 quote/order paths.

## 7. Stripe Core — behaviour

- **Payment Intents** (NOT Checkout Sessions). Raw `stripe` SDK, `stripe.api_key = settings.stripe_api_key`.
- Amount always derived server-side from Invoice reconciliation. Client cannot pass amount, tenant, or invoice total.
- `idempotency_key` derived server-side as `pi:{invoice_id}:{amount_cents}:{nonce}` where nonce comes from `Idempotency-Key` header if present, else stable UUID persisted on the pending Payment row.
- Metadata written into the PaymentIntent: `tenant_id, invoice_id, internal_payment_id`. Never trust these back from Stripe — always look up the internal `Payment` row by our own `stripe_payment_intent_id`.
- Frontend receives `{ payment_id, client_secret, publishable_key }`. Client uses Stripe Elements PaymentElement.
- Confirmation happens **only via webhook** (`payment_intent.succeeded`). Redirect success is not authoritative.
- Refunds server-initiated via `stripe.Refund.create(payment_intent=…, amount=…)`; webhook `charge.refunded` finalizes state.

## 8. Stripe webhook events handled

- `payment_intent.succeeded` → mark Payment `confirmed`, reconcile Invoice.
- `payment_intent.payment_failed` → mark Payment `failed`.
- `payment_intent.canceled` → mark Payment `voided` (system-void with reason `stripe:canceled`).
- `charge.refunded` → look up internal `refund` Payment row (or create one) with `stripe_refund_id`; reconcile.

All webhook rows land in the EC2 `webhook_events` collection with `provider="stripe"`, `provider_event_id=event.id`. Replay protection = unique index on `(provider, provider_event_id)`.

## 9. Overpayment policy

- Reject on record time. Server re-derives `balance_due_cents` inside the write path and rejects `amount_cents > balance_due_cents` with **400**. Concurrent writes protected by re-checking after insert; if the newly-derived paid > total, rollback the payment (delete + audit `payment_idempotency_replay` overshoot).

## 10. Manual payment void

- Only `source == "manual"` AND `status == "confirmed"` may be voided.
- Reason required (400 otherwise).
- Void writes new state; original amount stays intact but excluded from reconciliation.
- Stripe payments cannot be manually voided (400 with `stripe_payments_cannot_be_manually_voided`).

## 11. Invoice void

- Reason required.
- Blocked if net confirmed payments remain (400) — refund or void manual payments first. Safer default per EC4 §22 "block void when net confirmed Payments remain".

## 12. Data compatibility

- Existing invoices without new fields:
  - `document_status` derived: if `status in {paid, partially_paid}` → `issued`, if `void` → `void`, else map `sent/viewed/overdue → issued`, `draft → draft`.
  - `financial_status` derived from live reconciliation.
- Existing payments default `source="manual"`, `status="confirmed"`.

## 13. Collections + indexes

Existing: `invoices`, `payments` retained. New indexes:
- `payments`: `(tenant_id, invoice_id, received_at)`, unique sparse `stripe_payment_intent_id`, unique sparse `stripe_charge_id`, unique sparse `stripe_refund_id`, unique `(tenant_id, invoice_id, idempotency_key)` sparse.

## 14. Test plan

Backend:
- **Invoice dual status:** create, direct `paid` mutation rejected, void with confirmed payments blocked, void with reason succeeds.
- **Manual payments:** full / partial / multiple / exact final / overpayment rejected / draft invoice allowed but no auto-issue.
- **Reconciliation:** correct across pending, confirmed, failed, voided, refunded mixes.
- **Idempotency:** repeated Idempotency-Key returns same row; unique index prevents duplicate.
- **Void:** reason required, Stripe payment blocked, double-void blocked, actor recorded.
- **Stripe Core:** initiate returns client_secret; `stripe_payment_intent_id` unique; second call returns existing pending payment when amount matches.
- **Stripe webhook:** invalid signature 401, valid signature marks row `verified`, `payment_intent.succeeded` reconciles Invoice, replay is no-op, mismatched invoice ignored.
- **Cross-tenant:** all endpoints 404 for foreign tenant.

Frontend: paired status badges, Record Payment dialog with overpayment error surfaced from API, void dialog reason required, initiate-Stripe dialog shows pending until webhook, refund dialog gated on `payment:refund` perm.

## 15. Stripe test-mode plan

- Use `STRIPE_API_KEY` from `.env` (defaults to `sk_test_emergent`).
- Unit-test Stripe calls with `unittest.mock.patch("stripe.PaymentIntent.create", ...)` to avoid network.
- Manual smoke-test path documented in `/app/docs/integrations/stripe_core.md`.

## 16. Rollback plan

- Fully additive schema. Rollback = revert new files + revert additive lines in Invoice model + delete new indexes.
- No destructive data migration to reverse.

## 17. Sign-off

Preflight complete. Proceeding to implementation.
