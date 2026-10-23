"""Webstore Owner portal operations."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch import _payment_readiness, _terms_acceptance
from .webstore_next_action import compute_next_action, owner_view, with_derived_state
from .webstore_owner_products import owner_product_view, submitted_product_snapshot

async def owner_portal_list(identity: dict) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"} or not identity.get("webstore_owner_id"):
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    assignment_records = [
        doc
        async for doc in db.webstore_access_assignments.find(
            {"tenant_id": identity["tenant_id"], "portal_identity_id": identity.get("id")},
            {"_id": 0, "webstore_id": 1, "status": 1},
        )
    ]
    if assignment_records:
        assignments = [doc["webstore_id"] for doc in assignment_records if doc.get("status") == "active"]
        return await stores_repo.list(
            tenant_id=identity["tenant_id"],
            filters={"id": {"$in": assignments}, "status": {"$ne": "archived"}},
            sort=[("updated_at", -1)],
        )
    filters = {"owner_id": identity["webstore_owner_id"]}
    filters["status"] = {"$ne": "archived"}
    if identity.get("portal_type") == "webstore_manager":
        if not identity.get("webstore_id"):
            raise WebstoreError("webstore_manager_assignment_required", "Webstore manager scope is required", 403)
        filters["id"] = identity["webstore_id"]
    return await stores_repo.list(
        tenant_id=identity["tenant_id"],
        filters=filters,
        sort=[("updated_at", -1)],
    )


async def owner_portal_detail(identity: dict, webstore_id: str) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    products = []
    async for doc in db.webstore_products.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort([("display_order", 1), ("name", 1)]):
        item = await owner_product_view(identity["tenant_id"], store, doc)
        if item is not None:
            products.append(item)
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(identity["tenant_id"], webstore_id, terms_version, identity.get("id"))
    changes = [
        _portal_change_request(doc)
        async for doc in db.webstore_change_requests.find(
            {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
            {"_id": 0, "staff_only_history": 0},
        ).sort([("created_at", -1)])
    ]
    payment = await _payment_readiness(store)
    derived = await with_derived_state(store)
    owner_gates = [
        {
            "key": "packet_delivered",
            "state": "ready" if packet and packet.get("status") in {"delivered", "sent_for_approval", "owner_approved", "changes_requested"} else "waiting",
            "owner_wording": "Launch packet is available for review." if packet else "The shop is preparing your launch packet.",
        },
        {
            "key": "packet_approval",
            "state": "ready" if store.get("owner_approved_packet_id") == (packet or {}).get("id") else "waiting",
            "owner_wording": "You approved the current packet." if store.get("owner_approved_packet_id") == (packet or {}).get("id") else "Packet approval is still needed.",
        },
        {
            "key": "terms",
            "state": "ready" if terms else "waiting",
            "owner_wording": f"Terms version {terms_version} accepted." if terms else f"Terms version {terms_version} still needs acceptance.",
        },
        {
            "key": "payment",
            "state": payment["state"],
            "owner_wording": "Payment setup is not live yet.",
        },
    ]
    from . import webstore_reports

    owner_report = await webstore_reports.owner_summary(identity["tenant_id"], webstore_id)
    return {
        "webstore": _portal_store(derived),
        "journey": owner_view(derived, await compute_next_action(derived)),
        "products": products,
        "launch_packet": await _portal_launch_packet_with_history(identity["tenant_id"], packet),
        "change_requests": changes,
        "current_terms_version": terms_version,
        "terms_acceptance": _portal_terms_acceptance(terms),
        "readiness_summary": owner_gates,
        "commerce_summary": {
            "order_count": owner_report["order_count"],
            "gross_sales_cents": owner_report["gross_sales_cents"],
            "refund_total_cents": owner_report["refund_total_cents"],
            "payout_total_cents": owner_report["payout_total_cents"],
            "dispute_hold_cents": owner_report["dispute_hold_cents"],
            "product_quantities": owner_report["product_quantities"],
        },
    }


async def owner_decide_product_approval(identity: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    product = await _get_product(identity["tenant_id"], product_id, webstore_id)
    decision = str(fields.get("decision") or "").strip().lower()
    if decision not in PRODUCT_APPROVAL_DECISIONS:
        raise WebstoreError("invalid_product_approval_decision", "Choose approve, request_changes, or reject", 400)
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    if decision in {"request_changes", "reject"} and not comment:
        raise WebstoreError("approval_comment_required", "A comment is required when requesting changes or rejecting a product", 400)
    if product.get("approval_status") != "pending_owner_approval":
        raise WebstoreError("product_not_pending_approval", "This product is not waiting for owner approval", 409)
    expected_revision = int(product.get("approval_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("approval_revision_superseded", "This product changed after it was sent for approval", 409)
    snapshot = await _product_approval_snapshot(identity["tenant_id"], webstore_id, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    if snapshot_hash != product.get("approval_snapshot_hash"):
        raise WebstoreError("approval_snapshot_superseded", "This product review snapshot is no longer current", 409)
    action = "decline" if decision == "reject" else decision
    approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_product",
        parent_id=product_id,
        parent_version=expected_revision,
        action=action,
        reason=comment,
        actor_type="staff",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("email"),
        snapshot_hash=snapshot_hash,
        snapshot=snapshot,
    )
    status = "approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else "rejected")
    now = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "id": product_id},
        {
            "$set": {
                "approval_status": status,
                "approval_decision_at": now,
                "approval_decision_by_portal_identity_id": identity["id"],
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        actor_email=identity.get("email"),
        action=f"webstore.product_approval_{status}",
        entity_type="webstore_product",
        entity_id=product_id,
        summary=f"Webstore product approval decision: {status.replace('_', ' ')}",
        metadata={"approval_id": approval["id"], "product_revision": expected_revision},
    )
    return await owner_product_view(identity["tenant_id"], store, updated or product)


async def owner_product_image(identity: dict, webstore_id: str, product_id: str, slot: str) -> tuple[dict, bytes, str]:
    """Serve only the last submitted image through existing managed storage."""
    store = await _owner_portal_store(identity, webstore_id)
    product = await _get_product(identity["tenant_id"], product_id, webstore_id)
    snapshot = await submitted_product_snapshot(identity["tenant_id"], store, product)
    if not snapshot or slot not in CUSTOMER_IMAGE_SLOTS:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    refs = product.get("approval_image_refs") or {}
    if not refs and int(product.get("revision") or 1) == snapshot["revision"]:
        refs = _product_image_map(product)
    file_id = (refs.get(slot) or {}).get("file_id")
    if not file_id:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    from .webstore_setup_files import find_webstore_setup_file
    doc = await find_webstore_setup_file(identity["tenant_id"], webstore_id, file_id)
    if (not doc or not doc.get("safe_preview_available") or not doc.get("inline_preview_allowed")
            or doc.get("private_download_only") or doc.get("extension") not in PRODUCT_IMAGE_EXTENSIONS):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    if doc.get("extension") == "svg" and not doc.get("svg_sanitized"):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    try:
        data, content_type = storage.get_bytes(doc["storage_key"])
    except FileNotFoundError:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    return doc, data, doc.get("detected_content_type") or content_type


async def owner_decide_mockup_approval(identity: dict, webstore_id: str, mockup_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    mockup = await _get_mockup(identity["tenant_id"], mockup_id, webstore_id)
    decision = str(fields.get("decision") or "").strip().lower()
    if decision not in PRODUCT_APPROVAL_DECISIONS:
        raise WebstoreError("invalid_mockup_approval_decision", "Choose approve, request_changes, or reject", 400)
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    if decision in {"request_changes", "reject"} and not comment:
        raise WebstoreError("approval_comment_required", "A comment is required when requesting changes or rejecting a mockup", 400)
    if mockup.get("approval_status") != "pending_owner_approval":
        raise WebstoreError("mockup_not_pending_approval", "This mockup is not waiting for owner approval", 409)
    product = await _get_product(identity["tenant_id"], mockup["product_id"], webstore_id) if mockup.get("product_id") else None
    if product:
        visible_product = await owner_product_view(identity["tenant_id"], store, product)
        if not visible_product or visible_product.get("review_notice"):
            raise WebstoreError("product_not_pending_approval", "The shop must submit the current product before mockup review", 409)
    snapshot = _mockup_approval_snapshot(mockup, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    if snapshot_hash != mockup.get("approval_snapshot_hash"):
        raise WebstoreError("mockup_snapshot_superseded", "This mockup review snapshot is no longer current", 409)
    action = "decline" if decision == "reject" else decision
    approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_mockup",
        parent_id=mockup_id,
        action=action,
        reason=comment,
        actor_type="staff",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("email"),
        snapshot_hash=snapshot_hash,
        snapshot=snapshot,
    )
    status = "approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else "rejected")
    now = _now_iso()
    updated = await db.webstore_mockups.find_one_and_update(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
        {
            "$set": {
                "approval_status": status,
                "approval_decision_at": now,
                "approval_decision_by_portal_identity_id": identity["id"],
                "owner_approved": decision == "approve",
                "status": "owner_approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else mockup.get("status", "generated")),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        actor_email=identity.get("email"),
        action=f"webstore.mockup_approval_{status}",
        entity_type="webstore_mockup",
        entity_id=mockup_id,
        summary=f"Webstore mockup approval decision: {status.replace('_', ' ')}",
        metadata={"approval_id": approval["id"]},
    )
    result = _owner_safe_mockup_snapshot(updated or mockup)
    result["owner_approved"] = bool((updated or mockup).get("owner_approved"))
    result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_mockup", mockup_id)
    return result

__all__ = [name for name in globals() if not name.startswith("__")]
