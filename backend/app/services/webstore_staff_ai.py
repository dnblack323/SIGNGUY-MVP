"""Explicit staff Webstore product AI preview, run, and audit-record operations."""
from __future__ import annotations

from .webstore_shared import *


async def create_ai_usage_event(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    event = WebstoreAIUsageEvent(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        action=_clean_text(fields.get("action"), "action"),
        status=fields.get("status", "drafted"),
        prompt_source=_clean_optional_text(fields.get("prompt_source")),
        output_snapshot=fields.get("output_snapshot") or {},
        reviewed_by_user_id=fields.get("reviewed_by_user_id"),
        reviewed_at=fields.get("reviewed_at"),
    ).model_dump()
    await db.webstore_ai_usage_events.insert_one(prepare_for_mongo(event))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.ai_contract_recorded",
        entity_type="webstore_ai_usage_event",
        entity_id=event["id"],
        summary="Webstore AI suggestion contract recorded without provider call",
    )
    return serialize_doc(event)  # type: ignore[return-value]


def _webstore_product_ai_action(action: Any) -> dict[str, Any]:
    key = str(action or "").strip()
    config = WEBSTORE_PRODUCT_AI_ACTIONS.get(key)
    if not config:
        raise WebstoreError("unsupported_webstore_ai_action", "Unsupported Webstore product AI action", 400)
    return {"action": key, **config}


async def _webstore_product_ai_preview(user: dict, webstore_id: str, product_id: str, action: Any) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    _require_staff_perm(user, Perm.AI_TOOL_USE)
    config = _webstore_product_ai_action(action)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY):
        raise WebstoreError("webstores_not_entitled", "Webstores entitlement is required before running Webstore AI actions.", 402)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=ai_studio.AI_STUDIO_ENTITLEMENT_FEATURE_KEY):
        raise WebstoreError("ai_studio_not_entitled", "AI Studio entitlement is required before running Webstore AI actions.", 402)

    capability = await db.ai_capabilities.find_one({"capability_key": config["capability_key"], "status": "active"}, {"_id": 0})
    if not capability:
        raise WebstoreError(
            "webstore_ai_capability_not_bootstrapped",
            "Platform AI admin must bootstrap the EC17 local mock catalog before this Webstore AI action can run.",
            409,
        )
    account = await ai_gateway.get_credit_account(user["tenant_id"])
    credit_charge = int(capability.get("default_credit_charge") or 0)
    available = int(account.get("available_credits") or 0)
    return {
        "action": config["action"],
        "label": config["label"],
        "tool_key": config["tool_key"],
        "mode_key": config["mode_key"],
        "capability_key": config["capability_key"],
        "result_record_type": config["result_record_type"],
        "output_kind": config["output_kind"],
        "credit_charge_credits": credit_charge,
        "available_credits": available,
        "credit_display": f"{credit_charge} AI credit{'s' if credit_charge != 1 else ''}",
        "confirmation_required": True,
        "can_run": available >= credit_charge,
        "insufficient_credits": available < credit_charge,
        "usage_note": config["usage_note"],
        "review_required": True,
        "auto_apply": False,
        "manual_setup_available": True,
        "h7_local_mock": True,
        "external_provider_calls": 0,
        "webstore": {"id": store["id"], "name": store.get("name")},
        "product": {"id": product["id"], "name": product.get("name"), "revision": product.get("revision")},
    }


async def preview_product_ai_action(user: dict, webstore_id: str, product_id: str, action: Any) -> dict[str, Any]:
    return await _webstore_product_ai_preview(user, webstore_id, product_id, action)


def _webstore_product_ai_prompt(product: dict[str, Any], fields: dict[str, Any], config: dict[str, Any]) -> str:
    supplied = _clean_optional_text(fields.get("prompt"), limit=1000)
    base = supplied or product.get("full_description") or product.get("short_description") or product.get("name") or "Webstore product"
    return (
        f"{base}\n\n"
        f"Product: {product.get('name') or 'Untitled product'}\n"
        f"Product type: {product.get('product_type') or 'not set'}\n"
        f"Category: {product.get('category_name') or product.get('category') or 'not set'}\n"
        f"Boundary: {config['usage_note']}"
    )


async def run_product_ai_action(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    preview = await _webstore_product_ai_preview(user, webstore_id, product_id, fields.get("action"))
    confirmed = fields.get("confirmed_credit_charge_credits")
    if confirmed is None:
        raise WebstoreError("ai_credit_confirmation_required", "Confirm the displayed AI credit charge before running this Webstore AI action.", 400)
    if int(confirmed) != int(preview["credit_charge_credits"]):
        raise WebstoreError("ai_credit_confirmation_stale", "The AI credit charge changed. Refresh the preview and confirm again.", 409)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    config = _webstore_product_ai_action(fields.get("action"))
    idempotency_key = _clean_optional_text(fields.get("idempotency_key"), limit=160)
    result = await ai_studio.run_tool(
        user,
        {
            "tool_key": config["tool_key"],
            "mode_key": config["mode_key"],
            "inputs": {
                "prompt": _webstore_product_ai_prompt(product, fields, config),
                "context_notes": _clean_optional_text(fields.get("context_notes"), limit=1000),
            },
            "context": {
                "context_type": "webstore",
                "context_id": webstore_id,
                "webstore_product_id": product_id,
                "webstore_product_revision": product.get("revision"),
            },
            "source_links": [{"entity_type": "webstore_product", "entity_id": product_id}],
            "idempotency_key": idempotency_key,
            "title": f"{preview['label']} - {product.get('name') or 'Webstore product'}",
        },
    )
    event = WebstoreAIUsageEvent(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        action=config["action"],
        status="drafted",
        prompt_source=_clean_optional_text(fields.get("prompt"), limit=1000),
        output_snapshot={
            "record_type": result.get("record_type"),
            "record_id": result.get("id"),
            "title": result.get("title"),
            "content_text": result.get("content_text"),
            "content_json": result.get("content_json") or {},
            "warnings": result.get("warnings") or [],
            "action_request_id": result.get("action_request_id"),
            "credit_charge_credits": preview["credit_charge_credits"],
            "credit_display": preview["credit_display"],
            "auto_apply": False,
            "review_required": True,
            "external_provider_calls": 0,
            "h7_local_mock": True,
            "webstore_product_id": product_id,
            "webstore_product_revision": product.get("revision"),
        },
    ).model_dump()
    await db.webstore_ai_usage_events.insert_one(prepare_for_mongo(event))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_ai_action_recorded",
        entity_type="webstore_ai_usage_event",
        entity_id=event["id"],
        summary="Webstore product AI output saved for staff review without applying changes",
        metadata={
            "product_id": product_id,
            "ai_result_record_type": result.get("record_type"),
            "ai_result_id": result.get("id"),
            "action_request_id": result.get("action_request_id"),
            "credit_charge_credits": preview["credit_charge_credits"],
            "auto_apply": False,
        },
    )
    return {
        "preview": preview,
        "ai_result": result,
        "webstore_ai_event": serialize_doc(event),
        "auto_apply": False,
        "review_required": True,
        "manual_setup_available": True,
    }

__all__ = ['create_ai_usage_event', '_webstore_product_ai_action', '_webstore_product_ai_preview', 'preview_product_ai_action', '_webstore_product_ai_prompt', 'run_product_ai_action']
