"""Real route/Gateway/storage/composer tests over an isolated Images HTTP double."""
import asyncio
import hashlib
import json
import uuid

import httpx
import pytest

from app.core.db import db
from app.models.ai_gateway import AICreditAccount, AIModelProfile, AIProviderConfig, AICapability
from app.core.time_utils import prepare_for_mongo
from app.services import ai_gateway, webstore_ai_presentations, openai_image_provider
from app.services.entitlements import _upsert_entitlement_for_tests
from tests.webstore_image_provider_double import install, response_payload
from tests.test_webstores_mockup_composition import _setup
from tests.test_webstores_stage4b_owner_approval import (
    stage4b_ctx, _client_as, _portal_client, _owner_token,
    _submit_product_for_approval, _submit_mockup_for_approval, _approve_product_and_mockup,
)
from tests.test_webstores_owner_product_visibility import _owner_read


async def configure(ctx):
    provider = await db.ai_provider_configs.find_one({"provider_key": "openai"}, {"_id": 0})
    if not provider:
        provider = AIProviderConfig(provider_key="openai", display_name="Isolated provider test double", status="active", created_by_user_id=ctx["staff"]["id"]).model_dump()
        await db.ai_provider_configs.insert_one(prepare_for_mongo(provider))
    model = AIModelProfile(provider_config_id=provider["id"], provider_key="openai", model_key=openai_image_provider.MODEL,
        display_name="Isolated provider test double — no live calls", task_category="image", status="active", created_by_user_id=ctx["staff"]["id"],
        metadata={"image_pricing": {"text_input_micros_per_million": 5_000_000, "image_input_micros_per_million": 8_000_000,
                  "image_output_micros_per_million": 30_000_000, "max_request_cost_micros": 1_000_000}}).model_dump()
    existing = await db.ai_model_profiles.find_one({"provider_key": "openai", "model_key": openai_image_provider.MODEL}, {"_id": 0})
    if existing:
        model = existing
    else:
        await db.ai_model_profiles.insert_one(prepare_for_mongo(model))
    capability = AICapability(capability_key=webstore_ai_presentations.CAPABILITY, display_name="Product mockup", feature_key="ai_studio", action_key="image.mockup", entitlement_feature_key="ai_studio", status="active", default_credit_charge=7, allowed_model_profile_ids=[model["id"]], created_by_user_id=ctx["staff"]["id"]).model_dump()
    await db.ai_capabilities.replace_one({"capability_key": capability["capability_key"]}, prepare_for_mongo(capability), upsert=True)
    await db.ai_credit_accounts.insert_one(prepare_for_mongo(AICreditAccount(tenant_id=ctx["tenant_id"], included_balance_credits=100).model_dump()))
    await _upsert_entitlement_for_tests(tenant_id=ctx["tenant_id"], feature_key="ai_studio", enabled=True)
    return model


@pytest.fixture
async def image_ctx(stage4b_ctx, monkeypatch):
    # Global registry edits are restored; the owned test DB remains disposable.
    ctx = stage4b_ctx
    saved = await db.ai_capabilities.find_one({"capability_key": webstore_ai_presentations.CAPABILITY}, {"_id": 0})
    ctx["model"] = await configure(ctx)
    ctx["calls"] = install(monkeypatch)
    yield ctx
    await db.ai_capabilities.delete_many({"capability_key": webstore_ai_presentations.CAPABILITY})
    if saved:
        await db.ai_capabilities.insert_one(saved)


def request(product, **extra):
    return {"expected_revision": product["revision"], "variant_id": "navy-m", "idempotency_key": uuid.uuid4().hex, "confirmed_credit_charge_credits": 7, **extra}


async def test_generation_review_composition_submission_and_private_revision(image_ctx):
    ctx = image_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built, product, sources, originals, composition = await _setup(staff, ctx)
        store = built["store"]; base = f"/api/webstores/{store['id']}/products/{product['id']}"
        preview = await staff.get(base + "/ai-presentations/preview")
        assert preview.status_code == 200 and preview.json()["can_run"]
        assert preview.json()["credit_charge_credits"] == 7
        fields = request(product)
        response = await staff.post(base + "/ai-presentations", json=fields)
        assert response.status_code == 200, response.text
        row = response.json()["items"][0]; file = row["file"]
        assert row["status"] == "succeeded" and file["ai_presentation"]["review_status"] == "pending"
        assert len(ctx["calls"]) == 1
        body = json.loads(ctx["calls"][0].content)
        assert body["size"] == "1024x1024" and body["quality"] == "medium" and "Navy" in body["prompt"]
        assert "image" not in body and "artwork_file_id" not in body and "original-logo" not in body["prompt"]
        assert ctx["calls"][0].headers["x-client-request-id"] == row["id"]
        assert (await staff.post(base + "/ai-presentations", json=fields)).status_code == 200
        assert len(ctx["calls"]) == 1
        composition["blank_file_id"] = file["id"]
        assert (await staff.post(base + "/mockup-composition/preview", json=composition)).status_code == 409
        assert (await staff.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"], "mockup_file_id": file["id"], "shop_approved": True})).status_code == 409
        review = await staff.post(base + f"/ai-presentations/{file['id']}/review", json={"expected_revision": product["revision"], "decision": "accepted"})
        assert review.status_code == 200, review.text
        composed = await staff.post(base + "/mockup-composition/preview", json=composition)
        assert composed.status_code == 200, composed.text
        accepted = await staff.post(base + "/mockup-composition", json={**composition, "preview_sha256": composed.headers["x-preview-sha256"], "reviewed": True, "alt_text": "Navy tee with original school logo"})
        assert accepted.status_code == 201, accepted.text
        result = accepted.json(); mockup = result["mockup"]
        assert mockup["preparation"]["artwork_sha256"] == hashlib.sha256(originals[1]).hexdigest()
        assert (await staff.get(f"/api/webstores/{store['id']}/setup-files/{sources[1]['id']}/preview")).content == originals[1]
        product = (await staff.patch(base, json={"expected_revision": product["revision"], "mockup_associations": [{"mockup_id": mockup["id"]}], "artwork_associations": [{"artwork_id": result["artwork"]["id"]}]})).json()
    token = await _owner_token(ctx, built["owner"])
    assert product["id"] not in str(await _owner_read(token, store))
    image_path = f"/api/portal/webstores/{store['id']}/products/{product['id']}/mockups/{mockup['id']}/image"
    async with await _portal_client(token) as owner:
        assert (await owner.get(image_path)).status_code == 404
        assert (await owner.get(f"/api/portal/webstores/{store['id']}/setup-files/{file['id']}/download")).status_code == 404
        assert (await owner.get(base + "/ai-presentations")).status_code in {401, 403}
    async with await _client_as(ctx["staff"]) as staff:
        await _submit_product_for_approval(staff, store, product)
        await _submit_mockup_for_approval(staff, store, mockup)
    await _approve_product_and_mockup(ctx, token, store, product, mockup)
    frozen = (await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}))["approval_snapshot"]
    async with await _client_as(ctx["staff"]) as staff:
        private = await staff.post(base + "/ai-presentations", json=request(product))
        assert private.status_code == 200
        private_file = private.json()["items"][0]["file"]
        assert private_file["id"] != file["id"]
        changed = await staff.patch(base, json={"expected_revision": product["revision"], "full_description": "PRIVATE WORK IN PROGRESS"})
        assert changed.status_code == 200
    async with await _portal_client(token) as owner:
        assert (await owner.get(image_path)).content == composed.content
    assert "PRIVATE WORK IN PROGRESS" not in str(await _owner_read(token, store))
    assert (await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}))["approval_snapshot"] == frozen
    account = await ai_gateway.get_credit_account(ctx["tenant_id"])
    assert account["included_balance_credits"] == 86 and account["reserved_credits"] == 0
    usage = [u async for u in db.ai_usage_ledger_entries.find({"tenant_id": ctx["tenant_id"]})]
    assert len(usage) == 2 and all(u["credits_charged"] == 7 and u["output_units"] == 2000 for u in usage)
    costs = [c async for c in db.ai_provider_cost_ledger_entries.find({"tenant_id": ctx["tenant_id"]})]
    assert len(costs) == 2 and all(c["estimated_cost_micros"] == 60500 and c["actual_cost_micros"] is None and c["status"] == "estimated" for c in costs)


@pytest.mark.parametrize("kind", ["reject", "timeout", "server", "missing_usage", "invalid_image", "storage", "settlement"])
async def test_failure_uncertainty_and_no_redispatch(image_ctx, monkeypatch, kind):
    ctx = image_ctx
    async def handler(req):
        if kind == "timeout":
            raise httpx.ReadTimeout("isolated ambiguous outcome", request=req)
        if kind == "reject":
            return httpx.Response(429, headers={"x-request-id": "isolated-rejected"})
        if kind == "server":
            return httpx.Response(500, headers={"x-request-id": "isolated-uncertain"})
        payload = response_payload(b"invalid png" if kind == "invalid_image" else None)
        if kind == "missing_usage":
            payload.pop("usage")
        return httpx.Response(200, json=payload, headers={"x-request-id": "isolated-delivered"})
    calls = install(monkeypatch, handler)
    async def fail(*args, **kwargs):
        raise OSError("isolated interruption")
    if kind == "storage": monkeypatch.setattr(webstore_ai_presentations, "store_setup_file", fail)
    if kind == "settlement": monkeypatch.setattr(ai_gateway, "_commit_credits", fail)
    async with await _client_as(ctx["staff"]) as staff:
        built, product, _, _, _ = await _setup(staff, ctx)
        base = f"/api/webstores/{built['store']['id']}/products/{product['id']}/ai-presentations"
        fields = request(product)
        response = await staff.post(base, json=fields)
        assert response.status_code == 200, response.text
        row = response.json()["items"][0]
        uncertain = kind not in {"reject", "invalid_image"}
        assert row["status"] == ("executing" if uncertain else "failed")
        await staff.post(base, json=fields)
        assert len(calls) == 1
        if uncertain:
            assert (await staff.post(base, json=request(product))).status_code == 409
        else:
            assert not row["file"]
        history = await ai_gateway.list_action_history(ctx["staff"])
        assert "_provider" not in str(history) and "_execution" not in str(history)
        replay = await staff.post("/api/ai/gateway/requests", json={"capability_key": webstore_ai_presentations.CAPABILITY, "model_profile_id": ctx["model"]["id"], "idempotency_key": f"webstore-image:{ctx['staff']['id']}:{fields['idempotency_key']}"})
        assert replay.status_code in {404, 409}, replay.text
    account = await ai_gateway.get_credit_account(ctx["tenant_id"])
    assert account["included_balance_credits"] == 100 and account["reserved_credits"] == (7 if uncertain else 0)
    assert not await db.ai_credit_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "entry_type": "commit"})


async def test_permissions_configuration_binding_and_governance(image_ctx, monkeypatch):
    ctx = image_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built, product, _, _, _ = await _setup(staff, ctx)
        base = f"/api/webstores/{built['store']['id']}/products/{product['id']}/ai-presentations"
        fields = request(product)
        for edit, status in [({"confirmed_credit_charge_credits": 1}, 409), ({"variant_id": "foreign"}, 409), ({"expected_revision": 99}, 409), ({"free": True}, 422)]:
            assert (await staff.post(base, json={**fields, **edit})).status_code == status
        assert not ctx["calls"]
        monkeypatch.setattr(openai_image_provider.get_settings(), "openai_image_generation_enabled", False)
        assert not (await staff.get(base + "/preview")).json()["can_run"]
        assert (await staff.post(base, json=fields)).status_code == 409
        monkeypatch.setattr(openai_image_provider.get_settings(), "openai_image_generation_enabled", True)
        await db.ai_governance_policies.insert_one({"id": "image-cap-" + ctx["suffix"], "scope_type": "tenant", "tenant_id": ctx["tenant_id"], "status": "active", "max_cost_micros_per_day": 999999})
        assert (await staff.post(base, json=fields)).status_code == 429
        await db.ai_governance_policies.update_one({"tenant_id": ctx["tenant_id"]}, {"$set": {"max_cost_micros_per_day": 2000000}})
        assert (await staff.post(base, json=fields)).status_code == 200
        await db.webstore_products.update_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}, {"$set": {"variants.0.color": "Red"}})
        assert (await staff.post(base, json=fields)).status_code == 409
    for user, status in [(ctx["other_staff"], 404), ({**ctx["staff"], "role": "viewer"}, 403), ({**ctx["staff"], "webstore_id": "foreign"}, 403)]:
        async with await _client_as(user) as client:
            assert (await client.post(base, json=fields)).status_code == status
    assert len(ctx["calls"]) == 1


async def test_concurrent_keys_and_pending_costs_are_admitted_atomically(image_ctx, monkeypatch):
    ctx = image_ctx
    async def timeout(req):
        await asyncio.sleep(.05)
        raise httpx.ReadTimeout("isolated ambiguous outcome", request=req)
    calls = install(monkeypatch, timeout)
    async with await _client_as(ctx["staff"]) as staff:
        built, product, _, _, _ = await _setup(staff, ctx)
        base = f"/api/webstores/{built['store']['id']}/products/{product['id']}/ai-presentations"
        fields = request(product)
        responses = await asyncio.gather(*(staff.post(base, json=fields) for _ in range(3)))
        assert all(r.status_code == 200 for r in responses)
        assert len({r.json()["items"][0]["id"] for r in responses}) == 1 and len(calls) == 1
        assert (await staff.post(base, json=request(product))).status_code == 409
        # Uncertain provider expense and reserved credits remain in tenant caps,
        # including attempts against a different product.
        product2 = (await staff.post(f"/api/webstores/{built['store']['id']}/products", json={"name": "Second tee", "product_type": "t-shirt", "selling_price_cents": 2500,
            "variants": [{"id": "navy-m", "color": "Navy", "size": "M", "selling_price_cents": 2500}]})).json()
        base2 = f"/api/webstores/{built['store']['id']}/products/{product2['id']}/ai-presentations"
        policy = {"id": "pending-policy-" + ctx["suffix"], "scope_type": "tenant", "tenant_id": ctx["tenant_id"], "status": "active", "max_cost_micros_per_day": 1500000}
        await db.ai_governance_policies.insert_one(policy)
        assert (await staff.post(base2, json=request(product2))).status_code == 429
        await db.ai_governance_policies.update_one({"id": policy["id"]}, {"$unset": {"max_cost_micros_per_day": ""}, "$set": {"max_credits_per_day": 10}})
        assert (await staff.post(base2, json=request(product2))).status_code == 429
        assert len(calls) == 1


async def test_rejected_image_cannot_be_used_or_reclassified_as_customer_artwork(image_ctx):
    ctx = image_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built, product, _, _, composition = await _setup(staff, ctx)
        base = f"/api/webstores/{built['store']['id']}/products/{product['id']}"
        row = (await staff.post(base + "/ai-presentations", json=request(product))).json()["items"][0]
        file_id = row["file"]["id"]
        review = await staff.post(base + f"/ai-presentations/{file_id}/review", json={"expected_revision": product["revision"], "decision": "rejected"})
        assert review.status_code == 200
        composition["blank_file_id"] = file_id
        assert (await staff.post(base + "/mockup-composition/preview", json=composition)).status_code == 409
        assert (await staff.patch(base, json={"expected_revision": product["revision"], "customer_images": [{"file_id": file_id, "alt_text": "Unreviewed background"}]})).status_code in {409, 422}
        assert (await staff.post(base + f"/ai-presentations/{file_id}/review", json={"expected_revision": product["revision"], "decision": "accepted"})).status_code == 409
        account = await ai_gateway.get_credit_account(ctx["tenant_id"])
        assert account["included_balance_credits"] == 93 and account["reserved_credits"] == 0
