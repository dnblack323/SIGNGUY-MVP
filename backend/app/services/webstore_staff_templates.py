"""Staff product template administration for Webstores."""
from __future__ import annotations

from .webstore_shared import *


async def create_template(user: dict, fields: dict[str, Any]) -> dict:
    scope = _clean_status(fields.get("scope"), TEMPLATE_SCOPES, "tenant", "template_scope")
    if scope == "platform":
        _require_platform_creator(user)
        tenant_id = PLATFORM_TEMPLATE_TENANT_ID
        _reject_private_file_refs_for_platform_template(
            fields.get("default_customer_images") or {},
            fields.get("default_artwork_associations") or [],
            fields.get("default_mockup_associations") or [],
        )
        default_customer_images = deepcopy(fields.get("default_customer_images") or {})
        default_artwork_associations = deepcopy(fields.get("default_artwork_associations") or [])
        default_mockup_associations = deepcopy(fields.get("default_mockup_associations") or [])
    else:
        _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
        tenant_id = user["tenant_id"]
        has_private_defaults = (
            _has_private_image_file_refs(fields.get("default_customer_images"))
            or bool(fields.get("default_artwork_associations"))
            or bool(fields.get("default_mockup_associations"))
        )
        if has_private_defaults and not fields.get("webstore_id"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        default_customer_images = await _normalize_customer_images(user["tenant_id"], fields["webstore_id"], fields.get("default_customer_images")) if fields.get("webstore_id") else deepcopy(fields.get("default_customer_images") or {})
        default_artwork_associations = await _normalize_template_artwork_associations(user, fields["webstore_id"], fields.get("default_artwork_associations")) if fields.get("webstore_id") else []
        default_mockup_associations = await _normalize_template_mockup_associations(user, fields["webstore_id"], fields.get("default_mockup_associations")) if fields.get("webstore_id") else []
    status = _clean_status(fields.get("status"), TEMPLATE_STATUSES, "active" if fields.get("active", True) else "archived", "template_status")
    template = WebstoreProductTemplate(
        tenant_id=tenant_id,
        template_name=_clean_text(fields.get("template_name"), "template_name"),
        product_category=_clean_text(fields.get("product_category"), "product_category"),
        product_type=_clean_text(fields.get("product_type"), "product_type"),
        scope=scope,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        default_title=_clean_optional_text(fields.get("default_title"), limit=200),
        default_short_description=_clean_optional_text(fields.get("default_short_description"), limit=500),
        default_description=_clean_optional_text(fields.get("default_description")),
        suggested_category_name=_clean_optional_text(fields.get("suggested_category_name") or fields.get("product_category"), limit=120),
        production_method=_clean_optional_text(fields.get("production_method"), limit=120),
        supplier_source_info=_clean_optional_text(fields.get("supplier_source_info")),
        default_production_notes=_clean_optional_text(fields.get("default_production_notes")),
        default_customer_images=default_customer_images,
        default_artwork_associations=default_artwork_associations,
        default_mockup_associations=default_mockup_associations,
        best_store_types=fields.get("best_store_types") or [],
        default_variants=fields.get("default_variants") or [],
        mockup_supported=bool(fields.get("mockup_supported", True)),
        suggested_production_cost_cents=_clean_money(fields.get("suggested_production_cost_cents")),
        suggested_selling_price_cents=_clean_money(fields.get("suggested_selling_price_cents")),
        suggested_store_owner_share_cents=_clean_money(fields.get("suggested_store_owner_share_cents")),
        platform_fee_basis_points=int(fields.get("platform_fee_basis_points", 0)),
        internal_notes=_clean_optional_text(fields.get("internal_notes")),
        active=status == "active",
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_product_templates.insert_one(prepare_for_mongo(template))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=template["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.template_created",
        entity_type="webstore_product_template",
        entity_id=template["id"],
        summary="Webstore product template created",
    )
    return serialize_doc(template)  # type: ignore[return-value]


async def ensure_starter_product_templates(tenant_id: str) -> None:
    for starter in STARTER_PRODUCT_TEMPLATES:
        existing = await db.webstore_product_templates.find_one(
            {"tenant_id": tenant_id, "template_name": starter["template_name"]},
            {"_id": 0, "id": 1},
        )
        if existing:
            continue
        template = WebstoreProductTemplate(
            tenant_id=tenant_id,
            scope="tenant",
            status="active",
            active=True,
            editable_by_shop=True,
            internal_notes=STARTER_PRODUCT_TEMPLATE_MARKER,
            **starter,
        ).model_dump()
        await db.webstore_product_templates.insert_one(prepare_for_mongo(template))


async def list_templates(user: dict, *, active: Optional[bool] = None, scope: Optional[str] = None, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await ensure_starter_product_templates(user["tenant_id"])
    status_filter = status
    if active is not None:
        status_filter = "active" if active else None
    query: dict[str, Any] = {"$or": [{"tenant_id": user["tenant_id"], "scope": {"$ne": "platform"}}, {"tenant_id": PLATFORM_TEMPLATE_TENANT_ID, "scope": "platform"}]}
    if status_filter:
        query["status"] = status_filter
    if scope:
        query["scope"] = scope
    cursor = db.webstore_product_templates.find(query, {"_id": 0}).sort([("scope", 1), ("template_name", 1)])
    items = [serialize_doc(doc) async for doc in cursor]
    return {"items": items, "total": len(items), "limit": 100, "skip": 0}


async def _get_template_for_staff(user: dict, template_id: str) -> dict:
    template = await db.webstore_product_templates.find_one(
        {"id": template_id, "$or": [{"tenant_id": user["tenant_id"]}, {"tenant_id": PLATFORM_TEMPLATE_TENANT_ID, "scope": "platform"}]},
        {"_id": 0},
    )
    if not template:
        raise WebstoreError("template_not_found", "Product template was not found", 404)
    return serialize_doc(template)


async def update_template(user: dict, template_id: str, fields: dict[str, Any]) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if template.get("scope") == "platform" or template.get("tenant_id") == PLATFORM_TEMPLATE_TENANT_ID:
        _require_platform_creator(user)
        tenant_id = PLATFORM_TEMPLATE_TENANT_ID
    else:
        _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
        tenant_id = user["tenant_id"]
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("template_revision_required", "Reload this template before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    text_fields = {
        "template_name": ("template_name", 200),
        "product_category": ("product_category", 120),
        "product_type": ("product_type", 120),
        "default_title": ("default_title", 200),
        "default_short_description": ("default_short_description", 500),
        "default_description": ("default_description", 2000),
        "suggested_category_name": ("suggested_category_name", 120),
        "production_method": ("production_method", 120),
        "supplier_source_info": ("supplier_source_info", 2000),
        "default_production_notes": ("default_production_notes", 2000),
        "internal_notes": ("internal_notes", 2000),
    }
    for key, (field, limit) in text_fields.items():
        if key in fields:
            if key in {"template_name", "product_category", "product_type"}:
                updates[field] = _clean_text(fields.get(key), field, limit=limit)
            else:
                updates[field] = _clean_optional_text(fields.get(key), limit=limit)
    for key in ("best_store_types", "default_variants"):
        if key in fields:
            updates[key] = deepcopy(fields.get(key) or [])
    if "default_artwork_associations" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or template.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or template.get("default_mockup_associations") or [],
            )
            updates["default_artwork_associations"] = deepcopy(fields.get("default_artwork_associations") or [])
        elif fields.get("webstore_id"):
            updates["default_artwork_associations"] = await _normalize_template_artwork_associations(user, fields["webstore_id"], fields.get("default_artwork_associations"))
        elif fields.get("default_artwork_associations"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        else:
            updates["default_artwork_associations"] = []
    if "default_mockup_associations" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or template.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or template.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or [],
            )
            updates["default_mockup_associations"] = deepcopy(fields.get("default_mockup_associations") or [])
        elif fields.get("webstore_id"):
            updates["default_mockup_associations"] = await _normalize_template_mockup_associations(user, fields["webstore_id"], fields.get("default_mockup_associations"))
        elif fields.get("default_mockup_associations"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        else:
            updates["default_mockup_associations"] = []
    if "default_customer_images" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or template.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or template.get("default_mockup_associations") or [],
            )
            updates["default_customer_images"] = deepcopy(fields.get("default_customer_images") or {})
        elif fields.get("webstore_id"):
            updates["default_customer_images"] = await _normalize_customer_images(user["tenant_id"], fields["webstore_id"], fields.get("default_customer_images"))
        elif _has_private_image_file_refs(fields.get("default_customer_images")):
            raise WebstoreError(
                "template_webstore_required_for_private_image",
                "Select a Webstore before using private uploaded files in a tenant template",
                400,
            )
        else:
            updates["default_customer_images"] = deepcopy(fields.get("default_customer_images") or {})
    for key in ("suggested_production_cost_cents", "suggested_selling_price_cents", "suggested_store_owner_share_cents"):
        if key in fields:
            updates[key] = _clean_money(fields.get(key))
    if "platform_fee_basis_points" in fields:
        bps = int(fields.get("platform_fee_basis_points") or 0)
        if bps < 0 or bps > 10000:
            raise WebstoreError("invalid_platform_fee", "Platform fee basis points must be between 0 and 10000", 400)
        updates["platform_fee_basis_points"] = bps
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), TEMPLATE_STATUSES, template.get("status", "active"), "template_status")
        updates["active"] = updates["status"] == "active"
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    try:
        result = await db.webstore_product_templates.find_one_and_update(
            {"tenant_id": tenant_id, "id": template_id, "revision": expected_revision},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_template", "An active template with that name already exists", 409)
    if not result:
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before saving.", 409)
    action = "webstore.template_updated"
    summary = "Webstore product template updated"
    if updates.get("status") == "archived":
        action = "webstore.template_archived"
        summary = "Webstore product template archived"
    elif template.get("status") == "archived" and updates.get("status") == "active":
        action = "webstore.template_restored"
        summary = "Webstore product template restored"
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=template_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product_template",
        entity_id=template_id,
        summary=summary,
    )
    return serialize_doc(result)


async def archive_template(user: dict, template_id: str, expected_revision: int) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if int(expected_revision) != int(template.get("revision") or 1):
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before archiving.", 409)
    if template.get("status") == "archived":
        return template
    return await update_template(user, template_id, {"status": "archived", "expected_revision": expected_revision})


async def restore_template(user: dict, template_id: str, expected_revision: int) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if int(expected_revision) != int(template.get("revision") or 1):
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before restoring.", 409)
    if template.get("status") == "active":
        return template
    return await update_template(user, template_id, {"status": "active", "expected_revision": expected_revision})

__all__ = ['create_template', 'ensure_starter_product_templates', 'list_templates', '_get_template_for_staff', 'update_template', 'archive_template', 'restore_template']
