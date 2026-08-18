"""Staff and Webstore Manager operations for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch import _compat_launch_readiness, _invalidate_packet_approval_if_needed, _payment_readiness, _terms_acceptance, launch_readiness

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


async def set_webstore_status(user: dict, webstore_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if status in {"live", "launch_ready", "scheduled", "paused", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _validate_status_change(store.get("status", "draft"), status)
    if status == "scheduled":
        raise WebstoreError(
            "webstore_scheduling_deferred",
            "Webstore scheduling is handled after the public storefront checkpoint.",
            409,
        )
    if status in {"launch_ready", "scheduled", "live"}:
        readiness = await _compat_launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": status}
    if status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif status == "launch_ready":
        updates["checkout_enabled"] = False
    elif status == "scheduled":
        updates["checkout_enabled"] = False
        updates["scheduled_at"] = _now_iso()
    elif status == "paused":
        updates["checkout_enabled"] = False
    elif status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    from_state = _phase6_state_for_status(store.get("status", "draft"))
    to_state = _phase6_state_for_status(status)
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=status,
        from_state=from_state,
        to_state=to_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "status_route"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action=f"webstore.status.{status}",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore status changed from {store.get('status')} to {status}",
        metadata={"from": store.get("status"), "to": status, "reason": reason},
    )
    return updated or {}


async def relaunch_webstore(user: dict, webstore_id: str, reason: Optional[str] = None) -> dict:
    """Re-check current launch evidence before reopening a completed store."""
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    current_status = store.get("status", "draft")
    if current_status not in {"closed", "completed", "relaunch_ready"}:
        raise WebstoreError(
            "invalid_relaunch_status",
            "Only closed or completed Webstores can be relaunched",
            409,
        )
    close_at = store.get("deadline_at") or store.get("intended_close_at")
    if close_at:
        try:
            close_time = datetime.fromisoformat(str(close_at).replace("Z", "+00:00"))
            if close_time.tzinfo and close_time <= datetime.now(timezone.utc):
                raise WebstoreError(
                    "relaunch_deadline_passed",
                    "Update the Webstore closing date before relaunching it",
                    409,
                )
        except ValueError:
            pass
    readiness = await _compat_launch_readiness(user, webstore_id)
    if not readiness["ready"]:
        raise WebstoreError(
            "launch_gates_failed",
            "Current catalog, branding, approval, payment, and date gates must pass before relaunch",
            409,
        )
    if current_status != "relaunch_ready":
        _validate_status_change(current_status, "relaunch_ready")
    updated = await stores_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "relaunch_ready",
            "checkout_enabled": False,
            "relaunch_requested_at": _now_iso(),
        },
    )
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=current_status,
        to_status="relaunch_ready",
        from_state=_phase6_state_for_status(current_status),
        to_state="closed",
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "relaunch_route", "readiness_rechecked": True},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.relaunch.requested",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore relaunch readiness passed",
        metadata={"from_status": current_status, "to_status": "relaunch_ready"},
    )
    return {"webstore": updated or {}, "readiness": readiness, "lifecycle_state": "closed"}


async def transition_webstore_lifecycle(user: dict, webstore_id: str, lifecycle_state: str, reason: Optional[str] = None) -> dict:
    requested_state = (lifecycle_state or "").strip().lower().replace("-", "_")
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if requested_state in {"ready_to_launch", "live", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    current_state = _phase6_state_for_status(store.get("status", "draft"))
    target_status = PHASE6_TO_INTERNAL_STATUS[requested_state]
    _validate_status_change(store.get("status", "draft"), target_status)
    if requested_state in {"ready_to_launch", "live"}:
        readiness = await _compat_launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": target_status}
    if target_status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif target_status in {"launch_ready", "approved"}:
        updates["checkout_enabled"] = False
    elif target_status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif target_status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    event = await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=target_status,
        from_state=current_state,
        to_state=requested_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "phase6_lifecycle_route"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.lifecycle.transitioned",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore lifecycle changed from {current_state} to {requested_state}",
        metadata={"from_state": current_state, "to_state": requested_state, "from_status": store.get("status"), "to_status": target_status, "reason": reason},
    )
    return {"webstore": updated or {}, "lifecycle_state": requested_state, "event": event}


async def list_lifecycle_events(user: dict, webstore_id: str, *, limit: int = 30) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    safe_limit = max(1, min(limit, 100))
    items = [
        serialize_doc(doc)
        async for doc in db.webstore_lifecycle_events.find(
            {"tenant_id": user["tenant_id"], "webstore_id": store["id"]},
            {"_id": 0},
        ).sort([("created_at", -1)]).limit(safe_limit)
    ]
    return {"items": items}


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


async def create_product(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _reject_stage4a_publication_request(fields)
    idempotency_key = fields.get("idempotency_key")
    operation = "copy_template" if fields.get("source_template_id") else "create_blank"
    source_template_id = fields.get("source_template_id")
    payload_hash = _stage4a_product_create_fingerprint(fields, operation=operation, source_template_id=source_template_id)
    if idempotency_key:
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
    template = None
    if source_template_id:
        template = await _get_template_for_staff(user, source_template_id)
        if template.get("status") != "active" or not template.get("active", True):
            raise WebstoreError("template_not_available", "Product template is not active", 409)
    category_id, category_name, legacy_category = await _normalize_product_category(user, webstore_id, fields)
    customer_images = await _normalize_customer_images(user["tenant_id"], webstore_id, fields.get("customer_images"))
    if not customer_images and template:
        customer_images = deepcopy(template.get("default_customer_images") or {})
    merged = {
        "name": fields.get("name") or (template or {}).get("default_title") or (template or {}).get("template_name"),
        "short_description": fields.get("short_description") or (template or {}).get("default_short_description"),
        "full_description": fields.get("full_description") or fields.get("description") or (template or {}).get("default_description"),
        "description": fields.get("description") or (template or {}).get("default_short_description") or (template or {}).get("default_description"),
        "category": legacy_category or (template or {}).get("suggested_category_name") or (template or {}).get("product_category"),
        "product_type": fields.get("product_type") or (template or {}).get("product_type"),
        "production_method": fields.get("production_method") or (template or {}).get("production_method"),
        "supplier_source_info": fields.get("supplier_source_info") or (template or {}).get("supplier_source_info"),
        "production_notes": fields.get("production_notes") or (template or {}).get("default_production_notes"),
    }
    production_cost_cents = _clean_money(fields.get("production_cost_cents"), default=int((template or {}).get("suggested_production_cost_cents") or 0))
    selling_price_cents = _clean_money(fields.get("selling_price_cents"), default=int((template or {}).get("suggested_selling_price_cents") or 0))
    store_owner_share_cents = _clean_money(fields.get("store_owner_share_cents"), default=int((template or {}).get("suggested_store_owner_share_cents") or 0))
    fundraiser_share_cents = _clean_money(fields.get("fundraiser_share_cents"), default=0)
    if store_owner_share_cents + fundraiser_share_cents > selling_price_cents:
        raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the product selling price", 400)
    status = _clean_status(fields.get("status"), PRODUCT_STATUSES, "draft", "product_status")
    if "display_order" in fields:
        display_order = _clean_quantity(fields.get("display_order"), default=0) or 0
    else:
        last = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
            {"_id": 0, "display_order": 1},
            sort=[("display_order", -1)],
        )
        display_order = int((last or {}).get("display_order") or 0) + 100
    product = WebstoreProduct(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        source_template_id=source_template_id,
        source_template_revision=(template or {}).get("revision"),
        name=_clean_text(merged["name"], "name"),
        short_description=_clean_optional_text(merged.get("short_description"), limit=500),
        full_description=_clean_optional_text(merged.get("full_description")),
        description=_clean_optional_text(merged.get("description")),
        category_id=category_id,
        category_name=category_name or legacy_category or merged.get("category"),
        category=category_name or legacy_category or merged.get("category"),
        product_type=merged.get("product_type"),
        production_method=_clean_optional_text(merged.get("production_method"), limit=120),
        supplier_source_info=_clean_optional_text(merged.get("supplier_source_info")),
        fulfillment_notes=_clean_optional_text(fields.get("fulfillment_notes")),
        sku=_clean_optional_text(fields.get("sku"), limit=120),
        production_cost_cents=production_cost_cents,
        selling_price_cents=selling_price_cents,
        store_owner_share_cents=store_owner_share_cents,
        fundraiser_share_cents=fundraiser_share_cents,
        platform_fee_basis_points=_clean_basis_points(fields.get("platform_fee_basis_points"), default=int((template or {}).get("platform_fee_basis_points") or 0)),
        fulfillment_methods=_normalize_fulfillment_methods(fields.get("fulfillment_methods")),
        default_fulfillment_method=(str(fields.get("default_fulfillment_method")).strip().lower() if fields.get("default_fulfillment_method") else None),
        pickup_instructions=_clean_optional_text(fields.get("pickup_instructions"), limit=2000),
        shipping_cost_cents=_clean_money(fields.get("shipping_cost_cents"), default=0),
        variants=[],
        personalization_enabled=bool(fields.get("personalization_enabled", False)),
        personalization_fields=[],
        bundle_items=[],
        inventory_policy=str(fields.get("inventory_policy") or "not_tracked")[:80],
        inventory_quantity=_clean_quantity(fields.get("inventory_quantity"), default=None),
        launch_packet_eligible=bool(fields.get("launch_packet_eligible", False)),
        launch_packet_include=bool(fields.get("launch_packet_include", False)),
        display_order=display_order,
        image_file_ids=[],
        customer_images=customer_images,
        production_notes=_clean_optional_text(merged.get("production_notes")),
        public=False,
        featured=False,
        status=status,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    variant_source = fields.get("variants") if "variants" in fields else (template or {}).get("default_variants")
    product["variants"] = _normalize_variants(variant_source, base_selling_price_cents=selling_price_cents)
    if product.get("default_fulfillment_method") and product["default_fulfillment_method"] not in product.get("fulfillment_methods"):
        raise WebstoreError("invalid_default_fulfillment_method", "The default fulfillment method must be enabled for this product", 400)
    product["personalization_fields"] = _normalize_personalization_fields(
        fields.get("personalization_fields"),
        enabled=bool(product.get("personalization_enabled")),
    )
    product["bundle_items"] = await _normalize_bundle_items(user, webstore_id, product["id"], fields.get("bundle_items"))
    await _ensure_unique_product_skus(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product["id"],
        sku=product.get("sku"),
        variants=product.get("variants") or [],
    )
    if product.get("launch_packet_include") and not bool(product.get("launch_packet_eligible")):
        product["launch_packet_eligible"] = True
    if product.get("status") in {"ready", "active"}:
        missing = [item["label"] for item in _product_setup_requirements(product) if not item["complete"]]
        if missing:
            raise WebstoreError("product_not_ready", f"Complete product setup before marking it ready: {', '.join(missing)}", 409)
        product["launch_packet_eligible"] = True
    if "artwork_associations" in fields:
        product["artwork_associations"] = await _normalize_artwork_associations(user, webstore_id, product["id"], fields.get("artwork_associations"))
    elif template:
        product["artwork_associations"] = deepcopy(template.get("default_artwork_associations") or [])
    if "mockup_associations" in fields:
        product["mockup_associations"] = await _normalize_mockup_associations(user, webstore_id, product["id"], fields.get("mockup_associations"))
    elif template:
        product["mockup_associations"] = deepcopy(template.get("default_mockup_associations") or [])
    if idempotency_key:
        product["stage4a_idempotency_key"] = idempotency_key
        product["stage4a_idempotency_actor_id"] = user.get("id")
        product["stage4a_idempotency_operation"] = operation
        product["stage4a_idempotency_source_template_id"] = source_template_id
        product["stage4a_idempotency_payload_hash"] = payload_hash
    try:
        await db.webstore_products.insert_one(prepare_for_mongo(product))
    except DuplicateKeyError:
        if not idempotency_key:
            raise
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
        raise WebstoreError("stage4a_idempotency_conflict", "This product action could not be safely retried. Start a new action and try again.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_created_from_template" if source_template_id else "webstore.product_created_blank",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product created from a template" if source_template_id else "Blank Webstore product draft created",
        metadata={"source_template_id": product.get("source_template_id")},
    )
    return _staff_product(product, public_slug=store.get("public_slug"))


async def list_products(
    user: dict,
    *,
    webstore_id: str,
    public_only: bool = False,
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    filters: dict[str, Any] = {"webstore_id": webstore_id}
    if public_only:
        filters.update({"public": True, "status": "active"})
    if status:
        filters["status"] = status
    if category_id:
        filters["category_id"] = category_id
    result = await products_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("display_order", 1), ("featured", -1), ("name", 1)])
    items = result["items"]
    if q:
        needle = _normalize_name(q)
        items = [item for item in items if needle in _normalize_name(item.get("name", ""))]
    return {**result, "items": [_staff_product(item, public_slug=store.get("public_slug")) for item in items], "total": len(items)}


async def duplicate_product(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before duplicating.", 409)
    source = deepcopy(product)
    for key in (
        "_id",
        "id",
        "created_at",
        "updated_at",
        "revision",
        "approval_status",
        "approval_revision",
        "approval_snapshot_hash",
        "approval_decision_at",
        "approval_decision_by_portal_identity_id",
        "approval_invalidated_at",
        "approval_invalidated_reason",
        "stage4a_idempotency_key",
        "stage4a_idempotency_actor_id",
        "stage4a_idempotency_operation",
        "stage4a_idempotency_source_template_id",
        "stage4a_idempotency_payload_hash",
        "name",
        "status",
        "public",
        "featured",
        "launch_packet_include",
        "display_order",
        "created_by_user_id",
        "updated_by_user_id",
        "sku",
        "variants",
    ):
        source.pop(key, None)
    last = await db.webstore_products.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0, "display_order": 1},
        sort=[("display_order", -1)],
    )
    duplicate = WebstoreProduct(
        **source,
        id=secrets.token_urlsafe(18),
        name=_clean_text(fields.get("name") or f"{product.get('name', 'Product')} Copy", "name"),
        sku=None,
        variants=[{**variant, "sku": None} for variant in source.get("variants") or []],
        status="draft",
        public=False,
        featured=False,
        launch_packet_include=False,
        approval_status="not_submitted",
        display_order=int((last or {}).get("display_order") or 0) + 100,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_products.insert_one(prepare_for_mongo(duplicate))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_duplicated",
        entity_type="webstore_product",
        entity_id=duplicate["id"],
        summary="Webstore product duplicated into a private draft",
        metadata={"source_product_id": product_id},
    )
    return _staff_product(duplicate, public_slug=store.get("public_slug"))


async def reorder_products(user: dict, webstore_id: str, product_ids: list[str]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    ids = [str(item) for item in product_ids if str(item or "").strip()]
    existing = [
        doc
        async for doc in db.webstore_products.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
    ]
    expected_ids = {doc["id"] for doc in existing}
    if set(ids) != expected_ids or len(ids) != len(expected_ids):
        raise WebstoreError("reorder_requires_all_active_products", "Reorder must include each non-archived product exactly once", 400)
    now = _now_iso()
    for index, current_id in enumerate(ids):
        await db.webstore_products.update_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": current_id},
            {"$set": {"display_order": (index + 1) * 100, "updated_at": now, "updated_by_user_id": user.get("id")}},
        )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.products_reordered",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore product display order updated",
        metadata={"product_ids": ids},
    )
    return await list_products(user, webstore_id=webstore_id)


async def submit_product_for_approval(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    if product.get("status") == "archived":
        raise WebstoreError("product_archived", "Archived products cannot be sent for approval", 409)
    snapshot = await _product_approval_snapshot(user["tenant_id"], webstore_id, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    now = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": product_id, "revision": expected_revision},
        {
            "$set": {
                "approval_status": "pending_owner_approval",
                "approval_revision": expected_revision,
                "approval_snapshot_hash": snapshot_hash,
                "approval_invalidated_at": None,
                "approval_invalidated_reason": None,
                "updated_at": now,
                "updated_by_user_id": user.get("id"),
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_submitted_for_approval",
        entity_type="webstore_product",
        entity_id=product_id,
        summary="Webstore product submitted for owner approval",
        metadata={"product_revision": expected_revision, "snapshot_hash": snapshot_hash, "comment": fields.get("comment")},
    )
    data = _staff_product(updated, public_slug=store.get("public_slug"))
    data["approval_history"] = await _approval_history(user["tenant_id"], "webstore_product", product_id)
    data["approval_snapshot"] = snapshot
    return data


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


async def submit_questionnaire(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    owner = await _get_owner(identity["tenant_id"], store["owner_id"])
    existing = await submissions_repo.find_one({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id})
    payload = {
        "answers": fields.get("answers") or {},
        "known_products": fields.get("known_products") or [],
        "open_to_suggestions": bool(fields.get("open_to_suggestions", True)),
        "missing_info_flags": fields.get("missing_info_flags") or [],
        "status": "submitted",
        "submitted_at": _now_iso(),
    }
    if existing:
        submission = await submissions_repo.update(tenant_id=identity["tenant_id"], entity_id=existing["id"], updates=payload)
    else:
        doc = WebstoreQuestionnaireSubmission(
            tenant_id=identity["tenant_id"],
            webstore_id=webstore_id,
            owner_id=owner["id"],
            **payload,
        ).model_dump()
        await db.webstore_questionnaire_submissions.insert_one(prepare_for_mongo(doc))
        submission = serialize_doc(doc)
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "questionnaire_submitted"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.questionnaire_submitted",
        entity_type="webstore_questionnaire_submission",
        entity_id=submission["id"],
        summary="Webstore owner submitted questionnaire",
    )
    return submission or {}


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


async def create_ai_usage_event(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    event = WebstoreAIUsageEvent(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        action=_clean_text(fields.get("action"), "action"),
        status=fields.get("status", "drafted"),
        prompt_source=_clean_optional_text(fields.get("prompt_source")),
        output_snapshot=fields.get("output_snapshot") or {},
        reviewed_by_user_id=fields.get("reviewed_by_user_id"),
        reviewed_at=fields.get("reviewed_at"),
    ).model_dump()
    await db.webstore_ai_usage_events.insert_one(prepare_for_mongo(event))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.ai_contract_recorded",
        entity_type="webstore_ai_usage_event",
        entity_id=event["id"],
        summary="Webstore AI suggestion contract recorded without provider call",
    )
    return serialize_doc(event)  # type: ignore[return-value]


def _webstore_product_ai_action(action: Any) -> dict[str, Any]:
    key = str(action or "").strip()
    config = WEBSTORE_PRODUCT_AI_ACTIONS.get(key)
    if not config:
        raise WebstoreError("unsupported_webstore_ai_action", "Unsupported Webstore product AI action", 400)
    return {"action": key, **config}


async def _webstore_product_ai_preview(user: dict, webstore_id: str, product_id: str, action: Any) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    _require_staff_perm(user, Perm.AI_TOOL_USE)
    config = _webstore_product_ai_action(action)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY):
        raise WebstoreError("webstores_not_entitled", "Webstores entitlement is required before running Webstore AI actions.", 402)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=ai_studio.AI_STUDIO_ENTITLEMENT_FEATURE_KEY):
        raise WebstoreError("ai_studio_not_entitled", "AI Studio entitlement is required before running Webstore AI actions.", 402)

    capability = await db.ai_capabilities.find_one({"capability_key": config["capability_key"], "status": "active"}, {"_id": 0})
    if not capability:
        raise WebstoreError(
            "webstore_ai_capability_not_bootstrapped",
            "Platform AI admin must bootstrap the EC17 local mock catalog before this Webstore AI action can run.",
            409,
        )
    account = await ai_gateway.get_credit_account(user["tenant_id"])
    credit_charge = int(capability.get("default_credit_charge") or 0)
    available = int(account.get("available_credits") or 0)
    return {
        "action": config["action"],
        "label": config["label"],
        "tool_key": config["tool_key"],
        "mode_key": config["mode_key"],
        "capability_key": config["capability_key"],
        "result_record_type": config["result_record_type"],
        "output_kind": config["output_kind"],
        "credit_charge_credits": credit_charge,
        "available_credits": available,
        "credit_display": f"{credit_charge} AI credit{'s' if credit_charge != 1 else ''}",
        "confirmation_required": True,
        "can_run": available >= credit_charge,
        "insufficient_credits": available < credit_charge,
        "usage_note": config["usage_note"],
        "review_required": True,
        "auto_apply": False,
        "manual_setup_available": True,
        "h7_local_mock": True,
        "external_provider_calls": 0,
        "webstore": {"id": store["id"], "name": store.get("name")},
        "product": {"id": product["id"], "name": product.get("name"), "revision": product.get("revision")},
    }


async def preview_product_ai_action(user: dict, webstore_id: str, product_id: str, action: Any) -> dict[str, Any]:
    return await _webstore_product_ai_preview(user, webstore_id, product_id, action)


def _webstore_product_ai_prompt(product: dict[str, Any], fields: dict[str, Any], config: dict[str, Any]) -> str:
    supplied = _clean_optional_text(fields.get("prompt"), limit=1000)
    base = supplied or product.get("full_description") or product.get("short_description") or product.get("name") or "Webstore product"
    return (
        f"{base}\n\n"
        f"Product: {product.get('name') or 'Untitled product'}\n"
        f"Product type: {product.get('product_type') or 'not set'}\n"
        f"Category: {product.get('category_name') or product.get('category') or 'not set'}\n"
        f"Boundary: {config['usage_note']}"
    )


async def run_product_ai_action(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    preview = await _webstore_product_ai_preview(user, webstore_id, product_id, fields.get("action"))
    confirmed = fields.get("confirmed_credit_charge_credits")
    if confirmed is None:
        raise WebstoreError("ai_credit_confirmation_required", "Confirm the displayed AI credit charge before running this Webstore AI action.", 400)
    if int(confirmed) != int(preview["credit_charge_credits"]):
        raise WebstoreError("ai_credit_confirmation_stale", "The AI credit charge changed. Refresh the preview and confirm again.", 409)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    config = _webstore_product_ai_action(fields.get("action"))
    idempotency_key = _clean_optional_text(fields.get("idempotency_key"), limit=160)
    result = await ai_studio.run_tool(
        user,
        {
            "tool_key": config["tool_key"],
            "mode_key": config["mode_key"],
            "inputs": {
                "prompt": _webstore_product_ai_prompt(product, fields, config),
                "context_notes": _clean_optional_text(fields.get("context_notes"), limit=1000),
            },
            "context": {
                "context_type": "webstore",
                "context_id": webstore_id,
                "webstore_product_id": product_id,
                "webstore_product_revision": product.get("revision"),
            },
            "source_links": [{"entity_type": "webstore_product", "entity_id": product_id}],
            "idempotency_key": idempotency_key,
            "title": f"{preview['label']} - {product.get('name') or 'Webstore product'}",
        },
    )
    event = WebstoreAIUsageEvent(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        action=config["action"],
        status="drafted",
        prompt_source=_clean_optional_text(fields.get("prompt"), limit=1000),
        output_snapshot={
            "record_type": result.get("record_type"),
            "record_id": result.get("id"),
            "title": result.get("title"),
            "content_text": result.get("content_text"),
            "content_json": result.get("content_json") or {},
            "warnings": result.get("warnings") or [],
            "action_request_id": result.get("action_request_id"),
            "credit_charge_credits": preview["credit_charge_credits"],
            "credit_display": preview["credit_display"],
            "auto_apply": False,
            "review_required": True,
            "external_provider_calls": 0,
            "h7_local_mock": True,
            "webstore_product_id": product_id,
            "webstore_product_revision": product.get("revision"),
        },
    ).model_dump()
    await db.webstore_ai_usage_events.insert_one(prepare_for_mongo(event))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_ai_action_recorded",
        entity_type="webstore_ai_usage_event",
        entity_id=event["id"],
        summary="Webstore product AI output saved for staff review without applying changes",
        metadata={
            "product_id": product_id,
            "ai_result_record_type": result.get("record_type"),
            "ai_result_id": result.get("id"),
            "action_request_id": result.get("action_request_id"),
            "credit_charge_credits": preview["credit_charge_credits"],
            "auto_apply": False,
        },
    )
    return {
        "preview": preview,
        "ai_result": result,
        "webstore_ai_event": serialize_doc(event),
        "auto_apply": False,
        "review_required": True,
        "manual_setup_available": True,
    }

__all__ = [name for name in globals() if not name.startswith("__")]
