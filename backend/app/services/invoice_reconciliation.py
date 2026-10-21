"""EC4 — Invoice reconciliation service.

Backend-authoritative derivation of Invoice `amount_paid_cents`,
`amount_refunded_cents`, `balance_due_cents`, and `financial_status`.
Safe to run repeatedly. Called on every payment write / confirmation /
void / refund event.
"""
from __future__ import annotations

from typing import Optional

from ..core.db import db
from ..core.time_utils import utc_now


def _financial_status(total_cents: int, paid_cents: int, refunded_cents: int, document_status: str) -> str:
    if document_status == "void":
        return "voided"
    net = paid_cents - refunded_cents
    if refunded_cents > 0 and net <= 0:
        return "refunded"
    if net <= 0:
        return "unpaid"
    if net >= total_cents and total_cents > 0:
        return "paid"
    return "partial"


def project_financials(inv: dict, payments: list[dict]) -> dict:
    """Pure canonical money projection, shared by writes and read-only consumers."""
    total = int(inv.get("total_cents") or 0)
    document_status = inv.get("document_status") or _derive_document_status_compat(inv.get("status"))
    paid = refunded = 0
    for payment in payments:
        if payment.get("status") != "confirmed":
            continue
        amount = int(payment.get("amount_cents") or 0)
        if payment.get("refund_of_payment_id"):
            refunded += amount
        else:
            paid += amount
    return {
        "amount_paid_cents": paid,
        "amount_refunded_cents": refunded,
        "balance_due_cents": max(0, total - (paid - refunded)),
        "financial_status": _financial_status(total, paid, refunded, document_status),
    }


async def read_financials(*, tenant_id: str, invoice: dict) -> dict:
    """Read-only projection; never calls reconciliation or writes business records."""
    if invoice.get("tenant_id") != tenant_id:
        raise ValueError("Invoice tenant mismatch")
    if type(invoice.get("total_cents")) is not int or invoice["total_cents"] < 0:
        raise ValueError("Canonical invoice total is unavailable; never invent a zero balance")
    payments = [p async for p in db.payments.find(
        {"tenant_id": tenant_id, "invoice_id": invoice["id"]}, {"_id": 0}
    ).limit(10001)]
    if len(payments) > 10000:
        raise ValueError("Payment history exceeds the bounded read; balance unavailable")
    return project_financials(invoice, payments)


async def reconcile(*, tenant_id: str, invoice_id: str) -> dict:
    """Recompute Invoice money fields from the current `payments` collection.

    Rules:
      - Only `confirmed` payments (source=manual OR stripe) count toward paid.
      - Confirmed refund rows with `refund_of_payment_id` contribute to refunded
        totals; the original payment remains part of gross paid.
      - `pending`, `failed`, `voided` are excluded.
    """
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        return {}
    document_status = inv.get("document_status") or _derive_document_status_compat(inv.get("status"))
    payments = [p async for p in db.payments.find(
        {"tenant_id": tenant_id, "invoice_id": invoice_id}, {"_id": 0}
    )]
    updates = {**project_financials(inv, payments), "updated_at": utc_now().isoformat()}
    if not inv.get("document_status"):
        updates["document_status"] = document_status
    await db.invoices.update_one({"id": invoice_id, "tenant_id": tenant_id}, {"$set": updates})
    return updates


def _derive_document_status_compat(legacy_status: Optional[str]) -> str:
    if legacy_status == "void":
        return "void"
    if legacy_status in {None, "draft"}:
        return "draft"
    return "issued"
