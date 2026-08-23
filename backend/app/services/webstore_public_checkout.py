"""Public purchase-intent and checkout session coordination for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_payment_boundary import provider_authority_for_webstore
from .webstore_public_cart import _validate_personalization, _variant_allowed, quote_public_cart
from .webstore_public_storefront import _storefront_by_slug

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
