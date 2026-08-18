"""Staff owner, Webstore management, list/detail, and update operations."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch import _invalidate_packet_approval_if_needed, _payment_readiness, _terms_acceptance
from .webstore_staff_products import list_products


async def create_owner(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    email = _clean_text(fields.get("email"), "email", limit=254).lower()
    owner = WebstoreOwner(
        tenant_id=user["tenant_id"],
        name=_clean_text(fields.get("name"), "name"),
        email=email,
        phone=_clean_optional_text(fields.get("phone"), limit=40),
        organization=_clean_optional_text(fields.get("organization")),
        customer_id=fields.get("customer_id"),
        status=fields.get("status", "active"),
    ).model_dump()
    try:
        await db.webstore_owners.insert_one(prepare_for_mongo(owner))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_owner", "A Webstore owner already exists for that email", 409)
    if fields.get("create_portal_identity", True):
        try:
            identity = await create_portal_identity(
                tenant_id=user["tenant_id"],
                portal_type="webstore_owner",
                webstore_owner_id=owner["id"],
                email=email,
                full_name=owner["name"],
                phone=owner.get("phone"),
                role_label="Webstore Owner",
                permissions_preset="webstore_owner_admin",
                magic_link_only=True,
            )
            owner["portal_identity_id"] = identity["id"]
            await db.webstore_owners.update_one(
                {"tenant_id": user["tenant_id"], "id": owner["id"]},
                {"$set": {"portal_identity_id": identity["id"], "updated_at": _now_iso()}},
            )
        except ValueError as e:
            raise WebstoreError(str(e), "Unable to create Webstore owner portal identity", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=owner["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.owner_created",
        entity_type="webstore_owner",
        entity_id=owner["id"],
        summary="Webstore owner created",
    )
    return serialize_doc(owner)  # type: ignore[return-value]


async def list_owners(user: dict) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    return await owners_repo.list(tenant_id=user["tenant_id"], sort=[("name", 1)])


async def create_webstore(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    if fields.get("idempotency_key"):
        existing = await db.webstores.find_one(
            {"tenant_id": user["tenant_id"], "creation_idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
    owner = await _get_owner(user["tenant_id"], fields["owner_id"])
    slug = _slug(fields.get("slug") or fields.get("name") or owner["name"])
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0, "name": 1, "slug": 1})
    public_slug = await _generate_public_slug(
        tenant_id=user["tenant_id"],
        shop_context=(tenant or {}).get("slug") or (tenant or {}).get("name") or user["tenant_id"],
        store_name=fields.get("name") or owner["name"],
        internal_slug=slug,
    )
    store = Webstore(
        tenant_id=user["tenant_id"],
        owner_id=owner["id"],
        name=_clean_text(fields.get("name"), "name"),
        slug=slug,
        public_slug=public_slug,
        store_type=_normalize_store_type(fields.get("store_type", "general")),
        description=_clean_optional_text(fields.get("description")),
        branding=fields.get("branding") or {},
        direct_owner_payout_required=bool(fields.get("direct_owner_payout_required", False)),
        stripe_onboarding_required=bool(fields.get("stripe_onboarding_required", False)),
        stripe_payment_ready=False,
        deadline_at=fields.get("deadline_at"),
        target_launch_at=fields.get("target_launch_at"),
        event_start_at=fields.get("event_start_at"),
        event_location=fields.get("event_location"),
        setup_profile=fields.get("setup_profile") or {},
        setup_requirements=fields.get("setup_requirements") or {},
        store_settings=default_store_settings(_normalize_store_type(fields.get("store_type", "general")), fields.get("store_settings") or {}),
        creation_idempotency_key=fields.get("idempotency_key"),
        public_url=f"/p/webstores/{public_slug}",
    ).model_dump()
    try:
        await db.webstores.insert_one(prepare_for_mongo(store))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_slug", "Webstore slug already exists for this tenant", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=store["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.created",
        entity_type="webstore",
        entity_id=store["id"],
        summary="Webstore created",
    )
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=store["id"],
        from_status=None,
        to_status=store["status"],
        from_state=None,
        to_state=_phase6_state_for_status(store["status"]),
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason="Webstore created",
        metadata={"store_type": store["store_type"]},
    )
    from .webstore_setup import WebstoreSetupError, initialize_store_setup

    try:
        await initialize_store_setup(user, store, owner, fields)
    except WebstoreSetupError as exc:
        await db.webstores.delete_one({"tenant_id": user["tenant_id"], "id": store["id"]})
        await db.webstore_access_assignments.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_invitations.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_questionnaire_submissions.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_setup_files.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_answer_applications.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        raise WebstoreError(exc.code, exc.detail, exc.status_code) from exc
    updated = await db.webstores.find_one({"tenant_id": user["tenant_id"], "id": store["id"]}, {"_id": 0})
    if updated:
        store = serialize_doc(updated)
    return serialize_doc(store)  # type: ignore[return-value]


async def list_webstores(user: dict, *, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    # Archived history remains queryable explicitly, but does not clutter the
    # default active Webstores list.
    filters = {"status": status} if status else {"status": {"$ne": "archived"}}
    result = await stores_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])
    items = []
    for item in result["items"]:
        safe_item = dict(item)
        type_requirements = evaluate_type_requirements(safe_item)
        payment = await _payment_readiness(safe_item)
        safe_item["checkout_enabled"] = bool(item.get("checkout_enabled")) and payment["provider_authority"]
        safe_item["checkout_unavailable_reason"] = (
            None if safe_item["checkout_enabled"] else payment["reason"]
        )
        safe_item["phase6_lifecycle_state"] = _phase6_state_for_status(safe_item.get("status", "draft"))
        safe_item["type_requirements"] = {
            "label": type_requirements["label"],
            "complete": type_requirements["complete"],
            "missing_count": len(type_requirements["missing"]),
        }
        safe_item["manager_action_required"] = (
            f"Complete {type_requirements['label']} requirements: {type_requirements['missing'][0]['label']}"
            if type_requirements["missing"]
            else None
        )
        items.append(safe_item)
    return {**result, "items": items}


async def list_activity(user: dict, webstore_id: str, *, limit: int = 30) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    safe_limit = max(1, min(limit, 100))
    items = [
        serialize_doc(doc)
        async for doc in db.webstore_activity_events.find(
            {"tenant_id": user["tenant_id"], "webstore_id": store["id"]},
            {"_id": 0},
        ).sort([("created_at", -1)]).limit(safe_limit)
    ]
    return {"items": items}


async def get_webstore(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    products = await list_products(user, webstore_id=webstore_id)
    detail_products = []
    for product in products["items"]:
        product["approval_history"] = await _approval_history(user["tenant_id"], "webstore_product", product["id"])
        detail_products.append(product)
    packets = await packets_repo.list(tenant_id=user["tenant_id"], filters={"webstore_id": webstore_id}, sort=[("created_at", -1)], limit=10)
    packet_items = []
    for packet in packets["items"]:
        safe_packet = dict(packet)
        safe_packet["approval_history"] = await _approval_history(user["tenant_id"], "webstore_launch_packet", packet["id"])
        packet_items.append(safe_packet)
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(user["tenant_id"], webstore_id, terms_version)
    changes = [
        _portal_change_request(doc)
        async for doc in db.webstore_change_requests.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {
        "webstore": store,
        "products": detail_products,
        "launch_packets": packet_items,
        "change_requests": changes,
        "phase6_lifecycle_state": _phase6_state_for_status(store.get("status", "draft")),
        "type_requirements": evaluate_type_requirements(store),
        "terms_acceptance": _portal_terms_acceptance(terms),
        "current_terms_version": terms_version,
    }


async def update_webstore(user: dict, webstore_id: str, updates: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store_before = await _get_store(user["tenant_id"], webstore_id)
    allowed = {
        k: v
        for k, v in updates.items()
        if k
        in {
            "name",
            "description",
            "branding",
            "store_type",
            "terms_fee_acknowledged",
            "required_terms_version",
            "direct_owner_payout_required",
            "stripe_onboarding_required",
            "deadline_at",
            "target_launch_at",
            "event_start_at",
            "event_location",
            "intended_launch_at",
            "intended_close_at",
            "launch_timezone",
            "payment_readiness_status",
            "store_settings",
        }
    }
    if "name" in allowed:
        allowed["name"] = _clean_text(allowed["name"], "name")
    if "description" in allowed:
        allowed["description"] = _clean_optional_text(allowed["description"])
    if "branding" in allowed:
        await _validate_webstore_asset_refs(user["tenant_id"], webstore_id, allowed.get("branding") or {}, field="branding")
    for date_key in ("deadline_at", "target_launch_at", "event_start_at", "intended_launch_at", "intended_close_at"):
        if date_key in allowed:
            allowed[date_key] = _require_timezone_iso(allowed.get(date_key), date_key)
    if allowed.get("intended_launch_at") and allowed.get("intended_close_at"):
        if allowed["intended_close_at"] <= allowed["intended_launch_at"]:
            raise WebstoreError("invalid_schedule_window", "Intended close must be after intended launch", 400)
    elif ("intended_launch_at" in allowed or "intended_close_at" in allowed) and (
        allowed.get("intended_launch_at", store_before.get("intended_launch_at")) and allowed.get("intended_close_at", store_before.get("intended_close_at"))
    ):
        start = allowed.get("intended_launch_at", store_before.get("intended_launch_at"))
        end = allowed.get("intended_close_at", store_before.get("intended_close_at"))
        if end <= start:
            raise WebstoreError("invalid_schedule_window", "Intended close must be after intended launch", 400)
    if "launch_timezone" in allowed:
        allowed["launch_timezone"] = _clean_optional_text(allowed.get("launch_timezone"), limit=80)
    if "payment_readiness_status" in allowed:
        allowed["payment_readiness_status"] = _clean_status(allowed.get("payment_readiness_status"), PAYMENT_READINESS_STATES, "not_configured", "payment_readiness_status")
    if "store_settings" in allowed:
        allowed["store_settings"] = default_store_settings(
            allowed.get("store_type") or store_before.get("store_type"),
            allowed["store_settings"] if isinstance(allowed.get("store_settings"), dict) else {},
        )
    if "required_terms_version" in allowed:
        allowed["required_terms_version"] = _clean_text(allowed["required_terms_version"], "required_terms_version", limit=80)
        if allowed["required_terms_version"] != store_before.get("required_terms_version", CURRENT_WEBSTORE_TERMS_VERSION):
            allowed["terms_fee_acknowledged"] = False
            allowed["terms_acceptance_id"] = None
            allowed["terms_accepted_version"] = None
            allowed["terms_accepted_at"] = None
            allowed["terms_accepted_by_portal_identity_id"] = None
    if "store_type" in allowed:
        allowed["store_type"] = _normalize_store_type(allowed["store_type"])
        if allowed["store_type"] != store_before.get("store_type"):
            if "store_settings" not in allowed:
                allowed["store_settings"] = default_store_settings(allowed["store_type"], store_before.get("store_settings") or {})
            owner_activity_count = sum(
                [
                    await db.webstore_access_assignments.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_invitations.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_questionnaire_submissions.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_setup_files.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                ]
            )
            if owner_activity_count:
                _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
                if not updates.get("confirm_type_change") or not updates.get("impact_review_acknowledged") or not updates.get("type_change_reason"):
                    raise WebstoreError(
                        "webstore_type_change_confirmation_required",
                        "Changing Webstore type after owner/setup activity requires confirmation, impact review, and a reason.",
                        409,
                    )
                inactive_keys: set[str] = set()
                async for submission in db.webstore_questionnaire_submissions.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0, "answers": 1, "submitted_snapshot": 1}):
                    inactive_keys.update((submission.get("answers") or {}).keys())
                    inactive_keys.update(((submission.get("submitted_snapshot") or {}).get("answers") or {}).keys())
                if inactive_keys:
                    await db.webstore_questionnaire_submissions.update_many(
                        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
                        {"$addToSet": {"inactive_answer_paths": {"$each": sorted(inactive_keys)}}, "$set": {"updated_at": _now_iso()}},
                    )
                history_entry = {
                    "from": store_before.get("store_type"),
                    "to": allowed["store_type"],
                    "reason": updates.get("type_change_reason"),
                    "actor_user_id": user.get("id"),
                    "actor_email": user.get("email"),
                    "changed_at": _now_iso(),
                }
                await db.webstores.update_one(
                    {"tenant_id": user["tenant_id"], "id": webstore_id},
                    {"$push": {"setup_profile.type_change_history": history_entry}},
                )
    if "name" in allowed and allowed["name"] != store_before.get("name"):
        public_slug = await _generate_public_slug(
            tenant_id=user["tenant_id"],
            shop_context=user["tenant_id"],
            store_name=allowed["name"],
            internal_slug=store_before.get("slug") or store_before["id"],
        )
        allowed["public_slug"] = public_slug
        allowed["public_url"] = f"/p/webstores/{public_slug}"
    if not allowed:
        raise WebstoreError("no_updates", "No supported updates provided", 400)
    store = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=allowed)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.updated",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore updated",
        metadata={"fields": sorted(allowed)},
    )
    if "store_type" in allowed and allowed["store_type"] != store_before.get("store_type"):
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user["id"],
            actor_email=user.get("email"),
            action="webstore.type_changed",
            entity_type="webstore",
            entity_id=webstore_id,
            summary=f"Webstore type changed from {store_before.get('store_type')} to {allowed['store_type']}",
            metadata={"from": store_before.get("store_type"), "to": allowed["store_type"], "reason": updates.get("type_change_reason")},
        )
    changed = {key for key, value in allowed.items() if value != store_before.get(key)}
    material_changed = changed & MATERIAL_STORE_FIELDS
    if material_changed:
        await _invalidate_packet_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material store fields changed: {', '.join(sorted(material_changed))}",
            changed_fields=material_changed,
        )
    if "required_terms_version" in changed:
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user["id"],
            actor_email=user.get("email"),
            action="webstore.terms_version_superseded",
            entity_type="webstore",
            entity_id=webstore_id,
            summary="Webstore required Terms version changed",
            metadata={"from": store_before.get("required_terms_version"), "to": allowed.get("required_terms_version")},
        )
    return store or {}

__all__ = ['create_owner', 'list_owners', 'create_webstore', 'list_webstores', 'list_activity', 'get_webstore', 'update_webstore']
