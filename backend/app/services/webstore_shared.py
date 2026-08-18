"""Shared validation, serialization, repository, and audit helpers for Webstores."""
from __future__ import annotations

from .webstore_context import *

def _now_iso() -> str:
    return utc_now().isoformat()


def _json_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _require_timezone_iso(value: Any, field: str) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WebstoreError("invalid_schedule_datetime", f"{field} must be an ISO datetime with timezone", 400) from exc
    if parsed.tzinfo is None:
        raise WebstoreError("invalid_schedule_timezone", f"{field} must include a timezone offset", 400)
    return parsed.astimezone(timezone.utc).isoformat()


def _owner_safe_terms_snapshot(store: dict, owner: dict, packet: Optional[dict] = None) -> dict[str, Any]:
    return {
        "terms_version": store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION,
        "store_name": store.get("name"),
        "store_type": store.get("store_type"),
        "store_owner_name": owner.get("name"),
        "store_owner_email": owner.get("email"),
        "platform_fee_percent": "Configured by the shop and snapshotted for backend-authoritative buyer checkout.",
        "stripe_processing_note": "Payment provider readiness is tracked separately; canonical Orders are created only after verified payment evidence.",
        "owner_share_formula": "Owner-visible product share is shown in cents in the launch packet when configured.",
        "payout_method": "Not configured in this batch unless an existing provider record says otherwise.",
        "store_deadline": store.get("deadline_at") or store.get("intended_close_at"),
        "pickup_instructions": (store.get("setup_profile") or {}).get("pickup_instructions"),
        "refund_policy_summary": (store.get("setup_profile") or {}).get("refund_policy_summary") or "Policy wording is managed by the sign shop before launch.",
        "approval_packet_version": (packet or {}).get("version"),
        "administrative_setup_required": True,
    }


def _clean_text(value: Any, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise WebstoreError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise WebstoreError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _clean_optional_text(value: Any, *, limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _clean_public_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise WebstoreError("buyer_email_invalid", "Enter a valid email address", 400)
    return email


def _collect_nested_file_ids(value: Any) -> set[str]:
    file_ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "file_id" and child not in (None, ""):
                file_ids.add(str(child))
            else:
                file_ids.update(_collect_nested_file_ids(child))
    elif isinstance(value, list):
        for child in value:
            file_ids.update(_collect_nested_file_ids(child))
    return file_ids


async def _validate_webstore_asset_refs(tenant_id: str, webstore_id: str, value: Any, *, field: str) -> None:
    file_ids = _collect_nested_file_ids(value)
    if not file_ids:
        return
    found = {
        doc["id"]
        async for doc in db.webstore_setup_files.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": {"$in": sorted(file_ids)}, "status": "active"},
            {"_id": 0, "id": 1},
        )
    }
    missing = sorted(file_ids - found)
    if missing:
        raise WebstoreError(
            "webstore_asset_scope_mismatch",
            f"{field} references files that do not belong to this Webstore.",
            400,
        )


def _clean_money(value: Any, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("money_must_be_integer_cents", "Money values must be integer cents", 400)
    amount = int(value)
    if amount < 0:
        raise WebstoreError("negative_money_not_allowed", "Money values cannot be negative", 400)
    return amount


def _clean_basis_points(value: Any, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("basis_points_must_be_integer", "Fee percentages must be stored as integer basis points", 400)
    amount = int(value)
    if amount < 0 or amount > 10000:
        raise WebstoreError("basis_points_out_of_range", "Fee basis points must be between 0 and 10000", 400)
    return amount


def _normalize_fulfillment_methods(value: Any, *, default: Optional[list[str]] = None) -> list[str]:
    if value is None:
        return list(default or [])
    if not isinstance(value, list):
        raise WebstoreError("fulfillment_methods_must_be_list", "Fulfillment methods must be a list", 400)
    methods = []
    for raw in value:
        method = str(raw or "").strip().lower()
        if method not in FULFILLMENT_METHODS:
            raise WebstoreError("invalid_fulfillment_method", "Fulfillment methods must be pickup or shipping", 400)
        if method not in methods:
            methods.append(method)
    return methods


def _effective_fulfillment_methods(product: dict[str, Any]) -> list[str]:
    if "fulfillment_methods" in product:
        return _normalize_fulfillment_methods(product.get("fulfillment_methods"))
    # Older accepted product records predate product-level fulfillment. Keep
    # them readable with a conservative pickup default until staff configures
    # an explicit Stage 6 fulfillment list.
    legacy_method = product.get("fulfillment_method")
    return _normalize_fulfillment_methods([legacy_method] if legacy_method else ["pickup"])


def _public_cart_config(store: dict[str, Any]) -> dict[str, Any]:
    setup = store.get("setup_profile") or {}
    settings = store.get("store_settings") or {}
    cart = settings.get("cart") or {}
    donation = settings.get("donations") or settings.get("donation") or {}
    fundraiser_goal = setup.get("fundraiser_goal_amount") or cart.get("fundraiser_goal_cents") or 0
    donation_enabled = donation.get("enabled", cart.get("donation_enabled", setup.get("allow_checkout_donations")))
    if isinstance(donation_enabled, str):
        donation_enabled = donation_enabled.strip().lower() in {"yes", "true", "1", "on"}
    return {
        "fundraiser_goal_cents": int(fundraiser_goal or 0) if store.get("store_type") == "fundraiser" else 0,
        "donation_enabled": bool(donation_enabled) if store.get("store_type") == "fundraiser" else False,
        "donation_min_cents": int(donation.get("minimum_cents", cart.get("donation_min_cents", 0)) or 0),
        "donation_max_cents": int(donation.get("maximum_cents", cart.get("donation_max_cents", 0)) or 0),
        "promo_codes_enabled": bool(settings.get("promo_codes") or cart.get("promo_codes")),
    }


def _clean_quantity(value: Any, *, default: Optional[int] = None, minimum: int = 0) -> Optional[int]:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("quantity_must_be_integer", "Inventory and bundle quantities must be whole numbers", 400)
    amount = int(value)
    if amount < minimum:
        raise WebstoreError("quantity_out_of_range", "Inventory and bundle quantities cannot be negative", 400)
    return amount


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _clean_status(value: Any, allowed: set[str], default: str, field: str) -> str:
    status = str(value or default).strip().lower()
    if status not in allowed:
        raise WebstoreError(f"invalid_{field}", f"Unsupported {field.replace('_', ' ')}", 400)
    return status


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _reject_stage4a_publication_request(fields: dict[str, Any], *, allow_system_transition: bool = False) -> None:
    if allow_system_transition:
        return
    if fields.get("public") is True:
        raise WebstoreError(
            "catalog_publication_not_available",
            "Products cannot be made public from Batch 1 catalog setup. Public launch and checkout are handled in later Webstore batches.",
            400,
        )
    if fields.get("featured") is True:
        raise WebstoreError(
            "catalog_featured_not_available",
            "Products cannot be featured publicly from Batch 1 catalog setup. Public storefront controls are handled later.",
            400,
        )


def _reject_stage4a_financial_variant_request(fields: dict[str, Any]) -> None:
    blocked = sorted(STAGE4A_FINANCIAL_VARIANT_FIELDS & set(fields))
    if blocked:
        raise WebstoreError(
            "stage4a_financial_fields_not_available",
            "Product Foundation cannot create or change pricing, fees, shares, SKUs, or variants. Those controls are handled in a later Webstore stage.",
            400,
        )


def _stage4a_product_create_fingerprint(fields: dict[str, Any], *, operation: str, source_template_id: Optional[str]) -> str:
    comparable = {key: deepcopy(value) for key, value in fields.items() if key != "idempotency_key"}
    comparable["operation"] = operation
    comparable["source_template_id"] = source_template_id
    return _hash_payload(comparable)


def _check_idempotent_product_replay(
    existing: dict[str, Any],
    *,
    actor_id: Optional[str],
    operation: str,
    source_template_id: Optional[str],
    payload_hash: str,
) -> None:
    if (
        existing.get("stage4a_idempotency_actor_id") != actor_id
        or existing.get("stage4a_idempotency_operation") != operation
        or (existing.get("stage4a_idempotency_source_template_id") or None) != (source_template_id or None)
        or existing.get("stage4a_idempotency_payload_hash") != payload_hash
    ):
        raise WebstoreError(
            "stage4a_idempotency_conflict",
            "This product action key was already used for a different product action. Start a new action and try again.",
            409,
        )


def _association_ids(items: Any, key: str) -> set[str]:
    return {str(item.get(key)) for item in items or [] if isinstance(item, dict) and item.get(key)}


def _association_change_summary(before: list[dict[str, Any]], after: list[dict[str, Any]], *, key: str, label: str) -> tuple[str, str, Optional[str]]:
    before_ids = _association_ids(before, key)
    after_ids = _association_ids(after, key)
    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    if added:
        return f"webstore.product_{label}_associated", f"Webstore product {label} associated", added[0]
    if removed:
        return f"webstore.product_{label}_removed", f"Webstore product {label} removed", removed[0]
    return f"webstore.product_{label}_updated", f"Webstore product {label} associations updated", None


def _slug(value: str) -> str:
    text = SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return text[:80] or "webstore"


def _normalize_store_type(value: Any) -> str:
    key = _slug(str(value or "general")).replace("-", "_")
    aliases = {"b_2_b": "b2b", "business_to_business": "b2b"}
    key = aliases.get(key, key)
    if key not in VALID_WEBSTORE_TYPES:
        raise WebstoreError("invalid_webstore_type", "Unsupported Webstore type", 400)
    return key


async def _public_slug_available(public_slug: str, *, existing_webstore_id: Optional[str] = None) -> bool:
    existing = await db.webstores.find_one({"public_slug": public_slug}, {"_id": 0, "id": 1})
    return not existing or existing.get("id") == existing_webstore_id


async def _generate_public_slug(*, tenant_id: str, shop_context: str, store_name: str, internal_slug: str) -> str:
    base = _slug(f"{shop_context}-{store_name}")[:72] or internal_slug
    candidate = base
    if await _public_slug_available(candidate):
        return candidate
    seed = _slug(f"{tenant_id}-{internal_slug}")[:72] or internal_slug
    candidate = seed
    if await _public_slug_available(candidate):
        return candidate
    for suffix in range(2, 1000):
        candidate = f"{seed[:72]}-{suffix}"
        if await _public_slug_available(candidate):
            return candidate
    raise WebstoreError("public_slug_unavailable", "Unable to allocate a public Webstore slug", 409)


async def _ensure_public_slug(store: dict) -> dict:
    if store.get("public_slug"):
        return store
    public_slug = await _generate_public_slug(
        tenant_id=store["tenant_id"],
        shop_context=store["tenant_id"],
        store_name=store.get("name") or store.get("slug") or store["id"],
        internal_slug=store.get("slug") or store["id"],
    )
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"], "public_slug": {"$exists": False}},
        {"$set": {"public_slug": public_slug, "public_url": f"/p/webstores/{public_slug}", "updated_at": _now_iso()}},
    )
    updated = await db.webstores.find_one({"tenant_id": store["tenant_id"], "id": store["id"]}, {"_id": 0})
    return serialize_doc(updated or {**store, "public_slug": public_slug, "public_url": f"/p/webstores/{public_slug}"})


def _validate_transition(current: str, requested: str) -> None:
    if requested not in VALID_WEBSTORE_STATUSES:
        raise WebstoreError("invalid_webstore_status", "Unsupported Webstore lifecycle status", 400)
    if requested == current:
        return
    allowed = WEBSTORE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_webstore_transition", f"Cannot move Webstore from {current} to {requested}", 409)


def _phase6_state_for_status(status: str) -> str:
    return INTERNAL_STATUS_TO_PHASE6.get(status or "draft", "draft")


def _validate_phase6_transition(current: str, requested: str) -> None:
    if requested not in PHASE6_LIFECYCLE_STATES:
        raise WebstoreError("invalid_lifecycle_state", "Unsupported Phase 6 Webstores lifecycle state", 400)
    if requested == current:
        return
    allowed = PHASE6_LIFECYCLE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_lifecycle_transition", f"Cannot move Webstore from {current} to {requested}", 409)


def _validate_status_change(current_status: str, requested_status: str) -> None:
    """Apply the canonical Phase 6 gate plus internal setup-state rules."""
    _validate_transition(current_status, requested_status)
    current_phase = _phase6_state_for_status(current_status)
    requested_phase = _phase6_state_for_status(requested_status)
    if current_phase != requested_phase:
        _validate_phase6_transition(current_phase, requested_phase)


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreError("permission_denied", f"Missing permission: {perm.value}", 403)


async def _require_webstore_assignment_scope(user: dict, webstore_id: str) -> None:
    """Enforce explicit active Webstore assignments when they exist for a user.

    Tenant owners/admins without an assignment remain tenant-wide. A user with
    an active assignment is restricted to the stores assigned to that account;
    this keeps staff routes consistent with the portal assignment authority.
    """
    assigned_store_id = user.get("webstore_id")
    assigned_store_ids = {str(value) for value in (user.get("webstore_ids") or [])}
    if assigned_store_id and str(assigned_store_id) != webstore_id:
        raise WebstoreError(
            "webstore_assignment_scope_forbidden",
            "Webstore access is limited to the assigned Webstore",
            403,
        )
    if assigned_store_ids and webstore_id not in assigned_store_ids:
        raise WebstoreError(
            "webstore_assignment_scope_forbidden",
            "Webstore access is limited to assigned Webstores",
            403,
        )

    identity_filters = [{"portal_identity_id": str(user.get("id"))}]
    email = str(user.get("email") or "").strip().lower()
    if email:
        identity_filters.append({"email": email})
    assignments = [
        doc
        async for doc in db.webstore_access_assignments.find(
            {
                "tenant_id": user["tenant_id"],
                "status": "active",
                "$or": identity_filters,
            },
            {"_id": 0, "webstore_id": 1},
        )
    ]
    if assignments:
        allowed_store_ids = {str(doc["webstore_id"]) for doc in assignments if doc.get("webstore_id")}
        if webstore_id not in allowed_store_ids:
            raise WebstoreError(
                "webstore_assignment_scope_forbidden",
                "Webstore access is limited to assigned Webstores",
                403,
            )


def _require_platform_creator(user: dict) -> None:
    if not has_platform_admin_access(user, extra_permissions={PlatformPerm.PLATFORM_CREATOR.value}):
        raise WebstoreError("platform_creator_required", "Platform Creator access is required for platform starter templates", 403)


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    activity = WebstoreActivity(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, **(metadata or {})},
    )


async def _record_lifecycle_event(
    *,
    tenant_id: str,
    webstore_id: str,
    from_status: Optional[str],
    to_status: str,
    from_state: Optional[str],
    to_state: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    reason: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = WebstoreLifecycleEvent(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        from_status=from_status,
        to_status=to_status,
        from_state=from_state,
        to_state=to_state,
        actor_id=actor_id,
        actor_email=actor_email,
        reason=reason,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_lifecycle_events.insert_one(prepare_for_mongo(event))
    return serialize_doc(event)


def _image_reference_for_response(
    product: dict,
    *,
    slot: str,
    image: dict[str, Any],
    public_slug: Optional[str] = None,
    include_private_id: bool = False,
) -> dict[str, Any]:
    result = {
        "slot": slot,
        "role": image.get("role") or slot,
        "alt_text": image.get("alt_text"),
        "file_name": image.get("file_name"),
        "content_type": image.get("content_type"),
        "recommended_dimensions": image.get("recommended_dimensions") or (
            "1600x1200 px or larger for primary images" if slot == "primary" else "1200x1200 px or larger for secondary images"
        ),
    }
    if image.get("url"):
        result["url"] = image["url"]
    elif public_slug and image.get("file_id"):
        result["url"] = f"/api/public/webstores/{public_slug}/product-images/{product['id']}/{slot}"
    if include_private_id and image.get("file_id"):
        result["file_id"] = image["file_id"]
        result["preview_url"] = f"/api/webstores/{product['webstore_id']}/setup-files/{image['file_id']}/preview"
    return {k: v for k, v in result.items() if v not in (None, "")}


def _product_image_map(product: dict) -> dict[str, dict[str, Any]]:
    images = product.get("customer_images") or {}
    if images:
        return {slot: dict(value or {}) for slot, value in images.items() if slot in CUSTOMER_IMAGE_SLOTS and value}
    legacy_ids = list(product.get("image_file_ids") or [])[:2]
    slots = ["primary", "secondary"]
    return {
        slots[index]: {"file_id": file_id, "role": slots[index], "alt_text": product.get("name"), "legacy": True}
        for index, file_id in enumerate(legacy_ids)
        if file_id
    }


def _variant_option_signature(variant: dict[str, Any]) -> str:
    option_keys = ["size", "color", "style", "material"]
    option_values = [
        f"{key}:{_normalize_name(str(variant.get(key) or ''))}"
        for key in option_keys
        if variant.get(key) not in (None, "")
    ]
    explicit_options = variant.get("options") if isinstance(variant.get("options"), dict) else {}
    for key in sorted(explicit_options):
        value = explicit_options.get(key)
        if value not in (None, ""):
            option_values.append(f"{_normalize_name(str(key))}:{_normalize_name(str(value))}")
    return "|".join(option_values) or _normalize_name(str(variant.get("name") or variant.get("sku") or "default"))


def _public_variant(variant: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "name",
        "size",
        "color",
        "style",
        "material",
        "options",
        "sku",
        "price_delta_cents",
        "selling_price_cents",
        "inventory_quantity",
        "available",
        "status",
    }
    return {k: v for k, v in variant.items() if k in allowed and v not in (None, "")}


def _public_personalization_field(field: dict[str, Any]) -> dict[str, Any]:
    allowed = {"key", "label", "type", "required", "choices", "placeholder", "max_length"}
    return {k: v for k, v in field.items() if k in allowed and v not in (None, "")}


def _product_setup_requirements(product: dict) -> list[dict[str, Any]]:
    has_images = bool(_product_image_map(product)) or bool(product.get("mockup_associations"))
    has_variants = bool(product.get("variants")) or bool(product.get("sku"))
    requirements = [
        {"key": "basic_information", "label": "Basic information", "complete": bool(product.get("name") and product.get("product_type"))},
        {"key": "catalog_organization", "label": "Category", "complete": bool(product.get("category_id") or product.get("category_name") or product.get("category"))},
        {"key": "pricing", "label": "Selling price", "complete": int(product.get("selling_price_cents") or 0) > 0},
        {"key": "images_or_mockups", "label": "Image or mockup", "complete": has_images},
        {"key": "options_or_sku", "label": "SKU or options", "complete": has_variants},
    ]
    if product.get("personalization_enabled"):
        requirements.append({"key": "personalization", "label": "Personalization prompts", "complete": bool(product.get("personalization_fields"))})
    return requirements


def _derived_catalog_status(product: dict) -> str:
    status = product.get("status") or "planned"
    if status in {"archived", "active", "ready", "incomplete", "planned"}:
        return status
    if status == "draft":
        requirements = _product_setup_requirements(product)
        complete = sum(1 for item in requirements if item["complete"])
        if complete == 0:
            return "planned"
        return "ready" if all(item["complete"] for item in requirements) else "incomplete"
    if status == "inactive":
        return "incomplete"
    return "planned"


def _image_slot_change_events(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    events: list[tuple[str, str, dict[str, Any]]] = []
    for slot in ("primary", "secondary"):
        before_image = dict((before or {}).get(slot) or {})
        after_image = dict((after or {}).get(slot) or {})
        if not before_image and not after_image:
            continue
        if before_image and after_image and before_image == after_image:
            continue
        if after_image and not before_image:
            action_word = "added"
            action = "webstore.product_image_added"
        elif before_image and not after_image:
            action_word = "removed"
            action = "webstore.product_image_removed"
        else:
            action_word = "replaced"
            action = "webstore.product_image_replaced"
        role = "Primary" if slot == "primary" else "Secondary"
        events.append(
            (
                action,
                f"{role} Webstore product image {action_word}",
                {
                    "image_association_id": f"{slot}_image",
                    "image_slot": slot,
                    "image_role": role,
                    "image_action": action_word,
                },
            )
        )
    return events


def _public_product_is_eligible(product: dict) -> bool:
    if product.get("status") != "active" or product.get("public") is not True:
        return False
    if product.get("approval_status") != "approved":
        return False
    if product.get("approval_invalidated_at"):
        return False
    if int(product.get("approval_revision") or 0) != int(product.get("revision") or 1):
        return False
    return bool(_effective_fulfillment_methods(product))


def _public_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public_variants = [
        variant
        for variant in (_public_variant(item) for item in product.get("variants") or [] if item.get("status", "active") != "archived")
        if variant
    ]
    result = {
        "id": product.get("id"),
        "name": product.get("name"),
        "description": product.get("short_description") or product.get("description"),
        "full_description": product.get("full_description"),
        "category": product.get("category_name") or product.get("category"),
        "category_id": product.get("category_id"),
        "product_type": product.get("product_type"),
        "sku": product.get("sku"),
        "selling_price_cents": product.get("selling_price_cents"),
        "personalization_enabled": bool(product.get("personalization_enabled")),
        "personalization_fields": [
            _public_personalization_field(field)
            for field in product.get("personalization_fields") or []
        ],
        "images": [
            _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug)
            for slot, image in _product_image_map(product).items()
        ],
        "public": bool(product.get("public")),
        "featured": bool(product.get("featured")),
        "status": product.get("status"),
        "fulfillment_methods": _effective_fulfillment_methods(product),
        "default_fulfillment_method": product.get("default_fulfillment_method") or (_effective_fulfillment_methods(product) or [None])[0],
        "pickup_instructions": product.get("pickup_instructions"),
        "shipping_cost_cents": int(product.get("shipping_cost_cents") or 0),
    }
    if public_variants:
        result["variants"] = public_variants
    return {k: v for k, v in result.items() if v not in (None, "")}


def _portal_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public = _public_product(product, public_slug=public_slug)
    public["webstore_id"] = product.get("webstore_id")
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        if product.get(key) not in (None, ""):
            public[key] = product.get(key)
    return {k: v for k, v in public.items() if v not in (None, "")}


def _staff_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    data = serialize_doc(product)
    data["images"] = [
        _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug, include_private_id=True)
        for slot, image in _product_image_map(product).items()
    ]
    data["catalog_status"] = _derived_catalog_status(product)
    data["setup_status"] = data["catalog_status"]
    data["setup_requirements"] = _product_setup_requirements(product)
    data["launch_packet_eligible"] = bool(product.get("launch_packet_eligible")) or data["catalog_status"] in {"ready", "active"}
    data["launch_packet_include"] = bool(product.get("launch_packet_include")) and data["launch_packet_eligible"]
    data["template_provenance"] = {
        "source_template_id": product.get("source_template_id"),
        "source_template_revision": product.get("source_template_revision"),
    }
    return data  # type: ignore[return-value]


def _approval_history_row(doc: dict) -> dict:
    return {
        key: doc.get(key)
        for key in (
            "id",
            "parent_type",
            "parent_id",
            "parent_version",
            "action",
            "reason",
            "actor_type",
            "actor_ref",
            "actor_display",
            "snapshot_hash",
            "status",
            "created_at",
            "superseded_at",
            "superseded_reason",
        )
        if doc.get(key) not in (None, "")
    }


async def _approval_history(tenant_id: str, parent_type: str, parent_id: str) -> list[dict[str, Any]]:
    return [
        _approval_history_row(doc)
        async for doc in db.approvals.find(
            {"tenant_id": tenant_id, "parent_type": parent_type, "parent_id": parent_id},
            {"_id": 0, "snapshot": 0},
        ).sort([("created_at", -1)])
    ]


def _owner_safe_product_snapshot(product: dict, *, public_slug: Optional[str] = None, mockups: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    safe = _portal_product(product, public_slug=public_slug)
    safe["revision"] = int(product.get("revision") or 1)
    safe["snapshot_type"] = "webstore_product"
    safe["mockups"] = mockups or []
    return safe


def _owner_safe_mockup_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = {
        "id": mockup.get("id"),
        "webstore_id": mockup.get("webstore_id"),
        "product_id": mockup.get("product_id"),
        "artwork_id": mockup.get("artwork_id"),
        "generation_source": mockup.get("generation_source"),
        "purpose": mockup.get("purpose"),
        "alt_text": mockup.get("alt_text"),
        "status": mockup.get("status"),
        "approval_status": mockup.get("approval_status"),
        "approval_decision_at": mockup.get("approval_decision_at"),
        "snapshot_type": "webstore_mockup",
    }
    if product:
        snapshot["product"] = _portal_product(product, public_slug=public_slug)
    return {k: v for k, v in snapshot.items() if v not in (None, "")}


def _mockup_approval_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = _owner_safe_mockup_snapshot(mockup, product, public_slug=public_slug)
    for key in ("approval_status", "approval_decision_at"):
        snapshot.pop(key, None)
    if isinstance(snapshot.get("product"), dict):
        for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
            snapshot["product"].pop(key, None)
    return snapshot


async def _current_mockups_for_product(tenant_id: str, webstore_id: str, product: dict) -> list[dict[str, Any]]:
    mockup_ids = _association_ids(product.get("mockup_associations") or [], "mockup_id")
    query: dict[str, Any] = {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$ne": "archived"}}
    if mockup_ids:
        query["$or"] = [{"id": {"$in": sorted(mockup_ids)}}, {"product_id": product["id"], "owner_visible": True}]
    else:
        query["product_id"] = product["id"]
        query["owner_visible"] = True
    rows: list[dict[str, Any]] = []
    async for doc in db.webstore_mockups.find(query, {"_id": 0}).sort([("created_at", -1)]):
        rows.append(_owner_safe_mockup_snapshot(serialize_doc(doc)))
    return rows


async def _product_approval_snapshot(tenant_id: str, webstore_id: str, product: dict, *, public_slug: Optional[str]) -> dict[str, Any]:
    mockups = []
    for mockup in await _current_mockups_for_product(tenant_id, webstore_id, product):
        frozen = dict(mockup)
        frozen.pop("approval_status", None)
        frozen.pop("approval_decision_at", None)
        mockups.append(frozen)
    snapshot = _owner_safe_product_snapshot(
        product,
        public_slug=public_slug,
        mockups=mockups,
    )
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        snapshot.pop(key, None)
    return snapshot


async def _invalidate_product_approval_if_needed(
    *,
    tenant_id: str,
    webstore_id: str,
    product: dict,
    reason: str,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
) -> None:
    if product.get("approval_status") not in {"pending_owner_approval", "approved"}:
        return
    now = _now_iso()
    await db.approvals.update_many(
        {"tenant_id": tenant_id, "parent_type": "webstore_product", "parent_id": product["id"], "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason}},
    )
    await db.webstore_products.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": product["id"]},
        {
            "$set": {
                "approval_status": "superseded",
                "approval_invalidated_at": now,
                "approval_invalidated_reason": reason,
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
        action="webstore.product_approval_superseded",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product approval superseded by material product change",
        metadata={"reason": reason},
    )


def _public_store(
    store: dict,
    published_branding: Optional[dict[str, Any]] = None,
    fundraiser_progress: Optional[dict[str, Any]] = None,
    provider_authority: Optional[bool] = None,
) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "deadline_at",
        "public_url",
        "checkout_enabled",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    result["branding"] = published_branding or {}
    provider_status = provider_configuration_status(get_settings())
    provider_ready = provider_status["provider_authority"] if provider_authority is None else provider_authority
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_ready
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    result["cart_config"] = _public_cart_config(store)
    if store.get("store_type") == "fundraiser":
        result["fundraiser_progress"] = fundraiser_progress or {
            "goal_cents": result["cart_config"]["fundraiser_goal_cents"],
            "completed_sales_cents": 0,
            "percent": 0,
            "over_goal": False,
            "paid_only": True,
        }
    return result


def _portal_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
        "terms_fee_acknowledged",
        "owner_approved_at",
        "launch_packet_id",
        "launch_packet_version",
        "owner_approved_packet_id",
        "owner_approved_packet_version",
        "owner_approval_invalidated_at",
        "owner_approval_invalidated_reason",
        "required_terms_version",
        "terms_acceptance_id",
        "terms_accepted_version",
        "terms_accepted_at",
        "setup_state",
        "setup_profile",
        "store_settings",
        "target_launch_at",
        "intended_launch_at",
        "intended_close_at",
        "launch_timezone",
        "event_start_at",
        "event_location",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    provider_status = provider_configuration_status(get_settings())
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_status["provider_authority"]
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    return result


def _portal_launch_packet(packet: Optional[dict]) -> Optional[dict]:
    if not packet:
        return None
    allowed = {
        "id",
        "webstore_id",
        "status",
        "version",
        "snapshot",
        "snapshot_hash",
        "pricing_summary",
        "promotion_copy",
        "qr_code_url",
        "share_url",
        "delivery_status",
        "delivery_recipient_email",
        "delivery_portal_path",
        "sent_at",
        "delivered_at",
        "owner_decision_at",
        "change_request_reason",
        "superseded_at",
        "invalidated_at",
        "invalidated_reason",
    }
    return {k: v for k, v in packet.items() if k in allowed}


async def _portal_launch_packet_with_history(tenant_id: str, packet: Optional[dict]) -> Optional[dict]:
    safe = _portal_launch_packet(packet)
    if not safe:
        return None
    safe["approval_history"] = await _approval_history(tenant_id, "webstore_launch_packet", safe["id"])
    return safe


def _portal_change_request(item: dict) -> dict:
    allowed = {
        "id",
        "packet_id",
        "packet_version",
        "category",
        "affected_item_ref",
        "owner_comment",
        "status",
        "owner_visible_history",
        "resolved_at",
        "created_at",
        "updated_at",
    }
    return {k: v for k, v in item.items() if k in allowed}


def _portal_terms_acceptance(item: Optional[dict]) -> Optional[dict]:
    if not item:
        return None
    allowed = {
        "id",
        "terms_version",
        "accepted_at",
        "packet_id",
        "packet_version",
        "terms_snapshot",
        "fee_summary_snapshot",
        "status",
    }
    return {k: v for k, v in item.items() if k in allowed}


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await stores_repo.get(tenant_id=tenant_id, entity_id=webstore_id)
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    return store


async def _get_owner(tenant_id: str, owner_id: str) -> dict:
    owner = await owners_repo.get(tenant_id=tenant_id, entity_id=owner_id)
    if not owner:
        raise WebstoreError("webstore_owner_not_found", "Webstore owner not found", 404)
    return owner


async def _get_product(tenant_id: str, product_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": product_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    product = await products_repo.find_one(filt)
    if not product:
        raise WebstoreError("webstore_product_not_found", "Webstore product not found", 404)
    return product


async def _get_mockup(tenant_id: str, mockup_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": mockup_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    mockup = await db.webstore_mockups.find_one(filt, {"_id": 0})
    if not mockup:
        raise WebstoreError("webstore_mockup_not_found", "Webstore mockup not found", 404)
    return serialize_doc(mockup)


async def _get_category(tenant_id: str, webstore_id: str, category_id: str) -> dict:
    category = await db.webstore_product_categories.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": category_id},
        {"_id": 0},
    )
    if not category:
        raise WebstoreError("webstore_category_not_found", "Webstore product category was not found", 404)
    return serialize_doc(category)


async def _setup_file_for_product_reference(tenant_id: str, webstore_id: str, file_id: str) -> dict:
    doc = await db.webstore_setup_files.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": file_id, "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise WebstoreError("product_file_not_found", "The selected product file was not found for this Webstore", 404)
    ext = str(doc.get("extension") or "").lower()
    if ext not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_type_not_allowed", "Product images must be JPG, PNG, WebP, or a safe SVG image", 400)
    if ext == "svg" and not doc.get("svg_sanitized"):
        raise WebstoreError("product_image_svg_not_safe", "SVG product images must pass the existing safe SVG policy", 400)
    return serialize_doc(doc)


async def _normalize_customer_images(tenant_id: str, webstore_id: str, images: Optional[dict[str, Any]]) -> dict[str, Any]:
    if images is None:
        return {}
    unknown = sorted(set(images.keys()) - CUSTOMER_IMAGE_SLOTS)
    if unknown:
        raise WebstoreError("too_many_product_image_slots", "Products support only primary and secondary customer-facing image slots", 400)
    normalized: dict[str, Any] = {}
    for slot in ("primary", "secondary"):
        image = dict(images.get(slot) or {})
        if not image:
            continue
        file_id = image.get("file_id")
        url = image.get("url")
        alt_text = _clean_optional_text(image.get("alt_text"), limit=200)
        if (file_id or url) and not alt_text:
            raise WebstoreError("product_image_alt_text_required", f"Add alternate text for the {slot} product image", 400)
        record = {
            "slot": slot,
            "role": _clean_optional_text(image.get("role"), limit=80) or slot,
            "alt_text": alt_text,
            "recommended_dimensions": image.get("recommended_dimensions") or (
                "1600x1200 px or larger" if slot == "primary" else "1200x1200 px or larger"
            ),
            "updated_at": _now_iso(),
        }
        if file_id:
            file_doc = await _setup_file_for_product_reference(tenant_id, webstore_id, str(file_id))
            record.update(
                {
                    "file_id": file_doc["id"],
                    "file_name": file_doc.get("file_name"),
                    "content_type": file_doc.get("detected_content_type") or file_doc.get("content_type"),
                    "file_version": file_doc.get("version"),
                }
            )
        elif url:
            record["url"] = str(url)
        normalized[slot] = {k: v for k, v in record.items() if v not in (None, "")}
    return normalized


def _reject_private_file_refs_for_platform_template(images: dict[str, Any], artwork: list[dict[str, Any]], mockups: Optional[list[dict[str, Any]]] = None) -> None:
    for image in (images or {}).values():
        if isinstance(image, dict) and image.get("file_id"):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)
    for item in [*(artwork or []), *(mockups or [])]:
        if isinstance(item, dict) and (item.get("file_id") or item.get("artwork_id") or item.get("mockup_id")):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)


def _has_private_image_file_refs(images: Any) -> bool:
    return any(isinstance(image, dict) and bool(image.get("file_id")) for image in (images or {}).values())


async def _normalize_product_category(user: dict, webstore_id: str, fields: dict[str, Any], existing: Optional[dict] = None) -> tuple[Optional[str], Optional[str], Optional[str]]:
    category_id = fields.get("category_id") if "category_id" in fields else (existing or {}).get("category_id")
    category_name = fields.get("category_name") if "category_name" in fields else (existing or {}).get("category_name")
    legacy_category = fields.get("category") if "category" in fields else (existing or {}).get("category")
    if category_id:
        category = await _get_category(user["tenant_id"], webstore_id, str(category_id))
        if category.get("status") != "active":
            raise WebstoreError("webstore_category_archived", "Archived categories cannot be assigned to products", 409)
        return category["id"], category["name"], category["name"]
    if category_name:
        return None, _clean_text(category_name, "category_name", limit=120), _clean_text(category_name, "category_name", limit=120)
    if legacy_category:
        cleaned = _clean_optional_text(legacy_category, limit=120)
        return None, cleaned, cleaned
    return None, None, None


async def _normalize_artwork_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected artwork was not found for this product", 404)
        if art.get("product_id") not in (None, "", product_id):
            raise WebstoreError("artwork_product_scope_mismatch", "Selected artwork belongs to a different product", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_mockup_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected mockup was not found for this product", 404)
        if mockup.get("product_id") not in (None, "", product_id):
            raise WebstoreError("mockup_product_scope_mismatch", "Selected mockup belongs to a different product", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


async def _normalize_template_artwork_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected template artwork was not found for this Webstore", 404)
        if art.get("product_id"):
            raise WebstoreError("artwork_product_scope_mismatch", "Product-specific artwork cannot be used as a reusable template default", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_template_mockup_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected template mockup was not found for this Webstore", 404)
        if mockup.get("product_id"):
            raise WebstoreError("mockup_product_scope_mismatch", "Product-specific mockups cannot be used as reusable template defaults", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


async def _ensure_unique_product_skus(
    *,
    tenant_id: str,
    webstore_id: str,
    product_id: str,
    sku: Optional[str],
    variants: list[dict[str, Any]],
) -> None:
    supplied = [str(value).strip() for value in [sku, *[variant.get("sku") for variant in variants]] if str(value or "").strip()]
    lowered = [_normalize_name(value) for value in supplied]
    if len(lowered) != len(set(lowered)):
        raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this product", 409)
    if not lowered:
        return
    async for doc in db.webstore_products.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": {"$ne": product_id}, "status": {"$ne": "archived"}},
        {"_id": 0, "sku": 1, "variants": 1},
    ):
        existing = [str(value).strip() for value in [doc.get("sku"), *[variant.get("sku") for variant in doc.get("variants") or []]] if str(value or "").strip()]
        if set(lowered) & {_normalize_name(value) for value in existing}:
            raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this Webstore", 409)


def _normalize_variants(variants: Optional[list[dict[str, Any]]], *, base_selling_price_cents: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    signatures: set[str] = set()
    for index, item in enumerate(variants or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_variant", "Each variant must be an object", 400)
        variant: dict[str, Any] = {
            "id": _clean_optional_text(item.get("id"), limit=80) or f"variant-{index + 1}",
            "name": _clean_optional_text(item.get("name"), limit=120),
            "size": _clean_optional_text(item.get("size"), limit=80),
            "color": _clean_optional_text(item.get("color"), limit=80),
            "style": _clean_optional_text(item.get("style"), limit=80),
            "material": _clean_optional_text(item.get("material"), limit=80),
            "sku": _clean_optional_text(item.get("sku"), limit=120),
            "options": item.get("options") if isinstance(item.get("options"), dict) else {},
            "status": _clean_status(item.get("status"), {"active", "inactive", "archived"}, "active", "variant_status"),
            "available": bool(item.get("available", True)),
            "inventory_quantity": _clean_quantity(item.get("inventory_quantity"), default=None),
            "production_cost_cents": _clean_money(item.get("production_cost_cents"), default=0),
            "store_owner_share_cents": _clean_money(item.get("store_owner_share_cents"), default=0),
            "fundraiser_share_cents": _clean_money(item.get("fundraiser_share_cents"), default=0),
            "price_delta_cents": _clean_money(item.get("price_delta_cents"), default=0),
        }
        variant["selling_price_cents"] = _clean_money(item.get("selling_price_cents"), default=base_selling_price_cents + variant["price_delta_cents"])
        if variant["store_owner_share_cents"] + variant["fundraiser_share_cents"] > variant["selling_price_cents"]:
            raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the variant selling price", 400)
        signature = _variant_option_signature(variant)
        if signature in signatures:
            raise WebstoreError("duplicate_variant_combination", "Each size/color/options variant combination must be unique", 409)
        signatures.add(signature)
        normalized.append({k: v for k, v in variant.items() if v not in (None, "", {})})
    return normalized


def _normalize_personalization_fields(items: Optional[list[dict[str, Any]]], *, enabled: bool) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_personalization_field", "Each personalization prompt must be an object", 400)
        label = _clean_text(item.get("label"), "personalization_label", limit=120)
        key = _clean_optional_text(item.get("key"), limit=80) or _slug(label).replace("-", "_") or f"field_{index + 1}"
        field_type = str(item.get("type") or "text").strip().lower()
        if field_type not in {"text", "textarea", "select", "number"}:
            raise WebstoreError("invalid_personalization_type", "Personalization prompts support text, textarea, select, or number", 400)
        field = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(item.get("required", False)),
            "choices": [str(choice).strip() for choice in item.get("choices") or [] if str(choice).strip()][:20],
            "placeholder": _clean_optional_text(item.get("placeholder"), limit=120),
            "max_length": _clean_quantity(item.get("max_length"), default=None, minimum=1),
        }
        if field_type == "select" and not field["choices"]:
            raise WebstoreError("personalization_choices_required", "Select personalization prompts require at least one choice", 400)
        normalized.append({k: v for k, v in field.items() if v not in (None, "", [])})
    if enabled and not normalized:
        raise WebstoreError("personalization_fields_required", "Add at least one personalization prompt or turn personalization off", 400)
    keys = [field["key"] for field in normalized]
    if len(keys) != len(set(keys)):
        raise WebstoreError("duplicate_personalization_field", "Personalization prompt keys must be unique", 409)
    return normalized


async def _normalize_bundle_items(
    user: dict,
    webstore_id: str,
    product_id: str,
    items: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            raise WebstoreError("invalid_bundle_item", "Each bundle item must be an object", 400)
        bundled_product_id = str(item.get("product_id") or "").strip()
        if not bundled_product_id:
            continue
        if bundled_product_id == product_id:
            raise WebstoreError("bundle_self_reference", "A product bundle cannot include itself", 409)
        if bundled_product_id in seen:
            raise WebstoreError("duplicate_bundle_item", "Bundle items must be unique", 409)
        bundled = await _get_product(user["tenant_id"], bundled_product_id, webstore_id)
        if bundled.get("status") == "archived":
            raise WebstoreError("bundle_item_archived", "Archived products cannot be included in bundles", 409)
        seen.add(bundled_product_id)
        normalized.append(
            {
                "product_id": bundled_product_id,
                "name_snapshot": bundled.get("name"),
                "quantity": _clean_quantity(item.get("quantity"), default=1, minimum=1),
                "sku_snapshot": bundled.get("sku"),
            }
        )
    return normalized

async def _owner_portal_store(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    store = await _get_store(identity["tenant_id"], webstore_id)
    assignment = await db.webstore_access_assignments.find_one(
        {
            "tenant_id": identity["tenant_id"],
            "webstore_id": webstore_id,
            "portal_identity_id": identity.get("id"),
            "status": "active",
        },
        {"_id": 0},
    )
    if assignment:
        return store
    assignment_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": identity["tenant_id"], "portal_identity_id": identity.get("id")}
    )
    if assignment_count:
        raise WebstoreError("webstore_assignment_scope_forbidden", "Webstore portal access is limited to assigned Webstores", 403)
    owner_id = identity.get("webstore_owner_id")
    if owner_id and store.get("owner_id") != owner_id:
        raise WebstoreError("webstore_scope_forbidden", "Webstore portal access is owner-scoped", 403)
    if not owner_id:
        raise WebstoreError("webstore_owner_scope_required", "Webstore owner scope is required", 403)
    assigned_webstore_id = identity.get("webstore_id")
    if identity.get("portal_type") == "webstore_manager":
        if not assigned_webstore_id:
            raise WebstoreError("webstore_manager_assignment_required", "Webstore manager scope is required", 403)
        if assigned_webstore_id != webstore_id:
            raise WebstoreError("webstore_manager_scope_forbidden", "Webstore manager access is limited to the assigned Webstore", 403)
    return store

__all__ = [name for name in globals() if not name.startswith("__")]
