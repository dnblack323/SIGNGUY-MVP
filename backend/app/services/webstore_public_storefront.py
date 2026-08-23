"""Public storefront reads and product media for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_payment_boundary import _provider_authority_from_record

async def _fundraiser_progress(store: dict[str, Any]) -> dict[str, Any]:
    """Expose only completed, verified Webstore sales as fundraiser progress."""
    settings = store.get("store_settings") or {}
    setup = store.get("setup_profile") or {}
    cart = settings.get("cart") or {}
    donation = settings.get("donations") or settings.get("donation") or {}
    goal = int(
        setup.get("fundraiser_goal_amount")
        or cart.get("fundraiser_goal_cents")
        or donation.get("goal_amount_cents")
        or 0
    )
    paid_sales = 0
    async for intent in db.webstore_purchase_intents.find(
        {
            "tenant_id": store["tenant_id"],
            "webstore_id": store["id"],
            "status": "paid_order_created",
            "canonical_payment_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0, "total_cents": 1},
    ):
        paid_sales += max(0, int(intent.get("total_cents") or 0))
    percent = int((Decimal(paid_sales) * Decimal(100) / Decimal(goal)).quantize(Decimal("1"))) if goal else 0
    return {
        "goal_cents": goal,
        "completed_sales_cents": paid_sales,
        "percent": percent,
        "over_goal": bool(goal and paid_sales > goal),
        "paid_only": True,
    }


async def _storefront_by_slug(slug: str) -> dict:
    store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    store = await _ensure_public_slug(serialize_doc(store))
    if store.get("status") != "live":
        raise WebstoreError("webstore_not_live", "Webstore is not available", 404)
    close_at = store.get("deadline_at") or store.get("intended_close_at")
    if close_at:
        try:
            closing = datetime.fromisoformat(str(close_at).replace("Z", "+00:00"))
            if closing.tzinfo and closing <= datetime.now(timezone.utc):
                raise WebstoreError("webstore_closed", "Webstore is not available", 404)
        except ValueError:
            pass
    access_mode = ((store.get("store_settings") or {}).get("access_policy") or {}).get("mode") or "open"
    if access_mode == "restricted":
        raise WebstoreError("webstore_not_public", "Webstore is not available", 404)
    products = []
    async for doc in db.webstore_products.find(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "status": "active", "public": True},
        {"_id": 0},
    ).sort([("featured", -1), ("name", 1)]):
        product = serialize_doc(doc)
        if _public_product_is_eligible(product):
            products.append(_public_product(product, public_slug=store.get("public_slug")))
    published_branding = await branding_svc.published_branding_for_store(store)
    fundraiser_progress = await _fundraiser_progress(store)
    provider_record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "record_type": "connected_account"},
        {"_id": 0},
    )
    provider_status = provider_configuration_status(get_settings(), _provider_authority_from_record(provider_record, get_settings()))
    return {
        "webstore": _public_store(serialize_doc(store), published_branding, fundraiser_progress, provider_status["provider_authority"]),
        "products": products,
    }


async def public_storefront(slug: str) -> dict:
    return await _storefront_by_slug(slug)


async def public_product_detail(slug: str, product_id: str) -> dict:
    storefront = await _storefront_by_slug(slug)
    product = next((item for item in storefront["products"] if item.get("id") == product_id), None)
    if not product:
        raise WebstoreError("product_not_available", "Product is not available", 404)
    return {"webstore": storefront["webstore"], "product": product}


async def public_product_image(slug: str, product_id: str, slot: str) -> tuple[dict, bytes, str]:
    if slot not in CUSTOMER_IMAGE_SLOTS:
        raise WebstoreError("product_image_slot_not_found", "Product image was not found", 404)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    product = await db.webstore_products.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": store["id"],
            "id": product_id,
            "status": "active",
            "public": True,
        },
        {"_id": 0},
    )
    if not product or not _public_product_is_eligible(product):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    image = _product_image_map(serialize_doc(product)).get(slot)
    if not image or not image.get("file_id"):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    file_doc = await db.webstore_setup_files.find_one(
        {"tenant_id": full_store["tenant_id"], "webstore_id": store["id"], "id": image["file_id"], "status": "active"},
        {"_id": 0},
    )
    if not file_doc:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    if str(file_doc.get("extension") or "").lower() not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_not_public", "Product image is not available publicly", 404)
    try:
        data, content_type = storage.get_bytes(file_doc["storage_key"])
    except FileNotFoundError:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    return serialize_doc(file_doc), data, file_doc.get("detected_content_type") or content_type
