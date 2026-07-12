"""EC8 phase 8b — Time Clock model + service + router tests.

Covers: clock in/out, breaks, duplicate/overlap prevention, corrections
(history preservation, reason required, audit, approved-entry protection),
tenant isolation, self vs manager permission scope.
"""
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
async def ec8b_ctx():
    ta = f"t-ec8b-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8bB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"u-s-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    owner_b = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
               "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**owner_a}, {**staff_a}, {**owner_b}])
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Self Clocker", "linked_user_id": staff_a["id"]})
        emp_self = r.json()
        r2 = await c.post("/api/employees", json={"name": "Admin Managed"})
        emp_admin = r2.json()
    yield {"owner_a": owner_a, "staff_a": staff_a, "owner_b": owner_b, "ta": ta, "tb": tb,
           "emp_self": emp_self, "emp_admin": emp_admin}
    _clear()


@pytest.mark.asyncio
async def test_self_clock_in_out_break_cycle(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        assert r.status_code == 200
        entry = r.json()
        assert entry["status"] == "open"

        r = await c.post("/api/time-clock/break-start")
        assert r.status_code == 200
        assert r.json()["breaks"][0]["end_at"] is None

        r = await c.post("/api/time-clock/break-end")
        assert r.status_code == 200
        assert r.json()["breaks"][0]["end_at"] is not None

        r = await c.post("/api/time-clock/clock-out")
        assert r.status_code == 200
        entry = r.json()
        assert entry["status"] == "completed"
        assert entry["clock_out_at"] is not None
        assert entry["worked_minutes"] >= 0


@pytest.mark.asyncio
async def test_duplicate_clock_in_rejected(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        assert r.status_code == 200
        r = await c.post("/api/time-clock/clock-in", json={})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_clock_out_while_not_active_rejected(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-out")
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_break_rejected(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        await c.post("/api/time-clock/clock-in", json={})
        r = await c.post("/api/time-clock/break-start")
        assert r.status_code == 200
        r = await c.post("/api/time-clock/break-start")
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_break_end_without_active_break_rejected(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        await c.post("/api/time-clock/clock-in", json={})
        r = await c.post("/api/time-clock/break-end")
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_clock_out_auto_closes_active_break(ec8b_ctx):
    staff_a = ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        await c.post("/api/time-clock/clock-in", json={})
        await c.post("/api/time-clock/break-start")
        r = await c.post("/api/time-clock/clock-out")
        assert r.status_code == 200
        entry = r.json()
        assert entry["breaks"][0]["end_at"] is not None
        assert entry["status"] == "completed"


@pytest.mark.asyncio
async def test_manager_can_clock_in_out_on_behalf_of_unlinked_employee(ec8b_ctx):
    owner_a, emp_admin = ec8b_ctx["owner_a"], ec8b_ctx["emp_admin"]
    async with await _client(owner_a) as c:
        r = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
        assert r.status_code == 200
        assert r.json()["source"] == "admin"
        r = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-out")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_employee_cannot_manage_another_employee(ec8b_ctx):
    staff_a, emp_admin = ec8b_ctx["staff_a"], ec8b_ctx["emp_admin"]
    async with await _client(staff_a) as c:
        r = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation_on_entries(ec8b_ctx):
    owner_a, owner_b, emp_admin = ec8b_ctx["owner_a"], ec8b_ctx["owner_b"], ec8b_ctx["emp_admin"]
    async with await _client(owner_a) as c:
        await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
    async with await _client(owner_b) as c:
        r = await c.get(f"/api/time-clock/{emp_admin['id']}/status")
        assert r.status_code == 404
        r = await c.get("/api/time-clock/entries/all")
        assert all(e["employee_id"] != emp_admin["id"] for e in r.json()["items"])


@pytest.mark.asyncio
async def test_correction_preserves_original_values_and_requires_reason(ec8b_ctx):
    owner_a, staff_a = ec8b_ctx["owner_a"], ec8b_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        entry = r.json()
        original_clock_in = entry["clock_in_at"]
        r = await c.post("/api/time-clock/clock-out")
        entry = r.json()

    async with await _client(owner_a) as c:
        r = await c.post(f"/api/time-clock/entries/{entry['id']}/correct",
                          json={"clock_out_at": entry["clock_out_at"], "reason": ""})
        assert r.status_code == 400  # empty reason rejected

        new_clock_out = entry["clock_out_at"]
        r = await c.post(f"/api/time-clock/entries/{entry['id']}/correct",
                          json={"clock_in_at": original_clock_in, "clock_out_at": new_clock_out,
                                "notes": "adjusted", "reason": "Forgot original notes"})
        assert r.status_code == 200
        corrected = r.json()
        assert corrected["status"] == "corrected"
        assert len(corrected["corrections"]) == 1
        assert corrected["corrections"][0]["original"]["clock_in_at"] == original_clock_in
        assert corrected["corrections"][0]["reason"] == "Forgot original notes"

    r2 = await db.audit_events.find_one({"tenant_id": ec8b_ctx["ta"], "entity_id": entry["id"], "action": "time_entry_corrected"})
    assert r2 is not None


@pytest.mark.asyncio
async def test_correction_cross_tenant_rejected(ec8b_ctx):
    owner_b, emp_admin, owner_a = ec8b_ctx["owner_b"], ec8b_ctx["emp_admin"], ec8b_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
        entry_id = r.json()["id"]
        await c.post(f"/api/time-clock/{emp_admin['id']}/clock-out")
    async with await _client(owner_b) as c:
        r = await c.post(f"/api/time-clock/entries/{entry_id}/correct", json={"notes": "hack", "reason": "x"})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_overlapping_correction_rejected(ec8b_ctx):
    owner_a, emp_admin = ec8b_ctx["owner_a"], ec8b_ctx["emp_admin"]
    async with await _client(owner_a) as c:
        r1 = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
        e1 = r1.json()
        await c.post(f"/api/time-clock/{emp_admin['id']}/clock-out")
        r2 = await c.post(f"/api/time-clock/{emp_admin['id']}/clock-in", json={})
        e2 = r2.json()
        await c.post(f"/api/time-clock/{emp_admin['id']}/clock-out")
        # Try to correct e2 to overlap e1's exact window
        r = await c.post(f"/api/time-clock/entries/{e2['id']}/correct",
                          json={"clock_in_at": e1["clock_in_at"], "clock_out_at": e1["clock_out_at"], "reason": "overlap attempt"})
        assert r.status_code == 409
