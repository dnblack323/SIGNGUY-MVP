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


async def reconcile(*, tenant_id: str, invoice_id: str) -> dict:
    """Recompute Invoice money fields from the current `payments` collection.

    Rules:
      - Only `confirmed` payments (source=manual OR stripe) count toward paid.
      - Only `refunded` / `partially_refunded` payments with `refund_of_payment_id`
        set contribute to refunded totals; native refunds recorded through
        `charge.refunded` also count.
      - `pending`, `failed`, `voided` are excluded.
    """
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        return {}
    total = int(inv.get("total_cents") or 0)
    document_status = inv.get("document_status") or _derive_document_status_compat(inv.get("status"))

    paid = 0
    refunded = 0
    cursor = db.payments.find(
        {"tenant_id": tenant_id, "invoice_id": invoice_id}, {"_id": 0}
    )
    async for p in cursor:
        st = p.get("status")
        amt = int(p.get("amount_cents") or 0)
        # A refund payment (refund_of_payment_id set) contributes to refunded totals;
        # its own `status` will be `confirmed` when the refund succeeds.
        if p.get("refund_of_payment_id"):
            if st in {"confirmed"}:
                refunded += amt
            continue
        if st == "confirmed":
            paid += amt

    balance = max(0, total - (paid - refunded))
    fin = _financial_status(total, paid, refunded, document_status)

    updates = {
        "amount_paid_cents": paid,
        "amount_refunded_cents": refunded,
        "balance_due_cents": balance,
        "financial_status": fin,
        "updated_at": utc_now().isoformat(),
    }
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
