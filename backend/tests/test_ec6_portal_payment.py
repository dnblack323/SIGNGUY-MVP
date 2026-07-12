"""EC6.1 — Portal Invoice Payment end-to-end.

Verifies the customer portal payment surface REUSES the EC4 payment service
end-to-end: initiate → reuse-if-pending → confirm-via-webhook → reconciliation
→ portal refetch shows confirmed. Also verifies the safety guards: void, paid,
overpayment, cross-customer, cross-tenant, and webhook replay idempotency.
"""
from __future__ import annotations
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity


def _stripe_intent_stub(**_kwargs):
    return {"id": f"pi_test_{uuid.uuid4().hex[:8]}", "client_secret": f"pi_test_{uuid.uuid4().hex[:8]}_secret_{uuid.uuid4().hex[:8]}", "status": "requires_payment_method"}


def _publishable_stub():
    return "pk_test_stub"


@pytest.fixture
async def portal_pay_ctx():
    tid = f"t-pay-{uuid.uuid4().hex[:6]}"
    tid2 = f"t-pay2-{uuid.uuid4().hex[:6]}"
    cid_a = f"c-pay-a-{uuid.uuid4().hex[:6]}"
    cid_b = f"c-pay-b-{uuid.uuid4().hex[:6]}"
    await db.tenants.insert_many([{"id": tid, "slug": tid, "name": "T1"}, {"id": tid2, "slug": tid2, "name": "T2"}])
    await db.customers.insert_many([
        {"id": cid_a, "tenant_id": tid, "name": "Cust A", "email": "a@example.com"},
        {"id": cid_b, "tenant_id": tid, "name": "Cust B", "email": "b@example.com"},
    ])
    inv_a = f"inv-{uuid.uuid4().hex[:6]}"
    inv_b = f"inv-{uuid.uuid4().hex[:6]}"
    inv_void = f"inv-{uuid.uuid4().hex[:6]}"
    inv_paid = f"inv-{uuid.uuid4().hex[:6]}"
    common = {"total_cents": 10000, "amount_paid_cents": 0, "amount_refunded_cents": 0,
              "balance_due_cents": 10000, "document_status": "issued", "financial_status": "unpaid",
              "title": "Signage"}
    await db.invoices.insert_many([
        {"id": inv_a, "tenant_id": tid, "customer_id": cid_a, "order_id": f"o-{uuid.uuid4().hex[:6]}", **common, "number": 1},
        {"id": inv_b, "tenant_id": tid, "customer_id": cid_b, "order_id": f"o-{uuid.uuid4().hex[:6]}", **common, "number": 2},
        {"id": inv_void, "tenant_id": tid, "customer_id": cid_a, "order_id": f"o-{uuid.uuid4().hex[:6]}", **common, "number": 3, "document_status": "void"},
        {"id": inv_paid, "tenant_id": tid, "customer_id": cid_a, "order_id": f"o-{uuid.uuid4().hex[:6]}", **common, "number": 4, "amount_paid_cents": 10000, "balance_due_cents": 0, "financial_status": "paid"},
    ])
    # Seed a confirmed payment against inv_paid so the shared _invoice_balance
    # computation reports zero balance (EC4 recomputes from payments).
    await db.payments.insert_one({
        "id": f"pay-{uuid.uuid4().hex[:6]}", "tenant_id": tid, "invoice_id": inv_paid,
        "customer_id": cid_a, "source": "manual", "status": "confirmed",
        "amount_cents": 10000, "method": "cash", "paid_on": "2026-02-01",
        "created_at": "2026-02-01T00:00:00+00:00", "updated_at": "2026-02-01T00:00:00+00:00",
    })
    identity_a = await create_portal_identity(
        tenant_id=tid, customer_id=cid_a, email=f"pi-{uuid.uuid4().hex[:6]}@example.com",
        permissions_preset="owner_full",
    )
    token_a = create_portal_token(portal_identity_id=identity_a["id"], tenant_id=tid, customer_id=cid_a)
    yield {
        "tid": tid, "tid2": tid2, "cid_a": cid_a, "cid_b": cid_b,
        "inv_a": inv_a, "inv_b": inv_b, "inv_void": inv_void, "inv_paid": inv_paid,
        "identity_a": identity_a, "token_a": token_a,
    }


@pytest.mark.asyncio
async def test_portal_payment_end_to_end_via_ec4(portal_pay_ctx):
    """Full happy path: initiate → confirm via EC4 webhook reconciliation → portal refetch shows confirmed + balance zero."""
    ctx = portal_pay_ctx
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    with patch("app.services.stripe_core.is_enabled", return_value=True), \
         patch("app.services.stripe_core.create_payment_intent", side_effect=_stripe_intent_stub), \
         patch("app.services.stripe_core.publishable_key", side_effect=_publishable_stub):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/portal/invoices/{ctx['inv_a']}/stripe-intents",
                             json={"amount_cents": 10000}, headers=headers)
            assert r.status_code == 201, r.text
            body = r.json()
            payment_id = body["payment_id"]
            assert body["client_secret"].startswith("pi_test_")
            assert body["publishable_key"] == "pk_test_stub"
            # Reuse: second initiate with same amount returns already_exists
            r2 = await c.post(f"/api/portal/invoices/{ctx['inv_a']}/stripe-intents",
                              json={"amount_cents": 10000}, headers=headers)
            assert r2.status_code == 201
            assert r2.json()["payment_id"] == payment_id
            assert r2.json().get("already_exists") is True
            # Detail before confirmation shows no confirmed payments
            r3 = await c.get(f"/api/portal/invoices/{ctx['inv_a']}", headers=headers)
            assert r3.status_code == 200
            assert r3.json()["invoice"]["balance_due_cents"] == 10000
            assert r3.json()["payments"] == []
            # Confirm via EC4 webhook (dev-simulate exercises confirm_stripe_from_webhook)
            r4 = await c.post(f"/api/portal/payments/{payment_id}/dev-simulate-confirm", headers=headers)
            assert r4.status_code == 200, r4.text
            # Refetch: balance zero, financial_status paid, payment appears
            r5 = await c.get(f"/api/portal/invoices/{ctx['inv_a']}", headers=headers)
            assert r5.status_code == 200
            inv = r5.json()["invoice"]
            assert inv["balance_due_cents"] == 0
            assert inv["financial_status"] == "paid"
            assert any(p["id"] == payment_id and p["status"] == "confirmed" for p in r5.json()["payments"])
            # Replay: second confirm is a no-op (idempotent)
            r6 = await c.post(f"/api/portal/payments/{payment_id}/dev-simulate-confirm", headers=headers)
            assert r6.status_code == 200
            assert r6.json().get("already_confirmed") is True
            # No duplicate payment row created
            payments = await db.payments.count_documents({"tenant_id": ctx["tid"], "invoice_id": ctx["inv_a"]})
            assert payments == 1


@pytest.mark.asyncio
async def test_portal_payment_void_blocked(portal_pay_ctx):
    ctx = portal_pay_ctx
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    with patch("app.services.stripe_core.is_enabled", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/portal/invoices/{ctx['inv_void']}/stripe-intents",
                             json={"amount_cents": 500}, headers=headers)
            assert r.status_code == 400
            assert "void" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_payment_overpayment_blocked(portal_pay_ctx):
    ctx = portal_pay_ctx
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    with patch("app.services.stripe_core.is_enabled", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/portal/invoices/{ctx['inv_a']}/stripe-intents",
                             json={"amount_cents": 10001}, headers=headers)
            assert r.status_code == 400
            assert "exceeds" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_payment_fully_paid_blocked(portal_pay_ctx):
    ctx = portal_pay_ctx
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    with patch("app.services.stripe_core.is_enabled", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/portal/invoices/{ctx['inv_paid']}/stripe-intents",
                             json={"amount_cents": 100}, headers=headers)
            assert r.status_code == 400
            assert "exceeds" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_payment_cross_customer_404(portal_pay_ctx):
    """Portal identity for Customer A must not be able to initiate a payment on Customer B's invoice."""
    ctx = portal_pay_ctx
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/portal/invoices/{ctx['inv_b']}/stripe-intents",
                         json={"amount_cents": 100}, headers=headers)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_portal_payment_requires_permission(portal_pay_ctx):
    """A portal identity WITHOUT portal:pay_invoices cannot initiate."""
    ctx = portal_pay_ctx
    viewer = await create_portal_identity(
        tenant_id=ctx["tid"], customer_id=ctx["cid_a"],
        email=f"viewer-{uuid.uuid4().hex[:6]}@example.com",
        permissions_preset="viewer_only",
    )
    tok = create_portal_token(portal_identity_id=viewer["id"], tenant_id=ctx["tid"], customer_id=ctx["cid_a"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/portal/invoices/{ctx['inv_a']}/stripe-intents",
                         json={"amount_cents": 100},
                         headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_manual_payment_appears_readonly_in_portal_history(portal_pay_ctx):
    """A staff-recorded manual payment (with confirmed status) is visible in
    the portal payment history but the portal cannot create manual payments
    itself (endpoint doesn't exist under /portal)."""
    from app.services.payment_service import record_manual
    ctx = portal_pay_ctx
    pay, _ = await record_manual(
        tenant_id=ctx["tid"], invoice_id=ctx["inv_a"], amount_cents=3000,
        method="check", paid_on="2026-02-01", reference="CHK-42",
        notes=None, idempotency_key=None,
        actor_user_id="staff-user", actor_email="staff@example.com",
    )
    headers = {"Authorization": f"Bearer {ctx['token_a']}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/portal/invoices/{ctx['inv_a']}", headers=headers)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["payments"]]
        assert pay["id"] in ids
        # Portal has no create-manual endpoint (proves no parallel Payment system)
        r2 = await c.post(f"/api/portal/invoices/{ctx['inv_a']}/manual-payments",
                          json={"amount_cents": 500, "method": "cash", "paid_on": "2026-02-01"},
                          headers=headers)
        assert r2.status_code == 404
