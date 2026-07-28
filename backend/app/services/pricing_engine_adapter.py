"""SaaS compatibility boundary for EC9 Phase 9I-L pricing-engine DTOs."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from pricing_engine.adapters import build_legacy_line_result

from .pricing import calculate_pricing


PRICING_ENGINE_RESULT_FIELD = "pricing_engine_result"


def attach_cents_first_compatibility_envelope(
    *,
    legacy_result: dict[str, Any],
    normalized_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return legacy result fields unchanged plus one normalized DTO envelope."""

    output = deepcopy(legacy_result)
    output[PRICING_ENGINE_RESULT_FIELD] = build_legacy_line_result(
        category_id=str(legacy_result.get("category") or ""),
        legacy_result=legacy_result,
        normalized_input=normalized_input or {},
    )
    return output


def calculate_pricing_with_cents_first_envelope(
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
    legacy_result = calculate_pricing(
        settings=settings,
        category=category,
        width_inches=width_inches,
        height_inches=height_inches,
        quantity=quantity,
        material_key=material_key,
        design_needed=design_needed,
        install_needed=install_needed,
        manual_selling_price=manual_selling_price,
        category_inputs=category_inputs or {},
        material_profile=material_profile,
        pricing_components=pricing_components,
        saved_item=saved_item,
    )
    return attach_cents_first_compatibility_envelope(
        legacy_result=legacy_result,
        normalized_input={
            "category": category,
            "width_inches": width_inches,
            "height_inches": height_inches,
            "quantity": quantity,
            "material_key": material_key,
            "design_needed": design_needed,
            "install_needed": install_needed,
            "manual_selling_price": manual_selling_price,
            "category_inputs": deepcopy(category_inputs or {}),
            "material_profile_id": (material_profile or {}).get("id"),
            "pricing_component_ids": [component.get("id") for component in pricing_components or []],
            "saved_item_id": (saved_item or {}).get("id"),
        },
    )
