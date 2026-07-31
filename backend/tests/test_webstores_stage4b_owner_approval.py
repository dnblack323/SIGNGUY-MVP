"""Webstores Connected Batch 2 owner approval and launch-readiness contracts."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import storage
from app.services.entitlements import _upsert_entitlement_for_tests
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _portal_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
async def stage4b_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage4b-{suffix}"
    other_tenant_id = f"t-webstore-stage4b-other-{suffix}"
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    other_staff = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([staff, other_staff])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="webstores", enabled=True)
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "staff": staff, "other_staff": other_staff}
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_setup_file(ctx: dict, webstore_id: str) -> dict:
    file_id = f"file-{uuid.uuid4().hex}"
    storage_key = f"tests/{ctx['tenant_id']}/{file_id}.png"
    storage.put_bytes(storage_key, b"stage4b-image", "image/png")
    doc = {
        "id": file_id,
        "tenant_id": ctx["tenant_id"],
        "webstore_id": webstore_id,
        "category": "product_image",
        "file_name": "product.png",
        "extension": "png",
        "content_type": "image/png",
        "detected_content_type": "image/png",
        "size_bytes": 13,
        "storage_key": storage_key,
        "uploaded_by_actor_type": "staff",
        "status": "active",
        "version": 1,
        "safe_preview_available": True,
        "inline_preview_allowed": True,
        "private_download_only": False,
        "svg_sanitized": True,
    }
    await db.webstore_setup_files.insert_one(doc)
    return doc


async def _create_ready_store(client: AsyncClient, ctx: dict) -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Store Owner {ctx['suffix']}", "email": f"webstore-owner-{ctx['suffix']}@example.com"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    owner = owner_resp.json()
    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": owner["id"],
            "name": f"Batch 2 Store {ctx['suffix']}",
            "slug": f"batch2-store-{ctx['suffix']}",
            "store_type": "fundraiser",
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    store = store_resp.json()
    category_resp = await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": "Spirit Wear"})
    assert category_resp.status_code == 201, category_resp.text
    image = await _seed_setup_file(ctx, store["id"])
    product_resp = await client.post(
        f"/api/webstores/{store['id']}/products",
        json={
            "name": "Owner Review Shirt",
            "product_type": "shirt",
            "category_id": category_resp.json()["id"],
            "selling_price_cents": 2500,
            "production_cost_cents": 900,
            "store_owner_share_cents": 300,
            "sku": "OWNER-SHIRT",
            "customer_images": {"primary": {"file_id": image["id"], "alt_text": "Owner review shirt"}},
            "launch_packet_eligible": True,
            "launch_packet_include": True,
            "status": "ready",
        },
    )
    assert product_resp.status_code == 201, product_resp.text
    return {"owner": owner, "store": store, "product": product_resp.json()}


@pytest.mark.asyncio
async def test_owner_packet_terms_change_request_and_invalidation_are_versioned(stage4b_ctx):
    async with await _client_as(stage4b_ctx["staff"]) as client:
        built = await _create_ready_store(client, stage4b_ctx)
        store = built["store"]
        owner_identity = await db.portal_identities.find_one({"id": built["owner"]["portal_identity_id"]}, {"_id": 0})
        owner_token = create_portal_token(portal_identity_id=owner_identity["id"], tenant_id=stage4b_ctx["tenant_id"], portal_type="webstore_owner")

        initial_readiness = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert initial_readiness["checks"]["included_products_ready"] is True
        assert initial_readiness["checks"]["packet_generated"] is False
        assert initial_readiness["public_launch_blocked_until_batch_3"] is False

        packet_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets", json={"promotion_copy": "Review the booster launch."})
        assert packet_resp.status_code == 201, packet_resp.text
        packet_v1 = packet_resp.json()
        assert packet_v1["version"] == 1
        assert packet_v1["snapshot"]["products"][0]["selling_price_cents"] == 2500
        assert "production_cost_cents" not in str(packet_v1["snapshot"])
        assert "supplier_source_info" not in str(packet_v1["snapshot"])
        assert "storage_key" not in str(packet_v1["snapshot"])

        delivered = await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet_v1['id']}/send")
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["status"] == "delivered"
        retry = await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet_v1['id']}/send")
        assert retry.status_code == 200
        assert await db.webstore_launch_packets.count_documents({"tenant_id": stage4b_ctx["tenant_id"], "webstore_id": store["id"]}) == 1

    async with await _portal_client(owner_token) as portal:
        detail = await portal.get(f"/api/portal/webstores/{store['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["launch_packet"]["version"] == 1
        assert "production_cost_cents" not in str(detail.json())

        change = await portal.post(
            f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v1['id']}/request-changes",
            json={"category": "description", "comment": "Please mention Friday pickup."},
        )
        assert change.status_code == 200, change.text
        assert change.json()["status"] == "open"
        blocked = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v1['id']}/approve")
        assert blocked.status_code == 409

    async with await _client_as(stage4b_ctx["staff"]) as client:
        resolved = await client.post(
            f"/api/webstores/{store['id']}/change-requests/{change.json()['id']}",
            json={"status": "resolved", "response": "Pickup wording updated.", "internal_note": "Owner called."},
        )
        assert resolved.status_code == 200, resolved.text
        product = (await client.get(f"/api/webstores/{store['id']}")).json()["products"][0]
        patched = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "fulfillment_notes": "Friday pickup at the front office."},
        )
        assert patched.status_code == 200, patched.text
        packet_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets", json={"promotion_copy": "Updated for Friday pickup."})
        assert packet_resp.status_code == 201, packet_resp.text
        packet_v2 = packet_resp.json()
        assert packet_v2["version"] == 2
        assert packet_v2["snapshot"]["products"][0]["packet_ref"] == product["id"]
        assert (await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet_v2['id']}/send")).status_code == 200

    async with await _portal_client(owner_token) as portal:
        old_approval = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v1['id']}/approve")
        assert old_approval.status_code == 409
        approved = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v2['id']}/approve")
        assert approved.status_code == 200, approved.text
        duplicate = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v2['id']}/approve")
        assert duplicate.status_code == 200
        terms = await portal.post(f"/api/portal/webstores/{store['id']}/terms/accept", json={"terms_version": "webstore_terms_2026_07"})
        assert terms.status_code == 200, terms.text
        duplicate_terms = await portal.post(f"/api/portal/webstores/{store['id']}/terms/accept", json={"terms_version": "webstore_terms_2026_07"})
        assert duplicate_terms.status_code == 200
        assert await db.webstore_terms_acceptances.count_documents({"tenant_id": stage4b_ctx["tenant_id"], "webstore_id": store["id"]}) == 1

    async with await _client_as(stage4b_ctx["staff"]) as client:
        ready = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert ready["checks"]["packet_approved"] is True
        assert ready["checks"]["terms_current"] is True
        assert ready["checks"]["buyer_commerce_connected"] is True
        nonmaterial = await client.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": patched.json()["revision"], "production_notes": "Internal heat press setting."})
        assert nonmaterial.status_code == 200
        still_ready = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert still_ready["checks"]["packet_approved"] is True

        material = await client.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": nonmaterial.json()["revision"], "selling_price_cents": 2600})
        assert material.status_code == 200, material.text
        invalidated = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert invalidated["checks"]["packet_approved"] is False
        assert "Material product fields changed" in invalidated["gates"][6]["reason"]

        terms_change = await client.patch(f"/api/webstores/{store['id']}", json={"required_terms_version": "webstore_terms_2026_08"})
        assert terms_change.status_code == 200, terms_change.text
        terms_missing = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert terms_missing["current_terms_version"] == "webstore_terms_2026_08"
        assert terms_missing["checks"]["terms_current"] is False


@pytest.mark.asyncio
async def test_owner_portal_packet_actions_are_tenant_and_store_scoped(stage4b_ctx):
    async with await _client_as(stage4b_ctx["staff"]) as client:
        built = await _create_ready_store(client, stage4b_ctx)
        store = built["store"]
        packet = (await client.post(f"/api/webstores/{store['id']}/launch-packets", json={})).json()
        assert (await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet['id']}/send")).status_code == 200
        owner_identity = await db.portal_identities.find_one({"id": built["owner"]["portal_identity_id"]}, {"_id": 0})
        owner_token = create_portal_token(portal_identity_id=owner_identity["id"], tenant_id=stage4b_ctx["tenant_id"], portal_type="webstore_owner")

    async with await _client_as(stage4b_ctx["other_staff"]) as other_client:
        denied = await other_client.post(f"/api/webstores/{store['id']}/launch-packets/{packet['id']}/send")
        assert denied.status_code == 404

    async with await _portal_client(owner_token) as portal:
        denied = await portal.post(f"/api/portal/webstores/not-this-store/launch-packets/{packet['id']}/approve")
        assert denied.status_code in {403, 404}
