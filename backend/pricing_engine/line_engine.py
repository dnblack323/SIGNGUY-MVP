"""Pure line-level pricing calculator entry point.

EC9 Phase 9I-O extracts the deterministic line calculator behind the SaaS
compatibility layer. Callers must resolve tenant settings, material profiles,
pricing components, and saved items before entering this module.
"""
from __future__ import annotations

from typing import Any

from .categories.apparel import calculate_apparel_pricing
from .categories.custom import calculate_custom_pricing
from .categories.flat_sqft import FLAT_SQFT_CATEGORIES, calculate_flat_sqft_pricing
from .categories.promotional import calculate_promotional_pricing
from .categories.services import calculate_services_pricing
from .categories.vehicle_graphics import calculate_vehicle_graphics_pricing
from .config import CATEGORY_IDS
from .method_outputs import normalize_category_method_outputs


def calculate_line(
    *,
    settings: dict[str, Any],
    category: str,
    width_inches: float | None,
    height_inches: float | None,
    quantity: int,
    material_key: str | None = None,
    design_needed: bool = False,
    install_needed: bool = False,
    manual_selling_price: float | None = None,
    category_inputs: dict[str, Any] | None = None,
    material_profile: dict[str, Any] | None = None,
    pricing_components: list[dict[str, Any]] | None = None,
    saved_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate one line item using only plain, already-resolved inputs.

    The contract intentionally accepts no tenant IDs, users, permissions,
    database clients, request objects, entitlement data, or audit handles.
    """

    if category not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category}")

    shop = settings.get("shop_defaults") or {}
    cats = settings.get("category_defaults") or {}
    materials = settings.get("materials") or {}
    cat = cats.get(category) or {}
    inputs = category_inputs or {}
    components = pricing_components or []

    if category in FLAT_SQFT_CATEGORIES:
        return normalize_category_method_outputs(calculate_flat_sqft_pricing(
            category=category,
            shop=shop,
            cat=cat,
            materials_legacy=materials,
            material_profile=material_profile,
            pricing_components=components,
            width_inches=width_inches,
            height_inches=height_inches,
            quantity=quantity,
            material_key=material_key,
            design_needed=design_needed,
            install_needed=install_needed,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
        ))

    if category == "apparel":
        return normalize_category_method_outputs(calculate_apparel_pricing(
            shop=shop,
            cat=cat,
            pricing_components=components,
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
        ))

    if category == "promotional":
        return normalize_category_method_outputs(calculate_promotional_pricing(
            shop=shop,
            cat=cat,
            pricing_components=components,
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
            saved_item=saved_item,
        ))

    if category == "vehicle_graphics":
        return normalize_category_method_outputs(calculate_vehicle_graphics_pricing(
            shop=shop,
            cat=cat,
            pricing_components=components,
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
        ))

    if category == "services":
        return normalize_category_method_outputs(calculate_services_pricing(
            shop=shop,
            cat=cat,
            pricing_components=components,
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
            material_profile=material_profile,
        ))

    if category == "custom":
        return normalize_category_method_outputs(calculate_custom_pricing(
            cat=cat,
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
        ))

    raise ValueError(f"Unhandled category: {category}")
