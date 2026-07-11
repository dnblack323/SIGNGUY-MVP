# Stripe Webhooks (EC4)

## Endpoint

`POST /api/webhooks/stripe`

## Enablement (fail-closed)

Route returns **404** unless BOTH `STRIPE_WEBHOOK_ENABLED=true` AND `STRIPE_WEBHOOK_SECRET` are set.

## Signature verification

`stripe.Webhook.construct_event(payload, signature, secret)`. Invalid → **401**.

## Handled events

| Event | Behaviour |
|---|---|
| `payment_intent.succeeded` | Look up internal Payment by `stripe_payment_intent_id`. Mark `confirmed`; capture `stripe_charge_id`. Reconcile Invoice. |
| `payment_intent.payment_failed` | Mark internal Payment `failed`; store `failure_reason`. |
| `payment_intent.canceled` | Mark internal Payment `voided` with `void_reason=stripe:canceled`. |
| `charge.refunded` | For each nested `refunds.data[]`, look up refund Payment by `stripe_refund_id` and mark `confirmed`; propagate parent Payment to `refunded` / `partially_refunded`. Reconcile Invoice. |
| `refund.updated` | Same as above when `status==succeeded`. |
| any other | Recorded + marked `processed` for observability, no state change. |

## Replay safety

Every event is recorded via the EC2 `services/webhooks.record_received` helper with unique `(provider="stripe", provider_event_id)`. Duplicates short-circuit to `deduplicated: true`. Handler functions also guard against downgrading a `confirmed` payment.
