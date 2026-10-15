"""CIR-028 — concurrent duplicate-source and resource double-booking protection."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.db import db, ensure_indexes
from app.services import calendar_service
from app.services.calendar_service import CalendarError

DAY = "2026-11-03"


def _at(hour: int, minute: int = 0) -> str:
    return f"{DAY}T{hour:02d}:{minute:02d}:00+00:00"


async def _shop() -> dict:
    s = uuid.uuid4().hex[:8]
    tid = f"t-cir028-{s}"
    await db.employees.insert_many([
        {"id": f"emp-{s}", "tenant_id": tid, "name": "Installer", "status": "active"},
        {"id": f"emp2-{s}", "tenant_id": tid, "name": "Printer", "status": "active"},
    ])
    await db.equipment.insert_many([
        {"id": f"eq-{s}", "tenant_id": tid, "name": "Latex printer", "category": "printer", "status": "active"},
        {"id": f"van-{s}", "tenant_id": tid, "name": "Install van", "category": "vehicle", "status": "active"},
    ])
    await db.schedulable_resources.insert_many([
        {"id": f"bay-{s}", "tenant_id": tid, "name": "Install bay", "resource_type": "installation_bay", "capacity": 1, "status": "active"},
        {"id": f"prep-{s}", "tenant_id": tid, "name": "Prep area", "resource_type": "work_area", "capacity": 2, "status": "active"},
    ])
    return {"tenant_id": tid, "s": s}


async def _create(shop: dict, *, role: str = "staff", **payload):
    base = {"title": "Install", "event_type": "installation", "start_at": _at(9), "end_at": _at(11)}
    return await calendar_service.create_event(
        tenant_id=shop["tenant_id"], actor_user_id="u1", actor_email="u1@example.com", payload={**base, **payload}, actor_role=role,
    )


async def _race(*coros):
    return await asyncio.gather(*coros, return_exceptions=True)


@pytest.mark.asyncio
async def test_simultaneous_creates_for_one_source_make_one_event():
    shop = await _shop()
    results = await _race(*[_create(shop, source_type="installation", source_id=f"inst-{shop['s']}") for _ in range(6)])
    assert not [r for r in results if isinstance(r, Exception)]
    ids = {r["id"] for r in results}
    assert len(ids) == 1
    assert sum(1 for r in results if r.get("duplicate_prevented")) == 5
    assert await db.calendar_events.count_documents({"tenant_id": shop["tenant_id"], "source_id": f"inst-{shop['s']}"}) == 1


@pytest.mark.parametrize("field,resource", [
    ("assigned_employee_ids", "emp"),
    ("reserved_equipment_ids", "eq"),
    ("reserved_vehicle_ids", "van"),
    ("reserved_resource_ids", "bay"),
])
@pytest.mark.asyncio
async def test_simultaneous_bookings_of_a_single_capacity_resource_admit_one(field, resource):
    shop = await _shop()
    rid = f"{resource}-{shop['s']}"
    results = await _race(*[_create(shop, title=f"Job {i}", **{field: [rid]}) for i in range(5)])
    created = [r for r in results if isinstance(r, dict)]
    rejected = [r for r in results if isinstance(r, CalendarError)]
    assert len(created) == 1, results
    assert len(rejected) == 4 and {e.code for e in rejected} == {"conflict"}
    assert await db.calendar_events.count_documents({"tenant_id": shop["tenant_id"], field: rid}) == 1


@pytest.mark.asyncio
async def test_simultaneous_bookings_of_one_location_admit_one():
    shop = await _shop()
    results = await _race(*[_create(shop, title=f"Site {i}", location="123 Main St") for i in range(4)])
    assert len([r for r in results if isinstance(r, dict)]) == 1


@pytest.mark.asyncio
async def test_capacity_two_resource_admits_two_under_concurrency():
    shop = await _shop()
    rid = f"prep-{shop['s']}"
    results = await _race(*[_create(shop, title=f"Prep {i}", reserved_resource_ids=[rid]) for i in range(5)])
    assert len([r for r in results if isinstance(r, dict)]) == 2
    assert await db.calendar_events.count_documents({"tenant_id": shop["tenant_id"], "reserved_resource_ids": rid}) == 2


@pytest.mark.asyncio
async def test_simultaneous_updates_into_the_same_slot_admit_one():
    shop = await _shop()
    emp = f"emp-{shop['s']}"
    a = await _create(shop, title="A", start_at=_at(8), end_at=_at(9), assigned_employee_ids=[emp])
    b = await _create(shop, title="B", start_at=_at(13), end_at=_at(14), assigned_employee_ids=[emp])

    def move(event):
        return calendar_service.update_event(tenant_id=shop["tenant_id"], event_id=event["id"], actor_user_id="u1",
                                             actor_email="u1@example.com", payload={"start_at": _at(10), "end_at": _at(11)},
                                             action="rescheduled", actor_role="staff")

    results = await _race(move(a), move(b))
    assert len([r for r in results if isinstance(r, dict)]) == 1
    assert [r.code for r in results if isinstance(r, CalendarError)] == ["conflict"]


@pytest.mark.asyncio
async def test_authorized_override_still_allows_an_overlap():
    shop = await _shop()
    bay = f"bay-{shop['s']}"
    await _create(shop, reserved_resource_ids=[bay])
    with pytest.raises(CalendarError) as denied:
        await _create(shop, reserved_resource_ids=[bay], conflict_override_reason="Rush job")
    assert denied.value.code == "conflict_override_forbidden"
    second = await _create(shop, role="manager", reserved_resource_ids=[bay], conflict_override_reason="Rush job")
    assert second["conflicts"] and second["id"]


@pytest.mark.asyncio
async def test_reopen_and_restore_cannot_create_a_second_active_source_event():
    shop = await _shop()
    source = {"source_type": "installation", "source_id": f"inst-{shop['s']}"}
    first = await _create(shop, **source)
    await calendar_service.cancel_event(tenant_id=shop["tenant_id"], event_id=first["id"], actor_user_id="u1", actor_email="u1@example.com")
    second = await _create(shop, start_at=_at(13), end_at=_at(14), **source)  # canceled event released the key
    assert second["id"] != first["id"] and not second.get("duplicate_prevented")
    with pytest.raises(CalendarError) as reopened:
        await calendar_service.reopen_event(tenant_id=shop["tenant_id"], event_id=first["id"], actor_user_id="u1",
                                            actor_email="u1@example.com", reason="Customer rebooked")
    assert reopened.value.code == "duplicate_source_event"
    await calendar_service.archive_event(tenant_id=shop["tenant_id"], event_id=second["id"], actor_user_id="u1", actor_email="u1@example.com")
    third = await _create(shop, start_at=_at(15), end_at=_at(16), **source)
    with pytest.raises(CalendarError) as restored:
        await calendar_service.restore_event(tenant_id=shop["tenant_id"], event_id=second["id"], actor_user_id="u1", actor_email="u1@example.com")
    assert restored.value.code == "duplicate_source_event"
    assert third["id"]


@pytest.mark.asyncio
async def test_existing_duplicates_are_preserved_when_keys_are_backfilled():
    shop = await _shop()
    tid, s = shop["tenant_id"], shop["s"]
    legacy = [{"id": f"dup{i}-{s}", "tenant_id": tid, "title": f"Legacy {i}", "event_type": "installation", "status": "scheduled",
               "archived_at": None, "source_type": "installation", "source_id": f"legacy-{s}", "start_at": _at(9), "end_at": _at(10),
               "created_at": f"2026-01-0{i + 1}T00:00:00+00:00"} for i in range(2)]
    await db.calendar_events.insert_many(legacy)
    report = await calendar_service.backfill_active_source_keys()
    assert report["existing_duplicates_left_unchanged"] >= 1
    docs = [d async for d in db.calendar_events.find({"tenant_id": tid, "source_id": f"legacy-{s}"}, {"_id": 0})]
    assert len(docs) == 2  # nothing deleted
    assert {d["id"]: d.get("active_source_key") for d in docs} == {f"dup0-{s}": f"installation:legacy-{s}", f"dup1-{s}": None}
    await ensure_indexes()  # unique index builds over the preserved records
    again = await _create(shop, start_at=_at(13), end_at=_at(14), source_type="installation", source_id=f"legacy-{s}")
    assert again["duplicate_prevented"] is True


@pytest.mark.asyncio
async def test_locks_and_source_keys_are_tenant_isolated():
    a, b = await _shop(), await _shop()
    results = await _race(_create(a, source_type="installation", source_id="shared-src", assigned_employee_ids=[f"emp-{a['s']}"]),
                          _create(b, source_type="installation", source_id="shared-src", assigned_employee_ids=[f"emp-{b['s']}"]))
    assert all(isinstance(r, dict) and not r.get("duplicate_prevented") for r in results)
    assert await db.schedule_locks.count_documents({"tenant_id": {"$in": [a["tenant_id"], b["tenant_id"]]}}) == 0  # released
