"""EC9 Phase 9F — canonical pricing resolution shared by:
    - `POST /pricing/calculate` (the independent Pricing Calculator)
    - Quote Line Item create/update/recalculate
    - Order Item create/update/recalculate

No pricing math is duplicated here. This module only resolves references
(EC7 canonical Material, Pricing Components, Saved Item) and delegates the
actual calculation to `services.pricing.calculate_pricing` — the single
backend-authoritative pricing engine. Quote/Order routers call INTO this
module; they never compute cost/price themselves.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.money import dollars_to_cents
from ..core.time_utils import utc_now
from .pricing import calculate_pricing
from .pricing_components import list_components
from .pricing_materials import get_profile
from .pricing_saved_items import get_saved_item
from .pricing_snapshot import build_calculated_snapshot, build_manual_snapshot


async def resolve_references(
    *, tenant_id: str, material_profile_id: Optional[str] = None,
    pricing_component_ids: Optional[list[str]] = None, saved_item_id: Optional[str] = None,
) -> tuple[Optional[dict], list[dict], Optional[dict]]:
    """Resolve EC7 material profile / Pricing Components / Saved Item by id.

    Returns (material_profile, pricing_components, saved_item). Raises
    ValueError("material_profile_not_found" | "saved_item_not_found") for a
    supplied id that doesn't resolve — the caller maps this to HTTP 404.
    """
    material_profile = None
    if material_profile_id:
        material_profile = await get_profile(tenant_id, material_profile_id)
        if not material_profile:
            raise ValueError("material_profile_not_found")
        material_doc = await db.materials.find_one(
            {"id": material_profile["material_id"], "tenant_id": tenant_id}, {"_id": 0, "name": 1}
        )
        material_profile = {**material_profile, "material_name": (material_doc or {}).get("name")}

    pricing_components: list[dict] = []
    if pricing_component_ids:
        all_components = await list_components(tenant_id, active=True)
        by_id = {c["id"]: c for c in all_components}
        pricing_components = [by_id[cid] for cid in pricing_component_ids if cid in by_id]

    saved_item = None
    if saved_item_id:
        saved_item = await get_saved_item(tenant_id, saved_item_id)
        if not saved_item:
            raise ValueError("saved_item_not_found")

    return material_profile, pricing_components, saved_item


async def calculate_for_references(
    *, settings: dict, category: str, quantity: int, category_inputs: dict[str, Any],
    material_profile_id: Optional[str] = None, pricing_component_ids: Optional[list[str]] = None,
    saved_item_id: Optional[str] = None, width_inches: Optional[float] = None,
    height_inches: Optional[float] = None, manual_selling_price: Optional[float] = None,
) -> dict[str, Any]:
    """Resolve references then call the canonical `calculate_pricing`. Used by
    both `/pricing/calculate` and the Quote/Order item helpers below so the
    resolution logic is never duplicated."""
    tenant_id = settings["tenant_id"]
    material_profile, pricing_components, saved_item = await resolve_references(
        tenant_id=tenant_id, material_profile_id=material_profile_id,
        pricing_component_ids=pricing_component_ids, saved_item_id=saved_item_id,
    )
    return calculate_pricing(
        settings=settings, category=category, width_inches=width_inches, height_inches=height_inches,
        quantity=quantity, category_inputs=category_inputs, material_profile=material_profile,
        pricing_components=pricing_components, saved_item=saved_item, manual_selling_price=manual_selling_price,
    )


def build_item_pricing_fields(
    *, calc_result: Optional[dict[str, Any]], quantity: int, category: Optional[str],
    category_inputs: dict[str, Any], material_profile_id: Optional[str], pricing_component_ids: list[str],
    saved_item_id: Optional[str], manual_price_cents: Optional[int], selected_price_source: Optional[str],
    fallback_unit_price_cents: int, user_id: str, actor_email: str, foundation_effective_at: Optional[str],
    manual_override_reason: Optional[str], recalculated: bool = False,
) -> dict[str, Any]:
    """Build the additive pricing fields to merge onto a QuoteLineItem /
    OrderItem document. Pure function — no I/O, no persistence.

    Backward compatible: when `calc_result` is None (no category, or the
    calculator was never invoked for this item), behaves exactly like the
    pre-Phase-9F manual-only path — `unit_price_cents` is taken as-is and the
    snapshot is `build_manual_snapshot(..., source="user_entered")`.
    """
    suggested_price_cents: Optional[int] = None
    if calc_result is not None and calc_result.get("selling_price") is not None:
        suggested_price_cents = dollars_to_cents(str(calc_result["selling_price"]))

    if calc_result is None:
        source = "manual"
        unit_price_cents = int(manual_price_cents if manual_price_cents is not None else fallback_unit_price_cents)
        pricing_status = "manual"
        snapshot = build_manual_snapshot(
            unit_price_cents=unit_price_cents, quantity=quantity, reason=manual_override_reason,
            actor_user_id=user_id, actor_email=actor_email, source="user_entered",
        )
        estimated_cost_cents = None
        estimated_profit_cents = None
        estimated_margin_percent = None
        calculation_warnings: list[str] = []
        source_labels: dict[str, Any] = {}
    else:
        pricing_status = "calculated"
        # "suggested" is backend-authoritative — the client cannot spoof it.
        # "manual" always wins when explicitly selected, per Manual Price rules.
        if selected_price_source == "manual":
            source = "manual"
            unit_price_cents = int(manual_price_cents if manual_price_cents is not None else fallback_unit_price_cents)
        else:
            source = "suggested"
            unit_price_cents = int(suggested_price_cents)
        snapshot = build_calculated_snapshot(
            calc_result=calc_result, quantity=quantity,
            override_unit_price_cents=(unit_price_cents if source == "manual" else None),
            override_reason=manual_override_reason if source == "manual" else None,
            actor_user_id=user_id if source == "manual" else None,
            actor_email=actor_email if source == "manual" else None,
            foundation_effective_at=foundation_effective_at,
            saved_item_id=saved_item_id, material_profile_id=material_profile_id,
            pricing_component_ids=pricing_component_ids,
        )
        true_cost_cents_per_unit = dollars_to_cents(str(calc_result.get("true_cost") or 0))
        estimated_cost_cents = true_cost_cents_per_unit * max(1, int(quantity))
        line_revenue_cents = unit_price_cents * max(1, int(quantity))
        estimated_profit_cents = line_revenue_cents - estimated_cost_cents
        estimated_margin_percent = (
            round((estimated_profit_cents / line_revenue_cents) * 100, 2) if line_revenue_cents > 0 else 0.0
        )
        calculation_warnings = list(calc_result.get("calculation_warnings") or [])
        source_labels = dict(calc_result.get("source_labels") or {})

    now_iso = utc_now().isoformat()
    return {
        "category": category,
        "category_inputs": category_inputs or {},
        "material_profile_id": material_profile_id,
        "pricing_component_ids": pricing_component_ids or [],
        "saved_item_id": saved_item_id,
        "suggested_price_cents": suggested_price_cents,
        "manual_price_cents": manual_price_cents,
        "selected_price_source": source,
        "unit_price_cents": unit_price_cents,
        "pricing_status": pricing_status,
        "estimated_cost_cents": estimated_cost_cents,
        "estimated_profit_cents": estimated_profit_cents,
        "estimated_margin_percent": estimated_margin_percent,
        "calculation_warnings": calculation_warnings,
        "source_labels": source_labels,
        "pricing_snapshot": snapshot,
        "price_selected_by_user_id": user_id,
        "last_recalculated_at": now_iso if recalculated else None,
    }
