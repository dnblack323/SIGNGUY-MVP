"""Dedicated Stage 5 Webstore launch packet, owner approval, and readiness tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import storage
from app.services.entitlements import _upsert_entitlement_for_tests
from app.services.webstore_branding import default_branding
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
async def stage5_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage5-{suffix}"
    other_tenant_id = f"t-webstore-stage5-other-{suffix}"
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    basic_staff = {"id": f"staff-basic-{suffix}", "tenant_id": tenant_id, "email": f"staff-basic-{suffix}@example.com", "role": "staff", "is_active": True}
    other_staff = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([staff, basic_staff, other_staff])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="webstores", enabled=True)
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "staff": staff, "basic_staff": basic_staff, "other_staff": other_staff}
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_file(tenant_id: str, webstore_id: str, *, name: str = "asset.png") -> dict:
    file_id = f"file-{uuid.uuid4().hex}"
    storage_key = f"tests/{tenant_id}/{file_id}.png"
    storage.put_bytes(storage_key, b"stage5-image", "image/png")
    doc = {
        "id": file_id,
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "category": "product_image",
        "file_name": name,
        "extension": "png",
        "content_type": "image/png",
        "detected_content_type": "image/png",
        "size_bytes": 12,
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


async def _create_stage5_store(client: AsyncClient, ctx: dict) -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Stage 5 Owner {ctx['suffix']}", "email": f"stage5-owner-{ctx['suffix']}@example.com"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    owner = owner_resp.json()
    other_owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Other Owner {ctx['suffix']}", "email": f"other-owner-{ctx['suffix']}@example.com"},
    )
    assert other_owner_resp.status_code == 201, other_owner_resp.text
    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": owner["id"],
            "name": f"Stage 5 Store {ctx['suffix']}",
            "slug": f"stage5-store-{ctx['suffix']}",
            "store_type": "general",
            "setup_profile": {"store_purpose": "Spirit wear", "audience": "Families"},
            "store_settings": {"fulfillment": {"method": "pickup", "pickup_copy": "Front desk pickup"}, "promo": {"copy_notes": "Share with families"}},
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    store = store_resp.json()
    await db.webstore_questionnaire_submissions.insert_one(
        {
            "id": f"submission-{uuid.uuid4().hex}",
            "tenant_id": ctx["tenant_id"],
            "webstore_id": store["id"],
            "owner_id": owner["id"],
            "portal_identity_id": owner["portal_identity_id"],
            "template_ids": [],
            "template_version_ids": [],
            "template_snapshot": {},
            "answers": {"store_purpose": "Spirit wear", "audience": "Families"},
            "known_products": [],
            "open_to_suggestions": True,
            "missing_info_flags": [],
            "status": "submitted",
            "submitted_snapshot": {"answers": {"store_purpose": "Spirit wear", "audience": "Families"}},
            "inactive_answer_paths": [],
            "submitted_at": "2026-08-02T12:00:00+00:00",
        }
    )
    image = await _seed_file(ctx["tenant_id"], store["id"], name="product.png")
    branding = default_branding(store)
    branding["brand_basics"]["display_name"] = store["name"]
    branding["brand_basics"]["primary_logo"] = {"file_id": image["id"], "alt_text": "Store logo"}
    branding["hero"]["image"] = {"file_id": image["id"], "alt_text": "Store banner"}
    branding["hero"]["headline"] = "Final Launch Review"
    branding["store_information"]["welcome_text"] = "Pick up at the front desk."
    branding["store_type_content"]["general_welcome"] = "Welcome families."
    branding_resp = await client.patch(f"/api/webstores/{store['id']}", json={"branding": branding})
    assert branding_resp.status_code == 200, branding_resp.text
    store = branding_resp.json()
    category_resp = await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": "Apparel"})
    assert category_resp.status_code == 201, category_resp.text
    product_resp = await client.post(
        f"/api/webstores/{store['id']}/products",
        json={
            "name": "Launch Shirt",
            "description": "Owner-safe shirt description",
            "product_type": "shirt",
            "category_id": category_resp.json()["id"],
            "selling_price_cents": 2500,
            "production_cost_cents": 900,
            "store_owner_share_cents": 300,
            "supplier_source_info": "Internal supplier",
            "production_notes": "Internal production detail",
            "sku": "STAGE5-SHIRT",
            "customer_images": {"primary": {"file_id": image["id"], "alt_text": "Launch shirt"}},
            "launch_packet_eligible": True,
            "launch_packet_include": True,
            "status": "ready",
        },
    )
    assert product_resp.status_code == 201, product_resp.text
    product = product_resp.json()
    mockup_resp = await client.post(
        f"/api/webstores/{store['id']}/mockups",
        json={"product_id": product["id"], "mockup_file_id": image["id"], "purpose": "Front proof", "alt_text": "Front proof", "owner_visible": True},
    )
    assert mockup_resp.status_code == 201, mockup_resp.text
    owner_token = await _owner_token(ctx, owner)
    other_owner_token = await _owner_token(ctx, other_owner_resp.json())
    return {"owner": owner, "other_owner": other_owner_resp.json(), "store": store, "product": product, "mockup": mockup_resp.json(), "owner_token": owner_token, "other_owner_token": other_owner_token, "image": image}


async def _owner_token(ctx: dict, owner: dict) -> str:
    identity = await db.portal_identities.find_one({"id": owner["portal_identity_id"]}, {"_id": 0})
    return create_portal_token(portal_identity_id=identity["id"], tenant_id=ctx["tenant_id"], portal_type="webstore_owner")


async def _approve_product_and_mockup(ctx: dict, owner_token: str, store: dict, product: dict, mockup: dict) -> None:
    async with await _client_as(ctx["staff"]) as client:
        product_submit = await client.post(f"/api/webstores/{store['id']}/products/{product['id']}/submit-approval", json={"expected_revision": product["revision"]})
        assert product_submit.status_code == 200, product_submit.text
        mockup_submit = await client.post(f"/api/webstores/{store['id']}/mockups/{mockup['id']}/submit-approval", json={})
        assert mockup_submit.status_code == 200, mockup_submit.text
    async with await _portal_client(owner_token) as portal:
        product_decision = await portal.post(f"/api/portal/webstores/{store['id']}/products/{product['id']}/approval", json={"decision": "approve", "comment": "Product approved."})
        assert product_decision.status_code == 200, product_decision.text
        mockup_decision = await portal.post(f"/api/portal/webstores/{store['id']}/mockups/{mockup['id']}/approval", json={"decision": "approve", "comment": "Mockup approved."})
        assert mockup_decision.status_code == 200, mockup_decision.text


async def _generate_and_send_packet(client: AsyncClient, store: dict, copy: str = "Manual promo copy.") -> dict:
    packet_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets", json={"promotion_copy": copy})
    assert packet_resp.status_code == 201, packet_resp.text
    packet = packet_resp.json()
    send_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet['id']}/send")
    assert send_resp.status_code == 200, send_resp.text
    return packet


@pytest.mark.asyncio
async def test_stage5_owner_decisions_terms_readiness_and_authorization(stage5_ctx):
    async with await _client_as(stage5_ctx["staff"]) as client:
        built = await _create_stage5_store(client, stage5_ctx)
        store = built["store"]
        other_asset = await _seed_file(stage5_ctx["other_tenant_id"], "other-store", name="other-logo.png")
        bad_branding = default_branding(store)
        bad_branding["brand_basics"]["primary_logo"] = {"file_id": other_asset["id"], "alt_text": "Wrong tenant logo"}
        bad_branding["store_type_content"]["general_welcome"] = "Welcome."
        cross_tenant = await client.patch(f"/api/webstores/{store['id']}", json={"branding": bad_branding})
        assert cross_tenant.status_code == 400
        assert cross_tenant.json()["detail"] == "branding references files that do not belong to this Webstore."

    async with await _portal_client(built["owner_token"]) as portal:
        authorized_detail = await portal.get(f"/api/portal/webstores/{store['id']}")
        assert authorized_detail.status_code == 200, authorized_detail.text
        assert authorized_detail.json()["commerce_summary"]["order_count"] == 0
        assert authorized_detail.json()["commerce_summary"]["gross_sales_cents"] == 0
        assert authorized_detail.json()["public_launch_blocked_until_batch_3"] is True
    async with await _portal_client(built["other_owner_token"]) as portal:
        denied = await portal.get(f"/api/portal/webstores/{store['id']}")
        assert denied.status_code == 403
    async with await _client_as(stage5_ctx["other_staff"]) as other_client:
        denied = await other_client.get(f"/api/webstores/{store['id']}/launch-readiness")
        assert denied.status_code == 404

    await _approve_product_and_mockup(stage5_ctx, built["owner_token"], store, built["product"], built["mockup"])
    async with await _client_as(stage5_ctx["staff"]) as client:
        product_history_before = await db.approvals.count_documents({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_product", "parent_id": built["product"]["id"]})
        mockup_history_before = await db.approvals.count_documents({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_mockup", "parent_id": built["mockup"]["id"]})
        packet_v1 = await _generate_and_send_packet(client, store, "Manual promo copy for packet one.")
        assert packet_v1["version"] == 1
        assert packet_v1["generated_by_user_id"] == stage5_ctx["staff"]["id"]
        assert packet_v1["created_at"]
        assert packet_v1["snapshot_hash"]
        assert packet_v1["snapshot"]["owner_preview"]["headline"] == "Final Launch Review"
        assert packet_v1["snapshot"]["qr_reference"]["destination"].startswith("/p/webstores/")
        assert "only after the Webstore lifecycle status is live" in packet_v1["snapshot"]["qr_reference"]["warning"]
        serialized = str(packet_v1)
        for forbidden in ("production_cost_cents", "supplier_source_info", "storage_key", "provider_account_reference", "stripe_account_id", "production_notes", "internal supplier"):
            assert forbidden not in serialized

    async with await _portal_client(built["owner_token"]) as portal:
        terms = await portal.post(f"/api/portal/webstores/{store['id']}/terms/accept", json={"terms_version": "webstore_terms_2026_07"})
        assert terms.status_code == 200, terms.text
        assert terms.json()["terms_version"] == "webstore_terms_2026_07"
        terms_approval = await db.approvals.find_one({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_terms_acceptance", "parent_id": terms.json()["id"]}, {"_id": 0})
        assert terms_approval["action"] == "approve"
        assert terms_approval["snapshot_hash"]
    async with await _client_as(stage5_ctx["staff"]) as client:
        readiness_after_terms = await client.get(f"/api/webstores/{store['id']}/launch-readiness")
        assert readiness_after_terms.status_code == 200
        assert readiness_after_terms.json()["checks"]["terms_current"] is True
        assert readiness_after_terms.json()["checks"]["packet_approved"] is False

    async with await _portal_client(built["owner_token"]) as portal:
        change = await portal.post(
            f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v1['id']}/request-changes",
            json={"category": "description", "comment": "Please adjust the pickup wording."},
        )
        assert change.status_code == 200, change.text
        assert change.json()["status"] == "open"
        requested = await db.approvals.find_one({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_launch_packet", "parent_id": packet_v1["id"], "action": "request_changes"}, {"_id": 0})
        assert requested["parent_version"] == 1
        assert requested["reason"] == "Please adjust the pickup wording."
    async with await _client_as(stage5_ctx["staff"]) as client:
        blocked_by_change = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert blocked_by_change["open_change_request_count"] == 1
        assert next(g for g in blocked_by_change["gates"] if g["key"] == "change_requests_resolved")["blocking"] is True
        resolved = await client.post(f"/api/webstores/{store['id']}/change-requests/{change.json()['id']}", json={"status": "resolved", "response": "Updated.", "internal_note": "Staff-only note."})
        assert resolved.status_code == 200, resolved.text
        packet_v2 = await _generate_and_send_packet(client, store, "Manual promo copy for packet two.")
        assert packet_v2["version"] == 2

    async with await _portal_client(built["owner_token"]) as portal:
        missing_reject_reason = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v2['id']}/reject", json={"comment": ""})
        assert missing_reject_reason.status_code == 400
        rejected = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v2['id']}/reject", json={"comment": "Do not launch this packet."})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["approval_history"][0]["action"] == "decline"
        stale_approve = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v2['id']}/approve", json={"comment": "Changed my mind."})
        assert stale_approve.status_code == 409

    async with await _client_as(stage5_ctx["staff"]) as client:
        packet_v3 = await _generate_and_send_packet(client, store, "Manual promo copy for packet three.")
        assert packet_v3["version"] == 3
    async with await _portal_client(built["owner_token"]) as portal:
        approved = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{packet_v3['id']}/approve", json={"comment": "Approved for staff final authorization."})
        assert approved.status_code == 200, approved.text
        assert approved.json()["approval_history"][0]["action"] == "approve"
    async with await _client_as(stage5_ctx["staff"]) as client:
        after_owner_approval = (await client.get(f"/api/webstores/{store['id']}")).json()["webstore"]
        assert after_owner_approval["status"] == "approved"
        assert after_owner_approval["checkout_enabled"] is False
        assert await db.approvals.count_documents({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_product", "parent_id": built["product"]["id"]}) == product_history_before
        assert await db.approvals.count_documents({"tenant_id": stage5_ctx["tenant_id"], "parent_type": "webstore_mockup", "parent_id": built["mockup"]["id"]}) == mockup_history_before
        ready = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert ready["ready"] is True
        assert ready["checks"]["questionnaire_complete"] is True
        assert ready["checks"]["included_products_ready"] is True
        assert ready["checks"]["branding_preview_complete"] is True
        assert ready["checks"]["packet_approved"] is True
        assert ready["checks"]["terms_current"] is True
        assert ready["checks"]["active_public_products_with_prices"] is False
        assert ready["payment_readiness"]["ready"] is False
        assert next(g for g in ready["gates"] if g["key"] == "payment_ready")["stage5_deferred"] is True
        assert next(g for g in ready["gates"] if g["key"] == "buyer_commerce_connected")["blocking"] is False

    async with await _client_as(stage5_ctx["basic_staff"]) as basic_client:
        forbidden_final = await basic_client.post(f"/api/webstores/{store['id']}/status", json={"status": "launch_ready", "reason": "Not authorized."})
        assert forbidden_final.status_code == 403
    async with await _portal_client(built["owner_token"]) as portal:
        owner_cannot_authorize = await portal.post(f"/api/webstores/{store['id']}/status", json={"status": "launch_ready", "reason": "Owner tries staff action."})
        assert owner_cannot_authorize.status_code in {401, 403}
    async with await _client_as(stage5_ctx["staff"]) as client:
        launch_ready = await client.post(f"/api/webstores/{store['id']}/status", json={"status": "launch_ready", "reason": "Stage 5 gates passed."})
        assert launch_ready.status_code == 200, launch_ready.text
        assert launch_ready.json()["status"] == "launch_ready"
        assert launch_ready.json()["checkout_enabled"] is False
        scheduled = await client.post(f"/api/webstores/{store['id']}/status", json={"status": "scheduled", "reason": "Too soon."})
        assert scheduled.status_code == 409
        live = await client.post(f"/api/webstores/{store['id']}/status", json={"status": "live", "reason": "Too soon."})
        assert live.status_code == 409

        current_product = (await client.get(f"/api/webstores/{store['id']}")).json()["products"][0]
        nonmaterial = await client.patch(f"/api/webstores/{store['id']}/products/{current_product['id']}", json={"expected_revision": current_product["revision"], "production_notes": "Internal-only heat press setting."})
        assert nonmaterial.status_code == 200, nonmaterial.text
        still_ready = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert still_ready["checks"]["packet_approved"] is True
        material = await client.patch(f"/api/webstores/{store['id']}/products/{current_product['id']}", json={"expected_revision": nonmaterial.json()["revision"], "selling_price_cents": 2600})
        assert material.status_code == 200, material.text
        invalidated = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert invalidated["checks"]["packet_approved"] is False
        assert "Material product fields changed" in next(g for g in invalidated["gates"] if g["key"] == "packet_approved")["reason"]

        terms_change = await client.patch(f"/api/webstores/{store['id']}", json={"required_terms_version": "webstore_terms_2026_08"})
        assert terms_change.status_code == 200, terms_change.text
        terms_missing = (await client.get(f"/api/webstores/{store['id']}/launch-readiness")).json()
        assert terms_missing["current_terms_version"] == "webstore_terms_2026_08"
        assert terms_missing["checks"]["terms_current"] is False
        assert await db.webstore_terms_acceptances.count_documents({"tenant_id": stage5_ctx["tenant_id"], "webstore_id": store["id"]}) == 1
