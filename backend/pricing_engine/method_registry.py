"""EC9 Phase 9I-A pricing category and method registry.

The registry is descriptive metadata only in Phase 9I-A. Live calculations
continue to use `services.pricing.calculate_pricing()` and the existing
category formula modules.
"""
from __future__ import annotations

from typing import Any, Mapping

from .pricing_contracts import (
    MAX_COMPARISON_METHODS,
    PricingCategoryDefinition,
    PricingContractError,
    PricingMethodDefinition,
    PricingPresetDefinition,
)
from .config import CATEGORY_IDS, CATEGORY_META
from .saved_items import BUSINESS_CARD_STARTER_ITEMS


METHOD_DEFINITIONS: dict[str, PricingMethodDefinition] = {
    "square_foot_plus_addons": PricingMethodDefinition(
        id="square_foot_plus_addons",
        display_name="Square-foot plus add-ons",
        explanation="Uses area-based sell rate plus applicable finishing, hardware, design, install, rush, and minimum-charge logic.",
        family="area_based",
        handler_identity="pricing_flat_sqft.banners.square_foot_plus_addons",
        required_configuration_capabilities=("area", "material", "add_ons", "minimum_charge"),
    ),
    "per_sqft": PricingMethodDefinition(
        id="per_sqft",
        display_name="Per-square-foot",
        explanation="Uses product area, material sell-rate or category sell-rate, quantity, and applicable minimums.",
        family="area_based",
        handler_identity="pricing_flat_sqft.generic.per_sqft",
        required_configuration_capabilities=("area", "material", "sell_rate_per_sqft"),
    ),
    "cost_plus": PricingMethodDefinition(
        id="cost_plus",
        display_name="Cost-plus",
        explanation="Uses true cost, labor, overhead, and configured markup or margin to produce a suggested price.",
        family="cost_based",
        handler_identity="shared.cost_plus",
        required_configuration_capabilities=("material_cost", "labor", "overhead", "markup"),
    ),
    "target_margin": PricingMethodDefinition(
        id="target_margin",
        display_name="Target margin",
        explanation="Uses true cost and the configured target margin to calculate the required selling price.",
        family="cost_based",
        handler_identity="pricing_flat_sqft.banners.target_margin",
        required_configuration_capabilities=("true_cost", "target_margin"),
    ),
    "materials_labor_overhead": PricingMethodDefinition(
        id="materials_labor_overhead",
        display_name="Materials, labor, and overhead",
        explanation="Builds a price from material, labor, overhead, and method-specific add-on costs.",
        family="cost_based",
        handler_identity="pricing_flat_sqft.banners.materials_labor_overhead",
        required_configuration_capabilities=("material_cost", "labor", "overhead"),
    ),
    "minimum_charge": PricingMethodDefinition(
        id="minimum_charge",
        display_name="Minimum charge",
        explanation="Applies the configured category or item minimum when formula pricing would fall below it.",
        family="floor",
        handler_identity="shared.minimum_charge",
        required_configuration_capabilities=("minimum_charge",),
    ),
    "vehicle_benchmark": PricingMethodDefinition(
        id="vehicle_benchmark",
        display_name="Vehicle benchmark",
        explanation="Uses an approved vehicle type and coverage benchmark price when one exists.",
        family="vehicle_graphics",
        handler_identity="pricing_vehicle_graphics.benchmark",
        required_configuration_capabilities=("vehicle_type", "coverage_type", "approved_benchmark"),
    ),
    "vehicle_cost_plus": PricingMethodDefinition(
        id="vehicle_cost_plus",
        display_name="Vehicle cost-plus",
        explanation="Uses wrap area, vehicle materials, design, production, install, travel, removal, helper labor, overhead, and markup.",
        family="vehicle_graphics",
        handler_identity="pricing_vehicle_graphics.cost_plus",
        required_configuration_capabilities=("vehicle_type", "coverage_type", "material", "labor", "markup"),
    ),
    "apparel_table": PricingMethodDefinition(
        id="apparel_table",
        display_name="Table-based apparel pricing",
        explanation="Uses the approved garment, brand, quantity, and placement sell-price table where an exact table applies.",
        family="apparel",
        handler_identity="pricing_apparel.apparel_table",
        required_configuration_capabilities=("garment", "brand", "placement", "quantity_tier"),
    ),
    "apparel_cost_plus": PricingMethodDefinition(
        id="apparel_cost_plus",
        display_name="Apparel cost-plus",
        explanation="Uses garment cost, decoration material/setup, production assumptions, add-ons, rush, and markup for methods without an exact table.",
        family="apparel",
        handler_identity="pricing_apparel.apparel_cost_plus",
        required_configuration_capabilities=("garment_cost", "decoration_method", "setup", "markup"),
    ),
    "service_rate": PricingMethodDefinition(
        id="service_rate",
        display_name="Preset / service-rate",
        explanation="Uses the selected service preset or service-rate method such as hourly, flat-fee, per-unit, crew-hour, or pass-through where supported.",
        family="services",
        handler_identity="pricing_services.service_rate",
        required_configuration_capabilities=("service_type", "service_rate"),
    ),
    "tier_pricing": PricingMethodDefinition(
        id="tier_pricing",
        display_name="Tier pricing",
        explanation="Uses an exact configured quantity tier, such as the Business Card starter presets; non-matching quantities are not guessed.",
        family="promotional",
        handler_identity="pricing_promotional.tier_pricing",
        required_configuration_capabilities=("quantity_tiers",),
    ),
    "per_piece": PricingMethodDefinition(
        id="per_piece",
        display_name="Per-piece",
        explanation="Uses known supplier cost, quantity, and configured markup/add-ons for promotional items.",
        family="promotional",
        handler_identity="pricing_promotional.per_piece",
        required_configuration_capabilities=("unit_cost", "quantity", "markup"),
    ),
    "flat_fee": PricingMethodDefinition(
        id="flat_fee",
        display_name="Flat fee",
        explanation="Uses a configured flat selling price or flat service amount where that method is explicitly selected.",
        family="flat",
        handler_identity="pricing_promotional.flat_fee",
        required_configuration_capabilities=("flat_fee",),
    ),
    "unit_price_x_quantity": PricingMethodDefinition(
        id="unit_price_x_quantity",
        display_name="Manual / unit price",
        explanation="Uses the user-entered unit price and quantity; no automatic formula is invented for Custom/Miscellaneous work.",
        family="manual",
        handler_identity="pricing_custom.unit_price_x_quantity",
        required_configuration_capabilities=("unit_price", "quantity"),
        comparison_eligible=False,
    ),
    "manual_override": PricingMethodDefinition(
        id="manual_override",
        display_name="Manual override",
        explanation="Uses the authoritative calculator result's explicit manual selling price without recalculating or inventing formula-derived amounts.",
        family="manual",
        handler_identity="shared.manual_override",
        required_configuration_capabilities=("manual_selling_price",),
        comparison_eligible=False,
    ),
}


CATEGORY_DEFINITIONS: dict[str, PricingCategoryDefinition] = {
    "banners": PricingCategoryDefinition(
        id="banners",
        display_name=CATEGORY_META["banners"]["name"],
        family="area_based",
        description=CATEGORY_META["banners"]["description"],
        units=("in", "ft", "sqft"),
        supported_method_ids=("square_foot_plus_addons", "cost_plus", "target_margin", "materials_labor_overhead", "minimum_charge"),
        recommended_simple_setup_method_ids=("square_foot_plus_addons", "cost_plus"),
        recommended_primary_method_id="square_foot_plus_addons",
        supports_comparison=True,
        max_comparison_methods=MAX_COMPARISON_METHODS,
        configuration_requirements=("material", "base_sell_rate_per_sqft", "minimum_charge", "waste_percent"),
        conditional_capability_flags=("hems", "grommets", "pole_pockets", "hardware", "design", "installation", "rush"),
        implementation_service="pricing_flat_sqft.calculate_banner_pricing",
    ),
    "rigid_signs": PricingCategoryDefinition(
        id="rigid_signs",
        display_name=CATEGORY_META["rigid_signs"]["name"],
        family="area_based",
        description=CATEGORY_META["rigid_signs"]["description"],
        units=("in", "ft", "sqft"),
        supported_method_ids=("per_sqft", "cost_plus"),
        recommended_simple_setup_method_ids=("per_sqft", "cost_plus"),
        recommended_primary_method_id="per_sqft",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("material", "base_sell_rate_per_sqft", "minimum_charge", "waste_percent"),
        conditional_capability_flags=("substrate", "graphic_method", "hardware", "drill_prep", "design", "installation"),
        implementation_service="pricing_flat_sqft.calculate_rigid_signs_pricing",
    ),
    "cut_vinyl": PricingCategoryDefinition(
        id="cut_vinyl",
        display_name=CATEGORY_META["cut_vinyl"]["name"],
        family="area_based",
        description=CATEGORY_META["cut_vinyl"]["description"],
        units=("in", "ft", "sqft"),
        supported_method_ids=("per_sqft", "cost_plus"),
        recommended_simple_setup_method_ids=("per_sqft", "cost_plus"),
        recommended_primary_method_id="per_sqft",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("material", "base_sell_rate_per_sqft", "minimum_charge", "waste_percent"),
        conditional_capability_flags=("color_count", "weeding_complexity", "masking", "surface_type", "design", "installation"),
        implementation_service="pricing_flat_sqft.calculate_cut_vinyl_pricing",
        recommended_starter_values={"item_minimum": 25.00},
    ),
    "digital_print": PricingCategoryDefinition(
        id="digital_print",
        display_name=CATEGORY_META["digital_print"]["name"],
        family="area_based",
        description=CATEGORY_META["digital_print"]["description"],
        units=("in", "ft", "sqft"),
        supported_method_ids=("per_sqft", "cost_plus"),
        recommended_simple_setup_method_ids=("per_sqft", "cost_plus"),
        recommended_primary_method_id="per_sqft",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("material", "base_sell_rate_per_sqft", "item_minimum", "order_minimum", "waste_percent"),
        conditional_capability_flags=("ink_coverage", "lamination", "mounting", "contour_cut", "piece_separation", "design", "installation"),
        implementation_service="pricing_flat_sqft.calculate_digital_print_pricing",
        recommended_starter_values={
            "item_minimum": 20.00,
            "order_minimum": 40.00,
            "phase_9i_a_live_enforcement": "deferred",
        },
        conditional_method_notes={"order_minimum": "Order-level minimum must be enforced at document-total level in a later phase, not inside one line-item formula."},
    ),
    "vehicle_graphics": PricingCategoryDefinition(
        id="vehicle_graphics",
        display_name=CATEGORY_META["vehicle_graphics"]["name"],
        family="vehicle_graphics",
        description=CATEGORY_META["vehicle_graphics"]["description"],
        units=("vehicle_type", "coverage_type", "sqft"),
        supported_method_ids=("vehicle_benchmark", "vehicle_cost_plus"),
        recommended_simple_setup_method_ids=("vehicle_benchmark", "vehicle_cost_plus"),
        recommended_primary_method_id="vehicle_benchmark",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("vehicle_type", "coverage_type", "material", "labor", "benchmark_prices"),
        conditional_capability_flags=("approved_benchmark", "window_perf", "laminate", "surface_prep", "removal", "travel", "rush"),
        implementation_service="pricing_vehicle_graphics.calculate_vehicle_graphics_pricing",
        conditional_method_notes={"vehicle_benchmark": "Available only when an approved benchmark exists for the selected vehicle and coverage."},
    ),
    "apparel": PricingCategoryDefinition(
        id="apparel",
        display_name=CATEGORY_META["apparel"]["name"],
        family="apparel",
        description=CATEGORY_META["apparel"]["description"],
        units=("garment", "quantity", "placement"),
        supported_method_ids=("apparel_table", "apparel_cost_plus"),
        recommended_simple_setup_method_ids=("apparel_table", "apparel_cost_plus"),
        recommended_primary_method_id="apparel_table",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("garment_table", "decoration_method", "blank_cost", "minimum_charge"),
        conditional_capability_flags=("table_based_decoration", "foundation_estimate_decoration", "plus_size", "name_number", "specialty_finish", "rush"),
        implementation_service="pricing_apparel.calculate_apparel_pricing",
    ),
    "services": PricingCategoryDefinition(
        id="services",
        display_name=CATEGORY_META["services"]["name"],
        family="services",
        description=CATEGORY_META["services"]["description"],
        units=("service_type", "hours", "unit"),
        supported_method_ids=("service_rate", "cost_plus"),
        recommended_simple_setup_method_ids=("service_rate", "cost_plus"),
        recommended_primary_method_id="service_rate",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("service_type", "labor_rate", "minimum_charge"),
        conditional_capability_flags=("travel", "equipment", "subcontract", "permit", "rush", "labor_role"),
        implementation_service="pricing_services.calculate_services_pricing",
    ),
    "promotional": PricingCategoryDefinition(
        id="promotional",
        display_name=CATEGORY_META["promotional"]["name"],
        family="promotional",
        description=CATEGORY_META["promotional"]["description"],
        units=("quantity", "unit"),
        supported_method_ids=("tier_pricing", "per_piece", "flat_fee"),
        recommended_simple_setup_method_ids=("tier_pricing", "flat_fee"),
        recommended_primary_method_id="tier_pricing",
        supports_comparison=True,
        max_comparison_methods=2,
        configuration_requirements=("saved_item_or_unit_cost", "quantity", "markup_or_flat_fee"),
        conditional_capability_flags=("exact_tier", "per_piece_supplier_cost", "flat_fee", "setup", "decoration", "shipping", "rush"),
        implementation_service="pricing_promotional.calculate_promotional_pricing",
        conditional_method_notes={"tier_pricing": "Available only when exact quantity tiers exist; non-matching quantities require manual price."},
    ),
    "custom": PricingCategoryDefinition(
        id="custom",
        display_name=CATEGORY_META["custom"]["name"],
        family="custom_manual",
        description=CATEGORY_META["custom"]["description"],
        units=("quantity", "unit"),
        supported_method_ids=("unit_price_x_quantity",),
        recommended_simple_setup_method_ids=("unit_price_x_quantity",),
        recommended_primary_method_id="unit_price_x_quantity",
        supports_comparison=False,
        max_comparison_methods=1,
        configuration_requirements=("unit_price", "quantity"),
        conditional_capability_flags=("manual_cost", "manual_notes"),
        implementation_service="pricing_custom.calculate_custom_pricing",
    ),
}


PRESET_DEFINITIONS: dict[str, PricingPresetDefinition] = {
    starter["name"]: PricingPresetDefinition(
        id=starter["name"],
        display_name=starter["name"],
        category_id=starter["category"],
        supported_method_ids=(starter["default_pricing_method"],),
        recommended_primary_method_id=starter["default_pricing_method"],
    )
    for starter in BUSINESS_CARD_STARTER_ITEMS
}


def list_method_definitions() -> list[PricingMethodDefinition]:
    return list(METHOD_DEFINITIONS.values())


def get_method_definition(method_id: str) -> PricingMethodDefinition:
    try:
        return METHOD_DEFINITIONS[method_id]
    except KeyError as exc:
        raise PricingContractError(f"Unknown pricing method: {method_id}") from exc


def list_category_definitions() -> list[PricingCategoryDefinition]:
    return [CATEGORY_DEFINITIONS[category_id] for category_id in CATEGORY_IDS]


def get_category_definition(category_id: str) -> PricingCategoryDefinition:
    try:
        return CATEGORY_DEFINITIONS[category_id]
    except KeyError as exc:
        raise PricingContractError(f"Unknown pricing category: {category_id}") from exc


def list_preset_definitions() -> list[PricingPresetDefinition]:
    return list(PRESET_DEFINITIONS.values())


def get_preset_definition(preset_id: str) -> PricingPresetDefinition:
    try:
        return PRESET_DEFINITIONS[preset_id]
    except KeyError as exc:
        raise PricingContractError(f"Unknown pricing preset: {preset_id}") from exc


def _vehicle_benchmark_available(category_defaults: Mapping[str, Any] | None, category_inputs: Mapping[str, Any] | None) -> bool:
    defaults = category_defaults or {}
    benchmarks = defaults.get("benchmark_prices") or {}
    if not benchmarks:
        return False
    vehicle_type = (category_inputs or {}).get("vehicle_type")
    coverage_type = (category_inputs or {}).get("coverage_type")
    if vehicle_type and coverage_type:
        return coverage_type in (benchmarks.get(vehicle_type) or {})
    if vehicle_type:
        return bool(benchmarks.get(vehicle_type))
    return any(bool(coverage_map) for coverage_map in benchmarks.values())


def _promotional_available_methods(
    saved_item: Mapping[str, Any] | None,
    category_inputs: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    inputs = category_inputs or {}
    out: list[str] = []
    if saved_item and (saved_item.get("quantity_tiers") or []):
        out.append("tier_pricing")
    if inputs.get("pricing_method") == "tier_pricing" and "tier_pricing" not in out:
        out.append("tier_pricing")
    if inputs.get("unit_cost") is not None or inputs.get("pricing_method") == "per_piece":
        out.append("per_piece")
    if inputs.get("flat_fee_price") is not None or inputs.get("pricing_method") == "flat_fee":
        out.append("flat_fee")
    return tuple(method_id for method_id in ("tier_pricing", "per_piece", "flat_fee") if method_id in out)


def available_method_ids_for_context(
    category_id: str,
    *,
    category_defaults: Mapping[str, Any] | None = None,
    category_inputs: Mapping[str, Any] | None = None,
    saved_item: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Return methods honestly available for this category/context.

    Conditional methods remain in category definitions as supported methods, but
    this helper prevents later phases from presenting unavailable comparisons.
    """
    category = get_category_definition(category_id)
    if category_id == "vehicle_graphics":
        methods = ["vehicle_cost_plus"]
        if _vehicle_benchmark_available(category_defaults, category_inputs):
            methods.insert(0, "vehicle_benchmark")
        return tuple(method_id for method_id in category.supported_method_ids if method_id in methods)
    if category_id == "promotional":
        available = _promotional_available_methods(saved_item, category_inputs)
        return tuple(method_id for method_id in category.supported_method_ids if method_id in available)
    return category.supported_method_ids


def validate_registry() -> None:
    category_ids = [category.id for category in CATEGORY_DEFINITIONS.values()]
    if category_ids != CATEGORY_IDS:
        raise PricingContractError("Category registry must match starter default CATEGORY_IDS order")
    if len(set(category_ids)) != len(category_ids):
        raise PricingContractError("Category IDs must be unique")
    method_ids = [method.id for method in METHOD_DEFINITIONS.values()]
    if len(set(method_ids)) != len(method_ids):
        raise PricingContractError("Method IDs must be unique")
    for category in CATEGORY_DEFINITIONS.values():
        if category.max_comparison_methods > MAX_COMPARISON_METHODS:
            raise PricingContractError(f"{category.id}: too many comparison methods")
        for method_id in category.supported_method_ids:
            if method_id not in METHOD_DEFINITIONS:
                raise PricingContractError(f"{category.id}: unknown supported method '{method_id}'")
        for method_id in category.recommended_simple_setup_method_ids:
            if method_id not in category.supported_method_ids:
                raise PricingContractError(f"{category.id}: unsupported recommended method '{method_id}'")
        if category.recommended_primary_method_id not in category.supported_method_ids:
            raise PricingContractError(f"{category.id}: unsupported primary method")
        if len(category.recommended_simple_setup_method_ids) > MAX_COMPARISON_METHODS:
            raise PricingContractError(f"{category.id}: recommends more than three methods")
    for preset in PRESET_DEFINITIONS.values():
        if preset.category_id in CATEGORY_DEFINITIONS and preset.id in CATEGORY_DEFINITIONS:
            raise PricingContractError("Preset cannot be registered as a category")
        for method_id in preset.supported_method_ids:
            if method_id not in METHOD_DEFINITIONS:
                raise PricingContractError(f"{preset.id}: unknown preset method '{method_id}'")


validate_registry()
