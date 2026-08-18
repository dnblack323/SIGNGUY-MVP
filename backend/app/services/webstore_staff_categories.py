"""Staff product category administration for Webstores."""
from __future__ import annotations

from .webstore_shared import *


async def list_categories(user: dict, webstore_id: str, *, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if status:
        query["status"] = status
    items = []
    async for doc in db.webstore_product_categories.find(query, {"_id": 0}).sort([("status", 1), ("name", 1)]):
        item = serialize_doc(doc)
        item["product_count"] = await db.webstore_products.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": item["id"], "status": {"$ne": "archived"}})
        items.append(item)
    legacy_names = sorted({
        str(doc.get("category") or "").strip()
        async for doc in db.webstore_products.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": {"$in": [None, ""]}, "category": {"$nin": [None, ""]}},
            {"_id": 0, "category": 1},
        )
    })
    return {"items": items, "legacy_categories": legacy_names, "total": len(items)}


async def create_category(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    name = _clean_text(fields.get("name"), "name", limit=120)
    category = WebstoreProductCategory(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        name=name,
        normalized_name=_normalize_name(name),
        description=_clean_optional_text(fields.get("description"), limit=500),
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    try:
        await db.webstore_product_categories.insert_one(prepare_for_mongo(category))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_category", "An active category with that name already exists for this Webstore", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.category_created",
        entity_type="webstore_product_category",
        entity_id=category["id"],
        summary="Webstore product category created",
    )
    return serialize_doc(category)


async def update_category(user: dict, webstore_id: str, category_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("category_revision_required", "Reload this category before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    if "name" in fields:
        updates["name"] = _clean_text(fields.get("name"), "name", limit=120)
        updates["normalized_name"] = _normalize_name(updates["name"])
    if "description" in fields:
        updates["description"] = _clean_optional_text(fields.get("description"), limit=500)
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), CATEGORY_STATUSES, category.get("status", "active"), "category_status")
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    try:
        updated = await db.webstore_product_categories.find_one_and_update(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": category_id, "revision": expected_revision},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_category", "An active category with that name already exists for this Webstore", 409)
    if not updated:
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before saving.", 409)
    action = "webstore.category_updated"
    summary = "Webstore product category updated"
    if updates.get("status") == "archived":
        action = "webstore.category_archived"
        summary = "Webstore product category archived"
    elif category.get("status") == "archived" and updates.get("status") == "active":
        action = "webstore.category_restored"
        summary = "Webstore product category restored"
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product_category",
        entity_id=category_id,
        summary=summary,
    )
    return serialize_doc(updated)


async def archive_category(user: dict, webstore_id: str, category_id: str, expected_revision: int) -> dict:
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    if int(expected_revision) != int(category.get("revision") or 1):
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before archiving.", 409)
    if category.get("status") == "archived":
        return category
    count = await db.webstore_products.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": category_id, "status": {"$ne": "archived"}})
    if count:
        raise WebstoreError("category_in_use", "Move products out of this category before archiving it", 409)
    return await update_category(user, webstore_id, category_id, {"status": "archived", "expected_revision": expected_revision})


async def restore_category(user: dict, webstore_id: str, category_id: str, expected_revision: int) -> dict:
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    if int(expected_revision) != int(category.get("revision") or 1):
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before restoring.", 409)
    if category.get("status") == "active":
        return category
    return await update_category(user, webstore_id, category_id, {"status": "active", "expected_revision": expected_revision})

__all__ = ['list_categories', 'create_category', 'update_category', 'archive_category', 'restore_category']
