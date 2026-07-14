"""Tenant pricing settings storage + calculator + wizard suggestions.

One document per tenant in `pricing_settings` collection. Auto-cloned from the
starter default pack on first access.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from .starter_defaults import build_starter_pack, CATEGORY_IDS, MATERIALS, STARTER_DEFAULT_VERSION
from .pricing_flat_sqft import FLAT_SQFT_CATEGORIES, calculate_flat_sqft_pricing
from .pricing_apparel import calculate_apparel_pricing
from .pricing_promotional import calculate_promotional_pricing
from .pricing_vehicle_graphics import calculate_vehicle_graphics_pricing
from .pricing_services import calculate_services_pricing
from .pricing_custom import calculate_custom_pricing


def _now_iso() -> str:
    return utc_now().isoformat()


async def _apply_additive_default_merge(tenant_id: str, doc: dict[str, Any]) -> dict[str, Any]:
    """EC9 Phase 9E-2 Correction 2 — idempotent additive default merge.

    Long-lived tenants must receive newly-required `category_defaults` keys
    (e.g. Phase 9E-2's `garments`/`decoration_methods`, Phase 9E-3's vehicle
    tables) WITHOUT an explicit "Reset to starter" action and WITHOUT ever
    touching a key the tenant already has — even a stale/edited one. Only
    ever ADDS missing keys; never overwrites. Fast-paths to a no-op once
    `starter_default_version` already matches. Only ever touches this
    tenant's `pricing_settings` document — the separate `quotes`/`orders`
    collections (and any embedded historical pricing snapshots) are never
    read or written here, so past calculations are unaffected.
    """
    if doc.get("starter_default_version") == STARTER_DEFAULT_VERSION:
        return doc
    starter_cats = build_starter_pack()["category_defaults"]
    stored_cats = doc.get("category_defaults") or {}
    field_sources = dict(doc.get("field_sources") or {})
    set_ops: dict[str, Any] = {}
    any_missing = False
    for cat_id, starter_cat in starter_cats.items():
        stored_cat = stored_cats.get(cat_id) or {}
        for k, v in starter_cat.items():
            if k not in stored_cat:
                any_missing = True
                set_ops[f"category_defaults.{cat_id}.{k}"] = v
                field_sources[f"category_defaults.{cat_id}.{k}"] = "shop_default"
    set_ops["starter_default_version"] = STARTER_DEFAULT_VERSION
    if any_missing:
        set_ops["field_sources"] = field_sources
        set_ops["updated_at"] = _now_iso()
    await db.pricing_settings.update_one({"tenant_id": tenant_id}, {"$set": set_ops})
    return await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})


async def get_or_init_pricing_settings(tenant_id: str) -> dict[str, Any]:
    """Return the tenant's pricing settings document, cloning the starter pack on first use."""
    doc = await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if doc:
        return await _apply_additive_default_merge(tenant_id, doc)
    pack = build_starter_pack()
    pack["tenant_id"] = tenant_id
    pack["tenant_pricing_initialized_at"] = _now_iso()
    pack["updated_at"] = _now_iso()
    await db.pricing_settings.insert_one(prepare_for_mongo(pack))
    return await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})


async def update_shop_defaults(tenant_id: str, updates: dict[str, Any], source: str = "user_entered") -> dict[str, Any]:
    doc = await get_or_init_pricing_settings(tenant_id)
    sd = dict(doc.get("shop_defaults") or {})
    sources = dict(doc.get("field_sources") or {})
    for k, v in updates.items():
        if v is None:
            continue
        sd[k] = float(v) if isinstance(v, (int, float, Decimal)) else v
        sources[f"shop_defaults.{k}"] = source
    await db.pricing_settings.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"shop_defaults": sd, "field_sources": sources, "updated_at": _now_iso()}},
    )
    return await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})


async def update_category(tenant_id: str, category_id: str, updates: dict[str, Any], source: str = "user_entered") -> dict[str, Any]:
    if category_id not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category_id}")
    doc = await get_or_init_pricing_settings(tenant_id)
    cats = dict(doc.get("category_defaults") or {})
    current = dict(cats.get(category_id) or {})
    sources = dict(doc.get("field_sources") or {})
    for k, v in updates.items():
        if v is None:
            continue
        if k == "__mark_setup_complete__":
            continue
        current[k] = v
        sources[f"category_defaults.{category_id}.{k}"] = source
    if updates.get("__mark_setup_complete__") is True:
        current["setup_complete"] = True
        current["setup_updated_at"] = _now_iso()
        current["needs_tenant_setup"] = False
    cats[category_id] = current
    await db.pricing_settings.update_one(
        {"tenant_id": tenant_id},
        {"$set": {f"category_defaults.{category_id}": current, "field_sources": sources, "updated_at": _now_iso()}},
    )
    return await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})


async def reset_category_to_starter(tenant_id: str, category_id: str) -> dict[str, Any]:
    if category_id not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category_id}")
    starter = build_starter_pack()
    starter_cat = starter["category_defaults"][category_id]
    await db.pricing_settings.update_one(
        {"tenant_id": tenant_id},
        {"$set": {f"category_defaults.{category_id}": starter_cat, "updated_at": _now_iso()}},
    )
    return await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

def calculate_pricing(
    *,
    settings: dict[str, Any],
    category: str,
    width_inches: float | None,
    height_inches: float | None,
    quantity: int,
    material_key: Optional[str] = None,
    design_needed: bool = False,
    install_needed: bool = False,
    manual_selling_price: Optional[float] = None,
    category_inputs: Optional[dict[str, Any]] = None,
    material_profile: Optional[dict[str, Any]] = None,
    pricing_components: Optional[list[dict[str, Any]]] = None,
    saved_item: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return the canonical MVP pricing response.

    All money returned as float dollars, rounded to 2 decimals.
    Breakdown is a list of {label, amount} rows explaining how the total was built.

    EC9 Phase 9E-1: for the 4 "Core Flat & Square-Foot" categories (banners,
    rigid_signs, digital_print, cut_vinyl), this dispatches to the detailed
    EC09-controlling-document formulas in `services/pricing_flat_sqft.py`
    (still the single authoritative pipeline — this function is the only
    entrypoint routers call). All other categories keep the pre-existing
    generic per-sqft/cost-plus calculation below, unchanged.

    EC9 Phase 9E-2: `apparel` and `promotional` also dispatch to their own
    EC09-controlling-document formula libraries (`pricing_apparel.py`,
    `pricing_promotional.py`). `promotional` is driven primarily by an
    optional resolved `saved_item` (a `PricingSavedItem`, e.g. a preloaded
    Business Card tier item) rather than by `width_inches`/`height_inches`.
    """
    if category not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category}")

    shop = settings.get("shop_defaults") or {}
    cats = settings.get("category_defaults") or {}
    materials = settings.get("materials") or {}
    cat = cats.get(category) or {}

    if category in FLAT_SQFT_CATEGORIES:
        return calculate_flat_sqft_pricing(
            category=category, shop=shop, cat=cat, materials_legacy=materials,
            material_profile=material_profile, pricing_components=pricing_components or [],
            width_inches=width_inches, height_inches=height_inches, quantity=quantity,
            material_key=material_key, design_needed=design_needed, install_needed=install_needed,
            manual_selling_price=manual_selling_price, category_inputs=category_inputs or {},
        )

    if category == "apparel":
        return calculate_apparel_pricing(
            shop=shop, cat=cat, pricing_components=pricing_components or [], quantity=quantity,
            manual_selling_price=manual_selling_price, category_inputs=category_inputs or {},
        )

    if category == "promotional":
        return calculate_promotional_pricing(
            shop=shop, cat=cat, pricing_components=pricing_components or [], quantity=quantity,
            manual_selling_price=manual_selling_price, category_inputs=category_inputs or {},
            saved_item=saved_item,
        )

    if category == "vehicle_graphics":
        return calculate_vehicle_graphics_pricing(
            shop=shop, cat=cat, pricing_components=pricing_components or [], quantity=quantity,
            manual_selling_price=manual_selling_price, category_inputs=category_inputs or {},
        )

    if category == "services":
        return calculate_services_pricing(
            shop=shop, cat=cat, pricing_components=pricing_components or [], quantity=quantity,
            manual_selling_price=manual_selling_price, category_inputs=category_inputs or {},
            material_profile=material_profile,
        )

    if category == "custom":
        return calculate_custom_pricing(
            cat=cat, quantity=quantity, manual_selling_price=manual_selling_price,
            category_inputs=category_inputs or {},
        )

    # Unreachable: every id in CATEGORY_IDS is dispatched above.
    raise ValueError(f"Unhandled category: {category}")


# ---------------------------------------------------------------------------
# Wizard suggestions (banners full — others scaffolded)
# ---------------------------------------------------------------------------

def _make_suggestion(question: str, answer: Any, current: Any, target_field: str,
                     suggested: Any, confidence: str, note: str = "") -> dict[str, Any]:
    return {
        "question": question,
        "answer": answer,
        "current": current,
        "suggested": suggested,
        "target_field": target_field,      # dotted path within category_defaults
        "confidence": confidence,          # "recommended" | "review_recommended"
        "apply": True,                     # default checked; user can uncheck
        "note": note,
    }


def _banners_wizard_suggestions(answers: dict[str, Any], current: dict[str, Any]) -> list[dict]:
    out: list[dict] = []
    # Per-size sell rates -> base_sell_rate_per_sqft
    size_prices = []
    for size_key, sqft in [("price_2x4", 8), ("price_3x6", 18), ("price_4x8", 32)]:
        v = answers.get(size_key)
        if isinstance(v, (int, float)) and v > 0:
            rate = float(v) / sqft
            size_prices.append((size_key, rate, float(v), sqft))
    if size_prices:
        rates = [r for _, r, _, _ in size_prices]
        avg = sum(rates) / len(rates)
        confidence = "recommended" if len(rates) >= 2 else "review_recommended"
        pretty = ", ".join(f"${p:.0f} for {s} sqft" for _, r, p, s in size_prices)
        out.append(_make_suggestion(
            question="What would you charge for standard 13oz banners (with hems + grommets)?",
            answer=pretty,
            current=current.get("base_sell_rate_per_sqft"),
            target_field="base_sell_rate_per_sqft",
            suggested=round(avg, 2),
            confidence=confidence,
            note=f"Average of {len(rates)} entered price(s).",
        ))
    # Hems/grommets included
    if "hems_grommets_included" in answers and isinstance(answers["hems_grommets_included"], bool):
        out.append(_make_suggestion(
            question="Are hems & grommets normally included?",
            answer=answers["hems_grommets_included"],
            current=current.get("hems_grommets_included"),
            target_field="hems_grommets_included",
            suggested=answers["hems_grommets_included"],
            confidence="recommended",
        ))
    # Minimum charge
    if isinstance(answers.get("minimum_charge"), (int, float)) and answers["minimum_charge"] > 0:
        out.append(_make_suggestion(
            question="What is your minimum banner charge?",
            answer=answers["minimum_charge"],
            current=current.get("minimum_charge"),
            target_field="minimum_charge",
            suggested=float(answers["minimum_charge"]),
            confidence="recommended",
        ))
    for extra_field, question, target in [
        ("pole_pocket_charge_per_ft", "Do you charge extra for pole pockets ($ per linear ft)?", "pole_pocket_charge_per_ft"),
        ("reinforced_corners_charge", "Do you charge extra for reinforced corners?", "reinforced_corners_charge"),
        ("wind_slit_charge", "Do you charge extra for wind slits?", "wind_slit_charge"),
    ]:
        v = answers.get(extra_field)
        if isinstance(v, (int, float)) and v >= 0:
            out.append(_make_suggestion(
                question=question, answer=v, current=current.get(extra_field),
                target_field=target, suggested=float(v), confidence="recommended",
            ))
    # Install available
    if "install_available" in answers and isinstance(answers["install_available"], bool):
        out.append(_make_suggestion(
            question="Do you offer banner installation?",
            answer=answers["install_available"],
            current=current.get("install_available"),
            target_field="install_available",
            suggested=answers["install_available"],
            confidence="recommended",
        ))
    # Method
    if answers.get("pricing_method"):
        out.append(_make_suggestion(
            question="How do you want to price banners?",
            answer=answers["pricing_method"],
            current=current.get("pricing_method"),
            target_field="pricing_method",
            suggested=answers["pricing_method"],
            confidence="recommended",
        ))
    return out


def _generic_wizard_suggestions(category: str, answers: dict[str, Any], current: dict[str, Any]) -> list[dict]:
    """Simple scaffold: any of the known fields present in answers is suggested as-is."""
    passthrough_fields = [
        "pricing_method", "minimum_charge", "base_sell_rate_per_sqft",
        "default_markup_multiplier", "target_margin_percent",
        "blank_tshirt_cost", "decoration_cost_per_garment",
        "printed_wrap_sell_per_sqft", "color_change_wrap_sell_per_sqft",
        "minimum_design_charge", "minimum_install_charge",
        "minimum_setup_fee", "labor_hours_per_unit_default",
    ]
    out: list[dict] = []
    for f in passthrough_fields:
        if f in answers and answers[f] is not None:
            out.append(_make_suggestion(
                question=f"{f.replace('_', ' ').capitalize()}?",
                answer=answers[f],
                current=current.get(f),
                target_field=f,
                suggested=answers[f],
                confidence="review_recommended",
            ))
    # Common job prices freeform
    common = answers.get("common_job_prices") or {}
    if isinstance(common, dict) and common:
        out.append(_make_suggestion(
            question="Common job prices",
            answer=common,
            current=current.get("common_job_prices"),
            target_field="common_job_prices",
            suggested=common,
            confidence="review_recommended",
            note="Stored for reference; used later to inform quick-quote suggestions.",
        ))
    return out


def wizard_suggestions(category: str, answers: dict[str, Any], settings: dict[str, Any]) -> list[dict]:
    if category not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category}")
    current = (settings.get("category_defaults") or {}).get(category) or {}
    if category == "banners":
        return _banners_wizard_suggestions(answers, current)
    return _generic_wizard_suggestions(category, answers, current)
