"""Staff product creation, listing, ordering, duplication, and approval submission."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_staff_templates import _get_template_for_staff


async def create_product(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _reject_stage4a_publication_request(fields)
    idempotency_key = fields.get("idempotency_key")
    operation = "copy_template" if fields.get("source_template_id") else "create_blank"
    source_template_id = fields.get("source_template_id")
    payload_hash = _stage4a_product_create_fingerprint(fields, operation=operation, source_template_id=source_template_id)
    if idempotency_key:
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
    template = None
    if source_template_id:
        template = await _get_template_for_staff(user, source_template_id)
        if template.get("status") != "active" or not template.get("active", True):
            raise WebstoreError("template_not_available", "Product template is not active", 409)
    category_id, category_name, legacy_category = await _normalize_product_category(user, webstore_id, fields)
    customer_images = await _normalize_customer_images(user["tenant_id"], webstore_id, fields.get("customer_images"))
    if not customer_images and template:
        customer_images = deepcopy(template.get("default_customer_images") or {})
    merged = {
        "name": fields.get("name") or (template or {}).get("default_title") or (template or {}).get("template_name"),
        "short_description": fields.get("short_description") or (template or {}).get("default_short_description"),
        "full_description": fields.get("full_description") or fields.get("description") or (template or {}).get("default_description"),
        "description": fields.get("description") or (template or {}).get("default_short_description") or (template or {}).get("default_description"),
        "category": legacy_category or (template or {}).get("suggested_category_name") or (template or {}).get("product_category"),
        "product_type": fields.get("product_type") or (template or {}).get("product_type"),
        "production_method": fields.get("production_method") or (template or {}).get("production_method"),
        "supplier_source_info": fields.get("supplier_source_info") or (template or {}).get("supplier_source_info"),
        "production_notes": fields.get("production_notes") or (template or {}).get("default_production_notes"),
    }
    production_cost_cents = _clean_money(fields.get("production_cost_cents"), default=int((template or {}).get("suggested_production_cost_cents") or 0))
    selling_price_cents = _clean_money(fields.get("selling_price_cents"), default=int((template or {}).get("suggested_selling_price_cents") or 0))
    store_owner_share_cents = _clean_money(fields.get("store_owner_share_cents"), default=int((template or {}).get("suggested_store_owner_share_cents") or 0))
    fundraiser_share_cents = _clean_money(fields.get("fundraiser_share_cents"), default=0)
    if store_owner_share_cents + fundraiser_share_cents > selling_price_cents:
        raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the product selling price", 400)
    status = _clean_status(fields.get("status"), PRODUCT_STATUSES, "draft", "product_status")
    if "display_order" in fields:
        display_order = _clean_quantity(fields.get("display_order"), default=0) or 0
    else:
        last = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
            {"_id": 0, "display_order": 1},
            sort=[("display_order", -1)],
        )
        display_order = int((last or {}).get("display_order") or 0) + 100
    product = WebstoreProduct(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        source_template_id=source_template_id,
        source_template_revision=(template or {}).get("revision"),
        name=_clean_text(merged["name"], "name"),
        short_description=_clean_optional_text(merged.get("short_description"), limit=500),
        full_description=_clean_optional_text(merged.get("full_description")),
        description=_clean_optional_text(merged.get("description")),
        category_id=category_id,
        category_name=category_name or legacy_category or merged.get("category"),
        category=category_name or legacy_category or merged.get("category"),
        product_type=merged.get("product_type"),
        production_method=_clean_optional_text(merged.get("production_method"), limit=120),
        supplier_source_info=_clean_optional_text(merged.get("supplier_source_info")),
        fulfillment_notes=_clean_optional_text(fields.get("fulfillment_notes")),
        sku=_clean_optional_text(fields.get("sku"), limit=120),
        production_cost_cents=production_cost_cents,
        selling_price_cents=selling_price_cents,
        store_owner_share_cents=store_owner_share_cents,
        fundraiser_share_cents=fundraiser_share_cents,
        platform_fee_basis_points=_clean_basis_points(fields.get("platform_fee_basis_points"), default=int((template or {}).get("platform_fee_basis_points") or 0)),
        fulfillment_methods=_normalize_fulfillment_methods(fields.get("fulfillment_methods")),
        default_fulfillment_method=(str(fields.get("default_fulfillment_method")).strip().lower() if fields.get("default_fulfillment_method") else None),
        pickup_instructions=_clean_optional_text(fields.get("pickup_instructions"), limit=2000),
        shipping_cost_cents=_clean_money(fields.get("shipping_cost_cents"), default=0),
        variants=[],
        personalization_enabled=bool(fields.get("personalization_enabled", False)),
        personalization_fields=[],
        bundle_items=[],
        inventory_policy=str(fields.get("inventory_policy") or "not_tracked")[:80],
        inventory_quantity=_clean_quantity(fields.get("inventory_quantity"), default=None),
        launch_packet_eligible=bool(fields.get("launch_packet_eligible", False)),
        launch_packet_include=bool(fields.get("launch_packet_include", False)),
        display_order=display_order,
        image_file_ids=[],
        customer_images=customer_images,
        production_notes=_clean_optional_text(merged.get("production_notes")),
        public=False,
        featured=False,
        status=status,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    variant_source = fields.get("variants") if "variants" in fields else (template or {}).get("default_variants")
    product["variants"] = _normalize_variants(variant_source, base_selling_price_cents=selling_price_cents)
    if product.get("default_fulfillment_method") and product["default_fulfillment_method"] not in product.get("fulfillment_methods"):
        raise WebstoreError("invalid_default_fulfillment_method", "The default fulfillment method must be enabled for this product", 400)
    product["personalization_fields"] = _normalize_personalization_fields(
        fields.get("personalization_fields"),
        enabled=bool(product.get("personalization_enabled")),
    )
    product["bundle_items"] = await _normalize_bundle_items(user, webstore_id, product["id"], fields.get("bundle_items"))
    await _ensure_unique_product_skus(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product["id"],
        sku=product.get("sku"),
        variants=product.get("variants") or [],
    )
    if product.get("launch_packet_include") and not bool(product.get("launch_packet_eligible")):
        product["launch_packet_eligible"] = True
    if product.get("status") in {"ready", "active"}:
        missing = [item["label"] for item in _product_setup_requirements(product) if not item["complete"]]
        if missing:
            raise WebstoreError("product_not_ready", f"Complete product setup before marking it ready: {', '.join(missing)}", 409)
        product["launch_packet_eligible"] = True
    if "artwork_associations" in fields:
        product["artwork_associations"] = await _normalize_artwork_associations(user, webstore_id, product["id"], fields.get("artwork_associations"))
    elif template:
        product["artwork_associations"] = deepcopy(template.get("default_artwork_associations") or [])
    if "mockup_associations" in fields:
        product["mockup_associations"] = await _normalize_mockup_associations(user, webstore_id, product["id"], fields.get("mockup_associations"))
    elif template:
        product["mockup_associations"] = deepcopy(template.get("default_mockup_associations") or [])
    if idempotency_key:
        product["stage4a_idempotency_key"] = idempotency_key
        product["stage4a_idempotency_actor_id"] = user.get("id")
        product["stage4a_idempotency_operation"] = operation
        product["stage4a_idempotency_source_template_id"] = source_template_id
        product["stage4a_idempotency_payload_hash"] = payload_hash
    try:
        await db.webstore_products.insert_one(prepare_for_mongo(product))
    except DuplicateKeyError:
        if not idempotency_key:
            raise
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
        raise WebstoreError("stage4a_idempotency_conflict", "This product action could not be safely retried. Start a new action and try again.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_created_from_template" if source_template_id else "webstore.product_created_blank",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product created from a template" if source_template_id else "Blank Webstore product draft created",
        metadata={"source_template_id": product.get("source_template_id")},
    )
    return _staff_product(product, public_slug=store.get("public_slug"))


async def list_products(
    user: dict,
    *,
    webstore_id: str,
    public_only: bool = False,
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    filters: dict[str, Any] = {"webstore_id": webstore_id}
    if public_only:
        filters.update({"public": True, "status": "active"})
    if status:
        filters["status"] = status
    if category_id:
        filters["category_id"] = category_id
    result = await products_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("display_order", 1), ("featured", -1), ("name", 1)])
    items = result["items"]
    if q:
        needle = _normalize_name(q)
        items = [item for item in items if needle in _normalize_name(item.get("name", ""))]
    return {**result, "items": [_staff_product(item, public_slug=store.get("public_slug")) for item in items], "total": len(items)}


async def duplicate_product(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before duplicating.", 409)
    source = deepcopy(product)
    for key in (
        "_id",
        "id",
        "created_at",
        "updated_at",
        "revision",
        "approval_status",
        "approval_revision",
        "approval_snapshot_hash",
        "approval_decision_at",
        "approval_decision_by_portal_identity_id",
        "approval_invalidated_at",
        "approval_invalidated_reason",
        "stage4a_idempotency_key",
        "stage4a_idempotency_actor_id",
        "stage4a_idempotency_operation",
        "stage4a_idempotency_source_template_id",
        "stage4a_idempotency_payload_hash",
        "name",
        "status",
        "public",
        "featured",
        "launch_packet_include",
        "display_order",
        "created_by_user_id",
        "updated_by_user_id",
        "sku",
        "variants",
    ):
        source.pop(key, None)
    last = await db.webstore_products.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0, "display_order": 1},
        sort=[("display_order", -1)],
    )
    duplicate = WebstoreProduct(
        **source,
        id=secrets.token_urlsafe(18),
        name=_clean_text(fields.get("name") or f"{product.get('name', 'Product')} Copy", "name"),
        sku=None,
        variants=[{**variant, "sku": None} for variant in source.get("variants") or []],
        status="draft",
        public=False,
        featured=False,
        launch_packet_include=False,
        approval_status="not_submitted",
        display_order=int((last or {}).get("display_order") or 0) + 100,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_products.insert_one(prepare_for_mongo(duplicate))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_duplicated",
        entity_type="webstore_product",
        entity_id=duplicate["id"],
        summary="Webstore product duplicated into a private draft",
        metadata={"source_product_id": product_id},
    )
    return _staff_product(duplicate, public_slug=store.get("public_slug"))


async def reorder_products(user: dict, webstore_id: str, product_ids: list[str]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    ids = [str(item) for item in product_ids if str(item or "").strip()]
    existing = [
        doc
        async for doc in db.webstore_products.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
    ]
    expected_ids = {doc["id"] for doc in existing}
    if set(ids) != expected_ids or len(ids) != len(expected_ids):
        raise WebstoreError("reorder_requires_all_active_products", "Reorder must include each non-archived product exactly once", 400)
    now = _now_iso()
    for index, current_id in enumerate(ids):
        await db.webstore_products.update_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": current_id},
            {"$set": {"display_order": (index + 1) * 100, "updated_at": now, "updated_by_user_id": user.get("id")}},
        )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.products_reordered",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore product display order updated",
        metadata={"product_ids": ids},
    )
    return await list_products(user, webstore_id=webstore_id)


async def submit_product_for_approval(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    if product.get("status") == "archived":
        raise WebstoreError("product_archived", "Archived products cannot be sent for approval", 409)
    snapshot = await _product_approval_snapshot(user["tenant_id"], webstore_id, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    now = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": product_id, "revision": expected_revision},
        {
            "$set": {
                "approval_status": "pending_owner_approval",
                "approval_revision": expected_revision,
                "approval_snapshot_hash": snapshot_hash,
                "approval_invalidated_at": None,
                "approval_invalidated_reason": None,
                "updated_at": now,
                "updated_by_user_id": user.get("id"),
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_submitted_for_approval",
        entity_type="webstore_product",
        entity_id=product_id,
        summary="Webstore product submitted for owner approval",
        metadata={"product_revision": expected_revision, "snapshot_hash": snapshot_hash, "comment": fields.get("comment")},
    )
    data = _staff_product(updated, public_slug=store.get("public_slug"))
    data["approval_history"] = await _approval_history(user["tenant_id"], "webstore_product", product_id)
    data["approval_snapshot"] = snapshot
    return data

__all__ = ['create_product', 'list_products', 'duplicate_product', 'reorder_products', 'submit_product_for_approval']
