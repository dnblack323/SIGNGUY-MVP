"""Public cart validation and server-authoritative totals for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_public_storefront import _storefront_by_slug

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
