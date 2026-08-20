"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *
from .webstore_shared_catalog import _variant_option_signature
from .webstore_shared_contracts import _clean_money, _clean_optional_text, _clean_quantity, _clean_status, _clean_text, _normalize_name, _now_iso, _slug
from .webstore_shared_repository import _get_category, _get_product, _setup_file_for_product_reference

async def _normalize_customer_images(tenant_id: str, webstore_id: str, images: Optional[dict[str, Any]]) -> dict[str, Any]:
    if images is None:
        return {}
    unknown = sorted(set(images.keys()) - CUSTOMER_IMAGE_SLOTS)
    if unknown:
        raise WebstoreError("too_many_product_image_slots", "Products support only primary and secondary customer-facing image slots", 400)
    normalized: dict[str, Any] = {}
    for slot in ("primary", "secondary"):
        image = dict(images.get(slot) or {})
        if not image:
            continue
        file_id = image.get("file_id")
        url = image.get("url")
        alt_text = _clean_optional_text(image.get("alt_text"), limit=200)
        if (file_id or url) and not alt_text:
            raise WebstoreError("product_image_alt_text_required", f"Add alternate text for the {slot} product image", 400)
        record = {
            "slot": slot,
            "role": _clean_optional_text(image.get("role"), limit=80) or slot,
            "alt_text": alt_text,
            "recommended_dimensions": image.get("recommended_dimensions") or (
                "1600x1200 px or larger" if slot == "primary" else "1200x1200 px or larger"
            ),
            "updated_at": _now_iso(),
        }
        if file_id:
            file_doc = await _setup_file_for_product_reference(tenant_id, webstore_id, str(file_id))
            record.update(
                {
                    "file_id": file_doc["id"],
                    "file_name": file_doc.get("file_name"),
                    "content_type": file_doc.get("detected_content_type") or file_doc.get("content_type"),
                    "file_version": file_doc.get("version"),
                }
            )
        elif url:
            record["url"] = str(url)
        normalized[slot] = {k: v for k, v in record.items() if v not in (None, "")}
    return normalized


def _reject_private_file_refs_for_platform_template(images: dict[str, Any], artwork: list[dict[str, Any]], mockups: Optional[list[dict[str, Any]]] = None) -> None:
    for image in (images or {}).values():
        if isinstance(image, dict) and image.get("file_id"):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)
    for item in [*(artwork or []), *(mockups or [])]:
        if isinstance(item, dict) and (item.get("file_id") or item.get("artwork_id") or item.get("mockup_id")):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)


def _has_private_image_file_refs(images: Any) -> bool:
    return any(isinstance(image, dict) and bool(image.get("file_id")) for image in (images or {}).values())


async def _normalize_product_category(user: dict, webstore_id: str, fields: dict[str, Any], existing: Optional[dict] = None) -> tuple[Optional[str], Optional[str], Optional[str]]:
    category_id = fields.get("category_id") if "category_id" in fields else (existing or {}).get("category_id")
    category_name = fields.get("category_name") if "category_name" in fields else (existing or {}).get("category_name")
    legacy_category = fields.get("category") if "category" in fields else (existing or {}).get("category")
    if category_id:
        category = await _get_category(user["tenant_id"], webstore_id, str(category_id))
        if category.get("status") != "active":
            raise WebstoreError("webstore_category_archived", "Archived categories cannot be assigned to products", 409)
        return category["id"], category["name"], category["name"]
    if category_name:
        return None, _clean_text(category_name, "category_name", limit=120), _clean_text(category_name, "category_name", limit=120)
    if legacy_category:
        cleaned = _clean_optional_text(legacy_category, limit=120)
        return None, cleaned, cleaned
    return None, None, None


async def _normalize_artwork_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected artwork was not found for this product", 404)
        if art.get("product_id") not in (None, "", product_id):
            raise WebstoreError("artwork_product_scope_mismatch", "Selected artwork belongs to a different product", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_mockup_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected mockup was not found for this product", 404)
        if mockup.get("product_id") not in (None, "", product_id):
            raise WebstoreError("mockup_product_scope_mismatch", "Selected mockup belongs to a different product", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


async def _normalize_template_artwork_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected template artwork was not found for this Webstore", 404)
        if art.get("product_id"):
            raise WebstoreError("artwork_product_scope_mismatch", "Product-specific artwork cannot be used as a reusable template default", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_template_mockup_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected template mockup was not found for this Webstore", 404)
        if mockup.get("product_id"):
            raise WebstoreError("mockup_product_scope_mismatch", "Product-specific mockups cannot be used as reusable template defaults", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


async def _ensure_unique_product_skus(
    *,
    tenant_id: str,
    webstore_id: str,
    product_id: str,
    sku: Optional[str],
    variants: list[dict[str, Any]],
) -> None:
    supplied = [str(value).strip() for value in [sku, *[variant.get("sku") for variant in variants]] if str(value or "").strip()]
    lowered = [_normalize_name(value) for value in supplied]
    if len(lowered) != len(set(lowered)):
        raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this product", 409)
    if not lowered:
        return
    async for doc in db.webstore_products.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": {"$ne": product_id}, "status": {"$ne": "archived"}},
        {"_id": 0, "sku": 1, "variants": 1},
    ):
        existing = [str(value).strip() for value in [doc.get("sku"), *[variant.get("sku") for variant in doc.get("variants") or []]] if str(value or "").strip()]
        if set(lowered) & {_normalize_name(value) for value in existing}:
            raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this Webstore", 409)


def _normalize_variants(variants: Optional[list[dict[str, Any]]], *, base_selling_price_cents: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    signatures: set[str] = set()
    for index, item in enumerate(variants or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_variant", "Each variant must be an object", 400)
        variant: dict[str, Any] = {
            "id": _clean_optional_text(item.get("id"), limit=80) or f"variant-{index + 1}",
            "name": _clean_optional_text(item.get("name"), limit=120),
            "size": _clean_optional_text(item.get("size"), limit=80),
            "color": _clean_optional_text(item.get("color"), limit=80),
            "style": _clean_optional_text(item.get("style"), limit=80),
            "material": _clean_optional_text(item.get("material"), limit=80),
            "sku": _clean_optional_text(item.get("sku"), limit=120),
            "options": item.get("options") if isinstance(item.get("options"), dict) else {},
            "status": _clean_status(item.get("status"), {"active", "inactive", "archived"}, "active", "variant_status"),
            "available": bool(item.get("available", True)),
            "inventory_quantity": _clean_quantity(item.get("inventory_quantity"), default=None),
            "production_cost_cents": _clean_money(item.get("production_cost_cents"), default=0),
            "store_owner_share_cents": _clean_money(item.get("store_owner_share_cents"), default=0),
            "fundraiser_share_cents": _clean_money(item.get("fundraiser_share_cents"), default=0),
            "price_delta_cents": _clean_money(item.get("price_delta_cents"), default=0),
        }
        variant["selling_price_cents"] = _clean_money(item.get("selling_price_cents"), default=base_selling_price_cents + variant["price_delta_cents"])
        if variant["store_owner_share_cents"] + variant["fundraiser_share_cents"] > variant["selling_price_cents"]:
            raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the variant selling price", 400)
        signature = _variant_option_signature(variant)
        if signature in signatures:
            raise WebstoreError("duplicate_variant_combination", "Each size/color/options variant combination must be unique", 409)
        signatures.add(signature)
        normalized.append({k: v for k, v in variant.items() if v not in (None, "", {})})
    return normalized


def _normalize_personalization_fields(items: Optional[list[dict[str, Any]]], *, enabled: bool) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_personalization_field", "Each personalization prompt must be an object", 400)
        label = _clean_text(item.get("label"), "personalization_label", limit=120)
        key = _clean_optional_text(item.get("key"), limit=80) or _slug(label).replace("-", "_") or f"field_{index + 1}"
        field_type = str(item.get("type") or "text").strip().lower()
        if field_type not in {"text", "textarea", "select", "number"}:
            raise WebstoreError("invalid_personalization_type", "Personalization prompts support text, textarea, select, or number", 400)
        field = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(item.get("required", False)),
            "choices": [str(choice).strip() for choice in item.get("choices") or [] if str(choice).strip()][:20],
            "placeholder": _clean_optional_text(item.get("placeholder"), limit=120),
            "max_length": _clean_quantity(item.get("max_length"), default=None, minimum=1),
        }
        if field_type == "select" and not field["choices"]:
            raise WebstoreError("personalization_choices_required", "Select personalization prompts require at least one choice", 400)
        normalized.append({k: v for k, v in field.items() if v not in (None, "", [])})
    if enabled and not normalized:
        raise WebstoreError("personalization_fields_required", "Add at least one personalization prompt or turn personalization off", 400)
    keys = [field["key"] for field in normalized]
    if len(keys) != len(set(keys)):
        raise WebstoreError("duplicate_personalization_field", "Personalization prompt keys must be unique", 409)
    return normalized


async def _normalize_bundle_items(
    user: dict,
    webstore_id: str,
    product_id: str,
    items: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            raise WebstoreError("invalid_bundle_item", "Each bundle item must be an object", 400)
        bundled_product_id = str(item.get("product_id") or "").strip()
        if not bundled_product_id:
            continue
        if bundled_product_id == product_id:
            raise WebstoreError("bundle_self_reference", "A product bundle cannot include itself", 409)
        if bundled_product_id in seen:
            raise WebstoreError("duplicate_bundle_item", "Bundle items must be unique", 409)
        bundled = await _get_product(user["tenant_id"], bundled_product_id, webstore_id)
        if bundled.get("status") == "archived":
            raise WebstoreError("bundle_item_archived", "Archived products cannot be included in bundles", 409)
        seen.add(bundled_product_id)
        normalized.append(
            {
                "product_id": bundled_product_id,
                "name_snapshot": bundled.get("name"),
                "quantity": _clean_quantity(item.get("quantity"), default=1, minimum=1),
                "sku_snapshot": bundled.get("sku"),
            }
        )
    return normalized

__all__ = [name for name in globals() if not name.startswith("__")]
