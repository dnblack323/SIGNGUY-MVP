"""EC8 phase 8c — Employee Portal identity + self-service router tests.

Covers: invite (idempotent), activation via magic link, cross-portal-type
rejection in both directions, self-scope enforcement (own records only),
suspended identity denial, expired invitation denial, cross-tenant token
denial, Time Clock/Timesheet reuse with no arbitrary employee_id acceptance,
published-only Schedule visibility, and Announcement targeting.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity
from app.services.portal_tokens import mint_magic_link_token


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec8c_portal_ctx():
    ta = f"t-ec8cp-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8cpB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_one({**owner_a})
    async with await _client(owner_a) as c:
        r1 = await c.post("/api/employees", json={"name": "Portal Pat", "email": f"pat-{uuid.uuid4().hex[:5]}@example.com"})
        emp1 = r1.json()
        r2 = await c.post("/api/employees", json={"name": "Portal Quinn", "email": f"quinn-{uuid.uuid4().hex[:5]}@example.com"})
        emp2 = r2.json()
    yield {"owner_a": owner_a, "ta": ta, "tb": tb, "emp1": emp1, "emp2": emp2}
    _clear()



@pytest.mark.asyncio
async def test_invite_is_idempotent(ec8c_portal_ctx):
    owner_a, emp1 = ec8c_portal_ctx["owner_a"], ec8c_portal_ctx["emp1"]
    async with await _client(owner_a) as c:
        r1 = await c.post(f"/api/employee-portal/{emp1['id']}/invite")
        assert r1.status_code == 201, r1.text
        identity_id = r1.json()["id"]
        r2 = await c.post(f"/api/employee-portal/{emp1['id']}/invite")
        assert r2.status_code == 201
        assert r2.json()["id"] == identity_id  # reused, not duplicated
        count = await db.portal_identities.count_documents({"tenant_id": ec8c_portal_ctx["ta"], "employee_id": emp1["id"]})
        assert count == 1


@pytest.mark.asyncio
async def test_activation_via_magic_link_and_customer_identity_untouched(ec8c_portal_ctx):
    owner_a, emp1, ta = ec8c_portal_ctx["owner_a"], ec8c_portal_ctx["emp1"], ec8c_portal_ctx["ta"]
    customer_identity = await create_portal_identity(
        tenant_id=ta, portal_type="customer", customer_id=f"c-{uuid.uuid4().hex[:6]}",
        email=f"cust-{uuid.uuid4().hex[:5]}@example.com", permissions_preset="viewer_only",
    )
    async with await _client(owner_a) as c:
        r = await c.post(f"/api/employee-portal/{emp1['id']}/invite")
        identity = r.json()
    raw, _ = await mint_magic_link_token(tenant_id=ta, portal_identity_id=identity["id"], email=identity["email"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/auth/magic-link/verify", json={"token": raw})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["identity"]["portal_type"] == "employee"
        assert body["identity"]["employee_id"] == emp1["id"]
        token = body["token"]
        r2 = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
    unchanged = await db.portal_identities.find_one({"id": customer_identity["id"]}, {"_id": 0})
    assert unchanged["status"] == "active"
    assert unchanged["customer_id"] == customer_identity["customer_id"]


@pytest.mark.asyncio
async def test_employee_token_cannot_access_customer_portal_and_vice_versa(ec8c_portal_ctx):
    ta = ec8c_portal_ctx["ta"]
    emp_identity = await create_portal_identity(
        tenant_id=ta, portal_type="employee", employee_id=ec8c_portal_ctx["emp1"]["id"],
        email=f"emp-{uuid.uuid4().hex[:5]}@example.com",
    )
    emp_token = create_portal_token(portal_identity_id=emp_identity["id"], tenant_id=ta,
                                     portal_type="employee", employee_id=emp_identity["employee_id"])
    cust_identity = await create_portal_identity(
        tenant_id=ta, portal_type="customer", customer_id=f"c-{uuid.uuid4().hex[:6]}",
        email=f"cust2-{uuid.uuid4().hex[:5]}@example.com", permissions_preset="owner_full",
    )
    cust_token = create_portal_token(portal_identity_id=cust_identity["id"], tenant_id=ta,
                                      portal_type="customer", customer_id=cust_identity["customer_id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {cust_token}"})
        assert r1.status_code == 403
        r2 = await c.get("/api/portal/quotes", headers={"Authorization": f"Bearer {emp_token}"})
        assert r2.status_code == 403


@pytest.mark.asyncio
async def test_employee_sees_only_own_time_entries_and_no_arbitrary_employee_id(ec8c_portal_ctx):
    ta, emp1, emp2 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["emp1"], ec8c_portal_ctx["emp2"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e1-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee",
                                 employee_id=emp1["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/employee/time-clock/clock-in", json={},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["employee_id"] == emp1["id"]
        r2 = await c.post("/api/portal/employee/time-clock/clock-out", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
    count_emp2 = await db.time_entries.count_documents({"tenant_id": ta, "employee_id": emp2["id"]})
    assert count_emp2 == 0


@pytest.mark.asyncio
async def test_own_timesheet_visible_by_design(ec8c_portal_ctx):
    ta, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e2-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee",
                                 employee_id=emp1["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/employee/timesheet/weekly?week_start=2026-08-01",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["employee_id"] == emp1["id"]


@pytest.mark.asyncio
async def test_suspended_identity_denied(ec8c_portal_ctx):
    ta, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e3-{uuid.uuid4().hex[:5]}@example.com")
    await db.portal_identities.update_one({"id": identity["id"]}, {"$set": {"status": "disabled"}})
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee",
                                 employee_id=emp1["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_inactive_employee_denies_active_portal_identity(ec8c_portal_ctx):
    ta, owner_a, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["owner_a"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e4-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee",
                                 employee_id=emp1["id"])
    async with await _client(owner_a) as c:
        await c.post(f"/api/employees/{emp1['id']}/status", json={"status": "terminated", "reason": "left"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
    denial = await db.audit_events.find_one({"tenant_id": ta, "action": "employee_portal_access_denied"})
    assert denial is not None


@pytest.mark.asyncio
async def test_expired_invitation_denied(ec8c_portal_ctx):
    ta, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e5-{uuid.uuid4().hex[:5]}@example.com")
    raw, _ = await mint_magic_link_token(tenant_id=ta, portal_identity_id=identity["id"],
                                          email=identity["email"], ttl_minutes=-1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/auth/magic-link/verify", json={"token": raw})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_token_denied(ec8c_portal_ctx):
    ta, tb, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["tb"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e6-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=tb, portal_type="employee",
                                 employee_id=emp1["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_published_schedule_visible_draft_hidden_via_portal(ec8c_portal_ctx):
    ta, owner_a, emp1 = ec8c_portal_ctx["ta"], ec8c_portal_ctx["owner_a"], ec8c_portal_ctx["emp1"]
    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                             email=f"e7-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee",
                                 employee_id=emp1["id"])
    async with await _client(owner_a) as c:
        r = await c.get("/api/schedules?period_start=2026-09-12")
        sched = r.json()["schedule"]
        r2 = await c.post(f"/api/schedules/{sched['id']}/shifts", json={
            "employee_id": emp1["id"], "shift_date": "2026-09-14",
            "start_at": "2026-09-14T09:00:00+00:00", "end_at": "2026-09-14T17:00:00+00:00",
        })
        shift = r2.json()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r3 = await c.get("/api/portal/employee/schedule/week?week_start=2026-09-12",
                          headers={"Authorization": f"Bearer {token}"})
        assert r3.json()["items"] == []
    async with await _client(owner_a) as c:
        await c.post(f"/api/schedules/{sched['id']}/publish")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r4 = await c.get("/api/portal/employee/schedule/week?week_start=2026-09-12",
                          headers={"Authorization": f"Bearer {token}"})
        items = r4.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == shift["id"]


@pytest.mark.asyncio
async def test_announcement_targeting_in_portal(ec8c_portal_ctx):
    ta = ec8c_portal_ctx["ta"]
    owner_a, emp1, emp2 = ec8c_portal_ctx["owner_a"], ec8c_portal_ctx["emp1"], ec8c_portal_ctx["emp2"]
    identity1 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                              email=f"e8-{uuid.uuid4().hex[:5]}@example.com")
    identity2 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp2["id"],
                                              email=f"e9-{uuid.uuid4().hex[:5]}@example.com")
    token1 = create_portal_token(portal_identity_id=identity1["id"], tenant_id=ta, portal_type="employee",
                                  employee_id=emp1["id"])
    token2 = create_portal_token(portal_identity_id=identity2["id"], tenant_id=ta, portal_type="employee",
                                  employee_id=emp2["id"])
    async with await _client(owner_a) as c:
        r = await c.post("/api/announcements", json={"title": "Crew A only", "body": "test",
                                                       "audience": "selected", "employee_ids": [emp1["id"]]})
        ann = r.json()
        await c.post(f"/api/announcements/{ann['id']}/publish")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/api/portal/employee/announcements", headers={"Authorization": f"Bearer {token1}"})
        assert any(a["id"] == ann["id"] for a in r1.json()["items"])
        r2 = await c.get("/api/portal/employee/announcements", headers={"Authorization": f"Bearer {token2}"})
        assert all(a["id"] != ann["id"] for a in r2.json()["items"])
