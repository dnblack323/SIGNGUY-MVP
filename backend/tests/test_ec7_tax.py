"""EC7 phase 7c — Tax reporting + exemption tests."""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def tax_ctx():
    ta = f"t-tax-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"u-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    now = "2026-06-15T12:00:00+00:00"
    cust_ca = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": ta,
               "name": "CA Corp", "state": "CA", "country": "US",
               "archived": False, "created_at": now, "updated_at": now}
    cust_ny = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": ta,
               "name": "NY Corp", "state": "NY", "country": "US",
               "archived": False, "created_at": now, "updated_at": now}
    cust_ex = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": ta,
               "name": "Exempt Nonprofit", "state": "CA", "country": "US",
               "archived": False, "created_at": now, "updated_at": now}
    await db.customers.insert_many([cust_ca, cust_ny, cust_ex])
    # Invoices: CA customer 800c tax; NY customer 1000c tax; exempt customer 0c tax + override reason
    invs = [
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "number": 200,
         "order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer_id": cust_ca["id"],
         "title": "A", "status": "sent", "document_status": "issued",
         "financial_status": "paid",
         "subtotal_cents": 10000, "tax_cents": 800, "total_cents": 10800,
         "amount_paid_cents": 10800, "balance_due_cents": 0,
         "issued_at": "2026-02-10T00:00:00+00:00", "created_by": ua["id"],
         "created_at": now, "updated_at": now},
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "number": 201,
         "order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer_id": cust_ny["id"],
         "title": "B", "status": "sent", "document_status": "issued",
         "financial_status": "unpaid",
         "subtotal_cents": 12500, "tax_cents": 1000, "total_cents": 13500,
         "amount_paid_cents": 0, "balance_due_cents": 13500,
         "issued_at": "2026-02-11T00:00:00+00:00", "created_by": ua["id"],
         "created_at": now, "updated_at": now},
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "number": 202,
         "order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer_id": cust_ex["id"],
         "title": "Exempt", "status": "sent", "document_status": "issued",
         "financial_status": "paid",
         "subtotal_cents": 15000, "tax_cents": 0, "total_cents": 15000,
         "amount_paid_cents": 15000, "balance_due_cents": 0,
         "issued_at": "2026-02-12T00:00:00+00:00",
         "tax_manual_override": True, "tax_override_reason": "Nonprofit resale certificate on file",
         "created_by": ua["id"], "created_at": now, "updated_at": now},
    ]
    await db.invoices.insert_many(invs)
    yield {"ua": ua, "ta": ta, "cust_ca": cust_ca, "cust_ny": cust_ny,
           "cust_ex": cust_ex, "invs": invs}
    _clear()


@pytest.mark.asyncio
async def test_tax_collected_and_by_jurisdiction(tax_ctx):
    ua = tax_ctx["ua"]
    async with await _client(ua) as c:
        # Total tax
        r = (await c.get("/api/tax/collected",
                          params={"date_from": "2026-02-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "tax_collected"
        assert r["value_cents"] == 800 + 1000       # exempt row contributes 0
        assert r["invoice_count"] == 3
        # By jurisdiction (falls back to customer state)
        r2 = (await c.get("/api/tax/collected-by-jurisdiction",
                           params={"date_from": "2026-02-01", "date_to": "2026-02-28"})).json()
        items = {row["jurisdiction"]: row for row in r2["items"]}
        assert items["US-CA"]["tax_cents"] == 800
        assert items["US-NY"]["tax_cents"] == 1000
        # Exempt invoice has tax=0 so it doesn't appear in jurisdiction rollup
        assert "__unknown__" not in items


@pytest.mark.asyncio
async def test_manual_tax_override_report(tax_ctx):
    ua = tax_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/tax/manual-overrides",
                          params={"date_from": "2026-02-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "tax_collected"
        items = r["items"]
        assert len(items) == 1
        assert items[0]["override_reason"] == "Nonprofit resale certificate on file"


@pytest.mark.asyncio
async def test_exemption_crud_and_check(tax_ctx):
    ua = tax_ctx["ua"]
    ta = tax_ctx["ta"]
    cust_ex = tax_ctx["cust_ex"]
    async with await _client(ua) as c:
        # Create exemption
        r = await c.post("/api/tax/exemptions", json={
            "customer_id": cust_ex["id"], "jurisdiction": "US-CA",
            "reference": "CA-Exempt-12345", "effective_from": "2026-01-01",
            "reason": "Nonprofit resale",
        })
        assert r.status_code == 201, r.text
        exempt_id = r.json()["id"]
        # List
        lst = (await c.get("/api/tax/exemptions",
                            params={"customer_id": cust_ex["id"]})).json()["items"]
        assert len(lst) == 1
        # Check
        chk = (await c.get("/api/tax/exemptions/check",
                            params={"customer_id": cust_ex["id"],
                                    "jurisdiction": "US-CA",
                                    "at_date": "2026-06-01"})).json()
        assert chk["exempt"] is True
        # Non-exempt customer returns exempt=False
        chk2 = (await c.get("/api/tax/exemptions/check",
                             params={"customer_id": tax_ctx["cust_ca"]["id"],
                                     "jurisdiction": "US-CA"})).json()
        assert chk2["exempt"] is False
        # Archive
        assert (await c.post(f"/api/tax/exemptions/{exempt_id}/archive")).status_code == 200
        # Now the check returns exempt=False
        chk3 = (await c.get("/api/tax/exemptions/check",
                             params={"customer_id": cust_ex["id"]})).json()
        assert chk3["exempt"] is False


@pytest.mark.asyncio
async def test_exempt_customer_report(tax_ctx):
    ua = tax_ctx["ua"]
    cust_ex = tax_ctx["cust_ex"]
    async with await _client(ua) as c:
        # First create an active exemption
        await c.post("/api/tax/exemptions", json={
            "customer_id": cust_ex["id"], "jurisdiction": "US-CA",
            "reference": "CA-Ex-1", "effective_from": "2026-01-01",
        })
        r = (await c.get("/api/tax/exempt-customers",
                          params={"date_from": "2026-02-01", "date_to": "2026-02-28"})).json()
        items = r["items"]
        assert len(items) == 1
        row = items[0]
        assert row["customer_id"] == cust_ex["id"]
        assert row["invoice_count"] == 1
        assert row["tax_cents"] == 0                  # matches manual override
        assert len(row["exemptions"]) == 1
