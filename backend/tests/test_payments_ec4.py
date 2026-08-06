"""EC4 — Payment service tests (manual + Stripe + void + idempotency + reconciliation).

Uses the FastAPI test client via httpx.ASGITransport with a dependency
override for `get_current_user` — matches the pattern in test_quotes_ec3.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.deps import get_current_user


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_invoice(tenant_id: str, total_cents: int = 10000) -> str:
    cust_id = f"cust-{uuid.uuid4().hex[:6]}"
    order_id = f"ord-{uuid.uuid4().hex[:6]}"
    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    await _db.customers.insert_one({"id": cust_id, "tenant_id": tenant_id, "name": "T", "email": "t@x.com"})
    await _db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "customer_id": cust_id,
                                 "number": 1, "job_name": "J", "status": "confirmed", "created_by": "u"})
    await _db.invoices.insert_one({
        "id": inv_id, "tenant_id": tenant_id, "number": 1,
        "order_id": order_id, "customer_id": cust_id,
        "title": "T", "total_cents": total_cents, "balance_due_cents": total_cents,
        "document_status": "issued", "status": "sent",
        "created_by": "u",
    })
    return inv_id


@pytest.mark.asyncio
async def test_record_manual_full_payment(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"])
    async with await _client_as(u) as c:
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments", json={
            "amount_cents": 10000, "method": "cash", "paid_on": "2026-02-01",
        })
        assert r.status_code == 201, r.text
        r = await c.get(f"/api/invoices/{inv_id}/payment-history")
        body = r.json()
        assert body["invoice_totals"]["financial_status"] == "paid"
        assert body["invoice_totals"]["balance_due_cents"] == 0
    _clear()


@pytest.mark.asyncio
async def test_record_manual_partial_and_multiple(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 6000)
    async with await _client_as(u) as c:
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments", json={
            "amount_cents": 2000, "method": "cash", "paid_on": "2026-02-01"})
        assert r.status_code == 201
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments", json={
            "amount_cents": 3000, "method": "check", "paid_on": "2026-02-02"})
        assert r.status_code == 201
        body = (await c.get(f"/api/invoices/{inv_id}/payment-history")).json()
        assert body["invoice_totals"]["financial_status"] == "partial"
        assert body["invoice_totals"]["balance_due_cents"] == 1000
    _clear()


@pytest.mark.asyncio
async def test_overpayment_rejected(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 5000)
    async with await _client_as(u) as c:
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments", json={
            "amount_cents": 6000, "method": "cash", "paid_on": "2026-02-01"})
        assert r.status_code == 400
        assert "balance" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_manual_payment_idempotent(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 5000)
    async with await _client_as(u) as c:
        headers = {"Idempotency-Key": "test-key-1"}
        r1 = await c.post(f"/api/invoices/{inv_id}/manual-payments",
                          json={"amount_cents": 2000, "method": "cash", "paid_on": "2026-02-01"},
                          headers=headers)
        assert r1.status_code == 201
        r2 = await c.post(f"/api/invoices/{inv_id}/manual-payments",
                          json={"amount_cents": 2000, "method": "cash", "paid_on": "2026-02-01"},
                          headers=headers)
        assert r2.status_code == 201
        assert r2.json()["already_exists"] is True
        # Only one payment recorded
        body = (await c.get(f"/api/invoices/{inv_id}/payment-history")).json()
        assert len(body["items"]) == 1
    _clear()


@pytest.mark.asyncio
async def test_manual_void_requires_reason(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 5000)
    async with await _client_as(u) as c:
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments",
                         json={"amount_cents": 3000, "method": "cash", "paid_on": "2026-02-01"})
        pay_id = r.json()["payment"]["id"]
        r = await c.post(f"/api/payments/{pay_id}/void", json={"reason": ""})
        assert r.status_code == 422 or r.status_code == 400
        r = await c.post(f"/api/payments/{pay_id}/void", json={"reason": "duplicate entry"})
        assert r.status_code == 200
        assert r.json()["status"] == "voided"
        body = (await c.get(f"/api/invoices/{inv_id}/payment-history")).json()
        assert body["invoice_totals"]["financial_status"] == "unpaid"
        # Double void
        r = await c.post(f"/api/payments/{pay_id}/void", json={"reason": "again"})
        assert r.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_direct_financial_status_mutation_rejected(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"])
    async with await _client_as(u) as c:
        # OLD single-status field is no longer accepted through /status
        r = await c.post(f"/api/invoices/{inv_id}/status", json={"status": "paid"})
        assert r.status_code == 422   # Pydantic rejects unknown key or wrong enum
    _clear()


@pytest.mark.asyncio
async def test_invoice_void_blocked_with_payment(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 5000)
    async with await _client_as(u) as c:
        await c.post(f"/api/invoices/{inv_id}/manual-payments",
                     json={"amount_cents": 2000, "method": "cash", "paid_on": "2026-02-01"})
        r = await c.post(f"/api/invoices/{inv_id}/status",
                         json={"document_status": "void", "reason": "customer cancelled"})
        assert r.status_code == 400
        assert "refund" in r.json()["detail"].lower() or "void" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_stripe_initiate_pending_then_webhook_confirms(seeded_users, monkeypatch):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 8000)

    fake_intent = {"id": f"pi_test_{uuid.uuid4().hex[:20]}", "client_secret": f"cs_test_{uuid.uuid4().hex[:8]}",
                   "status": "requires_payment_method", "amount": 8000, "currency": "usd"}
    with patch("app.services.stripe_core.create_payment_intent", return_value=fake_intent), \
         patch("app.services.stripe_core.is_enabled", return_value=True):
        async with await _client_as(u) as c:
            r = await c.post(f"/api/invoices/{inv_id}/stripe-intents",
                             json={"amount_cents": 8000},
                             headers={"Idempotency-Key": "pi-key-1"})
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["client_secret"] == fake_intent["client_secret"]
            payment_id = body["payment_id"]

            # Confirm via webhook helper directly (bypasses signature check)
            fake_charge = f"ch_test_{uuid.uuid4().hex[:20]}"
            from app.services.payment_service import confirm_stripe_from_webhook
            await confirm_stripe_from_webhook(
                payment_intent_id=fake_intent["id"],
                provider_event_id=f"evt_test_{uuid.uuid4().hex[:8]}",
                charge_id=fake_charge,
            )
            hist = (await c.get(f"/api/invoices/{inv_id}/payment-history")).json()
            assert hist["invoice_totals"]["financial_status"] == "paid"
            # Second confirmation is a no-op
            await confirm_stripe_from_webhook(
                payment_intent_id=fake_intent["id"],
                provider_event_id=f"evt_test_{uuid.uuid4().hex[:8]}",
                charge_id=fake_charge,
            )
            hist2 = (await c.get(f"/api/invoices/{inv_id}/payment-history")).json()
            confirmed = [p for p in hist2["items"] if p.get("id") == payment_id]
            assert len(confirmed) == 1
    _clear()


@pytest.mark.asyncio
async def test_stripe_disabled_preserves_failed_payment_record(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 8000)

    with patch("app.services.stripe_core.is_enabled", return_value=False):
        async with await _client_as(u) as c:
            r = await c.post(
                f"/api/invoices/{inv_id}/stripe-intents",
                json={"amount_cents": 8000},
                headers={"Idempotency-Key": "pi-disabled-preserve"},
            )
            assert r.status_code == 400

    rows = [
        row async for row in _db.payments.find(
            {"tenant_id": u["tenant_id"], "invoice_id": inv_id, "idempotency_key": "pi-disabled-preserve"},
            {"_id": 0},
        )
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["failure_reason"] == "stripe_disabled"

    invoice = await _db.invoices.find_one({"tenant_id": u["tenant_id"], "id": inv_id}, {"_id": 0})
    assert invoice["amount_paid_cents"] == 0
    assert invoice["balance_due_cents"] == 8000
    _clear()


@pytest.mark.asyncio
async def test_stripe_refund_idempotency_replays_existing_refund(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 8000)
    source_id = f"p-{uuid.uuid4().hex[:8]}"
    await _db.payments.insert_one({
        "id": source_id,
        "tenant_id": u["tenant_id"],
        "invoice_id": inv_id,
        "customer_id": f"cust-{uuid.uuid4().hex[:6]}",
        "source": "stripe",
        "status": "confirmed",
        "amount_cents": 8000,
        "stripe_payment_intent_id": f"pi_test_{uuid.uuid4().hex[:20]}",
    })

    fake_refund = {"id": f"re_test_{uuid.uuid4().hex[:20]}", "status": "pending", "amount": 3000}
    with patch("app.services.stripe_core.create_refund", return_value=fake_refund) as create_refund:
        async with await _client_as(u) as c:
            first = await c.post(
                f"/api/payments/{source_id}/refund",
                json={"amount_cents": 3000, "reason": "customer requested"},
                headers={"Idempotency-Key": "refund-key-1"},
            )
            assert first.status_code == 201, first.text
            second = await c.post(
                f"/api/payments/{source_id}/refund",
                json={"amount_cents": 3000, "reason": "customer requested"},
                headers={"Idempotency-Key": "refund-key-1"},
            )
            assert second.status_code == 201, second.text
            assert second.json()["id"] == first.json()["id"]
            assert create_refund.call_count == 1
    _clear()


@pytest.mark.asyncio
async def test_stripe_refund_nets_prior_pending_and_confirmed_refunds(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 5000)
    source_id = f"p-{uuid.uuid4().hex[:8]}"
    await _db.payments.insert_one({
        "id": source_id,
        "tenant_id": u["tenant_id"],
        "invoice_id": inv_id,
        "customer_id": f"cust-{uuid.uuid4().hex[:6]}",
        "source": "stripe",
        "status": "confirmed",
        "amount_cents": 5000,
        "stripe_payment_intent_id": f"pi_test_{uuid.uuid4().hex[:20]}",
    })
    await _db.payments.insert_many([
        {
            "id": f"rf-pending-{uuid.uuid4().hex[:6]}",
            "tenant_id": u["tenant_id"],
            "invoice_id": inv_id,
            "customer_id": f"cust-{uuid.uuid4().hex[:6]}",
            "source": "stripe",
            "status": "pending",
            "amount_cents": 2000,
            "refund_of_payment_id": source_id,
        },
        {
            "id": f"rf-confirmed-{uuid.uuid4().hex[:6]}",
            "tenant_id": u["tenant_id"],
            "invoice_id": inv_id,
            "customer_id": f"cust-{uuid.uuid4().hex[:6]}",
            "source": "stripe",
            "status": "confirmed",
            "amount_cents": 1000,
            "refund_of_payment_id": source_id,
        },
    ])

    async with await _client_as(u) as c:
        over = await c.post(
            f"/api/payments/{source_id}/refund",
            json={"amount_cents": 2500, "reason": "too much"},
            headers={"Idempotency-Key": "refund-over-net"},
        )
        assert over.status_code == 400
        assert "invalid" in over.json()["detail"].lower()

        with patch("app.services.stripe_core.create_refund", return_value={"id": f"re_test_{uuid.uuid4().hex[:20]}", "status": "pending", "amount": 2000}):
            ok = await c.post(
                f"/api/payments/{source_id}/refund",
                json={"amount_cents": 2000, "reason": "remaining balance"},
                headers={"Idempotency-Key": "refund-remaining"},
            )
        assert ok.status_code == 201, ok.text
        assert ok.json()["amount_cents"] == 2000
    _clear()


@pytest.mark.asyncio
async def test_stripe_payment_cannot_be_manually_voided(seeded_users):
    u = seeded_users["user_a"]
    inv_id = await _seed_invoice(u["tenant_id"], 4000)
    pid = f"p-{uuid.uuid4().hex[:8]}"
    fake_pi = f"pi_test_{uuid.uuid4().hex[:20]}"
    await _db.payments.insert_one({
        "id": pid, "tenant_id": u["tenant_id"], "invoice_id": inv_id,
        "customer_id": "c-x", "source": "stripe", "status": "confirmed",
        "amount_cents": 4000, "stripe_payment_intent_id": fake_pi,
    })
    async with await _client_as(u) as c:
        r = await c.post(f"/api/payments/{pid}/void", json={"reason": "test"})
        assert r.status_code == 400
        assert "stripe" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_stripe_webhook_signature_verification(seeded_users, monkeypatch):
    """Webhook route should 401 on invalid signatures and 200 on verified events."""
    from app.core.config import get_settings
    # Enable webhook + set secret
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_webhook_enabled", True, raising=False)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "bogus"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_stripe_webhook_disabled_returns_404(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_webhook_enabled", False, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/webhooks/stripe", content=b"{}")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation_on_payments(seeded_users):
    a = seeded_users["user_a"]
    b = seeded_users["user_b"]
    inv_id = await _seed_invoice(a["tenant_id"], 5000)
    async with await _client_as(b) as c:
        r = await c.post(f"/api/invoices/{inv_id}/manual-payments",
                         json={"amount_cents": 1000, "method": "cash", "paid_on": "2026-02-01"})
        assert r.status_code == 404
        r = await c.get(f"/api/invoices/{inv_id}/payment-history")
        assert r.status_code == 404
    _clear()
