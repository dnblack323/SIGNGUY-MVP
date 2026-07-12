"""EC7 phase 7d — Curated reports + CSV export + Custom Report Builder tests."""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services import csv_export


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def rpt_ctx():
    ta = f"t-rpt-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"u-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    us = {"id": f"u-s-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"s-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_many([{**ua}, {**us}])
    now = "2026-07-01T00:00:00+00:00"
    # A couple of expenses so exports have rows
    await db.expenses.insert_many([
        {"id": f"exp-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "number": 1,
         "expense_date": "2026-06-01", "category_key": "materials",
         "category_label_snapshot": "Materials", "description": "Vinyl",
         "amount_cents": 5000, "tax_cents": 400, "total_cents": 5400,
         "payment_method": "card", "deductible_class": "fully_deductible",
         "recurring": False, "state": "active", "created_by": ua["id"],
         "created_at": now, "updated_at": now},
        {"id": f"exp-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "number": 2,
         "expense_date": "2026-06-05", "category_key": "fuel",
         "category_label_snapshot": "Fuel", "description": "=CMD",  # formula-injection candidate
         "amount_cents": 3000, "tax_cents": 0, "total_cents": 3000,
         "payment_method": "cash", "deductible_class": "unknown",
         "recurring": False, "state": "active", "created_by": ua["id"],
         "created_at": now, "updated_at": now},
    ])
    yield {"ua": ua, "us": us, "ta": ta}
    _clear()


@pytest.mark.asyncio
async def test_list_reports_and_datasets(rpt_ctx):
    ua = rpt_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.get("/api/reports")).json()
        keys = {rpt["key"] for rpt in r["reports"]}
        # Cover every category
        assert "inventory.on_hand" in keys
        assert "purchasing.vendor_spend" in keys
        assert "expenses.by_category" in keys
        assert "finance.top_customers" in keys
        assert "tax.by_jurisdiction" in keys
        # Each report exposes provenance + limitations
        exp = next(rpt for rpt in r["reports"] if rpt["key"] == "expenses.all")
        assert exp["data_source"] == "expenses"
        assert exp["date_basis"] == "expense_date"
        assert exp["calc_basis"] == "expenses"
        assert isinstance(exp["limitations"], list) and exp["limitations"]
        # Custom datasets appear
        assert {ds["key"] for ds in r["custom_datasets"]} == {"expenses", "purchase_orders", "invoices"}


@pytest.mark.asyncio
async def test_run_curated_report_and_csv_export_sanitizes_formula(rpt_ctx):
    ua = rpt_ctx["ua"]
    async with await _client(ua) as c:
        r = (await c.post("/api/reports/expenses.all/run", json={"filters": {}})).json()
        assert r["row_count"] == 2
        assert r["title"] == "All expenses"
        # Export -> CSV
        r2 = await c.post("/api/reports/expenses.all/export.csv", json={"filters": {}})
        assert r2.status_code == 200
        assert "text/csv" in r2.headers["content-type"]
        assert r2.headers["content-disposition"].startswith("attachment; filename=")
        text = r2.text
        # Header row
        assert "Description" in text.splitlines()[0]
        # Money formatted to dollars
        assert "54.00" in text and "30.00" in text
        # Formula injection neutralized (leading single-quote before =CMD)
        # csv module wraps it in quotes because of leading quote; body must NOT
        # contain a bare ",=CMD" cell.
        assert ",=CMD" not in text


@pytest.mark.asyncio
async def test_custom_report_preview_and_export_enforces_field_whitelist(rpt_ctx):
    ua = rpt_ctx["ua"]
    async with await _client(ua) as c:
        # Valid preview
        r = await c.post("/api/reports/custom/preview", json={
            "dataset": "expenses",
            "fields": ["number", "expense_date", "total_cents", "category_key"],
            "filters": {"date_from": "2026-06-01", "date_to": "2026-06-30"},
            "sort": [{"field": "expense_date", "dir": "asc"}],
            "limit": 50,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["dataset"] == "expenses"
        assert body["row_count"] == 2
        # Field not in whitelist -> 400
        r2 = await c.post("/api/reports/custom/preview", json={
            "dataset": "expenses", "fields": ["internal_notes"], "filters": {},
        })
        assert r2.status_code == 400
        assert "invalid_field" in r2.json()["detail"]
        # Filter not in whitelist -> 400
        r3 = await c.post("/api/reports/custom/preview", json={
            "dataset": "expenses", "fields": ["number"], "filters": {"tenant_id": "sneaky"},
        })
        assert r3.status_code == 400
        # CSV export succeeds and sets attachment filename
        r4 = await c.post("/api/reports/custom/export.csv", json={
            "dataset": "expenses",
            "fields": ["number", "total_cents", "category_key"],
            "filters": {},
        })
        assert r4.status_code == 200
        assert "text/csv" in r4.headers["content-type"]


@pytest.mark.asyncio
async def test_permission_enforcement_staff_cannot_see_finance_reports(rpt_ctx):
    us = rpt_ctx["us"]
    # Staff role does NOT include finance/tax/expense/vendor/purchasing/report perms
    async with await _client(us) as c:
        r = await c.get("/api/reports")
        # staff lacks REPORT_READ -> 403
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_csv_build_helper_neutralizes_all_injection_prefixes():
    text = csv_export.build_csv(
        columns=[{"key": "a", "label": "A"}, {"key": "b", "label": "B", "money": True}],
        rows=[{"a": "=cmd", "b": 1050},
              {"a": "+cmd", "b": 0},
              {"a": "@x",  "b": None},
              {"a": "-y",  "b": 199}],
    )
    lines = text.splitlines()
    assert lines[0] == "A,B"
    # Every dangerous prefix has a leading ' so spreadsheets don't execute them
    for line in lines[1:]:
        first_cell = line.split(",")[0]
        if first_cell.startswith('"'):
            first_cell = first_cell.strip('"')
        assert first_cell.startswith("'"), f"unsafe cell: {line}"
