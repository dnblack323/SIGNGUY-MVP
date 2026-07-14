"""Tenant pricing settings storage + calculator + wizard suggestions.

One document per tenant in `pricing_settings` collection. Auto-cloned from the
starter default pack on first access.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from .starter_defaults import build_starter_pack, CATEGORY_IDS, MATERIALS, STARTER_DEFAULT_VERSION
from .pricing_flat_sqft import FLAT_SQFT_CATEGORIES, calculate_flat_sqft_pricing
from .pricing_apparel import calculate_apparel_pricing
from .pricing_promotional import calculate_promotional_pricing
from .pricing_vehicle_graphics import calculate_vehicle_graphics_pricing


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

def _to_dec(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _round2(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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

    # Area
    width = _to_dec(width_inches)
    height = _to_dec(height_inches)
    qty = max(1, int(quantity or 1))
    area_sqft_each = (width * height) / Decimal("144") if width and height else Decimal("0")
    total_area = area_sqft_each * qty

    # Material cost
    material_key = material_key or cat.get("default_material")
    material_cost = Decimal("0")
    material_sell_rate = None
    if material_key and material_key in materials:
        m = materials[material_key]
        material_cost = _to_dec(m.get("cost_per_sqft")) * total_area
        material_sell_rate = m.get("sell_per_sqft")
    # apply waste
    waste_percent = _to_dec(cat.get("waste_percent") or 0)
    if waste_percent > 0:
        material_cost = material_cost * (Decimal("1") + waste_percent / Decimal("100"))

    # Labor cost (production)
    prod_rate = _to_dec(shop.get("production_hourly_rate") or 0)
    # Simple labor allocation: category-specific hr/sqft when we have one, else per-unit fallback.
    labor_hr_per_sqft = _to_dec(cat.get("production_labor_hr_per_sqft") or 0)
    if labor_hr_per_sqft == 0:
        # Reasonable defaults per category derived from the original repo
        defaults_hr_per_sqft = {
            "banners": Decimal("0.10"),
            "rigid_signs": Decimal("0.15"),
            "cut_vinyl": Decimal("0.20"),
            "digital_print": Decimal("0.08"),
            "services": Decimal("0"),
            "custom": Decimal("0"),
        }
        labor_hr_per_sqft = defaults_hr_per_sqft.get(category, Decimal("0"))
    labor_hours = labor_hr_per_sqft * total_area
    labor_cost = labor_hours * prod_rate

    # Design labor
    design_cost = Decimal("0")
    if design_needed:
        design_hours = _to_dec(cat.get("design_default_hours") or Decimal("0.5"))
        design_cost = design_hours * _to_dec(shop.get("design_hourly_rate") or 0)

    # Install labor
    install_cost = Decimal("0")
    if install_needed:
        install_hr_per_sqft = _to_dec(cat.get("install_labor_hr_per_sqft") or Decimal("0.08"))
        install_hours = install_hr_per_sqft * total_area
        install_cost = install_hours * _to_dec(shop.get("install_hourly_rate") or 0)
        min_install = _to_dec(cat.get("install_min_charge") or 0)
        if min_install > 0 and install_cost < min_install:
            install_cost = min_install

    # Setup / finishing / hardware / outsourcing default to 0 in MVP
    setup_cost = Decimal("0")
    finishing_cost = Decimal("0")
    hardware_cost = Decimal("0")
    outsourcing_cost = Decimal("0")

    base_cost = material_cost + labor_cost + design_cost + setup_cost + finishing_cost + hardware_cost + install_cost + outsourcing_cost

    # Overhead
    overhead_pct = _to_dec(shop.get("default_overhead_percent") or 0)
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost

    # Selling price
    pricing_method = cat.get("pricing_method") or "cost_plus_labor"
    method_used = pricing_method
    base_rate = _to_dec(cat.get("base_sell_rate_per_sqft") or 0)
    minimum_charge = _to_dec(cat.get("minimum_charge") or 0)
    target_margin = _to_dec(cat.get("target_margin_percent") or shop.get("target_profit_margin_percent") or 40)
    markup = _to_dec(cat.get("default_markup_multiplier") or shop.get("default_markup_multiplier") or 2.5)

    # 1) manual override
    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _to_dec(manual_selling_price)
        method_used = "manual_override"
    elif pricing_method == "per_sqft" and base_rate > 0 and total_area > 0:
        # per-sqft: max of (rate * area) vs (cost/(1 - margin/100)) vs minimum_charge
        by_rate = base_rate * total_area
        by_margin = true_cost / (Decimal("1") - target_margin / Decimal("100")) if target_margin < 100 else true_cost
        selling_price = max(by_rate, by_margin, minimum_charge)
        method_used = "per_sqft"
    else:
        # cost_plus_labor / common_job_prices fallback
        by_markup = true_cost * markup
        by_margin = true_cost / (Decimal("1") - target_margin / Decimal("100")) if target_margin < 100 else true_cost
        selling_price = max(by_markup, by_margin, minimum_charge)
        method_used = pricing_method if pricing_method != "per_sqft" else "cost_plus_labor"

    # Global minimum order guard
    global_min = _to_dec(shop.get("minimum_order_amount") or 0)
    if selling_price < global_min:
        selling_price = global_min

    profit_amount = selling_price - true_cost
    profit_margin_percent = (
        (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")
    )

    def r(v: Decimal) -> float:
        return _round2(v)

    breakdown = [
        {"label": "Material", "amount": r(material_cost)},
        {"label": "Production labor", "amount": r(labor_cost)},
    ]
    if design_cost > 0: breakdown.append({"label": "Design", "amount": r(design_cost)})
    if install_cost > 0: breakdown.append({"label": "Install", "amount": r(install_cost)})
    breakdown.append({"label": "Overhead", "amount": r(overhead_cost)})
    breakdown.append({"label": "True cost", "amount": r(true_cost)})
    breakdown.append({"label": "Selling price", "amount": r(selling_price)})
    breakdown.append({"label": "Profit", "amount": r(profit_amount)})

    return {
        "category": category,
        "width_inches": float(width_inches or 0),
        "height_inches": float(height_inches or 0),
        "quantity": qty,
        "area_sqft_each": _round2(area_sqft_each),
        "area_sqft_total": _round2(total_area),
        "material_key": material_key,
        "material_sell_rate_per_sqft": material_sell_rate,
        "material_cost": r(material_cost),
        "labor_cost": r(labor_cost),
        "design_cost": r(design_cost),
        "setup_cost": r(setup_cost),
        "finishing_cost": r(finishing_cost),
        "hardware_cost": r(hardware_cost),
        "install_cost": r(install_cost),
        "outsourcing_cost": r(outsourcing_cost),
        "overhead_cost": r(overhead_cost),
        "base_cost": r(base_cost),
        "true_cost": r(true_cost),
        "selling_price": r(selling_price),
        "profit_amount": r(profit_amount),
        "profit_margin_percent": _round2(profit_margin_percent),
        "pricing_method_used": method_used,
        "breakdown": breakdown,
        # Phase 9B — the exact shop-level Pricing Foundation values in effect
        # at calculation time, so a snapshot can "show the math" and remain
        # historically accurate even after the shop later edits its defaults.
        "shop_defaults_used": {
            "production_hourly_rate": shop.get("production_hourly_rate"),
            "design_hourly_rate": shop.get("design_hourly_rate"),
            "install_hourly_rate": shop.get("install_hourly_rate"),
            "default_overhead_percent": shop.get("default_overhead_percent"),
            "labor_burden_percent": shop.get("labor_burden_percent"),
            "target_profit_margin_percent": shop.get("target_profit_margin_percent"),
            "default_markup_multiplier": shop.get("default_markup_multiplier"),
            "minimum_order_amount": shop.get("minimum_order_amount"),
            "install_minimum_charge": shop.get("install_minimum_charge"),
            "setup_fee_default": shop.get("setup_fee_default"),
            "rush_fee_percent": shop.get("rush_fee_percent"),
        },
    }


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
