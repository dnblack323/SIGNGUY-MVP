"""Public storefront, cart, checkout, ledger, and commerce actions for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_payment_boundary import _provider_authority_from_record, provider_authority_for_webstore

async def _fundraiser_progress(store: dict[str, Any]) -> dict[str, Any]:
    """Expose only completed, verified Webstore sales as fundraiser progress."""
    settings = store.get("store_settings") or {}
    setup = store.get("setup_profile") or {}
    cart = settings.get("cart") or {}
    donation = settings.get("donations") or settings.get("donation") or {}
    goal = int(
        setup.get("fundraiser_goal_amount")
        or cart.get("fundraiser_goal_cents")
        or donation.get("goal_amount_cents")
        or 0
    )
    paid_sales = 0
    async for intent in db.webstore_purchase_intents.find(
        {
            "tenant_id": store["tenant_id"],
            "webstore_id": store["id"],
            "status": "paid_order_created",
            "canonical_payment_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0, "total_cents": 1},
    ):
        paid_sales += max(0, int(intent.get("total_cents") or 0))
    percent = int((Decimal(paid_sales) * Decimal(100) / Decimal(goal)).quantize(Decimal("1"))) if goal else 0
    return {
        "goal_cents": goal,
        "completed_sales_cents": paid_sales,
        "percent": percent,
        "over_goal": bool(goal and paid_sales > goal),
        "paid_only": True,
    }


async def _storefront_by_slug(slug: str) -> dict:
    store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    store = await _ensure_public_slug(serialize_doc(store))
    if store.get("status") != "live":
        raise WebstoreError("webstore_not_live", "Webstore is not available", 404)
    close_at = store.get("deadline_at") or store.get("intended_close_at")
    if close_at:
        try:
            closing = datetime.fromisoformat(str(close_at).replace("Z", "+00:00"))
            if closing.tzinfo and closing <= datetime.now(timezone.utc):
                raise WebstoreError("webstore_closed", "Webstore is not available", 404)
        except ValueError:
            pass
    access_mode = ((store.get("store_settings") or {}).get("access_policy") or {}).get("mode") or "open"
    if access_mode == "restricted":
        raise WebstoreError("webstore_not_public", "Webstore is not available", 404)
    products = []
    async for doc in db.webstore_products.find(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "status": "active", "public": True},
        {"_id": 0},
    ).sort([("featured", -1), ("name", 1)]):
        product = serialize_doc(doc)
        if _public_product_is_eligible(product):
            products.append(_public_product(product, public_slug=store.get("public_slug")))
    published_branding = await branding_svc.published_branding_for_store(store)
    fundraiser_progress = await _fundraiser_progress(store)
    provider_record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "record_type": "connected_account"},
        {"_id": 0},
    )
    provider_status = provider_configuration_status(get_settings(), _provider_authority_from_record(provider_record, get_settings()))
    return {
        "webstore": _public_store(serialize_doc(store), published_branding, fundraiser_progress, provider_status["provider_authority"]),
        "products": products,
    }


async def public_storefront(slug: str) -> dict:
    return await _storefront_by_slug(slug)


async def public_product_detail(slug: str, product_id: str) -> dict:
    storefront = await _storefront_by_slug(slug)
    product = next((item for item in storefront["products"] if item.get("id") == product_id), None)
    if not product:
        raise WebstoreError("product_not_available", "Product is not available", 404)
    return {"webstore": storefront["webstore"], "product": product}


async def public_product_image(slug: str, product_id: str, slot: str) -> tuple[dict, bytes, str]:
    if slot not in CUSTOMER_IMAGE_SLOTS:
        raise WebstoreError("product_image_slot_not_found", "Product image was not found", 404)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    product = await db.webstore_products.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": store["id"],
            "id": product_id,
            "status": "active",
            "public": True,
        },
        {"_id": 0},
    )
    if not product or not _public_product_is_eligible(product):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    image = _product_image_map(serialize_doc(product)).get(slot)
    if not image or not image.get("file_id"):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    file_doc = await db.webstore_setup_files.find_one(
        {"tenant_id": full_store["tenant_id"], "webstore_id": store["id"], "id": image["file_id"], "status": "active"},
        {"_id": 0},
    )
    if not file_doc:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    if str(file_doc.get("extension") or "").lower() not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_not_public", "Product image is not available publicly", 404)
    try:
        data, content_type = storage.get_bytes(file_doc["storage_key"])
    except FileNotFoundError:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    return serialize_doc(file_doc), data, file_doc.get("detected_content_type") or content_type


def _parse_public_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _promo_codes_for_store(store: dict[str, Any]) -> list[dict[str, Any]]:
    settings = store.get("store_settings") or {}
    configured = settings.get("promo_codes") or (settings.get("cart") or {}).get("promo_codes") or []
    return [item for item in configured if isinstance(item, dict)]


def _calculate_public_discount(store: dict[str, Any], code: Optional[str], subtotal: int, lines: list[dict[str, Any]]) -> tuple[int, Optional[str]]:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return 0, None
    now = datetime.now(timezone.utc)
    promo = next((item for item in _promo_codes_for_store(store) if str(item.get("code") or "").strip().upper() == normalized), None)
    if not promo:
        raise WebstoreError("promo_code_invalid", "That promo code is not available for this Webstore", 409)
    if str(promo.get("status") or "active").lower() != "active":
        raise WebstoreError("promo_code_inactive", "That promo code is not available", 409)
    starts_at = _parse_public_time(promo.get("starts_at"))
    expires_at = _parse_public_time(promo.get("expires_at"))
    if starts_at and starts_at > now:
        raise WebstoreError("promo_code_not_started", "That promo code is not active yet", 409)
    if expires_at and expires_at <= now:
        raise WebstoreError("promo_code_expired", "That promo code has expired", 409)
    usage_limit = int(promo.get("usage_limit") or 0)
    if usage_limit and int(promo.get("times_validated") or 0) >= usage_limit:
        raise WebstoreError("promo_code_exhausted", "That promo code is no longer available", 409)
    minimum = int(promo.get("minimum_subtotal_cents") or 0)
    if subtotal < minimum:
        raise WebstoreError("promo_code_minimum_not_met", "Add more merchandise to use that promo code", 409)
    product_ids = {str(item) for item in promo.get("product_ids") or []}
    category_ids = {str(item) for item in promo.get("category_ids") or []}
    eligible_subtotal = subtotal
    if product_ids or category_ids:
        eligible_subtotal = sum(
            int(line["line_total_cents"])
            for line in lines
            if (not product_ids or line["product_id"] in product_ids)
            and (not category_ids or str(line.get("category_id") or "") in category_ids)
        )
        if eligible_subtotal <= 0:
            raise WebstoreError("promo_code_not_applicable", "That promo code does not apply to the selected products", 409)
    if str(promo.get("discount_type") or "fixed").lower() == "percentage":
        basis_points = int(promo.get("discount_basis_points") or 0)
        if basis_points <= 0 or basis_points > 10000:
            raise WebstoreError("promo_code_invalid", "That promo code is not configured correctly", 409)
        discount = int((Decimal(eligible_subtotal) * Decimal(basis_points) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        discount = int(promo.get("discount_cents") or 0)
    maximum = promo.get("maximum_discount_cents")
    if maximum not in (None, ""):
        discount = min(discount, int(maximum))
    return max(0, min(discount, eligible_subtotal)), normalized


async def quote_public_cart(slug: str, fields: dict[str, Any]) -> dict:
    storefront = await _storefront_by_slug(slug)
    store_view = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store_view["id"]}, {"_id": 0})
    if not full_store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    product_ids = [str(item.get("product_id")) for item in fields.get("line_items") or [] if item.get("product_id")]
    full_products = {
        doc["id"]: serialize_doc(doc)
        async for doc in db.webstore_products.find(
            {"tenant_id": full_store["tenant_id"], "webstore_id": full_store["id"], "id": {"$in": product_ids}},
            {"_id": 0},
        )
        if _public_product_is_eligible(doc)
    }
    public_products = {item["id"]: item for item in storefront["products"]}
    line_items: list[dict[str, Any]] = []
    subtotal = 0
    shipping = 0
    fulfillment_groups: dict[str, int] = {"pickup": 0, "shipping": 0}
    for raw in fields.get("line_items") or []:
        product_id = str(raw.get("product_id") or "")
        full_product = full_products.get(product_id)
        public_product = public_products.get(product_id)
        if not full_product or not public_product:
            raise WebstoreError("product_not_available", "Product is not available", 409)
        quantity = int(raw.get("quantity") or 0)
        if quantity < 1 or quantity > 99:
            raise WebstoreError("invalid_quantity", "Quantity must be between 1 and 99", 400)
        variant = raw.get("variant") if isinstance(raw.get("variant"), dict) else {}
        if full_product.get("variants") and not variant:
            raise WebstoreError("variant_required", "Choose an available product option", 400)
        if not _variant_allowed(full_product.get("variants") or [], variant):
            raise WebstoreError("variant_not_available", "That product option is not available", 409)
        _validate_personalization(full_product, raw.get("personalization") or {})
        methods = _effective_fulfillment_methods(full_product)
        selected_method = str(raw.get("fulfillment_method") or full_product.get("default_fulfillment_method") or (methods[0] if len(methods) == 1 else "")).lower()
        if selected_method not in methods:
            raise WebstoreError("fulfillment_method_required", "Choose an available fulfillment method for each product", 400)
        matched_variant = next((item for item in full_product.get("variants") or [] if _variant_allowed([item], variant)), None)
        unit_price = int(full_product.get("selling_price_cents") or 0)
        if matched_variant:
            if matched_variant.get("selling_price_cents") not in (None, ""):
                unit_price = int(matched_variant["selling_price_cents"])
            else:
                unit_price += int(matched_variant.get("price_delta_cents") or 0)
        line_total = unit_price * quantity
        inventory_policy = str(full_product.get("inventory_policy") or "not_tracked").lower()
        if inventory_policy in {"track", "tracked", "finite"}:
            available = matched_variant.get("inventory_quantity") if matched_variant else full_product.get("inventory_quantity")
            if available not in (None, "") and quantity > int(available):
                raise WebstoreError("insufficient_inventory", "That product option does not have enough inventory", 409)
        line_shipping = int(full_product.get("shipping_cost_cents") or 0) * quantity if selected_method == "shipping" else 0
        subtotal += line_total
        shipping += line_shipping
        fulfillment_groups[selected_method] += line_total
        line_items.append({
            "product_id": product_id,
            "category_id": full_product.get("category_id"),
            "name": public_product.get("name"),
            "variant": variant,
            "personalization": raw.get("personalization") or {},
            "quantity": quantity,
            "fulfillment_method": selected_method,
            "unit_price_cents": unit_price,
            "line_total_cents": line_total,
            "shipping_cents": line_shipping,
        })
    donation = int(fields.get("donation_cents") or 0)
    cart_config = _public_cart_config(full_store)
    if donation < 0:
        raise WebstoreError("invalid_donation", "Donation cannot be negative", 400)
    if donation and not cart_config["donation_enabled"]:
        raise WebstoreError("donation_not_enabled", "Donations are not enabled for this Webstore", 409)
    if cart_config["donation_min_cents"] and donation and donation < cart_config["donation_min_cents"]:
        raise WebstoreError("donation_below_minimum", "Donation is below the configured minimum", 400)
    if cart_config["donation_max_cents"] and donation > cart_config["donation_max_cents"]:
        raise WebstoreError("donation_above_maximum", "Donation exceeds the configured maximum", 400)
    discount, applied_promo = _calculate_public_discount(full_store, fields.get("promo_code"), subtotal, line_items)
    total = max(0, subtotal + shipping + donation - discount)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    snapshot = {
        "webstore_id": full_store["id"],
        "public_slug": slug,
        "line_items": line_items,
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "donation_cents": donation,
        "discount_cents": discount,
        "total_cents": total,
        "promo_code": applied_promo,
        "currency": "usd",
        "expires_at": expires_at,
    }
    return {
        "quote_version": "webstore_cart_quote_v1",
        "quote_id": _json_hash(snapshot),
        "webstore_id": full_store["id"],
        "public_slug": slug,
        "line_items": line_items,
        "fulfillment_groups": {key: value for key, value in fulfillment_groups.items() if value},
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "donation_cents": donation,
        "discount_cents": discount,
        "total_cents": total,
        "currency": "usd",
        "expires_at": expires_at,
        "warnings": [],
        "applied_promo_code": applied_promo,
        "payment_status": "not_requested",
        "order_creation": "deferred_to_stage_8",
        "unpaid_progress_excluded": True,
    }


UNAUTHORIZED_PUBLIC_MONEY_FIELDS = {
    "shipping_cents",
    "tax_cents",
    "discount_cents",
    "fee_cents",
    "total_cents",
    "product_subtotal_cents",
}


def _reject_public_money_authority(fields: dict[str, Any]) -> None:
    supplied = [field for field in UNAUTHORIZED_PUBLIC_MONEY_FIELDS if int(fields.get(field) or 0) != 0]
    if supplied:
        raise WebstoreError(
            "public_money_fields_not_allowed",
            "Shipping, tax, discounts, fees, and final totals are calculated by the server during verified checkout.",
            400,
        )


def _variant_allowed(configured: list[dict[str, Any]], supplied: dict[str, Any]) -> bool:
    if not supplied:
        return True
    for option in configured or []:
        option_status = str(option.get("status") or "active").lower()
        if option_status in {"inactive", "archived", "unavailable"} or option.get("available") is False:
            continue
        if option.get("inventory_quantity") not in (None, "") and int(option["inventory_quantity"]) <= 0:
            continue
        if all(str(option.get(k)) == str(v) for k, v in supplied.items()):
            return True
    return False


def _validate_personalization(product: dict, supplied: dict[str, Any]) -> None:
    if not product.get("personalization_enabled"):
        return
    if not isinstance(supplied, dict) or len(supplied) > 20:
        raise WebstoreError("personalization_invalid", "Personalization details are invalid", 400)
    missing: list[str] = []
    allowed_keys: set[str] = set()
    for field in product.get("personalization_fields") or []:
        key = field.get("key") or field.get("name") or field.get("id")
        if not key:
            continue
        key = str(key)
        allowed_keys.add(key)
        value = supplied.get(key)
        if bool(field.get("required")) and key and not str(supplied.get(key) or "").strip():
            missing.append(str(key))
        if value in (None, ""):
            continue
        field_type = str(field.get("type") or "text").lower()
        if field_type in {"text", "textarea", "date"} and not isinstance(value, str):
            raise WebstoreError("personalization_invalid", f"Personalization field {key} is invalid", 400)
        if field_type in {"text", "textarea"} and len(value) > int(field.get("max_length") or (2000 if field_type == "textarea" else 500)):
            raise WebstoreError("personalization_too_long", f"Personalization field {key} is too long", 400)
        if field_type in {"number", "numeric"}:
            try:
                float(value)
            except (TypeError, ValueError) as exc:
                raise WebstoreError("personalization_invalid", f"Personalization field {key} must be a number", 400) from exc
        if field_type in {"select", "dropdown", "radio"}:
            options = {str(item.get("value", item.get("id", item.get("label", item)))) for item in field.get("options") or []}
            if options and str(value) not in options:
                raise WebstoreError("personalization_invalid", f"Personalization field {key} has an invalid choice", 400)
        if field_type in {"multi_select", "multiselect", "checkboxes"}:
            if not isinstance(value, list) or len(value) > 20:
                raise WebstoreError("personalization_invalid", f"Personalization field {key} must be a list", 400)
    unknown = set(supplied) - allowed_keys
    if unknown:
        raise WebstoreError("personalization_invalid", "Unknown personalization fields were supplied", 400)
    if missing:
        raise WebstoreError("personalization_required", "Required personalization fields are missing", 400)


def _checkout_response(intent: dict, *, created: bool) -> dict:
    public_intent = serialize_doc(intent)
    public_intent.pop("immutable_snapshot", None)
    return {
        "purchase_intent": public_intent,
        "checkout_available": False,
        "checkout_status": intent.get("checkout_status") or "created",
        "checkout": {
            "provider": intent.get("provider") or "deferred",
            "provider_checkout_id": intent.get("provider_checkout_id"),
            "payment_required": True,
            "payment_authority": "none",
            "verified_payment_creates_order": True,
            "unavailable_reason": "Provider checkout is unavailable until this Webstore's payment authority is enabled.",
        },
        "created": created,
    }


async def create_purchase_intent(slug: str, fields: dict[str, Any], *, allow_internal_draft: bool = False) -> dict:
    _reject_public_money_authority(fields)
    provider_status = provider_configuration_status(get_settings())
    if not allow_internal_draft and not provider_status["provider_authority"]:
        raise WebstoreError(
            "payment_provider_not_configured",
            "Online checkout is unavailable until the Webstore payment provider is configured and verified.",
            503,
        )
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    if not allow_internal_draft and not store.get("checkout_enabled"):
        raise WebstoreError("checkout_paused", "Checkout is currently paused for this Webstore", 409)
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    tenant_id = full_store["tenant_id"]
    if fields.get("idempotency_key"):
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return _checkout_response(existing, created=False)
    quote = await quote_public_cart(slug, fields)
    if not quote["line_items"]:
        raise WebstoreError("line_items_required", "At least one line item is required", 400)
    line_items: list[dict[str, Any]] = []
    financial_lines: list[dict[str, Any]] = []
    for line in quote["line_items"]:
        product_id = line["product_id"]
        qty = int(line["quantity"])
        full_product = await _get_product(tenant_id, product_id, store["id"])
        line_items.append(
            {
                **line,
                "product_snapshot": {
                    "id": product_id,
                    "name": full_product["name"],
                    "description": full_product.get("description"),
                    "category": full_product.get("category"),
                    "product_type": full_product.get("product_type"),
                    "sku": full_product.get("sku"),
                },
            }
        )
        line_total = int(line["line_total_cents"])
        fee_bps = int(full_product.get("platform_fee_basis_points") or 0)
        financial_lines.append(
            {
                "product_id": product_id,
                "line_total_cents": line_total,
                "platform_fee_basis_points": fee_bps,
                "platform_fee_cents": int((Decimal(line_total) * Decimal(fee_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                "store_owner_share_cents": int(full_product.get("store_owner_share_cents") or 0) * qty,
                "fundraiser_share_cents": int(full_product.get("fundraiser_share_cents") or 0) * qty,
                "production_cost_cents": int(full_product.get("production_cost_cents") or 0) * qty,
            }
        )
    subtotal = int(quote["subtotal_cents"])
    total = int(quote["total_cents"])
    intent = WebstorePurchaseIntent(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        public_slug=slug,
        buyer_name=_clean_text(fields.get("buyer_name"), "buyer_name"),
        buyer_email=_clean_public_email(fields.get("buyer_email")),
        buyer_phone=_clean_optional_text(fields.get("buyer_phone"), limit=40),
        line_items=line_items,
        product_subtotal_cents=subtotal,
        donation_cents=int(quote["donation_cents"]),
        shipping_cents=int(quote["shipping_cents"]),
        discount_cents=int(quote["discount_cents"]),
        total_cents=total,
        idempotency_key=fields.get("idempotency_key"),
        immutable_snapshot={
            "webstore": _public_store(full_store),
            "line_items": line_items,
            "server_calculated_totals": {
                "product_subtotal_cents": subtotal,
                "donation_cents": int(quote["donation_cents"]),
                "shipping_cents": int(quote["shipping_cents"]),
                "tax_cents": 0,
                "discount_cents": int(quote["discount_cents"]),
                "fee_cents": 0,
                "total_cents": total,
                "currency": "usd",
            },
            "checkout_contract": {
                "authority": "verified_provider_event",
                "success_redirect_is_not_payment_evidence": True,
            },
            "financial_lines": financial_lines,
        },
    ).model_dump()
    intent["confirmation_token"] = secrets.token_urlsafe(24)
    try:
        await db.webstore_purchase_intents.insert_one(prepare_for_mongo(intent))
    except DuplicateKeyError:
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields.get("idempotency_key")},
            {"_id": 0},
        )
        return _checkout_response(existing, created=False)
    await _audit(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        actor_type="public",
        actor_email=intent["buyer_email"],
        action="webstore.purchase_intent_created",
        entity_type="webstore_purchase_intent",
        entity_id=intent["id"],
        summary="Webstore checkout intent created; canonical records await verified payment evidence",
        metadata={"total_cents": total, "payment_authority": "verified_provider_event"},
    )
    saved = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": intent["id"]}, {"_id": 0})
    return _checkout_response(saved, created=True)


def _provider_checkout_response(intent: dict, provider_data: dict[str, Any], *, created: bool) -> dict:
    public_intent = serialize_doc(intent)
    public_intent.pop("immutable_snapshot", None)
    return {
        "purchase_intent": public_intent,
        "checkout_available": True,
        "checkout_status": intent.get("checkout_status") or "session_created",
        "checkout": {
            "provider": "stripe",
            "provider_checkout_id": intent.get("provider_checkout_id"),
            "checkout_url": intent.get("checkout_url"),
            "payment_required": True,
            "payment_authority": "verified_provider_event",
            "verified_payment_creates_order": True,
            "status": provider_data.get("checkout_status") or "open",
        },
        "created": created,
    }


async def create_checkout_session(slug: str, fields: dict[str, Any]) -> dict:
    """Create or reuse one server-priced Stripe Checkout Session.

    This boundary records only the purchase intent and provider session. The
    signed webhook boundary is the only path that can mark payment verified;
    canonical Order and Production creation remains a later stage.
    """
    _reject_public_money_authority(fields)
    if not str(fields.get("idempotency_key") or "").strip():
        raise WebstoreError("idempotency_key_required", "Checkout requires an idempotency key", 400)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    if not full_store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    authority = await provider_authority_for_webstore(full_store["tenant_id"], store["id"])
    if not store.get("checkout_enabled"):
        raise WebstoreError("checkout_paused", "Checkout is currently paused for this Webstore", 409)
    existing = None
    if fields.get("idempotency_key"):
        existing = await db.webstore_purchase_intents.find_one(
            {
                "tenant_id": full_store["tenant_id"],
                "webstore_id": store["id"],
                "idempotency_key": fields["idempotency_key"],
            },
            {"_id": 0},
        )
        if existing and existing.get("provider_checkout_id") and existing.get("checkout_url"):
            return _provider_checkout_response(existing, existing, created=False)
    intent_response = await create_purchase_intent(slug, fields, allow_internal_draft=True)
    intent_id = (intent_response.get("purchase_intent") or {}).get("id")
    intent = await db.webstore_purchase_intents.find_one(
        {"id": intent_id, "tenant_id": full_store["tenant_id"], "webstore_id": store["id"]},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("purchase_intent_not_found", "Webstore purchase intent could not be created", 500)
    provider = get_webstore_payment_provider(get_settings())
    provider_result = await provider.create_checkout_session(
        tenant_id=full_store["tenant_id"],
        webstore_id=store["id"],
        purchase_intent_id=intent["id"],
        buyer_email=intent["buyer_email"],
        currency=intent.get("currency") or "usd",
        line_items=[{
            "name": f"{store.get('name') or 'Webstore'} order",
            "quantity": 1,
            "unit_amount_cents": int(intent.get("total_cents") or 0),
        }],
        connected_account_reference=authority.account_reference,
        idempotency_key=fields.get("idempotency_key") or intent["id"],
    )
    if not provider_result.ok:
        raise WebstoreError("payment_provider_error", provider_result.message, 503)
    provider_data = dict(provider_result.data or {})
    checkout_id = str(provider_data.get("checkout_session_id") or "").strip()
    checkout_url = str(provider_data.get("checkout_url") or "").strip()
    if not checkout_id or not checkout_url:
        raise WebstoreError("payment_provider_error", "Stripe did not return a checkout session URL", 503)
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": full_store["tenant_id"], "webstore_id": store["id"], "id": intent["id"], "status": "pending_payment"},
        {
            "$set": {
                "provider": "stripe",
                "provider_mode": provider_data.get("provider_mode") or get_settings().stripe_mode,
                "provider_checkout_id": checkout_id,
                "checkout_url": checkout_url,
                "checkout_status": "session_created",
                "checkout_attempt_id": checkout_id,
                "checkout_attempt_state": "created",
                "expected_amount_cents": int(intent.get("total_cents") or 0),
                "expected_currency": intent.get("currency") or "usd",
                "updated_at": utc_now().isoformat(),
            }
        },
    )
    saved = await db.webstore_purchase_intents.find_one({"id": intent["id"], "tenant_id": full_store["tenant_id"]}, {"_id": 0})
    return _provider_checkout_response(saved, provider_data, created=existing is None)


async def create_buyer_order(
    slug: str,
    fields: dict[str, Any],
    *,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    """Create a pending intent only after typed internal authority exists.

    Public routers call ``create_purchase_intent`` with its fail-closed
    default. Without typed authority this compatibility helper remains
    fail-closed. With a controlled provider-authoritative fixture it creates
    only a pending intent and never creates a Payment, Order, inventory
    mutation, or Production record.
    """
    if provider_authority is None:
        return await create_purchase_intent(slug, fields)
    if not provider_authority.verified or not provider_authority.webhook_verified or provider_authority.charge_model == "deferred":
        raise WebstoreError("payment_provider_not_configured", "Provider-authoritative Webstore preparation is unavailable", 503)
    return await create_purchase_intent(slug, fields, allow_internal_draft=True)


async def public_confirmation(slug: str, confirmation_token: str) -> dict:
    # Historical receipts remain available after close/archive, but only with
    # the token issued for that purchase. No arbitrary Order ID is accepted.
    full_store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not full_store:
        raise WebstoreError("confirmation_not_found", "Webstore confirmation was not found", 404)
    intent = await db.webstore_purchase_intents.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": full_store["id"],
            "public_slug": slug,
            "confirmation_token": confirmation_token,
            "canonical_order_id": {"$type": "string"},
        },
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("confirmation_not_found", "Webstore confirmation was not found", 404)
    order = await db.orders.find_one({"tenant_id": full_store["tenant_id"], "id": intent.get("canonical_order_id")}, {"_id": 0})
    return {
        "purchase_intent": {
            "id": intent.get("id"),
            "buyer_name": intent.get("buyer_name"),
            "buyer_email": intent.get("buyer_email"),
            "total_cents": int(intent.get("total_cents") or 0),
            "currency": intent.get("currency") or "usd",
            "status": intent.get("status"),
            "fulfillment_status": intent.get("fulfillment_status"),
        },
        "order": {
            "number": (order or {}).get("number"),
            "status": (order or {}).get("status"),
            "total_cents": int(intent.get("total_cents") or 0),
        },
        "payment_status": intent.get("status"),
        "fulfillment_status": intent.get("fulfillment_status"),
    }


async def _create_ledger_rows(
    *,
    tenant_id: str,
    webstore_id: str,
    buyer_order_id: str,
    subtotal: int,
    donation: int,
    shipping: int,
    tax: int,
    total: int,
    platform_fee: int,
    owner_share: int,
    production_cost: int,
) -> None:
    shop_gross = subtotal - platform_fee - owner_share - production_cost
    rows = [
        ("buyer_payment", total, total, None),
        ("product_subtotal", subtotal, subtotal, None),
        ("donation", donation, donation, None),
        ("shipping", shipping, shipping, None),
        ("sales_tax", tax, tax, None),
        ("payment_processing_fee", 0, total, None),
        ("platform_usage_fee", platform_fee, subtotal, None),
        ("store_owner_share", owner_share, subtotal, None),
        ("production_cost_estimate", production_cost, subtotal, None),
        ("shop_gross_estimate", shop_gross, subtotal, None),
    ]
    for entry_type, amount, basis, bps in rows:
        entry = WebstoreLedgerEntry(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            buyer_order_id=buyer_order_id,
            entry_type=entry_type,  # type: ignore[arg-type]
            amount_cents=amount,
            basis_amount_cents=basis,
            snapshot_basis_points=bps,
            source_type="webstore_buyer_order",
            source_id=buyer_order_id,
        ).model_dump()
        await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))


async def _ledger_for_order(tenant_id: str, buyer_order_id: str) -> list[dict]:
    cursor = db.webstore_ledger_entries.find({"tenant_id": tenant_id, "buyer_order_id": buyer_order_id}, {"_id": 0}).sort("created_at", 1)
    return [serialize_doc(doc) async for doc in cursor]


async def reverse_platform_fee(user: dict, ledger_entry_id: str, refund_basis_amount_cents: int) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    original = await db.webstore_ledger_entries.find_one(
        {"tenant_id": user["tenant_id"], "id": ledger_entry_id, "entry_type": "platform_usage_fee", "reversal_of_ledger_entry_id": None},
        {"_id": 0},
    )
    if not original:
        raise WebstoreError("platform_fee_not_found", "Original Webstore platform fee ledger entry not found", 404)
    if refund_basis_amount_cents <= 0 or refund_basis_amount_cents > int(original.get("basis_amount_cents") or 0):
        raise WebstoreError("invalid_refund_basis", "Refund basis must be positive and cannot exceed original basis", 400)
    reversal = int(
        (Decimal(original["amount_cents"]) * Decimal(refund_basis_amount_cents) / Decimal(original["basis_amount_cents"]))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    entry = WebstoreLedgerEntry(
        tenant_id=original["tenant_id"],
        webstore_id=original["webstore_id"],
        buyer_order_id=original.get("buyer_order_id"),
        entry_type="platform_usage_fee_reversal",
        amount_cents=-reversal,
        basis_amount_cents=refund_basis_amount_cents,
        snapshot_basis_points=original.get("snapshot_basis_points"),
        source_type=original.get("source_type", "webstore_buyer_order"),
        source_id=original.get("source_id", original["id"]),
        status="reversed" if refund_basis_amount_cents == original.get("basis_amount_cents") else "adjusted",
        reversal_of_ledger_entry_id=original["id"],
        notes="Proportional platform-fee reversal. Original ledger entry is immutable.",
    ).model_dump()
    await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=original["webstore_id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.platform_fee_reversed",
        entity_type="webstore_ledger_entry",
        entity_id=entry["id"],
        summary="Webstore platform fee reversal recorded",
        metadata={"original_ledger_entry_id": original["id"], "refund_basis_amount_cents": refund_basis_amount_cents},
    )
    return serialize_doc(entry)  # type: ignore[return-value]


async def bridge_buyer_order_to_order(user: dict, buyer_order_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    buyer = await buyer_orders_repo.get(tenant_id=user["tenant_id"], entity_id=buyer_order_id)
    if not buyer:
        raise WebstoreError("buyer_order_not_found", "Buyer order not found", 404)
    if not buyer.get("verified_payment_event_id") or buyer.get("payment_status") != "paid":
        raise WebstoreError(
            "verified_payment_required",
            "Legacy Webstore buyer orders cannot become canonical Orders without verified payment evidence.",
            409,
        )
    if buyer.get("bridged_order_id"):
        order = await db.orders.find_one({"tenant_id": user["tenant_id"], "id": buyer["bridged_order_id"]}, {"_id": 0})
        return {"order": serialize_doc(order), "bridge_status": buyer.get("bridge_status", "bridged")}
    customer = await db.customers.find_one({"tenant_id": user["tenant_id"], "email": buyer["buyer_email"]}, {"_id": 0})
    if not customer:
        customer_doc = Customer(
            tenant_id=user["tenant_id"],
            name=buyer["buyer_name"],
            email=buyer["buyer_email"],
            phone=buyer.get("buyer_phone"),
            notes=f"Created from Webstore buyer order {buyer['id']}",
        ).model_dump()
        customer_number = await next_record_number(
            tenant_id=user["tenant_id"],
            record_type="customer",
            issued_to_entity_type="customer",
            issued_to_entity_id=customer_doc["id"],
            actor_user_id=user["id"],
            actor_email=user.get("email"),
            reason="webstore.bridge_customer_create",
            context={"buyer_order_id": buyer["id"], "webstore_id": buyer["webstore_id"]},
        )
        customer_doc["number"] = customer_number.number
        await db.customers.insert_one(prepare_for_mongo(customer_doc))
        customer = customer_doc
    number = await next_number(tenant_id=user["tenant_id"], name="order")
    order = Order(
        tenant_id=user["tenant_id"],
        number=number,
        customer_id=customer["id"],
        job_name=f"Webstore order - {buyer['buyer_name']}",
        title=f"Webstore order {buyer['id']}",
        description="Created from Webstore buyer order",
        subtotal_cents=buyer["product_subtotal_cents"],
        tax_cents=buyer["tax_cents"],
        total_cents=buyer["total_cents"],
        balance_cents=buyer["total_cents"],
        status="confirmed",
        created_by=user["id"],
    ).model_dump()
    await db.orders.insert_one(prepare_for_mongo(order))
    for idx, line in enumerate(buyer.get("line_items") or []):
        item = OrderItem(
            tenant_id=user["tenant_id"],
            order_id=order["id"],
            position=idx,
            category="webstore",
            product_type="webstore_product",
            description=line["name"],
            quantity=int(line["quantity"]),
            unit_price_cents=int(line["unit_price_cents"]),
            line_subtotal_cents=int(line["line_total_cents"]),
            line_total_cents=int(line["line_total_cents"]),
            pricing_snapshot={"source": "webstore_buyer_order", "buyer_order_id": buyer["id"], "line_item": line},
            production_required=True,
        ).model_dump()
        await db.order_items.insert_one(prepare_for_mongo(item))
    await buyer_orders_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=buyer["id"],
        updates={"bridged_order_id": order["id"], "bridge_status": "bridged", "status": "ready_for_production"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=buyer["webstore_id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.buyer_order_bridged",
        entity_type="order",
        entity_id=order["id"],
        summary="Webstore buyer order bridged to canonical Order",
        metadata={"buyer_order_id": buyer["id"]},
    )
    return {"order": serialize_doc(order), "bridge_status": "bridged"}


async def reports(user: dict, webstore_id: str) -> dict:
    from . import webstore_reports

    return await webstore_reports.staff_report(user, webstore_id)


async def refund_webstore_payment(user: dict, webstore_id: str, payment_id: str, fields: dict[str, Any], idempotency_key: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    await _get_store(user["tenant_id"], webstore_id)
    from . import webstore_payments

    return await webstore_payments.initiate_webstore_refund(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        payment_id=payment_id,
        amount_cents=fields.get("amount_cents"),
        reason=_clean_text(fields.get("reason"), "reason", limit=500),
        actor_user_id=user["id"],
        actor_email=user.get("email") or "",
        idempotency_key=idempotency_key or fields.get("idempotency_key"),
    )

__all__ = [name for name in globals() if not name.startswith("__")]
