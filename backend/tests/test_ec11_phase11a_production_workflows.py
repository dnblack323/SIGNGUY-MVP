"""EC11 Phase 11A - production workflow definitions and stage contracts."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from app.services import production_workflow_service as svc
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str):
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    ta, tb = f"t-ec11a-{suffix}", f"t-ec11a-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": ta, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": ta, "email": f"staff-{suffix}@example.com", "full_name": "Staff", "role": "staff", "password_hash": "x", "is_active": True}
    other_owner = {"id": f"owner-other-{suffix}", "tenant_id": tb, "email": f"owner-other-{suffix}@example.com", "full_name": "Other", "role": "owner", "password_hash": "x", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "Tenant A"}, {"id": tb, "slug": tb, "name": "Tenant B"}])
    await db.users.insert_many([owner, staff, other_owner])
    yield {"tenant_id": ta, "other_tenant_id": tb, "owner": owner, "staff": staff, "other_owner": other_owner}
    _clear()


@pytest.mark.asyncio
async def test_starter_seeding_default_category_resolution_and_no_workflow_fallback(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        first = await c.get("/api/production-workflows")
        assert first.status_code == 200, first.text
        items = first.json()["items"]
        assert len(items) >= 9
        assert sum(1 for w in items if w["is_tenant_default"]) == 1
        assert {w["workflow_key"] for w in items} >= {
            "starter_general_sign_production",
            "starter_banner_production",
            "starter_rigid_sign_panel",
            "starter_custom_manual",
        }
        before_count = await db.production_workflows.count_documents({"tenant_id": ctx["tenant_id"]})

        starter = next(w for w in items if w["workflow_key"] == "starter_general_sign_production")
        await db.production_workflows.update_one(
            {"id": starter["id"], "tenant_id": ctx["tenant_id"]},
            {"$set": {"description": "tenant local note"}},
        )
        second = await c.get("/api/production-workflows")
        assert second.status_code == 200
        assert await db.production_workflows.count_documents({"tenant_id": ctx["tenant_id"]}) == before_count
        assert next(w for w in second.json()["items"] if w["id"] == starter["id"])["description"] == "tenant local note"

        banner = await c.get("/api/production-workflows/resolve", params={"category_id": "banners"})
        assert banner.status_code == 200
        assert banner.json()["source"] == "category"
        assert banner.json()["workflow"]["workflow_key"] == "starter_banner_production"

        fallback = await c.get("/api/production-workflows/resolve", params={"category_id": "unknown_category"})
        assert fallback.status_code == 200
        assert fallback.json()["source"] == "tenant_default"

    empty = await svc.resolve_workflow(tenant_id=f"empty-{uuid.uuid4().hex}", category_id="banners", seed=False)
    assert empty == {"source": "manual_no_workflow", "workflow": None}


@pytest.mark.asyncio
async def test_crud_duplicate_stage_mutations_category_assignment_and_audit(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        bad = await c.post("/api/production-workflows", json={
            "name": "Bad workflow",
            "workflow_key": "bad_workflow",
            "stages": [
                {"stage_key": "print", "display_name": "Print", "sequence": 1},
                {"stage_key": "print", "display_name": "Print again", "sequence": 2},
            ],
        })
        assert bad.status_code == 409

        created = await c.post("/api/production-workflows", json={
            "name": "Custom Flow",
            "workflow_key": "custom_flow",
            "stages": [
                {"stage_key": "design", "display_name": "Design", "sequence": 1},
                {"stage_key": "print", "display_name": "Print", "sequence": 2, "default_role": "Production"},
            ],
        })
        assert created.status_code == 201, created.text
        wid = created.json()["id"]

        dup = await c.post(f"/api/production-workflows/{wid}/duplicate", json={"name": "Custom Flow Copy"})
        assert dup.status_code == 201, dup.text
        copy_id = dup.json()["id"]
        patched = await c.patch(f"/api/production-workflows/{copy_id}", json={"name": "Edited Copy", "description": "copy only"})
        assert patched.status_code == 200
        source = await c.get(f"/api/production-workflows/{wid}")
        assert source.json()["name"] == "Custom Flow"
        assert source.json().get("description") is None

        added = await c.post(f"/api/production-workflows/{copy_id}/stages", json={"stage_key": "laminate", "display_name": "Laminate"})
        assert added.status_code == 200, added.text
        assert [s["stage_key"] for s in added.json()["stages"] if s["active"]] == ["design", "print", "laminate"]

        updated = await c.patch(f"/api/production-workflows/{copy_id}/stages/laminate", json={"display_name": "Laminate / Finish", "requires_reason_to_skip": True})
        assert updated.status_code == 200
        assert next(s for s in updated.json()["stages"] if s["stage_key"] == "laminate")["requires_reason_to_skip"] is True

        invalid_order = await c.post(f"/api/production-workflows/{copy_id}/stages/reorder", json={"stage_keys": ["print", "design"]})
        assert invalid_order.status_code == 400
        ordered = await c.post(f"/api/production-workflows/{copy_id}/stages/reorder", json={"stage_keys": ["print", "design", "laminate"]})
        assert ordered.status_code == 200
        assert [s["stage_key"] for s in ordered.json()["stages"] if s["active"]] == ["print", "design", "laminate"]

        archived_stage = await c.post(f"/api/production-workflows/{copy_id}/stages/laminate/archive")
        assert archived_stage.status_code == 200
        assert next(s for s in archived_stage.json()["stages"] if s["stage_key"] == "laminate")["active"] is False

        assigned = await c.post(f"/api/production-workflows/{copy_id}/assign-category", json={"category_ids": ["banners", "rigid_signs"]})
        assert assigned.status_code == 200
        assert assigned.json()["category_ids"] == ["banners", "rigid_signs"]
        resolved = await c.get("/api/production-workflows/resolve", params={"category_id": "banners"})
        assert resolved.json()["workflow"]["id"] == copy_id

        defaulted = await c.post(f"/api/production-workflows/{copy_id}/set-default")
        assert defaulted.status_code == 200
        assert defaulted.json()["is_tenant_default"] is True

        archived = await c.post(f"/api/production-workflows/{copy_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["active"] is False
        restored = await c.post(f"/api/production-workflows/{copy_id}/restore")
        assert restored.status_code == 200
        assert restored.json()["active"] is True

    actions = {a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_type": "production_workflow"}, {"_id": 0})}
    assert {
        "production_workflow.created",
        "production_workflow.duplicated",
        "production_workflow.updated",
        "production_workflow.stage_added",
        "production_workflow.stage_updated",
        "production_workflow.stage_reordered",
        "production_workflow.stage_archived",
        "production_workflow.category_assignment_changed",
        "production_workflow.tenant_default_changed",
        "production_workflow.archived",
        "production_workflow.restored",
    } <= actions


@pytest.mark.asyncio
async def test_permissions_portal_denial_tenant_isolation_and_no_live_side_effects(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        created = await c.post("/api/production-workflows", json={
            "name": "Tenant A Workflow",
            "workflow_key": "tenant_a_workflow",
            "stages": [{"stage_key": "design", "display_name": "Design", "sequence": 1}],
        })
        assert created.status_code == 201
        wid = created.json()["id"]

    async with await _staff_client(ctx["staff"]) as c:
        read = await c.get("/api/production-workflows")
        assert read.status_code == 200
        blocked = await c.post("/api/production-workflows", json={"name": "Nope"})
        assert blocked.status_code == 403

    async with await _staff_client(ctx["other_owner"]) as c:
        isolated = await c.get(f"/api/production-workflows/{wid}")
        assert isolated.status_code == 404

    employee_portal_token = create_access_token(
        subject="portal-employee", tenant_id=ctx["tenant_id"], extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "employee"},
    )
    async with await _token_client(employee_portal_token) as c:
        denied = await c.get("/api/production-workflows")
        assert denied.status_code == 401

    customer_portal_token = create_access_token(
        subject="portal-customer", tenant_id=ctx["tenant_id"], extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "customer"},
    )
    async with await _token_client(customer_portal_token) as c:
        denied = await c.get("/api/production-workflows")
        assert denied.status_code == 401

    assert await db.work_order_stages.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
