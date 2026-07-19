"""EC15 - Wrap Lab shared-core contracts."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


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
    tenant_id = f"t-ec15-{suffix}"
    other_tenant_id = f"t-ec15-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    customer = {"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "Wrap Customer", "email": f"cust-{suffix}@example.com"}
    other_customer = {"id": f"cust-other-{suffix}", "tenant_id": other_tenant_id, "name": "Other Customer", "email": f"other-cust-{suffix}@example.com"}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC15 Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other EC15 Tenant"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    await db.customers.insert_many([customer, other_customer])
    yield {
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "customer": customer,
        "other_customer": other_customer,
        "suffix": suffix,
    }
    app.dependency_overrides.pop(get_current_user, None)


async def _create_project(client: AsyncClient, customer_id: str, suffix: str) -> dict:
    vehicle_resp = await client.post(
        "/api/wrap-lab/vehicles",
        json={
            "customer_id": customer_id,
            "year": "2024",
            "make": "Ford",
            "model": "Transit",
            "vehicle_type": "van",
            "template_key": "ford_transit_flat",
            "vin": f"VIN{suffix}",
        },
    )
    assert vehicle_resp.status_code == 201, vehicle_resp.text
    vehicle = vehicle_resp.json()
    project_resp = await client.post(
        "/api/wrap-lab/projects",
        json={
            "customer_id": customer_id,
            "vehicle_id": vehicle["id"],
            "project_name": f"Fleet Van {suffix}",
            "project_type": "partial_wrap",
            "estimate_total_cents": 304000,
            "deposit_required_cents": 100000,
            "material_estimate_cents": 84000,
            "labor_estimate_cents": 220000,
        },
    )
    assert project_resp.status_code == 201, project_resp.text
    return {"vehicle": vehicle, "project": project_resp.json()}


@pytest.mark.asyncio
async def test_wrap_lab_permission_tenant_and_portal_scope(ctx):
    async with await _client_as(ctx["staff"]) as staff_client:
        denied = await staff_client.post("/api/wrap-lab/vehicles", json={"customer_id": ctx["customer"]["id"], "make": "Ford", "model": "Transit"})
        assert denied.status_code == 403

    async with await _client_as(ctx["owner"]) as owner_client:
        built = await _create_project(owner_client, ctx["customer"]["id"], ctx["suffix"])

    async with await _client_as(ctx["other_owner"]) as other_client:
        isolated = await other_client.get(f"/api/wrap-lab/projects/{built['project']['id']}")
        assert isolated.status_code == 404

    token = create_portal_token(portal_identity_id=f"portal-{ctx['suffix']}", tenant_id=ctx["tenant_id"], portal_type="customer")
    async with await _token_client(token) as portal:
        staff_route = await portal.get("/api/wrap-lab/projects")
        assert staff_route.status_code == 401


@pytest.mark.asyncio
async def test_wrap_lab_lifecycle_packets_vector_and_boundaries(ctx):
    before_invoices = await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]})
    before_payments = await db.payments.count_documents({"tenant_id": ctx["tenant_id"]})
    before_entitlements = await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]})
    before_webstore_orders = await db.webstore_buyer_orders.count_documents({"tenant_id": ctx["tenant_id"]})
    before_calendar = await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]})

    async with await _client_as(ctx["owner"]) as owner_client:
        built = await _create_project(owner_client, ctx["customer"]["id"], ctx["suffix"])
        project = built["project"]
        assert project["status"] == "vehicle_recorded"
        assert project["estimate_total_cents"] == 304000

        skip = await owner_client.post(f"/api/wrap-lab/projects/{project['id']}/status", json={"status": "design_in_progress"})
        assert skip.status_code == 409
        advanced = await owner_client.post(f"/api/wrap-lab/projects/{project['id']}/status", json={"status": "measurement_planning"})
        assert advanced.status_code == 200, advanced.text

        coverage = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/coverage-plans",
            json={
                "coverage_level": "partial_wrap",
                "panels": [
                    {"name": "Driver front door", "width_inches": 42, "height_inches": 36, "status": "measured"},
                    {"name": "Passenger front door", "width_inches": 42, "height_inches": 36, "status": "measured"},
                    {"name": "Hood", "width_inches": 65, "height_inches": 50, "status": "measured"},
                ],
            },
        )
        assert coverage.status_code == 201, coverage.text
        assert coverage.json()["total_square_feet"] == 44

        inspection = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/inspections",
            json={
                "inspection_type": "pre_install",
                "status": "ready_for_signature",
                "damage_items": [{"panel": "Driver front door", "type": "scratch", "notes": "Pre-existing"}],
                "signature_request_id": "sigreq-1",
            },
        )
        assert inspection.status_code == 201, inspection.text
        assert inspection.json()["signature_request_id"] == "sigreq-1"

        scene = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/design-scenes",
            json={
                "vehicle_template_key": "ford_transit_flat",
                "layers": [
                    {"id": "template", "type": "vehicle_template", "name": "Template", "locked": True},
                    {"id": "logo-primary", "type": "logo_asset", "name": "Original logo", "locked": True, "source_file_id": "file-logo-svg", "original_format": "svg"},
                    {"id": "background", "type": "shape", "name": "Background", "locked": False},
                ],
            },
        )
        assert scene.status_code == 201, scene.text
        scene_doc = scene.json()
        assert scene_doc["preflight_results"]["passed"] is True
        assert scene_doc["original_asset_file_ids"] == ["file-logo-svg"]

        locked = await owner_client.patch(
            f"/api/wrap-lab/design-scenes/{scene_doc['id']}/layers/logo-primary",
            json={"updates": {"x": 10}},
        )
        assert locked.status_code == 409

        panel_plan = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/panel-plans",
            json={
                "status": "ready_for_production",
                "printer_max_width_inches": 54,
                "panels": [
                    {"name": "Driver side", "width_inches": 196, "height_inches": 70},
                    {"name": "Rear", "width_inches": 72, "height_inches": 64},
                ],
                "material_cost_cents": 84000,
                "labor_cost_cents": 220000,
            },
        )
        assert panel_plan.status_code == 201, panel_plan.text
        export_labels = [p["label"] for p in panel_plan.json()["export_manifest"]["panels"]]
        assert export_labels[:2] == ["Panel 1A", "Panel 1B"]
        assert panel_plan.json()["material_cost_cents"] == 84000

        schedule = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/schedules",
            json={
                "schedule_type": "install",
                "title": "Install",
                "start_at": "2026-07-20T09:00:00Z",
                "end_at": "2026-07-20T13:00:00Z",
                "calendar_event_id": "cal-local-reference",
            },
        )
        assert schedule.status_code == 201, schedule.text
        assert schedule.json()["calendar_event_id"] == "cal-local-reference"

        warranty = await owner_client.post(
            f"/api/wrap-lab/projects/{project['id']}/warranties",
            json={"status": "active", "coverage_terms": ["Workmanship"], "care_instructions": ["Avoid pressure washing"], "warranty_value_cents": 0},
        )
        assert warranty.status_code == 201, warranty.text

        packet_one = await owner_client.post(f"/api/wrap-lab/projects/{project['id']}/packets", json={"packet_type": "pre_install"})
        assert packet_one.status_code == 201, packet_one.text
        assert packet_one.json()["revision"] == 1
        assert packet_one.json()["layout_contract"]["style"] == "clean_white_card_packet"
        packet_two = await owner_client.post(f"/api/wrap-lab/projects/{project['id']}/packets", json={"packet_type": "pre_install"})
        assert packet_two.status_code == 201, packet_two.text
        assert packet_two.json()["revision"] == 2

        original_packet = await db.wrap_packets.find_one({"tenant_id": ctx["tenant_id"], "id": packet_one.json()["id"]}, {"_id": 0})
        assert original_packet["revision"] == 1
        assert original_packet["snapshot"]["financial_summary"]["estimate_total_cents"] == 304000

        detail = await owner_client.get(f"/api/wrap-lab/projects/{project['id']}")
        assert detail.status_code == 200
        assert len(detail.json()["coverage_plans"]) == 1
        assert len(detail.json()["packets"]) == 2

    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before_invoices
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before_payments
    assert await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}) == before_entitlements
    assert await db.webstore_buyer_orders.count_documents({"tenant_id": ctx["tenant_id"]}) == before_webstore_orders
    assert await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]}) == before_calendar
