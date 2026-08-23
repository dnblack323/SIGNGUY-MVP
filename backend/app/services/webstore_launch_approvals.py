"""Owner and staff launch packet decisions for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch_state import _open_change_requests, _payment_readiness, _terms_acceptance

async def _record_launch_packet_decision(
    *,
    identity: dict,
    packet: dict,
    decision: str,
    reason: Optional[str] = None,
) -> dict:
    action = "decline" if decision == "reject" else decision
    return await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_launch_packet",
        parent_id=packet["id"],
        parent_version=int(packet.get("version") or 1),
        action=action,
        reason=reason,
        actor_type="portal_webstore_owner",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("name") or identity.get("email"),
        snapshot_hash=packet.get("snapshot_hash") or _json_hash(packet.get("snapshot") or {}),
        snapshot=packet.get("snapshot") or {},
    )


async def owner_approve_launch_packet(identity: dict, webstore_id: str, packet_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    fields = fields or {}
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id"):
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be approved", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "owner_approved"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before owner approval", 409)
    if packet.get("invalidated_at") or packet.get("status") == "invalidated":
        raise WebstoreError("launch_packet_invalidated", "This launch packet was invalidated and cannot be approved", 409)
    blocking_changes = await _open_change_requests(identity["tenant_id"], webstore_id)
    if blocking_changes:
        raise WebstoreError("blocking_change_requests", "Resolve open owner change requests before approving this packet", 409)
    existing = await db.webstore_packet_approvals.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "packet_id": packet_id, "portal_identity_id": identity["id"]},
        {"_id": 0},
    )
    if existing and existing.get("status") == "current":
        return packet
    now = _now_iso()
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    shared_approval = await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="approve",
        reason=comment,
    )
    approval = WebstorePacketApproval(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        packet_id=packet_id,
        packet_version=int(packet.get("version") or 1),
        portal_identity_id=identity["id"],
        approver_name=identity.get("full_name") or identity.get("name"),
        approver_email=identity.get("email"),
        accepted_snapshot_hash=packet.get("snapshot_hash") or _json_hash(packet.get("snapshot") or {}),
        approved_at=now,
        audit_evidence={
            "portal_identity_id": identity["id"],
            "portal_type": identity.get("portal_type"),
            "packet_status_at_approval": packet.get("status"),
            "approval_id": shared_approval.get("id"),
        },
    ).model_dump()
    try:
        await db.webstore_packet_approvals.insert_one(prepare_for_mongo(approval))
    except DuplicateKeyError:
        existing = await db.webstore_packet_approvals.find_one(
            {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "packet_id": packet_id, "portal_identity_id": identity["id"]},
            {"_id": 0},
        )
        if existing and existing.get("status") == "current":
            return packet
        raise
    packet = await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "owner_approved", "owner_decision_at": now, "owner_decision_by_portal_identity_id": identity["id"]},
    )
    await stores_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "approved",
            "owner_approved_at": now,
            "owner_approved_by_portal_identity_id": identity["id"],
            "owner_approved_packet_id": packet_id,
            "owner_approved_packet_version": int((packet or {}).get("version") or 1),
            "owner_approval_invalidated_at": None,
            "owner_approval_invalidated_reason": None,
        },
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.owner_approved_launch",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary="Webstore owner approved launch packet",
    )
    result = packet or {}
    if result:
        result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_launch_packet", packet_id)
    return result


async def owner_request_launch_packet_changes(identity: dict, webstore_id: str, packet_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id") or packet.get("status") in {"superseded", "invalidated"}:
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can receive change requests", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "changes_requested"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before requesting changes", 409)
    category = _clean_status(fields.get("category"), CHANGE_REQUEST_CATEGORIES, "general", "change_request_category")
    comment = _clean_text(fields.get("comment"), "comment", limit=2000)
    if len(comment.strip()) < 5:
        raise WebstoreError("change_request_comment_required", "Add a meaningful change-request comment", 400)
    now = _now_iso()
    await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="request_changes",
        reason=comment,
    )
    request = WebstoreChangeRequest(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        packet_id=packet_id,
        packet_version=int(packet.get("version") or 1),
        category=category,
        affected_item_ref=_clean_optional_text(fields.get("affected_item_ref"), limit=200),
        owner_comment=comment,
        portal_identity_id=identity["id"],
        owner_visible_history=[
            {
                "at": now,
                "actor": "store_owner",
                "status": "open",
                "message": comment,
            }
        ],
    ).model_dump()
    await db.webstore_change_requests.insert_one(prepare_for_mongo(request))
    await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "changes_requested", "owner_decision_at": now, "change_request_reason": comment},
    )
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "changes_requested"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.change_request_submitted",
        entity_type="webstore_change_request",
        entity_id=request["id"],
        summary="Store Owner submitted Webstore launch packet change request",
        metadata={"packet_id": packet_id, "packet_version": packet.get("version"), "category": category},
    )
    return _portal_change_request(serialize_doc(request))


async def owner_reject_launch_packet(identity: dict, webstore_id: str, packet_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id") or packet.get("status") in {"superseded", "invalidated", "rejected"}:
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be rejected", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "changes_requested"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before rejection", 409)
    comment = _clean_text(fields.get("comment"), "comment", limit=2000)
    now = _now_iso()
    await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="reject",
        reason=comment,
    )
    packet = await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "rejected", "owner_decision_at": now, "owner_decision_by_portal_identity_id": identity["id"], "change_request_reason": comment},
    )
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "changes_requested"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.launch_packet_rejected",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary="Store Owner rejected Webstore launch packet",
        metadata={"packet_version": (packet or {}).get("version")},
    )
    result = packet or {}
    if result:
        result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_launch_packet", packet_id)
    return result


async def staff_update_change_request(user: dict, webstore_id: str, request_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    request = await db.webstore_change_requests.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": request_id}, {"_id": 0})
    if not request:
        raise WebstoreError("change_request_not_found", "Change request not found", 404)
    status = _clean_status(fields.get("status"), CHANGE_REQUEST_STATUSES, request.get("status") or "open", "change_request_status")
    if request.get("status") in {"resolved", "declined", "superseded"} and status != request.get("status"):
        raise WebstoreError("change_request_closed", "Closed change requests cannot be silently edited", 409)
    response = _clean_optional_text(fields.get("response"), limit=2000)
    if status in {"answered", "resolved", "declined"} and not response:
        raise WebstoreError("change_request_response_required", "A staff response is required", 400)
    now = _now_iso()
    history_entry = {
        "at": now,
        "actor": "staff",
        "status": status,
        "message": response,
    }
    updates: dict[str, Any] = {
        "status": status,
        "updated_at": now,
    }
    push: dict[str, Any] = {"owner_visible_history": history_entry}
    internal_note = _clean_optional_text(fields.get("internal_note"), limit=2000)
    if internal_note:
        push["staff_only_history"] = {"at": now, "actor": "staff", "message": internal_note}
    if status in {"resolved", "declined", "superseded"}:
        updates["resolved_at"] = now
    updated = await db.webstore_change_requests.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": request_id},
        {"$set": updates, "$push": push},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if status in {"resolved", "declined", "superseded"}:
        remaining = await _open_change_requests(user["tenant_id"], webstore_id)
        if not remaining and store.get("status") == "changes_requested":
            await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "store_packet_generated"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.change_request_updated",
        entity_type="webstore_change_request",
        entity_id=request_id,
        summary=f"Webstore change request marked {status}",
        metadata={"status": status},
    )
    return _portal_change_request(serialize_doc(updated or request))


async def owner_accept_terms(identity: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    fields = fields or {}
    store = await _owner_portal_store(identity, webstore_id)
    owner = await _get_owner(identity["tenant_id"], store["owner_id"])
    version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    requested_version = fields.get("terms_version") or version
    if requested_version != version:
        raise WebstoreError("terms_version_mismatch", "The current required Terms version must be accepted", 409)
    existing = await _terms_acceptance(identity["tenant_id"], webstore_id, version, identity["id"])
    if existing:
        return _portal_terms_acceptance(existing) or existing
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    now = _now_iso()
    terms_snapshot = _owner_safe_terms_snapshot(store, owner, packet)
    fee_summary = {
        "terms_version": version,
        "payment_readiness": await _payment_readiness(store),
        "store_owner_share_cents": ((packet or {}).get("pricing_summary") or {}).get("store_owner_share_cents", 0),
        "fundraiser_share_cents": ((packet or {}).get("pricing_summary") or {}).get("fundraiser_share_cents", 0),
    }
    authority_snapshot = {"terms": terms_snapshot, "fee_summary": fee_summary}
    authority_snapshot_hash = _json_hash(authority_snapshot)
    acceptance = WebstoreTermsAcceptance(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        terms_version=version,
        portal_identity_id=identity["id"],
        acceptor_name=identity.get("full_name") or identity.get("name"),
        acceptor_email=identity.get("email"),
        accepted_at=now,
        packet_id=(packet or {}).get("id"),
        packet_version=(packet or {}).get("version"),
        terms_snapshot=terms_snapshot,
        fee_summary_snapshot=fee_summary,
        audit_evidence={
            "portal_identity_id": identity["id"],
            "portal_type": identity.get("portal_type"),
            "terms_snapshot_hash": authority_snapshot_hash,
        },
    ).model_dump()
    try:
        await db.webstore_terms_acceptances.insert_one(prepare_for_mongo(acceptance))
    except DuplicateKeyError:
        existing = await _terms_acceptance(identity["tenant_id"], webstore_id, version, identity["id"])
        if existing:
            return _portal_terms_acceptance(existing) or existing
        raise
    shared_approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_terms_acceptance",
        parent_id=acceptance["id"],
        action="approve",
        reason=f"Accepted Webstore Terms version {version}",
        actor_type="portal_webstore_owner",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("name") or identity.get("email"),
        snapshot_hash=authority_snapshot_hash,
        snapshot=authority_snapshot,
    )
    acceptance["audit_evidence"]["approval_id"] = shared_approval.get("id")
    await db.webstore_terms_acceptances.update_one(
        {"tenant_id": identity["tenant_id"], "id": acceptance["id"]},
        {"$set": {"audit_evidence": acceptance["audit_evidence"], "updated_at": _now_iso()}},
    )
    await stores_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=webstore_id,
        updates={
            "terms_fee_acknowledged": True,
            "terms_acceptance_id": acceptance["id"],
            "terms_accepted_version": version,
            "terms_accepted_at": now,
            "terms_accepted_by_portal_identity_id": identity["id"],
        },
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.terms_accepted",
        entity_type="webstore_terms_acceptance",
        entity_id=acceptance["id"],
        summary="Store Owner accepted Webstore Terms",
        metadata={"terms_version": version, "packet_id": (packet or {}).get("id")},
    )
    return _portal_terms_acceptance(serialize_doc(acceptance)) or serialize_doc(acceptance)
