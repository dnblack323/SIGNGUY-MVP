"""EC9 Phase 9I-C shared pricing comparison adapter.

This module describes existing Banner comparison output through a stable
contract. It does not introduce formulas or persist comparison results.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from fastapi import status

from ..core.db import db
from .order_pricing import resolve_references
from .pricing import calculate_pricing
from .pricing_contracts import MAX_COMPARISON_METHODS, PRICING_CONTRACT_VERSION
from .pricing_method_configurations import (
    CONFIG_PATH,
    LEGACY_METHOD_ALIASES,
)
from .pricing_method_registry import get_category_definition, get_method_definition
from .starter_defaults import build_starter_pack


COMPARISON_CONTRACT_VERSION = f"{PRICING_CONTRACT_VERSION}.9i-c.1"
SUPPORTED_COMPARISON_CATEGORIES = {"banners"}


class PricingMethodComparisonError(ValueError):
    def __init__(self, field: str, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


def _normalize_method_id(method_id: Any, field: str) -> str:
    raw = str(method_id or "").strip()
    if not raw:
        raise PricingMethodComparisonError(field, "required", "Method ID is required.")
    if raw == "common_job_prices":
        raise PricingMethodComparisonError(
            field,
            "ambiguous_legacy_method",
            "Legacy method 'common_job_prices' is reference data and cannot be mapped to a pricing method.",
        )
    mapped = LEGACY_METHOD_ALIASES.get(raw, raw)
    try:
        get_method_definition(mapped)
    except Exception as exc:
        raise PricingMethodComparisonError(field, "unknown_method", f"Unknown pricing method: {mapped}") from exc
    return mapped


def _normalize_method_ids(values: list[str] | None, field: str) -> list[str]:
    methods = [_normalize_method_id(value, field) for value in values or []]
    if len(set(methods)) != len(methods):
        raise PricingMethodComparisonError(field, "duplicate_method", "Comparison methods cannot contain duplicates.")
    if len(methods) > MAX_COMPARISON_METHODS:
        raise PricingMethodComparisonError(
            field,
            "too_many_methods",
            "No more than three methods can be compared.",
        )
    return methods


def _method_availability_row(method_id: str) -> dict[str, Any]:
    return {
        "method_id": method_id,
        "method": get_method_definition(method_id).to_dict(),
        "supported": True,
        "available": True,
        "reason": None,
        "explanation": None,
    }


def _banner_availability(tenant_id: str, category_id: str) -> dict[str, Any]:
    category = get_category_definition(category_id)
    return {
        "tenant_id": tenant_id,
        "category_id": category_id,
        "supported_method_ids": list(category.supported_method_ids),
        "available_method_ids": list(category.supported_method_ids),
        "methods": [_method_availability_row(method_id) for method_id in category.supported_method_ids],
        "recommendation_version": COMPARISON_CONTRACT_VERSION,
    }


def _with_in_memory_starter_defaults(settings: Mapping[str, Any] | None, tenant_id: str) -> dict[str, Any]:
    starter = build_starter_pack()
    if not settings:
        starter["tenant_id"] = tenant_id
        return starter

    working = deepcopy(dict(settings))
    working["tenant_id"] = tenant_id
    starter_categories = starter.get("category_defaults") or {}
    stored_categories = deepcopy(working.get("category_defaults") or {})
    for category_id, starter_category in starter_categories.items():
        current = dict(stored_categories.get(category_id) or {})
        for key, value in starter_category.items():
            current.setdefault(key, value)
        stored_categories[category_id] = current
    working["category_defaults"] = stored_categories
    working.setdefault("shop_defaults", starter.get("shop_defaults") or {})
    working.setdefault("materials", starter.get("materials") or {})
    return working


async def _read_comparison_settings(tenant_id: str) -> tuple[dict[str, Any], Mapping[str, Any] | None, str]:
    stored = await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if stored:
        return _with_in_memory_starter_defaults(stored, tenant_id), stored, "persisted_settings"
    return _with_in_memory_starter_defaults(None, tenant_id), None, "starter_defaults_fallback"


def _saved_config_from_settings(settings: Mapping[str, Any] | None, category_id: str) -> dict[str, Any] | None:
    config = ((settings or {}).get(CONFIG_PATH) or {}).get(category_id)
    return deepcopy(dict(config)) if isinstance(config, Mapping) else None


async def _validated_methods(
    tenant_id: str,
    category_id: str,
    methods: list[str],
    primary_method_id: str,
    *,
    category_inputs: Mapping[str, Any],
    saved_item: Mapping[str, Any] | None,
) -> tuple[list[str], str, dict[str, Any]]:
    category = get_category_definition(category_id)
    unsupported = [method_id for method_id in methods if method_id not in category.supported_method_ids]
    if unsupported:
        raise PricingMethodComparisonError(
            "method_ids",
            "unsupported_method",
            f"Unsupported method(s) for {category_id}: {', '.join(unsupported)}",
        )
    if primary_method_id not in methods:
        raise PricingMethodComparisonError(
            "primary_method_id",
            "primary_method_not_enabled",
            "primary_method_id must be one of the compared methods.",
        )
    availability = _banner_availability(tenant_id, category_id)
    unavailable = [method_id for method_id in methods if method_id not in set(availability["available_method_ids"])]
    if unavailable:
        details = {item["method_id"]: item for item in availability["methods"]}
        first = unavailable[0]
        item = details.get(first) or {}
        raise PricingMethodComparisonError(
            "method_ids",
            item.get("reason") or "method_unavailable",
            item.get("explanation") or "The method is not currently available for this tenant/category.",
        )
    return methods, primary_method_id, availability


def _normalize_row(row: Mapping[str, Any], *, selected_method_id: str | None) -> dict[str, Any]:
    method_id = str(row.get("method") or row.get("method_id") or "")
    method = get_method_definition(method_id)
    statuses = list(row.get("status") or [])
    amount = row.get("amount")
    return {
        "method_id": method_id,
        "display_name": row.get("label") or method.display_name,
        "amount": amount,
        "pre_adjustment_amount": row.get("pre_adjustment_amount"),
        "status": statuses,
        "selected": method_id == selected_method_id,
        "enabled": bool(row.get("enabled", True)),
        "available": "failed" not in statuses and amount is not None,
        "handler_identity": method.handler_identity,
        "formula_source": "existing_banner_pricing",
    }


def _ordered_rows(calculation: Mapping[str, Any], methods: list[str] | None, selected_method_id: str | None) -> list[dict[str, Any]]:
    raw_rows = [dict(row) for row in calculation.get("pricing_method_results") or []]
    by_method = {str(row.get("method") or row.get("method_id")): row for row in raw_rows}
    order = methods or [str(row.get("method") or row.get("method_id")) for row in raw_rows]
    return [_normalize_row(by_method[method_id], selected_method_id=selected_method_id) for method_id in order if method_id in by_method]


async def compare_pricing_methods(
    *,
    tenant_id: str,
    category_id: str,
    width_inches: float | None,
    height_inches: float | None,
    quantity: int,
    material_key: str | None = None,
    design_needed: bool = False,
    install_needed: bool = False,
    manual_selling_price: float | None = None,
    category_inputs: Mapping[str, Any] | None = None,
    material_profile_id: str | None = None,
    pricing_component_ids: list[str] | None = None,
    saved_item_id: str | None = None,
    use_saved_configuration: bool = True,
    method_ids: list[str] | None = None,
    primary_method_id: str | None = None,
    expected_configuration_version: int | None = None,
) -> dict[str, Any]:
    if category_id not in SUPPORTED_COMPARISON_CATEGORIES:
        raise PricingMethodComparisonError(
            "category_id",
            "comparison_not_available",
            "Shared comparison is currently available only for Banners in Phase 9I-C.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    inputs = dict(category_inputs or {})
    try:
        material_profile, pricing_components, saved_item = await resolve_references(
            tenant_id=tenant_id,
            material_profile_id=material_profile_id,
            pricing_component_ids=pricing_component_ids or [],
            saved_item_id=saved_item_id,
        )
    except ValueError as exc:
        if str(exc) == "material_profile_not_found":
            raise PricingMethodComparisonError(
                "material_profile_id",
                "material_profile_not_found",
                "Material pricing profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            ) from exc
        if str(exc) == "saved_item_not_found":
            raise PricingMethodComparisonError(
                "saved_item_id",
                "saved_item_not_found",
                "Saved item not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            ) from exc
        raise
    settings, stored_settings, settings_source = await _read_comparison_settings(tenant_id)
    saved_config = _saved_config_from_settings(stored_settings, category_id) if use_saved_configuration else None

    comparison_methods: list[str] | None = None
    selected_primary = primary_method_id
    configuration_source = "existing_calculator_defaults" if stored_settings else "starter_defaults_fallback"
    configuration_version = None
    availability = _banner_availability(tenant_id, category_id)

    if method_ids:
        comparison_methods = _normalize_method_ids(method_ids, "method_ids")
        selected_primary = _normalize_method_id(primary_method_id or comparison_methods[0], "primary_method_id")
        configuration_source = "explicit_request"
    elif saved_config:
        if expected_configuration_version is not None and int(saved_config.get("configuration_version") or 0) != expected_configuration_version:
            raise PricingMethodComparisonError(
                "expected_configuration_version",
                "stale_configuration",
                "Pricing method configuration has changed; reload before comparing.",
                status_code=status.HTTP_409_CONFLICT,
            )
        comparison_methods = list(saved_config.get("comparison_order") or saved_config.get("enabled_method_ids") or [])
        selected_primary = str(saved_config.get("primary_method_id") or (comparison_methods[0] if comparison_methods else ""))
        configuration_source = "saved_tenant_configuration"
        configuration_version = saved_config.get("configuration_version")
    elif expected_configuration_version is not None:
        raise PricingMethodComparisonError(
            "expected_configuration_version",
            "stale_configuration",
            "No saved pricing method configuration exists for this category.",
            status_code=status.HTTP_409_CONFLICT,
        )

    if comparison_methods:
        comparison_methods, selected_primary, availability = await _validated_methods(
            tenant_id,
            category_id,
            comparison_methods,
            selected_primary or comparison_methods[0],
            category_inputs=inputs,
            saved_item=saved_item,
        )

    try:
        canonical_calculation = calculate_pricing(
            settings=settings,
            category=category_id,
            width_inches=width_inches,
            height_inches=height_inches,
            quantity=quantity,
            material_key=material_key,
            design_needed=design_needed,
            install_needed=install_needed,
            manual_selling_price=manual_selling_price,
            category_inputs=inputs,
            material_profile=material_profile,
            pricing_components=pricing_components,
            saved_item=saved_item,
        )
    except ValueError as exc:
        raise PricingMethodComparisonError("calculation", "invalid_calculation_input", str(exc)) from exc

    canonical_method_id = canonical_calculation.get("pricing_method_used") or canonical_calculation.get("selected_pricing_method")
    selected_method_id = selected_primary if comparison_methods else canonical_method_id
    normalized_rows = _ordered_rows(canonical_calculation, comparison_methods, selected_method_id)
    if not comparison_methods:
        comparison_methods = [row["method_id"] for row in normalized_rows]
        selected_primary = str(canonical_method_id or comparison_methods[0])
        selected_method_id = selected_primary

    return {
        "contract_version": COMPARISON_CONTRACT_VERSION,
        "tenant_id": tenant_id,
        "category_id": category_id,
        "settings_source": settings_source,
        "configuration_source": configuration_source,
        "configuration_version": configuration_version,
        "comparison_order": comparison_methods,
        "primary_method_id": selected_primary,
        "selected_method_id": selected_method_id,
        "canonical_method_id": canonical_method_id,
        "mutated": False,
        "persistent_entities_created": [],
        "availability": availability,
        "comparison_results": normalized_rows,
        "pricing_result": canonical_calculation,
    }
