"""Complete Report Builder checkpoint tests.

These tests cover the PDF-governed reporting contracts without asserting on
demo data or disconnected UI placeholders.
"""
from __future__ import annotations

import uuid
from io import BytesIO
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user


def _override(user):
    async def _get():
        return {**user}
    return _get


async def _client(user):
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def report_builder_ctx():
    tenant_a = f"tenant-report-{uuid.uuid4().hex[:8]}"
    tenant_b = f"tenant-other-{uuid.uuid4().hex[:8]}"
    owner_a = {
        "id": f"user-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_a,
        "email": "owner-a@example.com",
        "role": "owner",
        "is_active": True,
    }
    owner_b = {
        "id": f"user-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_b,
        "email": "owner-b@example.com",
        "role": "owner",
        "is_active": True,
    }
    owner_c = {
        "id": f"user-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_a,
        "email": "owner-c@example.com",
        "role": "owner",
        "is_active": True,
    }
    await db.tenants.insert_many([
        {"id": tenant_a, "slug": tenant_a, "name": "Tenant A"},
        {"id": tenant_b, "slug": tenant_b, "name": "Tenant B"},
    ])
    await db.users.insert_many([{**owner_a}, {**owner_b}, {**owner_c}])
    await db.orders.insert_many([
        {
            "id": f"order-{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_a,
            "number": "ORD-1001",
            "customer_id": "customer-a",
            "title": "Lobby sign",
            "status": "confirmed",
            "subtotal_cents": 90000,
            "tax_cents": 7200,
            "total_cents": 97200,
            "created_at": "2026-07-01T12:00:00+00:00",
            "updated_at": "2026-07-01T12:00:00+00:00",
        },
        {
            "id": f"order-{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_b,
            "number": "ORD-2001",
            "customer_id": "customer-b",
            "title": "Other tenant order",
            "status": "confirmed",
            "subtotal_cents": 100,
            "tax_cents": 0,
            "total_cents": 100,
            "created_at": "2026-07-01T12:00:00+00:00",
            "updated_at": "2026-07-01T12:00:00+00:00",
        },
    ])
    store_id = f"store-{uuid.uuid4().hex[:8]}"
    await db.webstores.insert_one({
        "id": store_id,
        "tenant_id": tenant_a,
        "name": "Team Store",
        "slug": "team-store",
        "store_type": "employee",
        "status": "active",
        "visibility": "public",
        "created_at": "2026-07-01T12:00:00+00:00",
        "updated_at": "2026-07-01T12:00:00+00:00",
    })
    await db.webstore_buyer_orders.insert_one({
        "id": f"wbo-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_a,
        "webstore_id": store_id,
        "status": "paid",
        "total_cents": 25000,
        "tax_cents": 1000,
        "shipping_cents": 500,
        "donation_cents": 0,
        "created_at": "2026-07-01T12:00:00+00:00",
        "updated_at": "2026-07-01T12:00:00+00:00",
    })
    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "owner_a": owner_a, "owner_b": owner_b, "owner_c": owner_c}
    _clear()


@pytest.mark.asyncio
async def test_report_catalog_is_pdf_governed_and_exposes_buildable_surfaces(report_builder_ctx):
    async with await _client(report_builder_ctx["owner_a"]) as client:
        response = await client.get("/api/reports")

    assert response.status_code == 200
    body = response.json()
    assert body["authority"]["title"] == "SIGNGUY AI | REPORT CATALOG & CUSTOM REPORT BUILDER SPEC"
    assert body["authority"]["pages"] == 11
    assert body["authority"]["location"] == "Business & Finance -> Reports"
    assert body["official_webstore_types"] == ["B2B", "Fundraiser", "Event", "Promotional", "General"]
    assert "Employee" not in body["reports"][[report["key"] for report in body["reports"]].index("webstores.sales_by_store")]["limitations"][0]
    keys = {report["key"] for report in body["reports"]}
    assert "overview.executive_summary" in keys
    assert "orders.by_status" in keys
    assert "webstores.sales_by_store" in keys
    datasets = {dataset["key"] for dataset in body["custom_datasets"]}
    assert {"customers", "orders", "webstores", "wrap_projects", "payroll_snapshots"}.issubset(datasets)
    assert body["blocked_requirements"]


@pytest.mark.asyncio
async def test_standard_run_and_exports_are_source_read_only(report_builder_ctx):
    owner = report_builder_ctx["owner_a"]
    async with await _client(owner) as client:
        before_exports = await db.report_exports.count_documents({"tenant_id": owner["tenant_id"]})
        before_defs = await db.report_definitions.count_documents({"tenant_id": owner["tenant_id"]})
        run = await client.post("/api/reports/orders.by_status/run", json={"filters": {}, "preview_limit": 100})
        assert run.status_code == 200
        assert run.json()["rows"] == [{"status": "confirmed", "order_count": 1, "value_cents": 97200}]
        assert await db.report_exports.count_documents({"tenant_id": owner["tenant_id"]}) == before_exports
        assert await db.report_definitions.count_documents({"tenant_id": owner["tenant_id"]}) == before_defs

        for export_format, expected_content_type in [
            ("csv", "text/csv"),
            ("xlsx", "spreadsheetml"),
            ("pdf", "application/pdf"),
            ("print", "text/plain"),
        ]:
            response = await client.post(f"/api/reports/orders.by_status/export/{export_format}", json={"filters": {}})
            assert response.status_code == 200
            assert expected_content_type in response.headers["content-type"]
            if export_format == "xlsx":
                with ZipFile(BytesIO(response.content)) as archive:
                    sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
                assert "Orders by Status" in sheet
            if export_format == "pdf":
                assert response.content.startswith(b"%PDF")

        specialized = await client.post("/api/reports/orders.by_status/export/accounting_csv", json={"filters": {}})
        assert specialized.status_code == 400
        assert specialized.json()["detail"] == "specialized_export_not_implemented"

        history = await client.get("/api/reports/exports/history")
        assert history.status_code == 200
        assert len(history.json()["exports"]) == 4


@pytest.mark.asyncio
async def test_custom_builder_rejects_unapproved_fields_and_groups_allowed_fields(report_builder_ctx):
    async with await _client(report_builder_ctx["owner_a"]) as client:
        blocked = await client.post("/api/reports/custom/preview", json={
            "dataset": "orders",
            "fields": ["tenant_id"],
            "filters": {},
        })
        assert blocked.status_code == 400

        injected = await client.post("/api/reports/custom/preview", json={
            "dataset": "orders",
            "fields": ["number", "status"],
            "filters": {"status": {"$ne": "confirmed"}},
        })
        assert injected.status_code == 400
        assert injected.json()["detail"] == "invalid_filter_value:status"

        grouped = await client.post("/api/reports/custom/preview", json={
            "dataset": "orders",
            "fields": ["status", "total_cents"],
            "filters": {},
            "group_by": ["status"],
        })
        assert grouped.status_code == 200
        assert grouped.json()["rows"] == [{"status": "confirmed", "row_count": 1, "total_cents": 97200}]


@pytest.mark.asyncio
async def test_saved_reports_are_tenant_scoped_duplicable_and_archivable(report_builder_ctx):
    owner_a = report_builder_ctx["owner_a"]
    owner_b = report_builder_ctx["owner_b"]
    owner_c = report_builder_ctx["owner_c"]
    async with await _client(owner_a) as client:
        created = await client.post("/api/reports/saved", json={
            "name": "Orders by Status",
            "source_kind": "standard",
            "standard_report_key": "orders.by_status",
            "filters": {},
            "visibility": "shared_users",
            "shared_user_ids": [owner_c["id"]],
        })
        assert created.status_code == 200
        saved_id = created.json()["saved_report"]["id"]
        run = await client.post(f"/api/reports/saved/{saved_id}/run", json={"filters": {}, "preview_limit": 50})
        assert run.status_code == 200
        duplicate = await client.post(f"/api/reports/saved/{saved_id}/duplicate")
        assert duplicate.status_code == 200
        assert duplicate.json()["saved_report"]["parent_definition_id"] == saved_id

    async with await _client(owner_c) as client:
        shared_run = await client.post(f"/api/reports/saved/{saved_id}/run", json={"filters": {}, "preview_limit": 50})
        assert shared_run.status_code == 200
        shared_update = await client.patch(f"/api/reports/saved/{saved_id}", json={"name": "Changed by shared user"})
        assert shared_update.status_code == 403
        shared_archive = await client.post(f"/api/reports/saved/{saved_id}/archive")
        assert shared_archive.status_code == 403

    async with await _client(owner_a) as client:
        archived = await client.post(f"/api/reports/saved/{saved_id}/archive")
        assert archived.status_code == 200
        blocked_run = await client.post(f"/api/reports/saved/{saved_id}/run", json={"filters": {}})
        assert blocked_run.status_code == 404

    async with await _client(owner_b) as client:
        cross_tenant = await client.get(f"/api/reports/saved/{saved_id}")
        assert cross_tenant.status_code == 404


@pytest.mark.asyncio
async def test_saved_report_creation_rejects_unimplemented_builder_features(report_builder_ctx):
    async with await _client(report_builder_ctx["owner_a"]) as client:
        for key, value, detail in [
            ("calculated_fields", [{"name": "margin", "formula": "total_cents - cost_cents"}], "calculated_fields_not_implemented"),
            ("comparisons", ["previous_period"], "comparisons_not_implemented"),
            ("dashboard_widget", {"size": "small"}, "dashboard_widget_publish_not_implemented"),
        ]:
            payload = {
                "name": "Unsupported Builder Feature",
                "source_kind": "standard",
                "standard_report_key": "orders.by_status",
                "filters": {},
                key: value,
            }
            response = await client.post("/api/reports/saved", json=payload)
            assert response.status_code == 400
            assert response.json()["detail"] == detail


@pytest.mark.asyncio
async def test_schedules_revalidate_permissions_and_record_run_history(report_builder_ctx):
    owner = report_builder_ctx["owner_a"]
    async with await _client(owner) as client:
        created = await client.post("/api/reports/saved", json={
            "name": "Orders by Status Schedule",
            "source_kind": "standard",
            "standard_report_key": "orders.by_status",
            "filters": {},
        })
        saved_id = created.json()["saved_report"]["id"]
        schedule = await client.post("/api/reports/schedules", json={
            "report_definition_id": saved_id,
            "cadence": "weekly",
            "delivery_formats": ["csv"],
        })
        assert schedule.status_code == 200
        schedule_id = schedule.json()["schedule"]["id"]

        run = await client.post(f"/api/reports/schedules/{schedule_id}/run")
        assert run.status_code == 200
        body = run.json()["schedule_run"]
        assert body["status"] == "succeeded"
        assert body["permissions_revalidated"] is True
        assert body["delivery_mode"] == "test_no_email"
        assert len(body["export_ids"]) == 1

        await db.report_schedule_runs.insert_one({
            "id": f"run-{uuid.uuid4().hex[:8]}",
            "tenant_id": owner["tenant_id"],
            "schedule_id": schedule_id,
            "report_definition_id": saved_id,
            "started_at": "2026-07-29T12:00:00+00:00",
            "status": "running",
            "permissions_revalidated": True,
            "delivery_mode": "test_no_email",
            "created_at": "2026-07-29T12:00:00+00:00",
            "updated_at": "2026-07-29T12:00:00+00:00",
        })
        duplicate = await client.post(f"/api/reports/schedules/{schedule_id}/run")
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "schedule_run_already_running"


@pytest.mark.asyncio
async def test_webstore_employee_type_is_legacy(report_builder_ctx):
    async with await _client(report_builder_ctx["owner_a"]) as client:
        run = await client.post("/api/reports/webstores.sales_by_store/run", json={"filters": {}, "preview_limit": 100})

    assert run.status_code == 200
    rows = run.json()["rows"]
    assert rows
    assert rows[0]["store_type"] == "other_or_legacy"
