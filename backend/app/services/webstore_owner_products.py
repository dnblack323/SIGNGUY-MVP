"""Owner reads of the last explicitly submitted canonical product snapshot."""
from __future__ import annotations

from copy import deepcopy

from .webstore_context import db
from .webstore_shared_catalog import (
    _approval_history, _current_mockups_for_product, _product_approval_snapshot, _product_image_map,
)
from .webstore_shared_contracts import _json_hash


async def submitted_product_snapshot(tenant_id: str, store: dict, product: dict) -> dict | None:
    """Reuse submission/approval evidence; never reconstruct an edited revision."""
    revision = int(product.get("approval_revision") or 0)
    if not revision or product.get("approval_status") == "not_submitted":
        return None
    snapshot = product.get("approval_snapshot")
    if not snapshot:
        approval = await db.approvals.find_one(
            {"tenant_id": tenant_id, "parent_type": "webstore_product",
             "parent_id": product["id"], "parent_version": revision,
             "snapshot": {"$type": "object"}},
            {"_id": 0, "snapshot": 1}, sort=[("created_at", -1)],
        )
        snapshot = (approval or {}).get("snapshot")
    if not snapshot:
        # Compatibility for old, still-unchanged submitted records. The first
        # staff edit retains this snapshot atomically with the draft update.
        if (int(product.get("revision") or 1) != revision
                or product.get("approval_invalidated_at")
                or product.get("approval_status") not in {
                    "pending_owner_approval", "approved", "changes_requested", "rejected"}):
            return None
        snapshot = await _product_approval_snapshot(
            tenant_id, store["id"], product, public_slug=store.get("public_slug"),
        )
    if (not isinstance(snapshot, dict) or snapshot.get("id") != product["id"]
            or snapshot.get("webstore_id") != store["id"]
            or int(snapshot.get("revision") or 0) != revision):
        return None
    if product.get("approval_snapshot_hash") and _json_hash(snapshot) != product["approval_snapshot_hash"]:
        return None
    return deepcopy(snapshot)


async def owner_product_view(tenant_id: str, store: dict, product: dict) -> dict | None:
    snapshot = await submitted_product_snapshot(tenant_id, store, product)
    if snapshot is None:
        return None
    # Both persisted snapshots and legacy approval evidence pass one allowlist.
    fields = {
        "id", "webstore_id", "name", "description", "full_description", "category",
        "category_id", "product_type", "sku", "selling_price_cents", "variants",
        "personalization_enabled", "personalization_fields", "images", "public",
        "featured", "status", "fulfillment_methods", "default_fulfillment_method",
        "pickup_instructions", "shipping_cost_cents", "revision", "mockups",
    }
    item = {key: deepcopy(value) for key, value in snapshot.items() if key in fields}
    image_refs = product.get("approval_image_refs") or {}
    if not image_refs and int(product.get("revision") or 1) == snapshot["revision"]:
        image_refs = _product_image_map(product)
    for image in item.get("images") or []:
        if (image_refs.get(image.get("slot")) or {}).get("file_id"):
            image["url"] = (f"/api/portal/webstores/{store['id']}/products/{product['id']}"
                            f"/images/{image['slot']}?revision={snapshot['revision']}")
            image["owner_review_media"] = True
    item["approval_revision"] = snapshot["revision"]
    item["approval_status"] = product.get("approval_status")
    item["approval_snapshot_hash"] = product.get("approval_snapshot_hash")
    if product.get("approval_decision_at"):
        item["approval_decision_at"] = product["approval_decision_at"]
    current = (int(product.get("revision") or 1) == snapshot["revision"]
               and not product.get("approval_invalidated_at"))
    if not current:
        if item["approval_status"] == "pending_owner_approval":
            item["approval_status"] = "superseded"
        item["review_notice"] = "Showing the last submitted version. The shop is preparing an update."
    # Mockup decisions may follow product submission. Refresh only decision
    # metadata for the same frozen mockup content, never add unsubmitted media.
    live_mockups = {row["id"]: row for row in await _current_mockups_for_product(tenant_id, store["id"], product)}
    for mockup in item.get("mockups") or []:
        live = live_mockups.get(mockup.get("id"))
        content_keys = {"id", "webstore_id", "product_id", "artwork_id", "generation_source", "purpose", "alt_text"}
        if live and all(mockup.get(key) == live.get(key) for key in content_keys):
            for key in ("approval_status", "approval_decision_at", "status"):
                if key in live:
                    mockup[key] = live[key]
        if not current and mockup.get("approval_status") == "pending_owner_approval":
            mockup["approval_status"] = "superseded"
    item["approval_history"] = await _approval_history(tenant_id, "webstore_product", product["id"])
    return item
