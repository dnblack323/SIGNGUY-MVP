"""Staff artwork and mockup listing, creation, and owner approval submission."""
from __future__ import annotations

from .webstore_shared import *


async def list_artwork(user: dict, webstore_id: str, *, product_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query: dict[str, Any] = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if product_id:
        query["product_id"] = {"$in": [None, "", product_id]}
    items = [
        {
            key: doc.get(key)
            for key in ("id", "product_id", "file_name", "file_type", "purpose", "artwork_status", "shop_approved_for_production")
            if doc.get(key) not in (None, "")
        }
        async for doc in db.webstore_artwork_files.find(query, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {"items": items, "total": len(items)}


async def list_mockups(user: dict, webstore_id: str, *, product_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query: dict[str, Any] = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if product_id:
        query["product_id"] = {"$in": [None, "", product_id]}
    items = [
        {
            key: doc.get(key)
            for key in ("id", "product_id", "artwork_id", "purpose", "alt_text", "status", "shop_approved", "owner_visible", "owner_approved", "approval_status", "approval_snapshot_hash", "approval_decision_at")
            if doc.get(key) not in (None, "")
        }
        async for doc in db.webstore_mockups.find(query, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {"items": items, "total": len(items)}


async def create_artwork(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    product_id = fields.get("product_id")
    if product_id:
        await _get_product(user["tenant_id"], product_id, webstore_id)
    file_id = fields.get("file_id") or fields.get("original_file_id")
    if file_id:
        file_doc = await db.webstore_setup_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": file_id, "status": "active"},
            {"_id": 0},
        )
        if not file_doc:
            raise WebstoreError("artwork_file_not_found", "Selected artwork file was not found for this Webstore", 404)
    art = WebstoreArtworkFile(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        uploaded_by_actor_type="staff",
        uploaded_by_id=user["id"],
        file_id=file_id,
        original_file_id=fields.get("original_file_id"),
        original_url=fields.get("original_url"),
        file_name=fields.get("file_name"),
        file_type=fields.get("file_type"),
        purpose=_clean_optional_text(fields.get("purpose"), limit=120),
        notes=_clean_optional_text(fields.get("notes")),
    ).model_dump()
    await db.webstore_artwork_files.insert_one(prepare_for_mongo(art))
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "artwork_needs_review"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.artwork_uploaded",
        entity_type="webstore_artwork_file",
        entity_id=art["id"],
        summary="Webstore artwork uploaded",
    )
    return serialize_doc(art)  # type: ignore[return-value]


async def create_mockup(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    product_id = fields.get("product_id")
    if product_id:
        await _get_product(user["tenant_id"], product_id, webstore_id)
    file_id = fields.get("mockup_file_id")
    if file_id:
        await _setup_file_for_product_reference(user["tenant_id"], webstore_id, file_id)
    mockup = WebstoreMockup(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        artwork_id=fields.get("artwork_id"),
        mockup_file_id=fields.get("mockup_file_id"),
        generation_source=fields.get("generation_source", "manual"),
        purpose=_clean_optional_text(fields.get("purpose"), limit=120),
        alt_text=_clean_optional_text(fields.get("alt_text"), limit=200),
        staff_note=_clean_optional_text(fields.get("staff_note")),
        status=fields.get("status", "generated"),
        shop_approved=bool(fields.get("shop_approved", False)),
        owner_visible=bool(fields.get("owner_visible", False)),
        notes=_clean_optional_text(fields.get("notes")),
    ).model_dump()
    await db.webstore_mockups.insert_one(prepare_for_mongo(mockup))
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "mockups_generated"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.mockup_created",
        entity_type="webstore_mockup",
        entity_id=mockup["id"],
        summary="Webstore mockup created",
    )
    return serialize_doc(mockup)  # type: ignore[return-value]


async def submit_mockup_for_approval(user: dict, webstore_id: str, mockup_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    mockup = await _get_mockup(user["tenant_id"], mockup_id, webstore_id)
    if mockup.get("status") == "archived":
        raise WebstoreError("mockup_archived", "Archived mockups cannot be sent for approval", 409)
    product = await _get_product(user["tenant_id"], mockup["product_id"], webstore_id) if mockup.get("product_id") else None
    snapshot = _mockup_approval_snapshot(mockup, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    now = _now_iso()
    updated = await db.webstore_mockups.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
        {
            "$set": {
                "approval_status": "pending_owner_approval",
                "approval_snapshot_hash": snapshot_hash,
                "owner_visible": True,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.mockup_submitted_for_approval",
        entity_type="webstore_mockup",
        entity_id=mockup_id,
        summary="Webstore mockup submitted for owner approval",
        metadata={"snapshot_hash": snapshot_hash, "comment": fields.get("comment")},
    )
    result = serialize_doc(updated or mockup)
    result["approval_history"] = await _approval_history(user["tenant_id"], "webstore_mockup", mockup_id)
    result["approval_snapshot"] = snapshot
    return result

__all__ = ['list_artwork', 'list_mockups', 'create_artwork', 'create_mockup', 'submit_mockup_for_approval']
