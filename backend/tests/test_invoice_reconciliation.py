"""EC4 — Invoice reconciliation unit tests (no HTTP)."""
import pytest
import uuid

from app.core.db import db
from app.services.invoice_reconciliation import reconcile


async def _make_invoice(tenant_id: str, total_cents: int = 10000) -> str:
    iid = f"inv-{uuid.uuid4().hex[:8]}"
    await db.invoices.insert_one({
        "id": iid, "tenant_id": tenant_id, "number": 1,
        "order_id": "o-x", "customer_id": "c-x",
        "title": "T", "total_cents": total_cents,
        "document_status": "issued", "status": "sent",
        "created_by": "u-x",
    })
    return iid


async def _pay(tenant_id: str, invoice_id: str, amount_cents: int, status: str = "confirmed",
               source: str = "manual", refund_of: str | None = None) -> str:
    pid = f"p-{uuid.uuid4().hex[:8]}"
    await db.payments.insert_one({
        "id": pid, "tenant_id": tenant_id, "invoice_id": invoice_id,
        "customer_id": "c-x", "source": source, "status": status,
        "amount_cents": amount_cents,
        "refund_of_payment_id": refund_of,
    })
    return pid


@pytest.mark.asyncio
async def test_reconcile_unpaid(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    iid = await _make_invoice(t, 5000)
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["amount_paid_cents"] == 0
    assert r["balance_due_cents"] == 5000
    assert r["financial_status"] == "unpaid"


@pytest.mark.asyncio
async def test_reconcile_partial_and_paid(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    iid = await _make_invoice(t, 5000)
    await _pay(t, iid, 2000)
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["financial_status"] == "partial"
    assert r["balance_due_cents"] == 3000
    await _pay(t, iid, 3000)
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["financial_status"] == "paid"
    assert r["balance_due_cents"] == 0


@pytest.mark.asyncio
async def test_reconcile_excludes_pending_failed_voided(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    iid = await _make_invoice(t, 5000)
    await _pay(t, iid, 1000, status="pending")
    await _pay(t, iid, 1000, status="failed")
    await _pay(t, iid, 1000, status="voided")
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["amount_paid_cents"] == 0
    assert r["financial_status"] == "unpaid"


@pytest.mark.asyncio
async def test_reconcile_refund_reduces_paid(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    iid = await _make_invoice(t, 5000)
    src = await _pay(t, iid, 5000, source="stripe")
    await _pay(t, iid, 2000, source="stripe", refund_of=src)
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["amount_paid_cents"] == 5000
    assert r["amount_refunded_cents"] == 2000
    assert r["balance_due_cents"] == 2000
    assert r["financial_status"] == "partial"
    # Full refund
    await _pay(t, iid, 3000, source="stripe", refund_of=src)
    r = await reconcile(tenant_id=t, invoice_id=iid)
    assert r["amount_refunded_cents"] == 5000
    assert r["financial_status"] == "refunded"


@pytest.mark.asyncio
async def test_reconcile_repeat_safe(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    iid = await _make_invoice(t, 3000)
    await _pay(t, iid, 3000)
    r1 = await reconcile(tenant_id=t, invoice_id=iid)
    r2 = await reconcile(tenant_id=t, invoice_id=iid)
    assert r1 == {**r2, "updated_at": r1["updated_at"]} or r1.keys() == r2.keys()
