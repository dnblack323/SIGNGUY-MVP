"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *
from .webstore_shared_audit import _audit
from .webstore_shared_contracts import _association_ids, _effective_fulfillment_methods, _normalize_name, _now_iso, _public_cart_config

def _image_reference_for_response(
    product: dict,
    *,
    slot: str,
    image: dict[str, Any],
    public_slug: Optional[str] = None,
    include_private_id: bool = False,
) -> dict[str, Any]:
    result = {
        "slot": slot,
        "role": image.get("role") or slot,
        "alt_text": image.get("alt_text"),
        "file_name": image.get("file_name"),
        "content_type": image.get("content_type"),
        "recommended_dimensions": image.get("recommended_dimensions") or (
            "1600x1200 px or larger for primary images" if slot == "primary" else "1200x1200 px or larger for secondary images"
        ),
    }
    if image.get("url"):
        result["url"] = image["url"]
    elif public_slug and image.get("file_id"):
        result["url"] = f"/api/public/webstores/{public_slug}/product-images/{product['id']}/{slot}"
    if include_private_id and image.get("file_id"):
        result["file_id"] = image["file_id"]
        result["preview_url"] = f"/api/webstores/{product['webstore_id']}/setup-files/{image['file_id']}/preview"
    return {k: v for k, v in result.items() if v not in (None, "")}


def _product_image_map(product: dict) -> dict[str, dict[str, Any]]:
    images = product.get("customer_images") or {}
    if images:
        return {slot: dict(value or {}) for slot, value in images.items() if slot in CUSTOMER_IMAGE_SLOTS and value}
    legacy_ids = list(product.get("image_file_ids") or [])[:2]
    slots = ["primary", "secondary"]
    return {
        slots[index]: {"file_id": file_id, "role": slots[index], "alt_text": product.get("name"), "legacy": True}
        for index, file_id in enumerate(legacy_ids)
        if file_id
    }


def _variant_option_signature(variant: dict[str, Any]) -> str:
    option_keys = ["size", "color", "style", "material"]
    option_values = [
        f"{key}:{_normalize_name(str(variant.get(key) or ''))}"
        for key in option_keys
        if variant.get(key) not in (None, "")
    ]
    explicit_options = variant.get("options") if isinstance(variant.get("options"), dict) else {}
    for key in sorted(explicit_options):
        value = explicit_options.get(key)
        if value not in (None, ""):
            option_values.append(f"{_normalize_name(str(key))}:{_normalize_name(str(value))}")
    return "|".join(option_values) or _normalize_name(str(variant.get("name") or variant.get("sku") or "default"))


def _public_variant(variant: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "name",
        "size",
        "color",
        "style",
        "material",
        "options",
        "sku",
        "price_delta_cents",
        "selling_price_cents",
        "inventory_quantity",
        "available",
        "status",
    }
    return {k: v for k, v in variant.items() if k in allowed and v not in (None, "")}


def _public_personalization_field(field: dict[str, Any]) -> dict[str, Any]:
    allowed = {"key", "label", "type", "required", "choices", "placeholder", "max_length"}
    return {k: v for k, v in field.items() if k in allowed and v not in (None, "")}


def _product_setup_requirements(product: dict) -> list[dict[str, Any]]:
    has_images = bool(_product_image_map(product)) or bool(product.get("mockup_associations"))
    has_variants = bool(product.get("variants")) or bool(product.get("sku"))
    requirements = [
        {"key": "basic_information", "label": "Basic information", "complete": bool(product.get("name") and product.get("product_type"))},
        {"key": "catalog_organization", "label": "Category", "complete": bool(product.get("category_id") or product.get("category_name") or product.get("category"))},
        {"key": "pricing", "label": "Selling price", "complete": int(product.get("selling_price_cents") or 0) > 0},
        {"key": "images_or_mockups", "label": "Image or mockup", "complete": has_images},
        {"key": "options_or_sku", "label": "SKU or options", "complete": has_variants},
    ]
    if product.get("personalization_enabled"):
        requirements.append({"key": "personalization", "label": "Personalization prompts", "complete": bool(product.get("personalization_fields"))})
    return requirements


def _derived_catalog_status(product: dict) -> str:
    status = product.get("status") or "planned"
    if status in {"archived", "active", "ready", "incomplete", "planned"}:
        return status
    if status == "draft":
        requirements = _product_setup_requirements(product)
        complete = sum(1 for item in requirements if item["complete"])
        if complete == 0:
            return "planned"
        return "ready" if all(item["complete"] for item in requirements) else "incomplete"
    if status == "inactive":
        return "incomplete"
    return "planned"


def _image_slot_change_events(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    events: list[tuple[str, str, dict[str, Any]]] = []
    for slot in ("primary", "secondary"):
        before_image = dict((before or {}).get(slot) or {})
        after_image = dict((after or {}).get(slot) or {})
        if not before_image and not after_image:
            continue
        if before_image and after_image and before_image == after_image:
            continue
        if after_image and not before_image:
            action_word = "added"
            action = "webstore.product_image_added"
        elif before_image and not after_image:
            action_word = "removed"
            action = "webstore.product_image_removed"
        else:
            action_word = "replaced"
            action = "webstore.product_image_replaced"
        role = "Primary" if slot == "primary" else "Secondary"
        events.append(
            (
                action,
                f"{role} Webstore product image {action_word}",
                {
                    "image_association_id": f"{slot}_image",
                    "image_slot": slot,
                    "image_role": role,
                    "image_action": action_word,
                },
            )
        )
    return events


def _public_product_is_eligible(product: dict) -> bool:
    if product.get("status") != "active" or product.get("public") is not True:
        return False
    if product.get("approval_status") != "approved":
        return False
    if product.get("approval_invalidated_at"):
        return False
    if int(product.get("approval_revision") or 0) != int(product.get("revision") or 1):
        return False
    return bool(_effective_fulfillment_methods(product))


def _public_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public_variants = [
        variant
        for variant in (_public_variant(item) for item in product.get("variants") or [] if item.get("status", "active") != "archived")
        if variant
    ]
    result = {
        "id": product.get("id"),
        "name": product.get("name"),
        "description": product.get("short_description") or product.get("description"),
        "full_description": product.get("full_description"),
        "category": product.get("category_name") or product.get("category"),
        "category_id": product.get("category_id"),
        "product_type": product.get("product_type"),
        "sku": product.get("sku"),
        "selling_price_cents": product.get("selling_price_cents"),
        "personalization_enabled": bool(product.get("personalization_enabled")),
        "personalization_fields": [
            _public_personalization_field(field)
            for field in product.get("personalization_fields") or []
        ],
        "images": [
            _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug)
            for slot, image in _product_image_map(product).items()
        ],
        "public": bool(product.get("public")),
        "featured": bool(product.get("featured")),
        "status": product.get("status"),
        "fulfillment_methods": _effective_fulfillment_methods(product),
        "default_fulfillment_method": product.get("default_fulfillment_method") or (_effective_fulfillment_methods(product) or [None])[0],
        "pickup_instructions": product.get("pickup_instructions"),
        "shipping_cost_cents": int(product.get("shipping_cost_cents") or 0),
    }
    if public_variants:
        result["variants"] = public_variants
    return {k: v for k, v in result.items() if v not in (None, "")}


def _portal_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public = _public_product(product, public_slug=public_slug)
    public["webstore_id"] = product.get("webstore_id")
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        if product.get(key) not in (None, ""):
            public[key] = product.get(key)
    return {k: v for k, v in public.items() if v not in (None, "")}


def _staff_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    data = serialize_doc(product)
    data["images"] = [
        _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug, include_private_id=True)
        for slot, image in _product_image_map(product).items()
    ]
    data["catalog_status"] = _derived_catalog_status(product)
    data["setup_status"] = data["catalog_status"]
    data["setup_requirements"] = _product_setup_requirements(product)
    data["launch_packet_eligible"] = bool(product.get("launch_packet_eligible")) or data["catalog_status"] in {"ready", "active"}
    data["launch_packet_include"] = bool(product.get("launch_packet_include")) and data["launch_packet_eligible"]
    data["template_provenance"] = {
        "source_template_id": product.get("source_template_id"),
        "source_template_revision": product.get("source_template_revision"),
    }
    return data  # type: ignore[return-value]


def _approval_history_row(doc: dict) -> dict:
    return {
        key: doc.get(key)
        for key in (
            "id",
            "parent_type",
            "parent_id",
            "parent_version",
            "action",
            "reason",
            "actor_type",
            "actor_ref",
            "actor_display",
            "snapshot_hash",
            "status",
            "created_at",
            "superseded_at",
            "superseded_reason",
        )
        if doc.get(key) not in (None, "")
    }


async def _approval_history(tenant_id: str, parent_type: str, parent_id: str) -> list[dict[str, Any]]:
    return [
        _approval_history_row(doc)
        async for doc in db.approvals.find(
            {"tenant_id": tenant_id, "parent_type": parent_type, "parent_id": parent_id},
            {"_id": 0, "snapshot": 0},
        ).sort([("created_at", -1)])
    ]


def _owner_safe_product_snapshot(product: dict, *, public_slug: Optional[str] = None, mockups: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    safe = _portal_product(product, public_slug=public_slug)
    safe["revision"] = int(product.get("revision") or 1)
    safe["snapshot_type"] = "webstore_product"
    safe["mockups"] = mockups or []
    return safe


def _owner_safe_mockup_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = {
        "id": mockup.get("id"),
        "webstore_id": mockup.get("webstore_id"),
        "product_id": mockup.get("product_id"),
        "artwork_id": mockup.get("artwork_id"),
        "generation_source": mockup.get("generation_source"),
        "purpose": mockup.get("purpose"),
        "alt_text": mockup.get("alt_text"),
        "status": mockup.get("status"),
        "approval_status": mockup.get("approval_status"),
        "approval_decision_at": mockup.get("approval_decision_at"),
        "snapshot_type": "webstore_mockup",
    }
    if product:
        snapshot["product"] = _portal_product(product, public_slug=public_slug)
    return {k: v for k, v in snapshot.items() if v not in (None, "")}


def _mockup_approval_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = _owner_safe_mockup_snapshot(mockup, product, public_slug=public_slug)
    for key in ("approval_status", "approval_decision_at"):
        snapshot.pop(key, None)
    if isinstance(snapshot.get("product"), dict):
        for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
            snapshot["product"].pop(key, None)
    return snapshot


async def _current_mockups_for_product(tenant_id: str, webstore_id: str, product: dict) -> list[dict[str, Any]]:
    mockup_ids = _association_ids(product.get("mockup_associations") or [], "mockup_id")
    query: dict[str, Any] = {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$ne": "archived"}}
    if mockup_ids:
        query["$or"] = [{"id": {"$in": sorted(mockup_ids)}}, {"product_id": product["id"], "owner_visible": True}]
    else:
        query["product_id"] = product["id"]
        query["owner_visible"] = True
    rows: list[dict[str, Any]] = []
    async for doc in db.webstore_mockups.find(query, {"_id": 0}).sort([("created_at", -1)]):
        rows.append(_owner_safe_mockup_snapshot(serialize_doc(doc)))
    return rows


async def _product_approval_snapshot(tenant_id: str, webstore_id: str, product: dict, *, public_slug: Optional[str]) -> dict[str, Any]:
    mockups = []
    for mockup in await _current_mockups_for_product(tenant_id, webstore_id, product):
        frozen = dict(mockup)
        frozen.pop("approval_status", None)
        frozen.pop("approval_decision_at", None)
        mockups.append(frozen)
    snapshot = _owner_safe_product_snapshot(
        product,
        public_slug=public_slug,
        mockups=mockups,
    )
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        snapshot.pop(key, None)
    return snapshot


async def _invalidate_product_approval_if_needed(
    *,
    tenant_id: str,
    webstore_id: str,
    product: dict,
    reason: str,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
) -> None:
    if product.get("approval_status") not in {"pending_owner_approval", "approved"}:
        return
    now = _now_iso()
    await db.approvals.update_many(
        {"tenant_id": tenant_id, "parent_type": "webstore_product", "parent_id": product["id"], "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason}},
    )
    await db.webstore_products.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": product["id"]},
        {
            "$set": {
                "approval_status": "superseded",
                "approval_invalidated_at": now,
                "approval_invalidated_reason": reason,
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action="webstore.product_approval_superseded",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product approval superseded by material product change",
        metadata={"reason": reason},
    )

__all__ = [name for name in globals() if not name.startswith("__")]
