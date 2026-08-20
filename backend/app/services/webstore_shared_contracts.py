"""Focused Webstore shared helpers."""
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

__all__ = [name for name in globals() if not name.startswith("__")]
