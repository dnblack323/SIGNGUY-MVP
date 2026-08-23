"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *

async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await stores_repo.get(tenant_id=tenant_id, entity_id=webstore_id)
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    return store


async def _get_owner(tenant_id: str, owner_id: str) -> dict:
    owner = await owners_repo.get(tenant_id=tenant_id, entity_id=owner_id)
    if not owner:
        raise WebstoreError("webstore_owner_not_found", "Webstore owner not found", 404)
    return owner


async def _get_product(tenant_id: str, product_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": product_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    product = await products_repo.find_one(filt)
    if not product:
        raise WebstoreError("webstore_product_not_found", "Webstore product not found", 404)
    return product


async def _get_mockup(tenant_id: str, mockup_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": mockup_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    mockup = await db.webstore_mockups.find_one(filt, {"_id": 0})
    if not mockup:
        raise WebstoreError("webstore_mockup_not_found", "Webstore mockup not found", 404)
    return serialize_doc(mockup)


async def _get_category(tenant_id: str, webstore_id: str, category_id: str) -> dict:
    category = await db.webstore_product_categories.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": category_id},
        {"_id": 0},
    )
    if not category:
        raise WebstoreError("webstore_category_not_found", "Webstore product category was not found", 404)
    return serialize_doc(category)


async def _setup_file_for_product_reference(tenant_id: str, webstore_id: str, file_id: str) -> dict:
    doc = await db.webstore_setup_files.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": file_id, "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise WebstoreError("product_file_not_found", "The selected product file was not found for this Webstore", 404)
    ext = str(doc.get("extension") or "").lower()
    if ext not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_type_not_allowed", "Product images must be JPG, PNG, WebP, or a safe SVG image", 400)
    if ext == "svg" and not doc.get("svg_sanitized"):
        raise WebstoreError("product_image_svg_not_safe", "SVG product images must pass the existing safe SVG policy", 400)
    return serialize_doc(doc)

__all__ = [name for name in globals() if not name.startswith("__")]
