"""EC9 Phase 9I-D shared method-output normalization.

The normalizer is an adapter over existing calculator results. It does not
calculate prices, mutate tenant settings, or replace category-specific output.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .pricing_contracts import PRICING_CONTRACT_VERSION
from .pricing_method_registry import (
    METHOD_DEFINITIONS,
    get_category_definition,
    get_method_definition,
)


METHOD_OUTPUT_CONTRACT_VERSION = f"{PRICING_CONTRACT_VERSION}.9i-d.1"
MANUAL_OVERRIDE_METHOD_ID = "manual_override"


SERVICE_RATE_METHODS = {
    "hourly",
    "per_crew_hour",
    "per_unit",
    "flat_fee",
    "custom_flat_fee",
    "pass_through",
    "hybrid",
    "manual",
}

METHOD_ALIASES_BY_CATEGORY = {
    "services": {method: "service_rate" for method in SERVICE_RATE_METHODS},
    "custom": {MANUAL_OVERRIDE_METHOD_ID: "unit_price_x_quantity"},
}

CATEGORY_DETAIL_KEYS = {
    "rigid_signs": (
        "width_inches",
        "height_inches",
        "area_sqft_each",
        "area_sqft_total",
        "material_key",
        "material_sell_rate_per_sqft",
        "material_cost",
        "labor_cost",
        "finishing_cost",
        "hardware_cost",
        "install_cost",
        "overhead_cost",
        "minimum_charge_applied",
    ),
    "cut_vinyl": (
        "width_inches",
        "height_inches",
        "area_sqft_each",
        "area_sqft_total",
        "material_key",
        "material_cost",
        "labor_cost",
        "finishing_cost",
        "install_cost",
        "overhead_cost",
        "minimum_charge_applied",
    ),
    "digital_print": (
        "width_inches",
        "height_inches",
        "area_sqft_each",
        "area_sqft_total",
        "material_key",
        "material_cost",
        "labor_cost",
        "finishing_cost",
        "install_cost",
        "overhead_cost",
        "minimum_charge_applied",
    ),
    "vehicle_graphics": (
        "area_sqft_each",
        "area_sqft_total",
        "material_key",
        "benchmark_price_used",
        "cost_plus_price",
        "vehicle_type_is_provisional",
        "install_hours_is_provisional",
        "estimated_sqft_was_overridden",
        "removal_cost",
        "helper_cost",
        "travel_cost",
    ),
    "apparel": (
        "garment_type",
        "brand",
        "is_hat",
        "plus_size_count",
        "decoration_method",
        "decoration_table_based",
        "decoration_pricing_source",
        "decoration_table_revenue",
        "decoration_material_cost",
        "decoration_area_assumption_sqin",
        "decoration_area_assumption_is_provisional",
        "personalization_cost",
    ),
    "promotional": (
        "saved_item_id",
        "saved_item_name",
        "tier_match",
        "tier_price",
        "requires_manual_price",
        "personalization_cost",
        "shipping_cost",
    ),
    "services": (
        "cost_plus_price",
        "minimum_charge_applied",
        "travel_cost",
        "travel_price_addon",
        "trip_charge_total",
        "vendor_cost",
        "outsourced_price_addon",
        "permit_cost",
        "service_rate_is_provisional",
        "labor_role_used",
    ),
    "custom": (
        "unit_price",
        "unit_cost_manual",
        "minimum_charge_applied",
        "markup_percent_adjustment",
        "markup_adjusted_unit_price_informational",
        "markup_adjusted_subtotal_informational",
        "item_name",
        "description",
        "notes",
    ),
}


def normalize_pricing_method_id(category_id: str, method_id: Any) -> str | None:
    raw = str(method_id or "").strip()
    if not raw:
        return None
    category_aliases = METHOD_ALIASES_BY_CATEGORY.get(category_id, {})
    if raw in category_aliases:
        return category_aliases[raw]
    if raw in METHOD_DEFINITIONS:
        return raw
    if category_id == "services" and raw in SERVICE_RATE_METHODS:
        return "service_rate"
    return raw


def _warning_list(result: Mapping[str, Any]) -> list[str]:
    warnings = result.get("calculation_warnings")
    if warnings is None:
        warnings = result.get("warnings")
    return [str(item) for item in (warnings or [])]


def _amount_for_method(result: Mapping[str, Any], method_id: str, selected_method_id: str | None) -> Any:
    if method_id == selected_method_id:
        return result.get("selling_price")
    if method_id == "vehicle_benchmark":
        return result.get("benchmark_price_used")
    if method_id in {"vehicle_cost_plus", "cost_plus"}:
        return result.get("cost_plus_price")
    if method_id == "tier_pricing" and result.get("tier_match"):
        return result.get("tier_price")
    return None


def _status_for_method(
    result: Mapping[str, Any],
    method_id: str,
    *,
    selected_method_id: str | None,
    amount: Any,
) -> list[str]:
    if method_id == selected_method_id:
        if amount is None:
            statuses = ["selected", "unavailable"]
        else:
            statuses = ["selected", "authoritative_total"]
    elif amount is None:
        statuses = ["unavailable", "not_calculated_by_existing_result"]
    else:
        statuses = ["available", "candidate_from_existing_result"]

    if result.get("requires_manual_price") and method_id == (selected_method_id or "tier_pricing"):
        for status in ("manual_price_required", "no_exact_tier_match"):
            if status not in statuses:
                statuses.append(status)
    return statuses


def _errors_for_method(result: Mapping[str, Any], method_id: str, selected_method_id: str | None) -> list[str]:
    if result.get("requires_manual_price") and method_id == (selected_method_id or "tier_pricing"):
        return ["manual_price_required", "no_exact_tier_match"]
    return []


def _method_rows(result: Mapping[str, Any], category_id: str) -> list[dict[str, Any]]:
    category = get_category_definition(category_id)
    selected_method_id = normalize_pricing_method_id(category_id, result.get("pricing_method_used"))
    method_ids = list(category.supported_method_ids)
    if selected_method_id and selected_method_id not in category.supported_method_ids:
        if selected_method_id == MANUAL_OVERRIDE_METHOD_ID:
            method_ids.append(MANUAL_OVERRIDE_METHOD_ID)
        else:
            selected_method_id = normalize_pricing_method_id(
                category_id,
                (result.get("category_inputs_used") or {}).get("pricing_method"),
            )

    rows: list[dict[str, Any]] = []
    for method_id in method_ids:
        method = get_method_definition(method_id)
        amount = _amount_for_method(result, method_id, selected_method_id)
        statuses = _status_for_method(result, method_id, selected_method_id=selected_method_id, amount=amount)
        rows.append(
            {
                "method": method_id,
                "method_id": method_id,
                "label": method.display_name,
                "display_name": method.display_name,
                "amount": amount,
                "pre_adjustment_amount": amount,
                "status": statuses,
                "warnings": _warning_list(result),
                "errors": _errors_for_method(result, method_id, selected_method_id),
                "enabled": True,
                "available": amount is not None and "unavailable" not in statuses,
                "selected": method_id == selected_method_id,
                "handler_identity": method.handler_identity,
                "formula_source": "existing_calculator_output",
            }
        )
    return rows


def _method_availability(result: Mapping[str, Any], category_id: str, rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    category = get_category_definition(category_id)
    by_method = {row["method_id"]: row for row in rows}
    availability = []
    for method_id, method in METHOD_DEFINITIONS.items():
        supported = method_id in category.supported_method_ids or method_id in by_method
        row = by_method.get(method_id)
        available = bool(row and row.get("available"))
        reason = None
        if not supported:
            reason = "unsupported_for_category"
        elif not available:
            reason = "not_calculated_by_existing_result"
            if result.get("requires_manual_price") and method_id == "tier_pricing":
                reason = "manual_price_required"
        availability.append(
            {
                "method_id": method_id,
                "display_name": method.display_name,
                "supported": supported,
                "available": available,
                "reason": reason,
            }
        )
    return availability


def _breakdown_section(result: Mapping[str, Any]) -> dict[str, Any] | None:
    breakdown = result.get("breakdown") or []
    if not breakdown:
        return None
    return {
        "section": "existing_breakdown",
        "lines": [dict(row) for row in breakdown],
    }


def _category_detail_section(result: Mapping[str, Any], category_id: str) -> dict[str, Any]:
    source_labels = result.get("source_labels") or {}
    lines = []
    for key in CATEGORY_DETAIL_KEYS.get(category_id, ()):
        if key in result:
            lines.append(
                {
                    "key": key,
                    "label": key.replace("_", " ").title(),
                    "value": deepcopy(result.get(key)),
                    "source": source_labels.get(key),
                }
            )
    return {"section": "category_specific_details", "lines": lines}


def _warning_section(result: Mapping[str, Any]) -> dict[str, Any] | None:
    warnings = _warning_list(result)
    if not warnings:
        return None
    return {
        "section": "warnings",
        "lines": [{"message": warning} for warning in warnings],
    }


def _detail_sections(result: Mapping[str, Any], category_id: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = [
        {
            "section": "authoritative_result",
            "lines": [
                {"key": "pricing_method_used", "value": result.get("pricing_method_used")},
                {"key": "selling_price", "amount": result.get("selling_price")},
                {"key": "suggested_price", "amount": result.get("suggested_price")},
                {"key": "true_cost", "amount": result.get("true_cost")},
                {"key": "profit_amount", "amount": result.get("profit_amount")},
                {"key": "profit_margin_percent", "value": result.get("profit_margin_percent")},
            ],
        },
        _category_detail_section(result, category_id),
    ]
    breakdown = _breakdown_section(result)
    if breakdown:
        sections.append(breakdown)
    warnings = _warning_section(result)
    if warnings:
        sections.append(warnings)
    return sections


def normalize_category_method_outputs(result: Mapping[str, Any]) -> dict[str, Any]:
    output = deepcopy(dict(result))
    category_id = str(output.get("category") or "")
    if category_id == "banners":
        return output
    if not category_id:
        return output

    rows = _method_rows(output, category_id)
    output["pricing_output_contract_version"] = METHOD_OUTPUT_CONTRACT_VERSION
    output["pricing_method_results"] = rows
    output["method_availability"] = _method_availability(output, category_id, rows)
    output["detail_sections"] = _detail_sections(output, category_id)
    output["canonical_method_id"] = normalize_pricing_method_id(category_id, output.get("pricing_method_used"))
    output["method_output_source"] = "existing_calculator_output"
    output["mutated"] = False
    output["persistent_entities_created"] = []
    return output
