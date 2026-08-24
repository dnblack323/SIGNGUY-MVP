"""CIR-029 - calendar linked records must belong to the same relationship graph."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}
    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _ts(slot: int, minute: int = 0) -> str:
    return datetime(2026, 10, 1, 8 + slot, minute, tzinfo=timezone.utc).isoformat()


def _event(title: str, slot: int, **links: str) -> dict:
    return {
        "title": title,
        "event_type": "installation",
        "start_at": _ts(slot),
        "end_at": _ts(slot, 30),
        **links,
    }


async def _seed_graph(tenant_id: str, suffix: str, label: str, customer_id: str, owner_id: str) -> dict:
    quote_id = f"quote-{label}-{suffix}"
    order_id = f"order-{label}-{suffix}"
    item_id = f"item-{label}-{suffix}"
    work_order_id = f"wo-{label}-{suffix}"
    stage_id = f"stage-{label}-{suffix}"
    wrap_project_id = f"wrap-{label}-{suffix}"
    inspection_id = f"insp-{label}-{suffix}"
    installation_id = f"install-{label}-{suffix}"
    task_id = f"task-{label}-{suffix}"

    await db.quotes.insert_one({
        "id": quote_id,
        "tenant_id": tenant_id,
        "number": 1000 + (1 if label == "a" else 2),
        "customer_id": customer_id,
        "job_name": f"Quote {label}",
        "status": "converted",
        "converted_order_id": order_id,
        "created_by": owner_id,
    })
    await db.orders.insert_one({
        "id": order_id,
        "tenant_id": tenant_id,
        "number": 2000 + (1 if label == "a" else 2),
        "customer_id": customer_id,
        "quote_id": quote_id,
        "source_quote_id": quote_id,
        "source_type": "quote",
        "source_id": quote_id,
        "job_name": f"Order {label}",
        "status": "confirmed",
        "created_by": owner_id,
    })
    await db.order_items.insert_one({
        "id": item_id,
        "tenant_id": tenant_id,
        "order_id": order_id,
        "position": 1,
        "description": f"Item {label}",
        "quantity": 1,
    })
    await db.work_orders.insert_one({
        "id": work_order_id,
        "tenant_id": tenant_id,
        "number": 3000 + (1 if label == "a" else 2),
        "order_id": order_id,
        "customer_id": customer_id,
        "production_status": "released",
        "current_version": True,
        "items_snapshot": [{"order_item_id": item_id, "description": f"Item {label}"}],
        "created_by": owner_id,
    })
    await db.production_stage_instances.insert_one({
        "id": stage_id,
        "tenant_id": tenant_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": work_order_id,
        "workflow_instance_id": f"workflow-{label}-{suffix}",
        "stage_key": "print",
        "stage_name": "Print",
        "sequence": 1,
        "status": "not_started",
        "history": [],
    })
    await db.wrap_projects.insert_one({
        "id": wrap_project_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "quote_id": quote_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": work_order_id,
        "work_order_summary_id": work_order_id,
        "project_name": f"Wrap {label}",
        "project_type": "partial_wrap",
        "status": "production_ready",
    })
    await db.wrap_inspections.insert_one({
        "id": inspection_id,
        "tenant_id": tenant_id,
        "project_id": wrap_project_id,
        "inspection_type": "pre_install",
        "status": "draft",
    })
    await db.wrap_installation_records.insert_one({
        "id": installation_id,
        "tenant_id": tenant_id,
        "project_id": wrap_project_id,
        "status": "planned",
    })
    await db.tasks.insert_one({
        "id": task_id,
        "tenant_id": tenant_id,
        "title": f"Task {label}",
        "status": "not_started",
        "priority": "normal",
        "task_type": "production",
        "customer_id": customer_id,
        "quote_id": quote_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": work_order_id,
        "production_stage_id": stage_id,
    })
    return {
        "customer_id": customer_id,
        "quote_id": quote_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": work_order_id,
        "production_stage_id": stage_id,
        "wrap_project_id": wrap_project_id,
        "vehicle_inspection_id": inspection_id,
        "installation_id": installation_id,
        "task_id": task_id,
    }


@pytest_asyncio.fixture
async def cir029_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-cir029-{suffix}"
    other_tenant_id = f"t-cir029-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_one(owner)
    customer_a = f"cust-a-{suffix}"
    customer_b = f"cust-b-{suffix}"
    cross_customer = f"cust-cross-{suffix}"
    await db.customers.insert_many([
        {"id": customer_a, "tenant_id": tenant_id, "name": "Alpha"},
        {"id": customer_b, "tenant_id": tenant_id, "name": "Beta"},
        {"id": cross_customer, "tenant_id": other_tenant_id, "name": "Cross Tenant"},
    ])
    graph_a = await _seed_graph(tenant_id, suffix, "a", customer_a, owner["id"])
    graph_b = await _seed_graph(tenant_id, suffix, "b", customer_b, owner["id"])
    yield {
        "tenant_id": tenant_id,
        "owner": owner,
        "a": graph_a,
        "b": graph_b,
        "cross_customer_id": cross_customer,
    }
    app.dependency_overrides.pop(get_current_user, None)


def _assert_link_mismatch(response) -> None:
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "link_mismatch"


@pytest.mark.asyncio
async def test_valid_related_schedule_links_succeed_on_create(cir029_ctx):
    async with await _client_as(cir029_ctx["owner"]) as client:
        created = await client.post("/api/calendar/events", json=_event("Valid graph", 1, **cir029_ctx["a"]))
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["customer_id"] == cir029_ctx["a"]["customer_id"]
        assert body["wrap_project_id"] == cir029_ctx["a"]["wrap_project_id"]
        assert body["task_id"] == cir029_ctx["a"]["task_id"]


@pytest.mark.asyncio
async def test_same_tenant_customer_and_order_mismatches_fail_before_write(cir029_ctx):
    async with await _client_as(cir029_ctx["owner"]) as client:
        before = await db.calendar_events.count_documents({"tenant_id": cir029_ctx["tenant_id"]})

        wrong_customer = await client.post(
            "/api/calendar/events",
            json=_event(
                "Wrong customer",
                2,
                customer_id=cir029_ctx["b"]["customer_id"],
                quote_id=cir029_ctx["a"]["quote_id"],
                conflict_override_reason="Manager override cannot bypass bad links",
            ),
        )
        _assert_link_mismatch(wrong_customer)

        wrong_order = await client.post(
            "/api/calendar/events",
            json=_event("Wrong order", 3, order_id=cir029_ctx["a"]["order_id"], order_item_id=cir029_ctx["b"]["order_item_id"]),
        )
        _assert_link_mismatch(wrong_order)

        assert await db.calendar_events.count_documents({"tenant_id": cir029_ctx["tenant_id"]}) == before


@pytest.mark.asyncio
async def test_work_order_stage_wrap_and_task_relationship_mismatches_fail(cir029_ctx):
    async with await _client_as(cir029_ctx["owner"]) as client:
        item_work_order = await client.post(
            "/api/calendar/events",
            json=_event("Wrong item snapshot", 4, order_item_id=cir029_ctx["b"]["order_item_id"], work_order_id=cir029_ctx["a"]["work_order_id"]),
        )
        _assert_link_mismatch(item_work_order)

        stage_order = await client.post(
            "/api/calendar/events",
            json=_event("Wrong stage order", 5, production_stage_id=cir029_ctx["a"]["production_stage_id"], order_id=cir029_ctx["b"]["order_id"]),
        )
        _assert_link_mismatch(stage_order)

        wrap_inspection = await client.post(
            "/api/calendar/events",
            json=_event("Wrong wrap inspection", 6, wrap_project_id=cir029_ctx["a"]["wrap_project_id"], vehicle_inspection_id=cir029_ctx["b"]["vehicle_inspection_id"]),
        )
        _assert_link_mismatch(wrap_inspection)

        wrap_installation = await client.post(
            "/api/calendar/events",
            json=_event("Wrong wrap installation", 7, wrap_project_id=cir029_ctx["a"]["wrap_project_id"], installation_id=cir029_ctx["b"]["installation_id"]),
        )
        _assert_link_mismatch(wrap_installation)

        task_order = await client.post(
            "/api/calendar/events",
            json=_event("Wrong task order", 8, task_id=cir029_ctx["a"]["task_id"], order_id=cir029_ctx["b"]["order_id"]),
        )
        _assert_link_mismatch(task_order)


@pytest.mark.asyncio
async def test_update_validates_complete_prospective_event_and_preserves_original(cir029_ctx):
    async with await _client_as(cir029_ctx["owner"]) as client:
        created = await client.post(
            "/api/calendar/events",
            json=_event(
                "Update guard",
                9,
                customer_id=cir029_ctx["a"]["customer_id"],
                order_id=cir029_ctx["a"]["order_id"],
            ),
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]

        rejected = await client.patch(f"/api/calendar/events/{event_id}", json={"order_id": cir029_ctx["b"]["order_id"]})
        _assert_link_mismatch(rejected)

        stored = await db.calendar_events.find_one({"tenant_id": cir029_ctx["tenant_id"], "id": event_id}, {"_id": 0})
        assert stored["order_id"] == cir029_ctx["a"]["order_id"]
        assert stored["customer_id"] == cir029_ctx["a"]["customer_id"]
        assert stored["title"] == "Update guard"


@pytest.mark.asyncio
async def test_cross_tenant_link_rejection_still_uses_tenant_scope(cir029_ctx):
    async with await _client_as(cir029_ctx["owner"]) as client:
        rejected = await client.post(
            "/api/calendar/events",
            json=_event("Cross tenant", 10, customer_id=cir029_ctx["cross_customer_id"]),
        )
        assert rejected.status_code == 404
        assert rejected.json()["detail"]["code"] == "linked_record_not_found"
