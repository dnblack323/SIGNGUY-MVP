"""EC7 phase 7c — Finance Dashboard service tests.

Covers:
  - every metric returns an explicit `basis` label
  - invoice_revenue counts only document_status="issued" (drafts + voids excluded)
  - payments_received excludes refund records and unconfirmed payments
  - refunds returns refund total separately (never silently netted)
  - outstanding_receivables sums balance_due + aging buckets
  - tax_collected uses invoice tax snapshots
  - expenses_total excludes voided + archived
  - estimated_gross_profit uses only available cost inputs + warns on partial coverage
  - estimated_net_operating = revenue − expenses − refunds with labels preserved
  - trends return the requested month buckets, filled with 0s when empty
  - top_customers ranks by revenue
"""
from __future__ import annotations
import uuid
import pytest
from datetime import datetime, timezone
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


async def _seed_finance_fixture(tenant_id: str, uid: str) -> dict:
    """Insert deterministic invoices, payments, refunds, expenses covering
    Jan + Feb 2026 for revenue/payments/expense/trend/refund/tax tests."""
    now = "2026-06-15T12:00:00+00:00"
    # Customer
    cust1 = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
             "name": "ACME", "state": "CA", "country": "US",
             "archived": False, "created_at": now, "updated_at": now}
    cust2 = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
             "name": "Beta", "state": "NY", "country": "US",
             "archived": False, "created_at": now, "updated_at": now}
    await db.customers.insert_many([cust1, cust2])
    # 3 issued invoices in Jan + Feb 2026
    invs = [
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "number": 100, "order_id": f"ord-{uuid.uuid4().hex[:8]}",
         "customer_id": cust1["id"], "title": "A", "status": "sent",
         "document_status": "issued", "financial_status": "paid",
         "subtotal_cents": 10000, "tax_cents": 800, "total_cents": 10800,
         "amount_paid_cents": 10800, "balance_due_cents": 0,
         "issued_at": "2026-01-10T10:00:00+00:00", "due_date": "2026-01-30",
         "created_by": uid, "created_at": now, "updated_at": now},
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "number": 101, "order_id": f"ord-{uuid.uuid4().hex[:8]}",
         "customer_id": cust1["id"], "title": "B", "status": "sent",
         "document_status": "issued", "financial_status": "unpaid",
         "subtotal_cents": 20000, "tax_cents": 1600, "total_cents": 21600,
         "amount_paid_cents": 0, "balance_due_cents": 21600,
         "issued_at": "2026-02-05T10:00:00+00:00", "due_date": "2026-02-28",
         "created_by": uid, "created_at": now, "updated_at": now},
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "number": 102, "order_id": f"ord-{uuid.uuid4().hex[:8]}",
         "customer_id": cust2["id"], "title": "C", "status": "sent",
         "document_status": "issued", "financial_status": "partial",
         "subtotal_cents": 40000, "tax_cents": 3200, "total_cents": 43200,
         "amount_paid_cents": 10000, "balance_due_cents": 33200,
         "issued_at": "2026-02-20T10:00:00+00:00", "due_date": "2026-03-15",
         "created_by": uid, "created_at": now, "updated_at": now},
        # Draft should be EXCLUDED
        {"id": f"inv-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "number": 103, "order_id": f"ord-{uuid.uuid4().hex[:8]}",
         "customer_id": cust1["id"], "title": "Draft", "status": "draft",
         "document_status": "draft", "financial_status": "unpaid",
         "subtotal_cents": 99999, "tax_cents": 0, "total_cents": 99999,
         "amount_paid_cents": 0, "balance_due_cents": 99999,
         "created_by": uid, "created_at": now, "updated_at": now},
    ]
    await db.invoices.insert_many(invs)
    # Payments — 1 confirmed (10800), 1 partial (10000), 1 pending (excluded), 1 refund (2000)
    pays = [
        {"id": f"pay-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "invoice_id": invs[0]["id"], "customer_id": cust1["id"],
         "source": "manual", "status": "confirmed", "amount_cents": 10800,
         "method": "cash", "confirmed_at": "2026-01-12T00:00:00+00:00",
         "created_by": uid, "created_at": now, "updated_at": now},
        {"id": f"pay-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "invoice_id": invs[2]["id"], "customer_id": cust2["id"],
         "source": "manual", "status": "confirmed", "amount_cents": 10000,
         "method": "check", "confirmed_at": "2026-02-25T00:00:00+00:00",
         "created_by": uid, "created_at": now, "updated_at": now},
        {"id": f"pay-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "invoice_id": invs[1]["id"], "customer_id": cust1["id"],
         "source": "manual", "status": "pending", "amount_cents": 5000,
         "method": "check",
         "created_by": uid, "created_at": now, "updated_at": now},
        {"id": f"pay-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
         "invoice_id": invs[0]["id"], "customer_id": cust1["id"],
         "source": "manual", "status": "refunded",
         "amount_cents": 2000, "method": "cash",
         "refund_of_payment_id": "some-parent",
         "refunded_at": "2026-02-01T00:00:00+00:00",
         "created_by": uid, "created_at": now, "updated_at": now},
    ]
    await db.payments.insert_many(pays)
    # Expenses — 1 active, 1 archived, 1 voided
    exp1 = {"id": f"exp-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
            "number": 1, "expense_date": "2026-02-10",
            "category_key": "materials", "category_label_snapshot": "Materials",
            "description": "Vinyl roll", "amount_cents": 5000, "tax_cents": 400,
            "total_cents": 5400, "payment_method": "card",
            "deductible_class": "fully_deductible", "recurring": False,
            "state": "active", "created_by": uid,
            "created_at": now, "updated_at": now}
    exp2 = {"id": f"exp-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
            "number": 2, "expense_date": "2026-01-15",
            "category_key": "fuel", "category_label_snapshot": "Fuel",
            "description": "Gas", "amount_cents": 3000, "tax_cents": 0,
            "total_cents": 3000, "payment_method": "card",
            "deductible_class": "unknown", "recurring": False,
            "state": "archived", "archived_at": now, "created_by": uid,
            "created_at": now, "updated_at": now}
    exp3 = {"id": f"exp-{uuid.uuid4().hex[:8]}", "tenant_id": tenant_id,
            "number": 3, "expense_date": "2026-02-20",
            "category_key": "utilities", "category_label_snapshot": "Utilities",
            "description": "Voided electric bill", "amount_cents": 9000, "tax_cents": 0,
            "total_cents": 9000, "payment_method": "ach",
            "deductible_class": "fully_deductible", "recurring": False,
            "state": "voided", "voided_at": now, "created_by": uid,
            "created_at": now, "updated_at": now}
    await db.expenses.insert_many([exp1, exp2, exp3])
    return {"cust1": cust1, "cust2": cust2, "invs": invs, "pays": pays,
            "exp_active": exp1}


@pytest.fixture
async def fin_ctx():
    ta = f"t-fin-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"u-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    seed = await _seed_finance_fixture(ta, ua["id"])
    yield {"ua": ua, "ta": ta, **seed}
    _clear()


@pytest.mark.asyncio
async def test_invoice_revenue_excludes_drafts_and_labels_basis(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/revenue",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "issued_invoices"
        # Sum of the 3 issued invoices (drafts excluded): 10800 + 21600 + 43200 = 75600
        assert r["value_cents"] == 75600
        assert r["count"] == 3


@pytest.mark.asyncio
async def test_payments_and_refunds_are_never_silently_netted(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        pay = (await c.get("/api/finance/payments-received",
                            params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        # pending payment excluded; refund excluded; two confirmed = 10800 + 10000 = 20800
        assert pay["basis"] == "confirmed_payments_received"
        assert pay["value_cents"] == 20800
        assert pay["count"] == 2
        rf = (await c.get("/api/finance/refunds",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        # Refund returned as its own line
        assert rf["basis"] == "refunds"
        assert rf["value_cents"] == 2000


@pytest.mark.asyncio
async def test_outstanding_receivables_aging(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/outstanding")).json()
        # Unpaid $216 + Partial $332 balance = 54800
        assert r["basis"] == "outstanding_receivables"
        assert r["value_cents"] == 21600 + 33200
        assert r["unpaid_count"] == 1
        assert r["partial_count"] == 1
        # Aging buckets exist and sum to total
        aging = r["aging_cents"]
        assert sum(aging.values()) == r["value_cents"]


@pytest.mark.asyncio
async def test_tax_collected_uses_invoice_snapshots(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/tax-collected",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        # 800 + 1600 + 3200 = 5600
        assert r["basis"] == "tax_collected"
        assert r["value_cents"] == 5600
        assert any("snapshot" in l.lower() for l in r["limitations"])


@pytest.mark.asyncio
async def test_expenses_exclude_voided_and_archived(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/expenses",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "expenses"
        # Only the active expense (5400) is counted; archived + voided excluded
        assert r["value_cents"] == 5400
        assert r["count"] == 1


@pytest.mark.asyncio
async def test_estimated_gross_profit_warns_on_partial_coverage(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/estimated-gross-profit",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "estimated_gross_profit"
        # No Orders have cost_snapshot_cents set -> orders_missing_cost > 0 -> warning
        assert r["coverage"]["orders_missing_cost"] >= 3
        assert r["coverage_label"] == "partial_coverage"
        assert any("partial_cost_coverage" in w for w in r["warnings"])
        # value_cents is revenue (75600) minus 0 known cost = 75600
        assert r["value_cents"] == 75600


@pytest.mark.asyncio
async def test_estimated_net_operating_preserves_basis_labels(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/estimated-net-operating",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        assert r["basis"] == "estimated_net_operating"
        # 75600 revenue - 5400 expenses - 2000 refunds = 68200
        assert r["value_cents"] == 68200
        assert any("Invoice-basis" in l or "labels" in l for l in r["limitations"])


@pytest.mark.asyncio
async def test_revenue_trend_returns_month_buckets(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/revenue-trend",
                          params={"date_from": "2026-01-01", "date_to": "2026-03-31"})).json()
        series = r["series"]
        assert len(series) == 3
        by_period = {s["period"]: s["value_cents"] for s in series}
        assert by_period["2026-01"] == 10800
        assert by_period["2026-02"] == 21600 + 43200
        assert by_period["2026-03"] == 0                  # empty month still present


@pytest.mark.asyncio
async def test_top_customers_ranked_by_revenue(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/top-customers",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28",
                                  "limit": 5})).json()
        items = r["items"]
        assert len(items) == 2
        # cust2 has 43200; cust1 has 32400 (10800+21600) -> cust2 first
        assert items[0]["revenue_cents"] == 43200
        assert items[1]["revenue_cents"] == 32400


@pytest.mark.asyncio
async def test_dashboard_summary_bundles_labeled_metrics(fin_ctx):
    ua = fin_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/finance/summary",
                          params={"date_from": "2026-01-01", "date_to": "2026-02-28"})).json()
        # Every top-level metric preserves its basis label
        assert r["revenue_issued_invoices"]["basis"] == "issued_invoices"
        assert r["payments_received"]["basis"] == "confirmed_payments_received"
        assert r["refunds"]["basis"] == "refunds"
        assert r["expenses"]["basis"] == "expenses"
        assert r["tax_collected"]["basis"] == "tax_collected"
        assert r["estimated_gross_profit"]["basis"] == "estimated_gross_profit"
        assert r["estimated_net_operating"]["basis"] == "estimated_net_operating"
