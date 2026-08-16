"""Shop Operations SO-28 resource reservations over the shared calendar."""
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


def _ts(hour: int, minute: int = 0) -> str:
    return datetime(2026, 8, 14, hour, minute, tzinfo=timezone.utc).isoformat()


@pytest_asyncio.fixture
async def resource_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-so28-{suffix}"
    other_tenant_id = f"t-so28-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_many([owner, other_owner])
    employees = [
        {"id": f"emp-a-{suffix}", "tenant_id": tenant_id, "name": "Donnell", "status": "active", "role_label": "Installer"},
        {"id": f"emp-b-{suffix}", "tenant_id": tenant_id, "name": "Bill", "status": "active", "role_label": "Production"},
        {"id": f"emp-inactive-{suffix}", "tenant_id": tenant_id, "name": "Inactive", "status": "inactive"},
        {"id": f"emp-other-{suffix}", "tenant_id": other_tenant_id, "name": "Other", "status": "active"},
    ]
    await db.employees.insert_many(employees)
    yield {
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "other_owner": other_owner,
        "emp1": employees[0],
        "emp2": employees[1],
        "inactive_emp": employees[2],
        "other_emp": employees[3],
    }
    app.dependency_overrides.pop(get_current_user, None)


async def _create_resources(client: AsyncClient):
    printer = (await client.post("/api/equipment", json={"name": "HP Latex", "category": "printer"})).json()
    inactive = (await client.post("/api/equipment", json={"name": "Old Plotter", "category": "plotter"})).json()
    await client.patch(f"/api/equipment/{inactive['id']}", json={"status": "inactive"})
    van = (await client.post("/api/equipment", json={"name": "Install Van", "category": "vehicle"})).json()
    bay = (await client.post("/api/calendar/resources", json={"name": "Install Bay 1", "resource_type": "installation_bay", "capacity": 1, "location": "Shop"})).json()
    inactive_bay = (await client.post("/api/calendar/resources", json={"name": "Old Bay", "resource_type": "work_area"})).json()
    await client.patch(f"/api/calendar/resources/{inactive_bay['id']}", json={"status": "inactive"})
    return {"printer": printer, "inactive_equipment": inactive, "van": van, "bay": bay, "inactive_bay": inactive_bay}


@pytest.mark.asyncio
async def test_resource_assignment_validation_conflicts_and_override_history(resource_ctx):
    async with await _client_as(resource_ctx["owner"]) as client:
        resources = await _create_resources(client)
        payload = {
            "title": "Trailer install",
            "event_type": "installation",
            "start_at": _ts(9),
            "end_at": _ts(11),
            "assigned_employee_ids": [resource_ctx["emp1"]["id"], resource_ctx["emp2"]["id"]],
            "reserved_equipment_ids": [resources["printer"]["id"]],
            "reserved_vehicle_ids": [resources["van"]["id"]],
            "reserved_resource_ids": [resources["bay"]["id"]],
        }
        created = await client.post("/api/calendar/events", json=payload)
        assert created.status_code == 201, created.text
        event = created.json()
        assert event["employee_id"] == resource_ctx["emp1"]["id"]
        assert event["assigned_employee_ids"] == [resource_ctx["emp1"]["id"], resource_ctx["emp2"]["id"]]
        assert event["assignment_summary"]["employees"][0]["name"] == "Donnell"
        assert event["assignment_summary"]["equipment"][0]["name"] == "HP Latex"
        assert event["assignment_summary"]["vehicles"][0]["name"] == "Install Van"
        assert event["assignment_summary"]["resources"][0]["name"] == "Install Bay 1"

        availability = await client.post("/api/calendar/availability", json={**payload, "event_id": event["source_id"]})
        assert availability.status_code == 200
        assert availability.json()["summary"]["assigned_employees"] == 2
        assert availability.json()["summary"]["reserved_equipment"] == 1

        conflict = await client.post("/api/calendar/events", json={**payload, "title": "Second install", "start_at": _ts(10), "end_at": _ts(12)})
        assert conflict.status_code == 409
        conflict_detail = conflict.json()["detail"]
        assert conflict_detail["code"] == "conflict"
        assert {item["resource_type"] for item in conflict_detail["conflicts"]} >= {"employee", "equipment", "vehicle", "resource"}

        adjacent = await client.post("/api/calendar/events", json={**payload, "title": "Adjacent install", "start_at": _ts(11), "end_at": _ts(12)})
        assert adjacent.status_code == 201, adjacent.text

        patched = await client.patch(f"/api/calendar/events/{event['source_id']}", json={"title": "Trailer install updated"})
        assert patched.status_code == 200

        reschedule_conflict = await client.post(
            f"/api/calendar/events/{event['source_id']}/reschedule",
            json={"start_at": _ts(11, 30), "end_at": _ts(12, 30), "reserved_resource_ids": [resources["bay"]["id"]]},
        )
        assert reschedule_conflict.status_code == 409

        override = await client.post("/api/calendar/events", json={
            **payload,
            "title": "Manager override install",
            "start_at": _ts(10),
            "end_at": _ts(12),
            "conflict_override_reason": "Owner approved shared setup window",
        })
        assert override.status_code == 201
        override_event = override.json()
        assert len(override_event["conflicts"]) >= 1

        changed = await client.patch(
            f"/api/calendar/events/{override_event['source_id']}",
            json={"assigned_employee_ids": [resource_ctx["emp1"]["id"]], "conflict_override_reason": "Keep lead installer only"},
        )
        assert changed.status_code == 200
        stored = await db.calendar_events.find_one({"tenant_id": resource_ctx["tenant_id"], "id": override_event["source_id"]}, {"_id": 0})
        assert any(entry.get("assignment_diff") for entry in stored["history"])
        assert stored["conflict_overrides"]
        assert await db.activity_events.count_documents({"tenant_id": resource_ctx["tenant_id"], "action": "calendar_event.conflict_override"}) >= 1

        cancel_seed = await client.post("/api/calendar/events", json={**payload, "title": "Cancel seed", "start_at": _ts(15), "end_at": _ts(16)})
        assert cancel_seed.status_code == 201
        await client.post(f"/api/calendar/events/{cancel_seed.json()['source_id']}/cancel", json={"reason": "free resources"})
        after_cancel = await client.post("/api/calendar/events", json={**payload, "title": "Reuse canceled resources", "start_at": _ts(15), "end_at": _ts(16)})
        assert after_cancel.status_code == 201
        archive_seed = await client.post("/api/calendar/events", json={**payload, "title": "Archive seed", "start_at": _ts(17), "end_at": _ts(18)})
        assert archive_seed.status_code == 201
        await client.post(f"/api/calendar/events/{archive_seed.json()['source_id']}/archive")
        after_archive = await client.post("/api/calendar/events", json={**payload, "title": "Reuse archived resources", "start_at": _ts(17), "end_at": _ts(18)})
        assert after_archive.status_code == 201
        complete_seed = await client.post("/api/calendar/events", json={**payload, "title": "Complete seed", "start_at": _ts(19), "end_at": _ts(20)})
        assert complete_seed.status_code == 201
        await db.calendar_events.update_one(
            {"tenant_id": resource_ctx["tenant_id"], "id": complete_seed.json()["source_id"]},
            {"$set": {"status": "completed"}},
        )
        after_complete = await client.post("/api/calendar/events", json={**payload, "title": "Reuse completed resources", "start_at": _ts(19), "end_at": _ts(20)})
        assert after_complete.status_code == 201


@pytest.mark.asyncio
async def test_cross_tenant_inactive_and_legacy_event_compatibility(resource_ctx):
    async with await _client_as(resource_ctx["owner"]) as client:
        resources = await _create_resources(client)
        base = {"title": "Compat", "start_at": _ts(13), "end_at": _ts(14)}
        legacy = await client.post("/api/calendar/events", json=base)
        assert legacy.status_code == 201
        assert legacy.json()["assigned_employee_ids"] == []

        cross_tenant = await client.post("/api/calendar/events", json={**base, "assigned_employee_ids": [resource_ctx["other_emp"]["id"]]})
        assert cross_tenant.status_code == 404
        inactive_employee = await client.post("/api/calendar/events", json={**base, "assigned_employee_ids": [resource_ctx["inactive_emp"]["id"]]})
        assert inactive_employee.status_code == 400
        inactive_equipment = await client.post("/api/calendar/events", json={**base, "reserved_equipment_ids": [resources["inactive_equipment"]["id"]]})
        assert inactive_equipment.status_code == 400
        inactive_space = await client.post("/api/calendar/events", json={**base, "reserved_resource_ids": [resources["inactive_bay"]["id"]]})
        assert inactive_space.status_code == 400

    async with await _client_as(resource_ctx["other_owner"]) as other_client:
        isolated = await other_client.get("/api/calendar/feed", params={"start_at": _ts(12), "end_at": _ts(15)})
        assert isolated.status_code == 200
        assert isolated.json()["total"] == 0
