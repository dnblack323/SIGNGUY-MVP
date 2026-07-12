"""EC8 phase 8a — Employee model + service + router tests.

Covers: tenant isolation, permission enforcement, CRUD, linked_user_id
validation (same tenant, uniqueness), status transitions (audit trail,
duplicate-status rejection), status counts.
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
async def ec8a_ctx():
    ta = f"t-ec8a-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8aB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"u-s-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    owner_b = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
               "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"},
                                   {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**owner_a}, {**staff_a}, {**owner_b}])
    yield {"owner_a": owner_a, "staff_a": staff_a, "owner_b": owner_b, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_employee_crud_happy_path(ec8a_ctx):
    owner_a = ec8a_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Jamie Rivera", "role_label": "Install Tech", "hourly_rate_cents": 1800})
        assert r.status_code == 201
        emp = r.json()
        assert emp["status"] == "active"
        assert emp["hourly_rate_cents"] == 1800

        r = await c.get(f"/api/employees/{emp['id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "Jamie Rivera"

        r = await c.patch(f"/api/employees/{emp['id']}", json={"role_label": "Senior Install Tech"})
        assert r.status_code == 200
        assert r.json()["role_label"] == "Senior Install Tech"

        r = await c.get("/api/employees")
        assert r.status_code == 200
        assert any(e["id"] == emp["id"] for e in r.json()["items"])


@pytest.mark.asyncio
async def test_default_hourly_rate_baseline_is_15_dollars(ec8a_ctx):
    owner_a = ec8a_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "No Rate Given"})
        assert r.status_code == 201
        assert r.json()["hourly_rate_cents"] == 1500


@pytest.mark.asyncio
async def test_employee_tenant_isolation(ec8a_ctx):
    owner_a, owner_b = ec8a_ctx["owner_a"], ec8a_ctx["owner_b"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Tenant A Employee"})
        emp_id = r.json()["id"]
    async with await _client(owner_b) as c:
        r = await c.get(f"/api/employees/{emp_id}")
        assert r.status_code == 404
        r = await c.get("/api/employees")
        assert all(e["id"] != emp_id for e in r.json()["items"])


@pytest.mark.asyncio
async def test_staff_role_lacks_employee_manage_by_default(ec8a_ctx):
    staff_a = ec8a_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/employees", json={"name": "Should Fail"})
        assert r.status_code == 403
        r = await c.get("/api/employees")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_linked_user_id_must_belong_to_same_tenant(ec8a_ctx):
    owner_a, owner_b = ec8a_ctx["owner_a"], ec8a_ctx["owner_b"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Cross Tenant Link", "linked_user_id": owner_b["id"]})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_linked_user_id_cannot_be_double_linked(ec8a_ctx):
    owner_a, staff_a = ec8a_ctx["owner_a"], ec8a_ctx["staff_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "First Link", "linked_user_id": staff_a["id"]})
        assert r.status_code == 201
        r = await c.post("/api/employees", json={"name": "Second Link Attempt", "linked_user_id": staff_a["id"]})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_status_transition_records_audit_and_history(ec8a_ctx):
    owner_a = ec8a_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Status Test Employee"})
        emp_id = r.json()["id"]

        r = await c.post(f"/api/employees/{emp_id}/status", json={"status": "suspended", "reason": "Investigation"})
        assert r.status_code == 200
        emp = r.json()
        assert emp["status"] == "suspended"
        assert len(emp["status_history"]) == 1
        assert emp["status_history"][0]["from"] == "active"
        assert emp["status_history"][0]["to"] == "suspended"
        assert emp["status_history"][0]["reason"] == "Investigation"
        assert emp["status_history"][0]["actor_user_id"] == owner_a["id"]

        # Audit event recorded
        r = await c.get("/api/audit", params={"entity_type": "employee", "entity_id": emp_id})
        assert r.status_code == 200
        actions = [e["action"] for e in r.json()["items"]]
        assert "employee.status_change" in actions
        assert "employee.create" in actions


@pytest.mark.asyncio
async def test_duplicate_status_change_rejected(ec8a_ctx):
    owner_a = ec8a_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Dup Status Test"})
        emp_id = r.json()["id"]
        r = await c.post(f"/api/employees/{emp_id}/status", json={"status": "inactive", "reason": "x"})
        assert r.status_code == 200
        r = await c.post(f"/api/employees/{emp_id}/status", json={"status": "inactive", "reason": "x"})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_termination_sets_termination_date(ec8a_ctx):
    owner_a = ec8a_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "Termination Test"})
        emp_id = r.json()["id"]
        r = await c.post(f"/api/employees/{emp_id}/status", json={"status": "terminated", "reason": "role eliminated"})
        assert r.status_code == 200
        assert r.json()["termination_date"] is not None


@pytest.mark.asyncio
async def test_status_counts_reflect_tenant_only(ec8a_ctx):
    owner_a, owner_b = ec8a_ctx["owner_a"], ec8a_ctx["owner_b"]
    async with await _client(owner_a) as c:
        await c.post("/api/employees", json={"name": "Counted Employee"})
        r = await c.get("/api/employees/status-counts")
        assert r.status_code == 200
        counts = r.json()
        assert counts["active"] >= 1
    async with await _client(owner_b) as c:
        r = await c.get("/api/employees/status-counts")
        assert r.json()["active"] == 0


@pytest.mark.asyncio
async def test_employee_requires_auth(ec8a_ctx):
    app.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/employees")
        assert r.status_code == 401
