from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

# Legacy single-status enum retained ONLY for backwards-compatible reads.
InvoiceStatus = Literal["draft", "sent", "viewed", "partially_paid", "paid", "overdue", "void"]

# EC4 permanent dual-status enums.
DocumentStatus = Literal["draft", "issued", "void"]
FinancialStatus = Literal["unpaid", "partial", "paid", "refunded", "voided"]
PaymentMethod = Literal["cash", "check", "card_external", "bank_transfer_external", "other"]


class InvoiceLineItem(BaseDoc):
    tenant_id: str
    invoice_id: str
    description: str
    quantity: int = 1
    unit_price_cents: int = 0
    position: int = 0


class Invoice(BaseDoc):
    tenant_id: str
    number: int
    order_id: str
    customer_id: str
    title: str
    description: Optional[str] = None

    # Legacy single-status field (kept as compat mirror; NEVER mutated for
    # financial state through the router).
    status: InvoiceStatus = "draft"

    # EC4 — permanent dual status
    document_status: DocumentStatus = "draft"
    financial_status: FinancialStatus = "unpaid"

    # Money (integer cents)
    subtotal_cents: int = 0
    discount_cents: int = 0
    tax_cents: int = 0
    fee_cents: int = 0
    total_cents: int = 0
    amount_paid_cents: int = 0
    amount_refunded_cents: int = 0
    balance_due_cents: int = 0

    # Lifecycle
    issued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None

    due_date: Optional[str] = None
    notes: Optional[str] = None
    created_by: str


# Backward-compat re-export so any older import of `Payment` from
# `models.invoice` continues to work while EC4 finalizes.
from .payment import Payment  # noqa: E402,F401
