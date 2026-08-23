"""Staff product draft updates, archival, restoration, and approval invalidation."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch import _invalidate_packet_approval_if_needed


async def update_product(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any], *, allow_system_transition: bool = False) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if not allow_system_transition:
        if STAGE4A_PUBLICATION_FIELDS & set(fields):
            _reject_stage4a_publication_request(fields)
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("product_revision_required", "Reload this product before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    text_fields = {
        "name": ("name", 200, True),
        "short_description": ("short_description", 500, False),
        "full_description": ("full_description", 2000, False),
        "description": ("description", 2000, False),
        "product_type": ("product_type", 120, False),
        "production_method": ("production_method", 120, False),
        "supplier_source_info": ("supplier_source_info", 2000, False),
        "fulfillment_notes": ("fulfillment_notes", 2000, False),
        "production_notes": ("production_notes", 2000, False),
    }
    for key, (field, limit, required) in text_fields.items():
        if key in fields:
            updates[field] = _clean_text(fields.get(key), field, limit=limit) if required else _clean_optional_text(fields.get(key), limit=limit)
    if {"category_id", "category_name", "category"} & set(fields):
        category_id, category_name, legacy_category = await _normalize_product_category(user, webstore_id, fields, product)
        updates.update({"category_id": category_id, "category_name": category_name, "category": legacy_category})
    if "customer_images" in fields:
        updates["customer_images"] = await _normalize_customer_images(user["tenant_id"], webstore_id, fields.get("customer_images"))
    if "artwork_associations" in fields:
        updates["artwork_associations"] = await _normalize_artwork_associations(user, webstore_id, product_id, fields.get("artwork_associations"))
    if "mockup_associations" in fields:
        updates["mockup_associations"] = await _normalize_mockup_associations(user, webstore_id, product_id, fields.get("mockup_associations"))
    if "sku" in fields:
        updates["sku"] = _clean_optional_text(fields.get("sku"), limit=120)
    selling_price_cents = int(product.get("selling_price_cents") or 0)
    if "selling_price_cents" in fields:
        selling_price_cents = _clean_money(fields.get("selling_price_cents"), default=selling_price_cents)
        updates["selling_price_cents"] = selling_price_cents
    if "production_cost_cents" in fields:
        updates["production_cost_cents"] = _clean_money(fields.get("production_cost_cents"), default=int(product.get("production_cost_cents") or 0))
    if "store_owner_share_cents" in fields:
        updates["store_owner_share_cents"] = _clean_money(fields.get("store_owner_share_cents"), default=int(product.get("store_owner_share_cents") or 0))
    if "fundraiser_share_cents" in fields:
        updates["fundraiser_share_cents"] = _clean_money(fields.get("fundraiser_share_cents"), default=int(product.get("fundraiser_share_cents") or 0))
    if "platform_fee_basis_points" in fields:
        updates["platform_fee_basis_points"] = _clean_basis_points(fields.get("platform_fee_basis_points"), default=int(product.get("platform_fee_basis_points") or 0))
    if "fulfillment_methods" in fields:
        updates["fulfillment_methods"] = _normalize_fulfillment_methods(fields.get("fulfillment_methods"))
    if "default_fulfillment_method" in fields:
        default_method = str(fields.get("default_fulfillment_method") or "").strip().lower() or None
        updates["default_fulfillment_method"] = default_method
    if "pickup_instructions" in fields:
        updates["pickup_instructions"] = _clean_optional_text(fields.get("pickup_instructions"), limit=2000)
    if "shipping_cost_cents" in fields:
        updates["shipping_cost_cents"] = _clean_money(fields.get("shipping_cost_cents"), default=int(product.get("shipping_cost_cents") or 0))
    if "variants" in fields:
        updates["variants"] = _normalize_variants(fields.get("variants"), base_selling_price_cents=selling_price_cents)
    personalization_enabled = bool(product.get("personalization_enabled"))
    if "personalization_enabled" in fields:
        personalization_enabled = bool(fields.get("personalization_enabled"))
        updates["personalization_enabled"] = personalization_enabled
    if "personalization_fields" in fields or "personalization_enabled" in fields:
        updates["personalization_fields"] = _normalize_personalization_fields(
            fields.get("personalization_fields", product.get("personalization_fields") or []),
            enabled=personalization_enabled,
        )
    if "bundle_items" in fields:
        updates["bundle_items"] = await _normalize_bundle_items(user, webstore_id, product_id, fields.get("bundle_items"))
    if "inventory_policy" in fields:
        updates["inventory_policy"] = str(fields.get("inventory_policy") or "not_tracked")[:80]
    if "inventory_quantity" in fields:
        updates["inventory_quantity"] = _clean_quantity(fields.get("inventory_quantity"), default=None)
    if "display_order" in fields:
        updates["display_order"] = _clean_quantity(fields.get("display_order"), default=int(product.get("display_order") or 0)) or 0
    if "launch_packet_eligible" in fields:
        updates["launch_packet_eligible"] = bool(fields.get("launch_packet_eligible"))
    if "launch_packet_include" in fields:
        updates["launch_packet_include"] = bool(fields.get("launch_packet_include"))
    projected_owner_share = int(updates.get("store_owner_share_cents", product.get("store_owner_share_cents") or 0) or 0)
    projected_fundraiser_share = int(updates.get("fundraiser_share_cents", product.get("fundraiser_share_cents") or 0) or 0)
    if projected_owner_share + projected_fundraiser_share > selling_price_cents:
        raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the product selling price", 400)
    await _ensure_unique_product_skus(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        sku=updates.get("sku", product.get("sku")),
        variants=updates.get("variants", product.get("variants") or []),
    )
    if "public" in fields:
        updates["public"] = bool(fields.get("public"))
    if "featured" in fields:
        updates["featured"] = bool(fields.get("featured"))
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), PRODUCT_STATUSES, product.get("status", "draft"), "product_status")
    projected = {**product, **updates}
    if projected.get("default_fulfillment_method") and projected["default_fulfillment_method"] not in _normalize_fulfillment_methods(projected.get("fulfillment_methods")):
        raise WebstoreError("invalid_default_fulfillment_method", "The default fulfillment method must be enabled for this product", 400)
    if projected.get("status") in {"ready", "active"}:
        missing = [item["label"] for item in _product_setup_requirements(projected) if not item["complete"]]
        if missing:
            raise WebstoreError("product_not_ready", f"Complete product setup before marking it ready: {', '.join(missing)}", 409)
        updates["launch_packet_eligible"] = True
    if updates.get("launch_packet_include") and not bool(projected.get("launch_packet_eligible") or updates.get("launch_packet_eligible")):
        updates["launch_packet_eligible"] = True
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": product_id, "revision": expected_revision},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before saving.", 409)
    activity_events: list[tuple[str, str, dict[str, Any]]] = []
    if "customer_images" in updates:
        activity_events.extend(_image_slot_change_events(product.get("customer_images") or {}, updates.get("customer_images") or {}))
    if "artwork_associations" in updates:
        art_action, art_summary, artwork_id = _association_change_summary(
            product.get("artwork_associations") or [],
            updates.get("artwork_associations") or [],
            key="artwork_id",
            label="artwork",
        )
        activity_events.append((art_action, art_summary, {"artwork_id": artwork_id} if artwork_id else {}))
    if "mockup_associations" in updates:
        mock_action, mock_summary, mockup_id = _association_change_summary(
            product.get("mockup_associations") or [],
            updates.get("mockup_associations") or [],
            key="mockup_id",
            label="mockup",
        )
        activity_events.append((mock_action, mock_summary, {"mockup_id": mockup_id} if mockup_id else {}))
    action = "webstore.product_draft_updated"
    summary = "Webstore product draft updated"
    metadata: dict[str, Any] = {}
    if updates.get("status") == "archived":
        action = "webstore.product_archived"
        summary = "Webstore product archived"
    elif product.get("status") == "archived" and updates.get("status") == "draft":
        action = "webstore.product_restored"
        summary = "Webstore product restored to draft"
    elif len(activity_events) == 1:
        action, summary, metadata = activity_events[0]
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product",
        entity_id=product_id,
        summary=summary,
        metadata={k: v for k, v in metadata.items() if v not in (None, "")},
    )
    for event_action, event_summary, metadata in activity_events:
        if event_action == action:
            continue
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            action=event_action,
            entity_type="webstore_product",
            entity_id=product_id,
            summary=event_summary,
            metadata={k: v for k, v in metadata.items() if v not in (None, "")},
        )
    changed_material_fields = {
        key for key in (set(updates) & MATERIAL_PRODUCT_FIELDS)
        if key in updated and updated.get(key) != product.get(key)
    }
    if changed_material_fields:
        await _invalidate_product_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            product=product,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material product fields changed: {', '.join(sorted(changed_material_fields))}",
        )
        updated["approval_status"] = "superseded"
        updated["approval_invalidated_at"] = _now_iso()
        updated["approval_invalidated_reason"] = f"Material product fields changed: {', '.join(sorted(changed_material_fields))}"
        await _invalidate_packet_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material product fields changed: {', '.join(sorted(changed_material_fields))}",
            changed_fields=changed_material_fields,
        )
    return _staff_product(updated, public_slug=store.get("public_slug"))


async def archive_product(user: dict, webstore_id: str, product_id: str, expected_revision: int) -> dict:
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if int(expected_revision) != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before archiving.", 409)
    if product.get("status") == "archived":
        return _staff_product(product)
    return await update_product(user, webstore_id, product_id, {"status": "archived", "expected_revision": expected_revision}, allow_system_transition=True)


async def restore_product(user: dict, webstore_id: str, product_id: str, expected_revision: int) -> dict:
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if int(expected_revision) != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before restoring.", 409)
    if product.get("status") == "draft":
        return _staff_product(product)
    if product.get("status") != "archived":
        raise WebstoreError("product_restore_not_archived", "Only archived products can be restored", 409)
    return await update_product(user, webstore_id, product_id, {"status": "draft", "public": False, "featured": False, "expected_revision": expected_revision}, allow_system_transition=True)

__all__ = ['update_product', 'archive_product', 'restore_product']
