"""EC4 — Permanent Payment model.

Superset of the legacy `Payment` shape in `models/invoice.py`. Handles both
manual and Stripe payments; includes void + refund lifecycles.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from .base import BaseDoc

PaymentSource = Literal["manual", "stripe"]
PaymentStatus = Literal[
    "pending", "confirmed", "failed", "voided", "refunded", "partially_refunded"
]
ManualMethod = Literal["cash", "check", "card_external", "bank_transfer_external", "other"]


class Payment(BaseDoc):
    tenant_id: str
    invoice_id: str
    customer_id: str
    order_id: Optional[str] = None

    source: PaymentSource = "manual"
    status: PaymentStatus = "pending"

    amount_cents: int = 0
    currency: str = "usd"

    # Manual entry
    method: Optional[ManualMethod] = None
    paid_on: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None

    # Stripe
    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_refund_id: Optional[str] = None
    provider_event_id: Optional[str] = None

    # Void
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None

    # Refund linkage (for refund records, points to the source payment)
    refund_of_payment_id: Optional[str] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None

    # Lifecycle
    confirmed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    # Idempotency
    idempotency_key: Optional[str] = None

    created_by: Optional[str] = None
