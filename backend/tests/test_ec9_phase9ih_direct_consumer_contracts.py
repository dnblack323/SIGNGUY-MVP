"""EC9 Phase 9I-H - direct consumers read stored pricing evidence only."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from app.services import (
    order_pricing,
    pricing,
    pricing_method_comparisons,
    pricing_saved_calculations,
    reports_service,
    webstores,
    wrap_lab,
)
from server import app


WATCHED_COLLECTIONS = [
    "pricing_settings",
    "pricing_saved_calculations",
    "quote_line_items",
    "order_items",
    "work_orders",
    "orders",
    "invoices",
    "webstore_buyer_orders",
    "wrap_projects",
]


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _forbid_recalculation(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args, **kwargs):
        raise AssertionError("9I-H direct consumers must not call pricing calculators")

    monkeypatch.setattr(pricing, "calculate_pricing", _blocked)
    monkeypatch.setattr(order_pricing, "calculate_pricing_with_cents_first_envelope", _blocked)
    monkeypatch.setattr(pricing_method_comparisons, "calculate_pricing", _blocked)
    monkeypatch.setattr(pricing_saved_calculations, "calculate_pricing", _blocked)


async def _counts(tenant_id: str) -> dict[str, int]:
    return {
        name: await db[name].count_documents({"tenant_id": tenant_id})
        for name in WATCHED_COLLECTIONS
    }


@pytest.mark.asyncio
async def test_work_order_summary_reads_item_snapshot_without_repricing(seeded_users, monkeypatch):
    _forbid_recalculation(monkeypatch)
    user = {**seeded_users["user_a"], "permissions": ["work_order:read", "invoice:read"]}
    tenant_id = user["tenant_id"]
    suffix = _suffix()
    customer_id = f"cust-9ih-{suffix}"
    order_id = f"ord-9ih-{suffix}"
    work_order_id = f"wo-9ih-{suffix}"
    await db.customers.insert_one(
        {"id": customer_id, "tenant_id": tenant_id, "name": "Snapshot Customer", "email": f"{suffix}@example.com"}
    )
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "number": 9101,
            "job_name": "Snapshot Job",
            "status": "confirmed",
            "created_by": user["id"],
        }
    )
    await db.order_items.insert_one(
        {
            "id": f"oi-9ih-{suffix}",
            "tenant_id": tenant_id,
            "order_id": order_id,
            "description": "Current source line",
            "quantity": 1,
            "unit_price_cents": 99999,
            "category": "banners",
            "production_required": True,
            "position": 0,
        }
    )
    await db.work_orders.insert_one(
        {
            "id": work_order_id,
            "tenant_id": tenant_id,
            "number": 9102,
            "order_id": order_id,
            "customer_id": customer_id,
            "production_status": "released",
            "priority": "normal",
            "items_snapshot": [
                {
                    "order_item_id": f"oi-9ih-{suffix}",
                    "description": "Historical snapshot line",
                    "quantity": 2,
                    "unit_price_cents": 12345,
                    "category": "banners",
                    "production_required": True,
                }
            ],
            "created_by": user["id"],
            "version": 1,
            "current_version": True,
        }
    )
    before = await _counts(tenant_id)

    async with await _client_as(user) as client:
        response = await client.get(f"/api/work-orders/{work_order_id}/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_number"] == 9101
    assert body["customer"]["name"] == "Snapshot Customer"
    assert body["items"] == [
        {
            "description": "Historical snapshot line",
            "quantity": 2,
            "category": "banners",
            "product_type": None,
            "width_inches": None,
            "height_inches": None,
            "unit_of_measure": None,
            "material_key": None,
            "notes": None,
            "unit_price_cents": 12345,
        }
    ]
    assert await _counts(tenant_id) == before
    _clear_override()


@pytest.mark.asyncio
async def test_work_order_summary_does_not_leak_cross_tenant_order_or_customer(seeded_users, monkeypatch):
    _forbid_recalculation(monkeypatch)
    user_a = {**seeded_users["user_a"], "permissions": ["work_order:read", "invoice:read"]}
    user_b = seeded_users["user_b"]
    tenant_id = user_a["tenant_id"]
    other_tenant_id = user_b["tenant_id"]
    suffix = _suffix()
    other_customer_id = f"cust-other-9ih-{suffix}"
    other_order_id = f"ord-other-9ih-{suffix}"
    work_order_id = f"wo-cross-9ih-{suffix}"
    await db.customers.insert_one(
        {"id": other_customer_id, "tenant_id": other_tenant_id, "name": "Other Tenant Customer"}
    )
    await db.orders.insert_one(
        {
            "id": other_order_id,
            "tenant_id": other_tenant_id,
            "customer_id": other_customer_id,
            "number": 9911,
            "job_name": "Other Job",
            "status": "confirmed",
            "created_by": user_b["id"],
        }
    )
    await db.work_orders.insert_one(
        {
            "id": work_order_id,
            "tenant_id": tenant_id,
            "number": 9912,
            "order_id": other_order_id,
            "customer_id": other_customer_id,
            "production_status": "released",
            "priority": "normal",
            "items_snapshot": [],
            "created_by": user_a["id"],
            "version": 1,
            "current_version": True,
        }
    )

    async with await _client_as(user_a) as client:
        response = await client.get(f"/api/work-orders/{work_order_id}/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_number"] is None
    assert body["customer"] == {"id": None, "name": None}
    _clear_override()


@pytest.mark.asyncio
async def test_finance_report_reads_snapshot_cost_evidence_without_repricing(seeded_users, monkeypatch):
    _forbid_recalculation(monkeypatch)
    user = seeded_users["user_a"]
    tenant_id = user["tenant_id"]
    suffix = _suffix()
    order_id = f"ord-fin-9ih-{suffix}"
    invoice_id = f"inv-fin-9ih-{suffix}"
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": tenant_id,
            "customer_id": f"cust-fin-9ih-{suffix}",
            "number": 9201,
            "status": "completed",
            "cost_snapshot_cents": 17000,
            "created_by": user["id"],
        }
    )
    await db.invoices.insert_one(
        {
            "id": invoice_id,
            "tenant_id": tenant_id,
            "order_id": order_id,
            "number": 9202,
            "document_status": "issued",
            "financial_status": "paid",
            "issued_at": "2026-07-10T00:00:00+00:00",
            "total_cents": 50000,
            "balance_due_cents": 0,
        }
    )
    before = await _counts(tenant_id)

    result = await reports_service.run_report(
        key="finance.summary",
        tenant_id=tenant_id,
        filters={"date_from": "2026-07-01", "date_to": "2026-07-31"},
        user_perms={"finance:read"},
    )

    rows = {row["metric"]: row for row in result["rows"]}
    assert rows["revenue_issued_invoices"]["value_cents"] == 50000
    assert rows["estimated_gross_profit"]["value_cents"] == 33000
    assert await _counts(tenant_id) == before


@pytest.mark.asyncio
async def test_webstore_reports_read_buyer_order_and_ledger_snapshots_without_repricing(seeded_users, monkeypatch):
    _forbid_recalculation(monkeypatch)
    user = seeded_users["user_a"]
    tenant_id = user["tenant_id"]
    suffix = _suffix()
    webstore_id = f"store-9ih-{suffix}"
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "owner_id": f"owner-9ih-{suffix}",
            "name": "Snapshot Store",
            "slug": f"snapshot-store-{suffix}",
            "store_type": "fundraiser",
            "status": "live",
        }
    )
    await db.webstore_buyer_orders.insert_one(
        {
            "id": f"buyer-order-9ih-{suffix}",
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "status": "paid",
            "total_cents": 6750,
            "line_items": [
                {"product_id": "shirt", "quantity": 2, "unit_price_cents": 2500, "line_total_cents": 5000},
                {"product_id": "hat", "quantity": 1, "unit_price_cents": 1750, "line_total_cents": 1750},
            ],
        }
    )
    await db.webstore_ledger_entries.insert_many(
        [
            {
                "id": f"ledger-fee-9ih-{suffix}",
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "entry_type": "platform_fee",
                "amount_cents": 450,
            },
            {
                "id": f"ledger-payout-9ih-{suffix}",
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "entry_type": "owner_payout",
                "amount_cents": 1200,
            },
        ]
    )
    before = await _counts(tenant_id)

    result = await webstores.reports({**user, "role": "owner"}, webstore_id)

    assert result["order_count"] == 1
    assert result["gross_sales_cents"] == 6750
    assert result["ledger_totals_cents"] == {"platform_fee": 450, "owner_payout": 1200}
    assert result["product_quantities"] == {"shirt": 2, "hat": 1}
    assert await _counts(tenant_id) == before


@pytest.mark.asyncio
async def test_wrap_lab_reports_read_project_money_fields_without_repricing(seeded_users, monkeypatch):
    _forbid_recalculation(monkeypatch)
    user = seeded_users["user_a"]
    tenant_id = user["tenant_id"]
    suffix = _suffix()
    project_id = f"wrap-project-9ih-{suffix}"
    await db.wrap_projects.insert_one(
        {
            "id": project_id,
            "tenant_id": tenant_id,
            "customer_id": f"cust-wrap-9ih-{suffix}",
            "vehicle_id": f"veh-wrap-9ih-{suffix}",
            "project_name": "Snapshot Wrap",
            "project_type": "partial_wrap",
            "status": "estimate_ready",
            "estimate_total_cents": 304000,
            "deposit_required_cents": 100000,
            "material_estimate_cents": 84000,
            "labor_estimate_cents": 220000,
        }
    )
    before = await _counts(tenant_id)

    result = await wrap_lab.reports({**user, "role": "owner"})

    assert result["project_count"] >= 1
    assert result["status_counts"]["estimate_ready"] >= 1
    assert result["estimate_total_cents"] >= 304000
    assert result["deposit_required_cents"] >= 100000
    assert result["material_estimate_cents"] >= 84000
    assert result["labor_estimate_cents"] >= 220000
    assert await _counts(tenant_id) == before
