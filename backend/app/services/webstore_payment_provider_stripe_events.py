"""Stripe webhook parsing and event normalization for Webstores."""
from __future__ import annotations

from typing import Any

import stripe

from .webstore_payment_provider_types import ProviderResult

class StripeWebhookMixin:
        def verify_webhook_signature_and_parse(self, **kwargs: Any) -> ProviderResult:
            failure = self._configure()
            if failure:
                return failure
            payload = kwargs.get("payload")
            signature = str(kwargs.get("signature") or "")
            secret = self.settings.stripe_webhook_secret
            if not isinstance(payload, (bytes, bytearray)) or not signature or not secret:
                return self._failure("WEBHOOK_INPUT_INVALID", "A Stripe payload, signature, and webhook secret are required.")
            try:
                event = stripe.Webhook.construct_event(bytes(payload), signature, secret)
                event_type = str(event.get("type") or "")
                if event_type not in {
                    "checkout.session.completed",
                    "checkout.session.async_payment_succeeded",
                    "checkout.session.async_payment_failed",
                    "checkout.session.expired",
                    "payment_intent.succeeded",
                    "payment_intent.payment_failed",
                    "payment_intent.canceled",
                    "payout.paid",
                    "payout.failed",
                    "payout.canceled",
                    "transfer.created",
                    "transfer.paid",
                    "transfer.failed",
                    "transfer.reversed",
                    "charge.dispute.created",
                    "charge.dispute.closed",
                    "refund.created",
                    "refund.updated",
                    "charge.refunded",
                }:
                    return ProviderResult.success({"ignored": True, "provider_event_id": str(event.get("id") or ""), "event_type": event_type})
                data_object = ((event.get("data") or {}).get("object") or {})
                metadata = data_object.get("metadata") or {}
                payment_intent = data_object.get("payment_intent") or data_object.get("id")
                if isinstance(payment_intent, dict):
                    payment_intent = payment_intent.get("id")
                amount = data_object.get("amount_total") or data_object.get("amount_received") or data_object.get("amount")
                currency = str(data_object.get("currency") or "usd").lower()
                if event_type in {"refund.created", "refund.updated", "charge.refunded"}:
                    refund_object = data_object
                    if event_type == "charge.refunded":
                        refunds = ((data_object.get("refunds") or {}).get("data") or [])
                        refund_object = refunds[0] if refunds else {}
                    refund_metadata = refund_object.get("metadata") or metadata
                    refund_reference = refund_object.get("id")
                    payment_reference = refund_object.get("payment_intent") or data_object.get("payment_intent")
                    if isinstance(payment_reference, dict):
                        payment_reference = payment_reference.get("id")
                    refund_amount = refund_object.get("amount") or data_object.get("amount_refunded") or amount
                    refund_currency = str(refund_object.get("currency") or currency).lower()
                    if not refund_reference or not payment_reference or refund_amount is None or not refund_metadata.get("tenant_id") or not refund_metadata.get("webstore_id"):
                        return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe refund event is missing Webstore metadata, payment, or amount.")
                    return ProviderResult.success(
                        {
                            "event_kind": "refund",
                            "provider": self.provider_name,
                            "provider_mode": self.settings.stripe_mode,
                            "provider_event_id": str(event["id"]),
                            "provider_refund_reference": str(refund_reference),
                            "provider_payment_reference": str(payment_reference),
                            "provider_account_reference": event.get("account"),
                            "tenant_id": str(refund_metadata["tenant_id"]),
                            "webstore_id": str(refund_metadata["webstore_id"]),
                            "purchase_intent_id": str(refund_metadata.get("purchase_intent_id") or "") or None,
                            "amount_cents": int(refund_amount),
                            "currency": refund_currency,
                            "status": str(refund_object.get("status") or "succeeded").lower(),
                            "idempotency_key": str(refund_metadata.get("idempotency_key") or f"webstore-refund-webhook:{refund_reference}"),
                            "raw_event_snapshot": {
                                "provider_event_id": str(event["id"]),
                                "event_type": event_type,
                                "refund_reference": str(refund_reference),
                                "payment_reference": str(payment_reference),
                                "amount_cents": int(refund_amount),
                                "currency": refund_currency,
                                "metadata": {
                                    "tenant_id": str(refund_metadata["tenant_id"]),
                                    "webstore_id": str(refund_metadata["webstore_id"]),
                                    "purchase_intent_id": str(refund_metadata.get("purchase_intent_id") or "") or None,
                                },
                            },
                        }
                    )
                financial_event_types = {
                    "payout.paid": "payout",
                    "payout.failed": "payout",
                    "payout.canceled": "payout",
                    "transfer.created": "transfer",
                    "transfer.paid": "transfer",
                    "transfer.failed": "transfer",
                    "transfer.reversed": "transfer",
                    "charge.dispute.created": "dispute",
                    "charge.dispute.closed": "dispute",
                }
                normalized_financial_type = financial_event_types.get(event_type)
                if normalized_financial_type:
                    financial_reference = (
                        data_object.get("payment_intent")
                        or metadata.get("provider_payment_reference")
                        or metadata.get("payment_intent_id")
                    )
                    if isinstance(financial_reference, dict):
                        financial_reference = financial_reference.get("id")
                    if not financial_reference or amount is None or not metadata.get("tenant_id") or not metadata.get("webstore_id"):
                        return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe financial event is missing Webstore payment metadata or amount.")
                    status = str(data_object.get("status") or "pending").lower()
                    if normalized_financial_type == "dispute" and event_type.endswith("closed"):
                        status = status or "closed"
                    return ProviderResult.success(
                        {
                            "event_kind": "financial",
                            "event_type": normalized_financial_type,
                            "provider": self.provider_name,
                            "provider_mode": self.settings.stripe_mode,
                            "provider_event_id": str(event["id"]),
                            "provider_payment_reference": str(financial_reference),
                            "provider_account_reference": event.get("account"),
                            "tenant_id": str(metadata.get("tenant_id") or ""),
                            "webstore_id": str(metadata.get("webstore_id") or ""),
                            "amount_cents": int(amount),
                            "currency": currency,
                            "status": status,
                            "sequence": int(metadata["sequence"]) if metadata.get("sequence") is not None else None,
                            "raw_event_snapshot": {
                                "provider_event_id": str(event["id"]),
                                "event_type": event_type,
                                "account": event.get("account"),
                                "amount_cents": int(amount),
                                "currency": currency,
                                "status": status,
                                "sequence": int(metadata["sequence"]) if metadata.get("sequence") is not None else None,
                                "metadata": {
                                    "tenant_id": str(metadata["tenant_id"]),
                                    "webstore_id": str(metadata["webstore_id"]),
                                    "provider_payment_reference": str(financial_reference),
                                },
                            },
                        }
                    )
                provider_payment_reference = payment_intent
                if event_type == "checkout.session.completed" and str(data_object.get("payment_status") or "").lower() != "paid":
                    event_kind = "payment_pending"
                    status = "pending"
                    failure_code = None
                    failure_reason = "Stripe Checkout has not confirmed payment yet."
                elif event_type in {"checkout.session.async_payment_failed", "payment_intent.payment_failed"}:
                    event_kind = "payment_failure"
                    status = "payment_failed"
                    last_error = data_object.get("last_payment_error") or {}
                    failure_code = str(last_error.get("code") or data_object.get("failure_code") or "payment_failed")
                    failure_reason = str(
                        last_error.get("message")
                        or data_object.get("failure_message")
                        or data_object.get("status")
                        or event_type
                    )
                elif event_type in {"checkout.session.expired", "payment_intent.canceled"}:
                    event_kind = "payment_failure"
                    status = "expired" if event_type == "checkout.session.expired" else "canceled"
                    failure_code = status
                    failure_reason = str(data_object.get("cancellation_reason") or data_object.get("status") or event_type)
                else:
                    event_kind = "payment_success"
                    status = "succeeded"
                    failure_code = None
                    failure_reason = None
                required = (
                    event.get("id"),
                    metadata.get("tenant_id"),
                    metadata.get("webstore_id"),
                    metadata.get("purchase_intent_id"),
                    provider_payment_reference,
                    amount,
                )
                if any(value in (None, "") for value in required):
                    return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe payment event is missing Webstore metadata or amount.")
                if event_kind != "payment_success":
                    return ProviderResult.success(
                        {
                            "event_kind": event_kind,
                            "provider": self.provider_name,
                            "provider_mode": self.settings.stripe_mode,
                            "provider_event_id": str(event["id"]),
                            "provider_payment_id": str(provider_payment_reference),
                            "purchase_intent_id": str(metadata["purchase_intent_id"]),
                            "webstore_id": str(metadata["webstore_id"]),
                            "tenant_id": str(metadata["tenant_id"]),
                            "amount_cents": int(amount),
                            "currency": currency,
                            "status": status,
                            "failure_code": failure_code,
                            "failure_reason": failure_reason,
                            "provider_account_reference": event.get("account"),
                            "raw_event_snapshot": {
                                "provider_event_id": str(event["id"]),
                                "event_type": event_type,
                                "account": event.get("account"),
                                "amount_cents": int(amount),
                                "currency": currency,
                                "payment_status": data_object.get("payment_status"),
                                "status": status,
                                "failure_code": failure_code,
                                "failure_reason": failure_reason,
                                "metadata": {
                                    "tenant_id": str(metadata["tenant_id"]),
                                    "webstore_id": str(metadata["webstore_id"]),
                                    "purchase_intent_id": str(metadata["purchase_intent_id"]),
                                },
                            },
                        }
                    )
                required = (
                    event.get("id"),
                    metadata.get("tenant_id"),
                    metadata.get("webstore_id"),
                    metadata.get("purchase_intent_id"),
                    payment_intent,
                    amount,
                )
                if any(value in (None, "") for value in required):
                    return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe payment event is missing Webstore metadata or amount.")
                return ProviderResult.success(
                    {
                        "ignored": False,
                        "provider": self.provider_name,
                        "provider_mode": self.settings.stripe_mode,
                        "provider_event_id": str(event["id"]),
                        "provider_payment_id": str(payment_intent),
                        "purchase_intent_id": str(metadata["purchase_intent_id"]),
                        "webstore_id": str(metadata["webstore_id"]),
                        "tenant_id": str(metadata["tenant_id"]),
                        "amount_cents": int(amount),
                        "currency": currency,
                        "provider_account_reference": event.get("account"),
                        "event_type": event_type,
                        "raw_event_snapshot": {
                            "provider_event_id": str(event["id"]),
                            "event_type": event_type,
                            "account": event.get("account"),
                            "amount_cents": int(amount),
                            "currency": currency,
                            "metadata": {
                                "tenant_id": str(metadata["tenant_id"]),
                                "webstore_id": str(metadata["webstore_id"]),
                                "purchase_intent_id": str(metadata["purchase_intent_id"]),
                            },
                        },
                    }
                )
            except Exception as exc:
                return self._failure("WEBHOOK_SIGNATURE_INVALID", f"Stripe webhook verification failed: {exc}")
