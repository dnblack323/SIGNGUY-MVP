"""Staff-private presentation assets. EC16 executes/meters; existing composer finishes."""
from __future__ import annotations

import hashlib
import io
import json

from starlette.concurrency import run_in_threadpool

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import utc_now
from . import ai_gateway, openai_image_provider as provider
from .entitlements import has_entitlement
from .webstore_mockup_composition import _decode
from .webstore_shared_access import _require_staff_perm, _require_webstore_assignment_scope
from .webstore_shared_contracts import WebstoreError
from .webstore_shared_repository import _get_store, _get_product
from .webstore_setup_files import store_setup_file, list_setup_files
from .webstore_shared_audit import _audit

CAPABILITY = "studio.image.mockup"


async def _product(user, store_id, product_id):
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    _require_staff_perm(user, Perm.AI_TOOL_USE)
    await _require_webstore_assignment_scope(user, store_id)
    store = await _get_store(user["tenant_id"], store_id)
    product = await _get_product(user["tenant_id"], product_id, store_id)
    for feature in {store.get("entitlement_feature_key") or "webstores", "ai_studio"}:
        if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=feature):
            raise WebstoreError("feature_not_entitled", "Webstores and AI Studio entitlements are required", 402)
    if str(product.get("product_type", "")).lower().replace("_", "-").replace(" ", "-") not in {"t-shirt", "tshirt", "tee"} or product.get("status") == "archived":
        raise WebstoreError("presentation_product_unsupported", "AI presentations currently support active flat-front T-shirts", 409)
    return product


async def _profile():
    capability = await db.ai_capabilities.find_one({"capability_key": CAPABILITY, "status": "active"}, {"_id": 0})
    if not capability:
        raise ValueError("Platform AI configuration is required")
    model = await db.ai_model_profiles.find_one({"id": {"$in": capability.get("allowed_model_profile_ids") or []}, "provider_key": "openai", "model_key": provider.MODEL, "status": "active"}, {"_id": 0})
    if not model:
        raise ValueError("The pinned OpenAI image model is not configured")
    config = await db.ai_provider_configs.find_one({"id": model["provider_config_id"], "provider_key": "openai", "status": "active"}, {"_id": 0})
    if not config or config.get("credential_mode") != "platform_managed":
        raise ValueError("An active platform-managed OpenAI provider is required")
    return model, provider.pricing(model)


async def preview(user, store_id, product_id):
    await _product(user, store_id, product_id)
    base = {"can_run": False, "model_key": provider.MODEL, "credit_charge_credits": None,
            "unavailable_reason": "Paid image generation is disabled pending owner-authorized live testing."}
    if not provider.available():
        return base
    try:
        model, rates = await _profile()
        execution = ai_gateway.ProviderExecution("preview", "", rates["max_request_cost_micros"], lambda: None)
        result = await ai_gateway.preview_gateway_request(user, {"capability_key": CAPABILITY, "model_profile_id": model["id"]}, execution=execution)
        return {**result, "model_key": model["model_key"], "model_display_name": model["display_name"], "request_estimate_micros": rates["max_request_cost_micros"]}
    except (ValueError, ai_gateway.AIGatewayError) as exc:
        return {**base, "unavailable_reason": str(exc)}


def _validated_png(data):
    image = _decode(data)
    if image.size != (1024, 1024):
        raise ValueError("Provider returned unexpected dimensions")
    result = io.BytesIO()
    image.info.clear()
    image.save(result, format="PNG")
    return result.getvalue()


async def status(user, store_id, product_id):
    await _product(user, store_id, product_id)
    scope = f"webstore_presentation:{store_id}:{product_id}"
    actions = [a async for a in db.ai_action_requests.find({"tenant_id": user["tenant_id"], "_execution.scope": scope}, {"_id": 0}).sort("created_at", -1).limit(20)]
    files = (await list_setup_files(user, store_id))["items"]
    return {"items": [{"id": a["id"], "status": a["status"], "credit_charge_credits": a["credit_charge_credits"],
                       "model_key": a["model_key"], "reconciliation_required": a.get("reconciliation_required", False),
                       "file": next((f for f in files if f.get("ai_presentation", {}).get("action_request_id") == a["id"]), None)} for a in actions]}


async def run(user, store_id, product_id, fields):
    product = await _product(user, store_id, product_id)
    if not provider.available():
        raise WebstoreError("ai_execution_unavailable", "Paid image generation is disabled", 409)
    if product.get("revision", 1) != fields["expected_revision"]:
        raise WebstoreError("revision_conflict", "Save and reload the product configuration before generation", 409)
    variant = next((v for v in product.get("variants", []) if v["id"] == fields["variant_id"]), None)
    if not variant or not variant.get("color") or variant.get("status", "active") != "active" or variant.get("available", True) is False:
        raise WebstoreError("presentation_variant_unavailable", "Select an active, manually available variant with a color", 409)
    try:
        model, rates = await _profile()
    except ValueError as exc:
        raise WebstoreError("image_configuration_required", str(exc), 409) from exc
    scope = f"webstore_presentation:{store_id}:{product_id}"
    binding = {"product_id": product_id, "webstore_id": store_id, "product_revision": product["revision"],
               "variant_id": variant["id"], "color": variant["color"], "size": variant.get("size"), "model_key": model["model_key"]}
    fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    key = f"webstore-image:{user['id']}:{fields['idempotency_key']}"
    pending = await db.ai_action_requests.find_one({"tenant_id": user["tenant_id"], "_execution.scope": scope, "status": {"$in": ["received", "reserved", "executing"]}, "idempotency_key": {"$ne": key}})
    if pending:
        raise WebstoreError("image_reconciliation_required", "A previous generation is unresolved. Check its status; do not start another paid generation", 409)

    async def execute(profile, request_fields, action_id):
        await db.ai_action_requests.update_one({"tenant_id": user["tenant_id"], "id": action_id}, {"$set": {"_provider": {"client_request_id": action_id, "model": provider.MODEL}}})
        receipt = await provider.generate(request_id=action_id,
            safety_identifier=hashlib.sha256(f"{user['tenant_id']}:{user['id']}".encode()).hexdigest(),
            color=variant["color"], size=variant.get("size") or "unspecified", rates=rates)
        data = receipt.pop("image_bytes", None)
        # Persist identity/usage before storage. An interrupted upload never
        # causes a second provider call, and remains visible for reconciliation.
        await db.ai_action_requests.update_one({"tenant_id": user["tenant_id"], "id": action_id}, {"$set": {"_provider": receipt}})
        if not receipt.get("verified_success"):
            return receipt
        try:
            png = await run_in_threadpool(_validated_png, data)
        except (ValueError, OSError):
            return {**receipt, "verified_success": False}
        provenance = {**binding, "action_request_id": action_id, "review_status": "pending",
                      "sha256": hashlib.sha256(png).hexdigest(), "provider_request_id": receipt.get("provider_event_id")}
        file = await store_setup_file(tenant_id=user["tenant_id"], webstore_id=store_id,
            actor_type="staff", actor_id=user["id"], filename=f"ai-presentation-{action_id}.png", content_type="image/png",
            data=png, category="artwork", ai_presentation=provenance,
            notes="AI-generated unbranded presentation. Staff review required; original artwork has not been sent to AI.")
        await db.ai_action_requests.update_one({"tenant_id": user["tenant_id"], "id": action_id}, {"$set": {"_provider.file_id": file["id"]}})
        return receipt

    execution = ai_gateway.ProviderExecution(scope, fingerprint, rates["max_request_cost_micros"], execute)
    try:
        await ai_gateway.create_gateway_request(user, {"capability_key": CAPABILITY, "model_profile_id": model["id"],
            "idempotency_key": key, "confirmed_credit_charge_credits": fields["confirmed_credit_charge_credits"]}, execution=execution)
    except ai_gateway.AIGatewayError as exc:
        raise WebstoreError(exc.code, exc.detail, exc.status_code) from exc
    return await status(user, store_id, product_id)


async def review(user, store_id, product_id, file_id, fields):
    product = await _product(user, store_id, product_id)
    if product.get("revision", 1) != fields["expected_revision"]:
        raise WebstoreError("revision_conflict", "Reload the product before reviewing this presentation", 409)
    link = await db.file_links.find_one({"tenant_id": user["tenant_id"], "id": file_id, "parent_type": "webstore", "parent_id": store_id,
        "archived": {"$ne": True}, "metadata.status": "active", "metadata.ai_presentation.product_id": product_id}, {"_id": 0})
    if not link:
        raise WebstoreError("presentation_not_found", "Private presentation not found", 404)
    generation = link["metadata"]["ai_presentation"]
    action = await db.ai_action_requests.find_one({"tenant_id": user["tenant_id"], "id": generation["action_request_id"], "status": "succeeded"})
    if not action:
        raise WebstoreError("image_reconciliation_required", "Generation must finish settlement before review", 409)
    if generation["review_status"] != "pending":
        raise WebstoreError("presentation_already_reviewed", "This presentation already has a recorded review", 409)
    updated = await db.file_links.update_one({"tenant_id": user["tenant_id"], "id": file_id, "metadata.ai_presentation.review_status": "pending"},
        {"$set": {"metadata.ai_presentation.review_status": fields["decision"], "metadata.ai_presentation.reviewed_by": user["id"],
                  "metadata.ai_presentation.reviewed_at": utc_now().isoformat()}})
    if not updated.modified_count:
        raise WebstoreError("presentation_already_reviewed", "Another staff member already reviewed this presentation", 409)
    await _audit(tenant_id=user["tenant_id"], webstore_id=store_id, actor_type="staff", actor_id=user["id"], actor_email=user.get("email"),
                 action="webstore.presentation_reviewed", entity_type="file_link", entity_id=file_id,
                 summary="Staff reviewed a private product presentation", metadata={"decision": fields["decision"], "action_request_id": generation["action_request_id"]})
    return await status(user, store_id, product_id)
