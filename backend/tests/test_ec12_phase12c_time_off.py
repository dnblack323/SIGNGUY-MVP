"""EC12 Phase 12C - employee time-off and absence workflow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services.portal_identity import create_portal_identity
from server import app


def _iso(days: int, hour: int = 9) -> str:
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d.isoformat()


def _date(days: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}
    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec12c-{suffix}"
    other_tenant_id = f"t-ec12c-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    employee = {"id": f"emp-{suffix}", "tenant_id": tenant_id, "name": "Alex Maker", "email": f"alex-{suffix}@example.com", "linked_user_id": staff["id"], "status": "active"}
    inactive = {"id": f"inactive-{suffix}", "tenant_id": tenant_id, "name": "Inactive", "email": f"inactive-{suffix}@example.com", "status": "inactive"}
    other_employee = {"id": f"emp-other-{suffix}", "tenant_id": other_tenant_id, "name": "Other Emp", "status": "active"}
    await db.employees.insert_many([employee, inactive, other_employee])
    schedule_id = f"schedule-{suffix}"
    await db.schedules.insert_one({"id": schedule_id, "tenant_id": tenant_id, "period_start": _date(1), "period_end": _date(7), "status": "published", "version": 1, "created_by": owner["id"], "updated_by": owner["id"]})
    await db.shifts.insert_one({"id": f"shift-{suffix}", "tenant_id": tenant_id, "schedule_id": schedule_id, "employee_id": employee["id"], "shift_date": _date(1), "start_at": _iso(1, 9), "end_at": _iso(1, 17), "status": "scheduled", "created_by": owner["id"], "updated_by": owner["id"]})
    identity = await create_portal_identity(tenant_id=tenant_id, portal_type="employee", employee_id=employee["id"], email=f"portal-{suffix}@example.com")
    inactive_identity = await create_portal_identity(tenant_id=tenant_id, portal_type="employee", employee_id=inactive["id"], email=f"inactive-portal-{suffix}@example.com")
    other_identity = await create_portal_identity(tenant_id=other_tenant_id, portal_type="employee", employee_id=other_employee["id"], email=f"other-portal-{suffix}@example.com")
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "staff": staff, "other_owner": other_owner,
        "employee": employee, "inactive": inactive,
        "token": create_portal_token(portal_identity_id=identity["id"], tenant_id=tenant_id, portal_type="employee", employee_id=employee["id"]),
        "inactive_token": create_portal_token(portal_identity_id=inactive_identity["id"], tenant_id=tenant_id, portal_type="employee", employee_id=inactive["id"]),
        "other_token": create_portal_token(portal_identity_id=other_identity["id"], tenant_id=other_tenant_id, portal_type="employee", employee_id=other_employee["id"]),
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_employee_request_review_clarification_cancel_and_security(ctx):
    before = {
        "payroll": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "shifts": await db.shifts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _token_client(ctx["token"]) as c:
        create = await c.post("/api/portal/employee/time-off", json={
            "request_type": "vacation",
            "start_at": _iso(1, 10),
            "end_at": _iso(1, 15),
            "reason": "Family appointment",
            "private_reason": "Private detail",
        })
        assert create.status_code == 201
        request = create.json()
        assert request["status"] == "pending"
        assert request["private_reason"] == "Private detail"
        assert any(conf["source_type"] == "shift" for conf in request["conflicts"])
        own = await c.get("/api/portal/employee/time-off")
        assert [r["id"] for r in own.json()["items"]] == [request["id"]]
        assert (await c.get("/api/time-off")).status_code == 401

    async with await _token_client(ctx["inactive_token"]) as c:
        denied = await c.post("/api/portal/employee/time-off", json={"start_at": _iso(2, 9), "end_at": _iso(2, 17)})
        assert denied.status_code == 400

    async with await _client_as(ctx["owner"]) as c:
        manager_list = await c.get("/api/time-off")
        assert manager_list.status_code == 200
        assert manager_list.json()["items"][0]["private_reason"] == "Private detail"
        clarify = await c.post(f"/api/time-off/{request['id']}/clarification", json={"note": "Which hours?"})
        assert clarify.status_code == 200
        assert clarify.json()["status"] == "clarification_requested"

    async with await _token_client(ctx["token"]) as c:
        detail = (await c.get(f"/api/portal/employee/time-off/{request['id']}")).json()
        assert detail["manager_note"] == "Which hours?"
        response = await c.post(f"/api/portal/employee/time-off/{request['id']}/clarification", json={"response": "10 to 3 only"})
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    async with await _client_as(ctx["owner"]) as c:
        approved = await c.post(f"/api/time-off/{request['id']}/approve", json={"note": "Approved"})
        assert approved.status_code == 200
        duplicate = await c.post(f"/api/time-off/{request['id']}/approve", json={"note": "duplicate"})
        assert duplicate.status_code == 200
        invalid = await c.post(f"/api/time-off/{request['id']}/deny", json={"note": "Too late"})
        assert invalid.status_code == 400
        feed = await c.get("/api/calendar/feed", params={"start_at": _iso(1, 0), "end_at": _iso(2, 0)})
        assert any(item["source_type"] == "time_off_request" and item["source_id"] == request["id"] for item in feed.json()["items"])
        safe_feed = feed.json()["items"]
        assert all("private_reason" not in item for item in safe_feed)

    async with await _token_client(ctx["other_token"]) as c:
        assert (await c.get(f"/api/portal/employee/time-off/{request['id']}")).status_code in {403, 404}

    async with await _token_client(ctx["token"]) as c:
        canceled = await c.post(f"/api/portal/employee/time-off/{request['id']}/cancel", json={"reason": "No longer needed"})
        assert canceled.status_code == 200
        assert canceled.json()["status"] == "canceled"

    after = {
        "payroll": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "shifts": await db.shifts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
    assert await db.activity_events.count_documents({"tenant_id": ctx["tenant_id"], "entity_type": "time_off_request"}) >= 4
    assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "module": "time_off"}) >= 1

