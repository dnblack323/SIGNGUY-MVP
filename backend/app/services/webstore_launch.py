"""Launch packet, approval, readiness, and lifecycle workflows for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_payment_boundary import _provider_authority_from_record

async def _included_packet_products(tenant_id: str, webstore_id: str, public_slug: Optional[str]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    async for product in db.webstore_products.find(
        {
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "status": {"$ne": "archived"},
            "launch_packet_include": True,
        },
        {"_id": 0},
    ).sort([("featured", -1), ("category_name", 1), ("name", 1)]):
        product = serialize_doc(product)
        requirements = _product_setup_requirements(product)
        eligible = bool(product.get("launch_packet_eligible")) and _derived_catalog_status(product) in {"ready", "active"}
        safe_product = _public_product(product, public_slug=public_slug)
        safe_product["packet_ref"] = product["id"]
        safe_product["revision"] = product.get("revision")
        safe_product["launch_packet_eligible"] = eligible
        safe_product["owner_visible_financial_summary"] = {
            "store_owner_share_cents": int(product.get("store_owner_share_cents") or 0),
            "fundraiser_share_cents": int(product.get("fundraiser_share_cents") or 0),
        }
        mockup_ids = _association_ids(product.get("mockup_associations") or [], "mockup_id")
        mockups: list[dict[str, Any]] = []
        async for mockup in db.webstore_mockups.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "$or": [
                    {"id": {"$in": sorted(mockup_ids)}} if mockup_ids else {"id": "__none__"},
                    {"product_id": product["id"], "owner_visible": True},
                ],
            },
            {"_id": 0},
        ).sort([("created_at", 1)]):
            mockup = serialize_doc(mockup)
            if mockup.get("status") == "archived":
                continue
            if not (mockup.get("owner_visible") or mockup.get("shop_approved") or mockup.get("status") in {"shop_approved", "owner_approved"}):
                continue
            mockups.append(
                {
                    "id": mockup.get("id"),
                    "purpose": mockup.get("purpose"),
                    "alt_text": mockup.get("alt_text"),
                    "status": mockup.get("status"),
                    "approval_status": mockup.get("approval_status"),
                    "owner_visible": bool(mockup.get("owner_visible")),
                }
            )
        safe_product["mockups"] = mockups
        product_approval_current = (
            product.get("approval_status") == "approved"
            and int(product.get("approval_revision") or 0) == int(product.get("revision") or 1)
            and not product.get("approval_invalidated_at")
        )
        included_mockups_approved = all(
            mockup.get("approval_status") == "approved" or mockup.get("status") == "owner_approved"
            for mockup in mockups
        )
        requirements = [
            *requirements,
            {"key": "product_owner_approval", "label": "Product owner approval", "complete": product_approval_current},
            {"key": "mockup_owner_approval", "label": "Mockup owner approval", "complete": included_mockups_approved},
        ]
        safe_product["approval_status"] = product.get("approval_status")
        safe_product["approval_revision"] = product.get("approval_revision")
        safe_product["readiness"] = {
            "status": "ready" if eligible and all(item["complete"] for item in requirements) else "blocked",
            "requirements": requirements,
        }
        products.append({k: v for k, v in safe_product.items() if v not in (None, "")})
    return products


async def _payment_readiness(store: dict) -> dict[str, Any]:
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store.get("tenant_id"), "webstore_id": store.get("id"), "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    provider_status = provider_configuration_status(settings, authority)
    state = provider_status["state"]
    return {
        "state": state,
        "label": provider_status["label"],
        "ready": bool(provider_status["provider_authority"]),
        "required": True,
        "provider_authority": bool(provider_status["provider_authority"]),
        "provider_mode": (record or {}).get("provider_mode") or getattr(settings, "stripe_mode", "test"),
        "provider_account_reference": (record or {}).get("connected_account_reference"),
        "requirements_currently_due": (record or {}).get("requirements_currently_due") or [],
        "reason": provider_status["reason"],
        "violations": provider_status["violations"],
        "stored_flags_ignored": True,
    }


async def _terms_acceptance(tenant_id: str, webstore_id: str, terms_version: str, portal_identity_id: Optional[str] = None) -> Optional[dict]:
    query: dict[str, Any] = {
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "terms_version": terms_version,
        "status": "current",
    }
    if portal_identity_id:
        query["portal_identity_id"] = portal_identity_id
    doc = await db.webstore_terms_acceptances.find_one(query, {"_id": 0}, sort=[("accepted_at", -1)])
    return serialize_doc(doc) if doc else None


async def _open_change_requests(tenant_id: str, webstore_id: str) -> list[dict[str, Any]]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_change_requests.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$in": ["open", "answered"]}},
            {"_id": 0},
        ).sort([("created_at", 1)])
    ]


async def _assemble_launch_packet_snapshot(user: dict, store: dict, fields: dict[str, Any]) -> dict[str, Any]:
    store = await _ensure_public_slug(store)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    published_branding = await branding_svc.published_branding_for_store(store)
    products = await _included_packet_products(user["tenant_id"], store["id"], store.get("public_slug"))
    qr_destination = store.get("public_url") or f"/p/webstores/{store.get('public_slug')}"
    qr_reference = {
        "destination": qr_destination,
        "status": "launch_destination",
        "download_url": f"/api/webstores/{store['id']}/qr-code-preview",
        "warning": "QR destination opens to buyers only after the Webstore lifecycle status is live.",
    }
    pricing_summary = {
        "product_count": len(products),
        "lowest_price_cents": min([int(p.get("selling_price_cents") or 0) for p in products], default=0),
        "highest_price_cents": max([int(p.get("selling_price_cents") or 0) for p in products], default=0),
        "store_owner_share_cents": sum(int((p.get("owner_visible_financial_summary") or {}).get("store_owner_share_cents") or 0) for p in products),
        "fundraiser_share_cents": sum(int((p.get("owner_visible_financial_summary") or {}).get("fundraiser_share_cents") or 0) for p in products),
    }
    branding_source = published_branding or store.get("branding") or {}
    await _validate_webstore_asset_refs(user["tenant_id"], store["id"], branding_source, field="branding")
    brand_basics = branding_source.get("brand_basics") or {}
    colors_fonts = branding_source.get("colors_fonts") or {}
    hero = branding_source.get("hero") or {}
    store_information = branding_source.get("store_information") or {}
    owner_preview = {
        "display_name": brand_basics.get("display_name") or store.get("name"),
        "logo": brand_basics.get("primary_logo") or {},
        "banner_image": hero.get("image") or {},
        "accent_color": colors_fonts.get("accent_color") or colors_fonts.get("primary_color"),
        "headline": hero.get("headline") or brand_basics.get("display_name") or store.get("name"),
        "greeting": store_information.get("welcome_text") or store_information.get("store_instructions") or "",
        "catalog_product_count": len(products),
    }
    snapshot = {
        "schema": "webstore_launch_packet_v2",
        "webstore": {
            "name": store.get("name"),
            "store_type": store.get("store_type"),
            "description": store.get("description"),
            "public_slug": store.get("public_slug"),
            "share_url": qr_destination,
            "deadline_at": store.get("deadline_at"),
            "target_launch_at": store.get("target_launch_at") or store.get("intended_launch_at"),
            "intended_close_at": store.get("intended_close_at"),
            "event_start_at": store.get("event_start_at"),
            "event_location": store.get("event_location"),
        },
        "store_owner": {
            "name": owner.get("name"),
            "email": owner.get("email"),
            "organization": owner.get("organization"),
        },
        "branding": branding_source,
        "owner_preview": {k: v for k, v in owner_preview.items() if v not in (None, "", {})},
        "products": products,
        "pricing_summary": pricing_summary,
        "terms": _owner_safe_terms_snapshot(store, owner),
        "qr_reference": qr_reference,
        "approval_instructions": "Review this exact packet version. Approve it or submit a structured change request.",
        "public_commerce_status": "Webstore catalog and approval preparation are available. Verified provider checkout is used when Stripe Connect is ready; canonical Order and Production handoff remains deferred to Stage 8.",
    }
    promotion_copy = _clean_optional_text(fields.get("promotion_copy")) or f"{store.get('name')} is being prepared for owner review."
    return {
        "snapshot": snapshot,
        "snapshot_hash": _json_hash(snapshot),
        "pricing_summary": pricing_summary,
        "promotion_copy": promotion_copy,
        "qr_code_url": fields.get("qr_code_url") or qr_reference["download_url"],
        "share_url": fields.get("share_url") or qr_destination,
    }


async def _invalidate_packet_approval_if_needed(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    reason: str,
    changed_fields: set[str],
) -> None:
    store = await _get_store(tenant_id, webstore_id)
    if not store.get("owner_approved_packet_id") or store.get("owner_approval_invalidated_at"):
        return
    now = _now_iso()
    await db.webstore_packet_approvals.update_many(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "packet_id": store.get("owner_approved_packet_id"), "status": "current"},
        {"$set": {"status": "invalidated", "invalidated_at": now, "invalidated_reason": reason, "updated_at": now}},
    )
    await db.approvals.update_many(
        {"tenant_id": tenant_id, "parent_type": "webstore_launch_packet", "parent_id": store.get("owner_approved_packet_id"), "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason, "updated_at": now}},
    )
    await db.webstore_launch_packets.update_one(
        {"tenant_id": tenant_id, "id": store.get("owner_approved_packet_id")},
        {"$set": {"status": "invalidated", "invalidated_at": now, "invalidated_reason": reason, "updated_at": now}},
    )
    await db.webstores.update_one(
        {"tenant_id": tenant_id, "id": webstore_id},
        {
            "$set": {
                "owner_approved_at": None,
                "owner_approved_by_portal_identity_id": None,
                "owner_approved_packet_id": None,
                "owner_approved_packet_version": None,
                "owner_approval_invalidated_at": now,
                "owner_approval_invalidated_reason": reason,
                "status": "store_packet_generated" if store.get("status") in {"approved", "launch_ready", "scheduled"} else store.get("status"),
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action="webstore.packet_approval_invalidated",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore owner packet approval invalidated by material change",
        metadata={"reason": reason, "fields": sorted(changed_fields)},
    )


async def generate_launch_packet(user: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    fields = fields or {}
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    assembled = await _assemble_launch_packet_snapshot(user, store, fields)
    products = assembled["snapshot"].get("products") or []
    if not products or any((product.get("readiness") or {}).get("status") != "ready" for product in products):
        raise WebstoreError(
            "launch_packet_products_not_ready",
            "Finish product setup and current product/mockup owner approvals before generating the final launch packet.",
            409,
        )
    branding_validation = branding_svc.validation_for_branding(store, assembled["snapshot"].get("branding") or {})
    if branding_validation["errors"]:
        raise WebstoreError(
            "launch_packet_branding_not_ready",
            "Publish owner-safe branding before generating the final launch packet.",
            409,
        )
    last = await db.webstore_launch_packets.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0, "version": 1, "status": 1},
        sort=[("version", -1)],
    )
    version = int((last or {}).get("version") or 0) + 1
    now = _now_iso()
    await db.webstore_launch_packets.update_many(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$in": ["generated", "sent_for_approval", "delivered", "changes_requested", "rejected"]}},
        {"$set": {"status": "superseded", "superseded_at": now, "updated_at": now}},
    )
    packet = WebstoreLaunchPacket(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        version=version,
        status="generated",
        snapshot=assembled["snapshot"],
        snapshot_hash=assembled["snapshot_hash"],
        pricing_summary=assembled["pricing_summary"],
        promotion_copy=assembled["promotion_copy"],
        qr_code_url=assembled["qr_code_url"],
        share_url=assembled["share_url"],
        generated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_launch_packets.insert_one(prepare_for_mongo(packet))
    await stores_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "store_packet_generated",
            "launch_packet_id": packet["id"],
            "launch_packet_version": version,
            "owner_approval_invalidated_at": None,
            "owner_approval_invalidated_reason": None,
        },
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.launch_packet_generated",
        entity_type="webstore_launch_packet",
        entity_id=packet["id"],
        summary=f"Webstore launch packet version {version} generated",
        metadata={"version": version, "snapshot_hash": packet.get("snapshot_hash")},
    )
    return serialize_doc(packet)  # type: ignore[return-value]


async def send_launch_packet(user: dict, webstore_id: str, packet_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    if owner.get("status") != "active" or not owner.get("portal_identity_id") or not owner.get("email"):
        raise WebstoreError("launch_packet_recipient_not_verified", "A verified Store Owner portal recipient is required before delivery", 409)
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("status") in {"sent_for_approval", "delivered"} and packet.get("delivery_recipient_email") == owner.get("email"):
        return packet
    if packet.get("status") != "generated":
        raise WebstoreError("launch_packet_not_deliverable", "Only the current generated packet can be delivered", 409)
    if packet.get("id") != store.get("launch_packet_id"):
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be delivered", 409)
    idempotency_key = f"{webstore_id}:packet:{packet_id}:owner:{owner['id']}:v{packet.get('version')}"
    existing = await db.webstore_launch_packets.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "delivery_idempotency_key": idempotency_key}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    portal_path = f"/portal/webstores/{webstore_id}"
    subject = f"{store.get('name')} launch packet is ready for review"
    body = (
        f"Your SignGuy Webstore launch packet version {packet.get('version')} is ready for review. "
        f"Open your secure Store Owner portal: {portal_path}"
    )
    ok, msg_id, error = send_email(to_email=owner["email"], subject=subject, body_text=body)
    email_log_id = f"webstore-packet-delivery-{packet_id}"
    await db.email_logs.update_one(
        {"tenant_id": user["tenant_id"], "id": email_log_id},
        {
            "$setOnInsert": {
                "id": email_log_id,
                "tenant_id": user["tenant_id"],
                "related_type": "general",
                "related_id": packet_id,
                "template": "general",
                "to_email": owner["email"],
                "from_email": "system@signguy.ai",
                "subject": subject,
                "body": body,
                "sent_by": user["id"],
                "attachment_file_ids": [],
                "idempotency_key": idempotency_key,
                "created_at": _now_iso(),
            },
            "$set": {
                "status": "sent" if ok else "skipped",
                "error_message": error,
                "sendgrid_message_id": msg_id,
                "updated_at": _now_iso(),
            },
        },
        upsert=True,
    )
    await record_processed_activity(
        tenant_id=user["tenant_id"],
        email_log_id=email_log_id,
        to_email=owner["email"],
        sendgrid_message_id=msg_id,
        related_entity_type="webstore_launch_packet",
        related_entity_id=packet_id,
        ok=ok,
        error=error,
    )
    now = _now_iso()
    updated = await db.webstore_launch_packets.find_one_and_update(
        {
            "tenant_id": user["tenant_id"],
            "id": packet_id,
            "status": "generated",
            "$or": [{"delivery_idempotency_key": {"$exists": False}}, {"delivery_idempotency_key": None}],
        },
        {
            "$set": {
                "status": "delivered",
                "sent_at": now,
                "delivered_at": now if ok else None,
                "delivered_by_user_id": user.get("id"),
                "delivery_recipient_email": owner["email"],
                "delivery_status": "sent" if ok else "test_capture_unavailable",
                "delivery_error": error,
                "delivery_idempotency_key": idempotency_key,
                "delivery_portal_path": portal_path,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        existing = await db.webstore_launch_packets.find_one({"tenant_id": user["tenant_id"], "id": packet_id}, {"_id": 0})
        return serialize_doc(existing or {})
    packet = serialize_doc(updated)
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "sent_for_approval"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.launch_packet_sent",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary=f"Webstore launch packet version {packet.get('version')} delivered for owner approval",
        metadata={"version": packet.get("version"), "delivery_status": packet.get("delivery_status"), "email_log_id": email_log_id},
    )
    return packet


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


async def launch_readiness(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    owner = await owners_repo.get(tenant_id=user["tenant_id"], entity_id=store["owner_id"])
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=store["launch_packet_id"]) if store.get("launch_packet_id") else None
    included_products = await _included_packet_products(user["tenant_id"], webstore_id, store.get("public_slug"))
    open_changes = await _open_change_requests(user["tenant_id"], webstore_id)
    questionnaire = await submissions_repo.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$in": ["submitted", "reviewed"]}}
    )
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(user["tenant_id"], webstore_id, terms_version)
    payment = await _payment_readiness(store)
    type_requirements = evaluate_type_requirements(store)
    branding = await branding_svc.published_branding_for_store(store)
    branding_source = branding or store.get("branding") or {}
    branding_validation = (
        branding_svc.validation_for_branding(store, branding_source)
        if branding_source
        else {"errors": ["Publish owner-safe branding with logo/color/greeting content before launch readiness."], "warnings": []}
    )
    branding_complete = bool(branding_source) and not branding_validation["errors"]
    entitlement_ready = await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY)
    delivered = bool(packet and packet.get("status") in {"delivered", "sent_for_approval", "owner_approved"} and packet.get("id") == store.get("launch_packet_id"))
    approved = bool(
        packet
        and store.get("owner_approved_packet_id") == packet.get("id")
        and store.get("owner_approved_packet_version") == packet.get("version")
        and store.get("owner_approved_at")
        and not store.get("owner_approval_invalidated_at")
        and packet.get("status") == "owner_approved"
    )
    active_public_count = await db.webstore_products.count_documents(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    gates = [
        {
            "key": "entitlement",
            "state": "ready" if entitlement_ready else "blocked",
            "reason": "Webstores entitlement is active." if entitlement_ready else "Webstores entitlement is not active.",
            "severity": "blocking",
            "action": "Enable the Webstores feature entitlement.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "The store workspace is not available yet.",
            "blocking": not entitlement_ready,
        },
        {
            "key": "owner_authorized",
            "state": "ready" if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "blocked",
            "reason": "Store Owner portal recipient is active." if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "Assign an active Store Owner portal recipient.",
            "severity": "blocking",
            "action": "Create or resend the Store Owner portal invitation.",
            "resource": {"type": "webstore_owner", "id": store.get("owner_id")},
            "owner_wording": "Store Owner access is not ready yet.",
            "blocking": not (owner and owner.get("status") == "active" and owner.get("portal_identity_id")),
        },
        {
            "key": "store_identity",
            "state": "ready" if store.get("name") and store.get("slug") and store.get("public_slug") else "blocked",
            "reason": "Store identity and safe public reference are present." if store.get("name") and store.get("slug") and store.get("public_slug") else "Complete store name, internal slug, and public slug.",
            "severity": "blocking",
            "action": "Complete store setup details.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "Store details are still being prepared.",
            "blocking": not (store.get("name") and store.get("slug") and store.get("public_slug")),
        },
        {
            "key": "questionnaire_complete",
            "state": "ready" if questionnaire else "blocked",
            "reason": "Store Owner questionnaire has been submitted." if questionnaire else "Store Owner questionnaire must be submitted before launch readiness.",
            "severity": "blocking",
            "action": "Send or complete the Webstore questionnaire.",
            "resource": {"type": "webstore_questionnaire_submission", "id": (questionnaire or {}).get("id")},
            "owner_wording": "Store questionnaire answers are still needed.",
            "blocking": not bool(questionnaire),
        },
        {
            "key": "included_products_ready",
            "state": "ready" if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "blocked",
            "reason": "Included products, product approvals, and mockup approvals are ready for owner review." if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "Include at least one ready product with price, variants/SKU, customer-facing media, and current product/mockup approvals.",
            "severity": "blocking",
            "action": "Finish Product Setup and packet inclusion.",
            "resource": {"type": "webstore_products", "id": webstore_id},
            "owner_wording": "Products are still being prepared.",
            "blocking": not (included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products)),
        },
        {
            "key": "branding_preview_complete",
            "state": "ready" if branding_complete else "blocked",
            "reason": "Owner-safe branding preview content is complete." if branding_complete else "Complete owner-visible branding display content.",
            "severity": "blocking",
            "action": "Review the Branding tab and complete the owner-safe preview.",
            "resource": {"type": "webstore_branding", "id": webstore_id},
            "owner_wording": "Store branding and welcome content are still being prepared.",
            "blocking": not branding_complete,
            "requirements": branding_validation,
        },
        {
            "key": "packet_generated",
            "state": "ready" if packet else "blocked",
            "reason": f"Launch packet version {packet.get('version')} exists." if packet else "Generate a Launch Packet.",
            "severity": "blocking",
            "action": "Generate the packet from current setup.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet is not ready yet.",
            "blocking": not bool(packet),
        },
        {
            "key": "packet_delivered",
            "state": "ready" if delivered else "blocked",
            "reason": "Current packet version was delivered to the Store Owner portal." if delivered else "Deliver the current packet version to the Store Owner.",
            "severity": "blocking",
            "action": "Send the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet has not been delivered yet.",
            "blocking": not delivered,
        },
        {
            "key": "packet_approved",
            "state": "ready" if approved else "blocked",
            "reason": f"Store Owner approved packet version {packet.get('version')}." if approved else (store.get("owner_approval_invalidated_reason") or "Store Owner approval is required for the current packet version."),
            "severity": "blocking",
            "action": "Have the Store Owner approve the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Approval is still required for the current packet version.",
            "blocking": not approved,
        },
        {
            "key": "terms_current",
            "state": "ready" if terms else "blocked",
            "reason": f"Current Terms version {terms_version} accepted." if terms else f"Store Owner must accept Terms version {terms_version}.",
            "severity": "blocking",
            "action": "Store Owner accepts the current Terms version.",
            "resource": {"type": "webstore_terms_acceptance", "id": (terms or {}).get("id")},
            "owner_wording": "Terms acceptance is still required.",
            "blocking": not bool(terms),
        },
        {
            "key": "change_requests_resolved",
            "state": "ready" if not open_changes else "blocked",
            "reason": "No open Store Owner change requests." if not open_changes else f"{len(open_changes)} owner change request(s) remain open or answered.",
            "severity": "blocking",
            "action": "Respond to and resolve owner change requests.",
            "resource": {"type": "webstore_change_requests", "id": webstore_id},
            "owner_wording": "Requested changes are being reviewed.",
            "blocking": bool(open_changes),
        },
        {
            "key": "type_requirements",
            "state": "ready" if type_requirements["complete"] else "blocked",
            "reason": "Store-type settings and requirements are complete." if type_requirements["complete"] else "Complete required store-type settings before launch.",
            "severity": "blocking",
            "action": "Review the Store Type Rules panel and complete missing settings.",
            "resource": {"type": "webstore_type_requirements", "id": webstore_id},
            "owner_wording": f"{type_requirements['label']} store details are still being completed.",
            "blocking": not type_requirements["complete"],
            "requirements": type_requirements["items"],
        },
        {
            "key": "payment_ready",
            "state": payment["state"],
            "reason": payment["reason"],
            "severity": "advisory",
            "action": "Complete existing payment-readiness prerequisites when available.",
            "resource": {"type": "payment_readiness", "id": webstore_id},
            "owner_wording": "Payment setup is not ready yet.",
            "blocking": False,
            "stage5_deferred": not bool(payment["provider_authority"]),
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
        {
            "key": "buyer_commerce_connected",
            "state": "ready" if payment["provider_authority"] else "blocked",
            "reason": "Verified provider checkout and webhook reconciliation are connected." if payment["provider_authority"] else payment["reason"],
            "severity": "advisory",
            "action": "Complete Stripe Connect setup and verification before enabling buyer checkout.",
            "resource": {"type": "batch_scope", "id": "batch_3"},
            "owner_wording": "Buyer checkout is available after provider verification.",
            "blocking": False,
            "stage5_deferred": not bool(payment["provider_authority"]),
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
    ]
    checks = {gate["key"]: not gate["blocking"] for gate in gates}
    checks.update(
        {
            "not_closed_or_archived": store.get("status") not in LIVE_BLOCKING_STATUSES,
            "active_public_products_with_prices": active_public_count > 0,
            "public_branding": branding_complete,
            "questionnaire_complete": bool(questionnaire),
            "launch_packet": bool(packet),
            "owner_approved": approved,
            "terms_fee_acknowledged": bool(terms),
            "payment_ready": bool(payment["ready"]),
            "buyer_commerce_connected": bool(payment["provider_authority"]),
        }
    )
    ready = all(not gate["blocking"] for gate in gates)
    return {
        "webstore_id": webstore_id,
        "ready": ready,
        "checks": checks,
        "gates": gates,
        "current_packet": await _portal_launch_packet_with_history(user["tenant_id"], packet),
        "current_terms_version": terms_version,
        "terms_acceptance": _portal_terms_acceptance(terms),
        "open_change_request_count": len(open_changes),
        "payment_readiness": payment,
        "type_requirements": type_requirements,
        "payment_readiness_source": "provider_boundary",
        "payment_unavailable_reason": payment["reason"],
        "public_launch_blocked_until_batch_3": not bool(payment["provider_authority"]),
    }


async def _compat_launch_readiness(user: dict, webstore_id: str) -> dict:
    import sys

    facade = sys.modules.get(__package__ + ".webstores")
    override = getattr(facade, "launch_readiness", None) if facade is not None else None
    if override is not None and override is not launch_readiness:
        return await override(user, webstore_id)
    return await launch_readiness(user, webstore_id)


__all__ = [name for name in globals() if not name.startswith("__")]
