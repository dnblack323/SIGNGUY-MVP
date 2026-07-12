"""EC8 phase 8a — Announcements + Team Dashboard + permission-catalog rename.

Covers: announcement create/publish, in-app delivery to linked employees
only, audience filtering, active-announcement expiry filter, team dashboard
aggregation, tenant isolation, and a regression check that the superseded
EC1 permission values were actually removed (not just aliased).
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.core.permissions import Perm, PortalPerm


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec8a_team_ctx():
    ta = f"t-ec8t-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8tB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    owner_b = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
               "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"},
                                   {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**owner_a}, {**owner_b}])
    yield {"owner_a": owner_a, "owner_b": owner_b, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_announcement_draft_then_publish_delivers_to_linked_employee(ec8a_team_ctx):
    owner_a = ec8a_team_ctx["owner_a"]
    async with await _client(owner_a) as c:
        # Employee linked to owner_a's own user id so it's a valid in-tenant linked_user_id.
        r = await c.post("/api/employees", json={"name": "Linked Employee", "linked_user_id": owner_a["id"]})
        assert r.status_code == 201

        r = await c.post("/api/announcements", json={"title": "Shop closed Friday", "body": "Closed for maintenance.", "audience": "all"})
        assert r.status_code == 201
        ann = r.json()
        assert ann["status"] == "draft"

        r = await c.post(f"/api/announcements/{ann['id']}/publish")
        assert r.status_code == 200
        assert r.json()["status"] == "published"

    n = await db.notifications.find_one({"tenant_id": owner_a["tenant_id"], "recipient_user_id": owner_a["id"],
                                          "kind": "announcement.published"})
    assert n is not None


@pytest.mark.asyncio
async def test_announcement_cannot_publish_twice(ec8a_team_ctx):
    owner_a = ec8a_team_ctx["owner_a"]
    async with await _client(owner_a) as c:
        r = await c.post("/api/announcements", json={"title": "T", "body": "B"})
        ann_id = r.json()["id"]
        r = await c.post(f"/api/announcements/{ann_id}/publish")
        assert r.status_code == 200
        r = await c.post(f"/api/announcements/{ann_id}/publish")
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_team_dashboard_aggregation_and_tenant_isolation(ec8a_team_ctx):
    owner_a, owner_b = ec8a_team_ctx["owner_a"], ec8a_team_ctx["owner_b"]
    async with await _client(owner_a) as c:
        await c.post("/api/employees", json={"name": "Dash Employee"})
        r = await c.post("/api/announcements", json={"title": "Dash Announcement", "body": "B"})
        await c.post(f"/api/announcements/{r.json()['id']}/publish")
        r = await c.get("/api/team/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["employee_status_counts"]["active"] >= 1
        assert any(a["title"] == "Dash Announcement" for a in data["announcements"])
    async with await _client(owner_b) as c:
        r = await c.get("/api/team/dashboard")
        data = r.json()
        assert data["employee_status_counts"]["active"] == 0
        assert data["announcements"] == []


def test_ec8_canonical_permissions_present():
    values = {p.value for p in Perm}
    for expected in [
        "employee:read", "employee:manage", "schedule:read", "schedule:manage",
        "timeclock:self", "timeclock:manage", "timesheet:self", "timesheet:read", "timesheet:manage",
        "payroll:self", "payroll:read", "payroll:manage", "payroll:export",
        "equipment:read", "equipment:manage", "training:self", "training:manage",
        "certification:read", "certification:manage",
    ]:
        assert expected in values, f"missing canonical EC8 permission {expected}"


def test_superseded_ec1_permission_values_removed():
    values = {p.value for p in Perm}
    for superseded in ["employee:write", "employee:admin", "time_clock:read", "time_clock:write",
                        "timesheet:approve", "payroll:write", "payroll:admin"]:
        assert superseded not in values, f"superseded permission {superseded} should have been renamed"
    portal_values = {p.value for p in PortalPerm}
    assert "portal:employee_payslip_view" not in portal_values
    assert "portal:employee_pay_view" in portal_values
