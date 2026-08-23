"""Launch packet assembly, invalidation, generation, and delivery."""
from __future__ import annotations

from .webstore_shared import *

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
