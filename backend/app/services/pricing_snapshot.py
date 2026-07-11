"""EC3 — Pricing snapshots.

A pricing snapshot preserves the calculation basis for a Quote/Order line
item at the moment it was committed. It captures enough context to explain the
result later — even after shop pricing defaults change. Historical records
must never be silently re-priced.

Snapshots are stored on the line item document under `pricing_snapshot`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from ..core.money import dollars_to_cents
from ..core.time_utils import utc_now
from .starter_defaults import STARTER_DEFAULT_VERSION


def build_manual_snapshot(
    *,
    unit_price_cents: int,
    quantity: int,
    reason: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Build a snapshot for a manually-entered price (no calculator used)."""
    return {
        "source": source,
        "pricing_method": "manual",
        "calculator_version": None,
        "unit_price_cents": int(unit_price_cents),
        "quantity": int(quantity),
        "calculated_unit_price_cents": None,
        "override_unit_price_cents": None,
        "override_reason": reason,
        "override_actor_user_id": actor_user_id,
        "override_actor_email": actor_email,
        "captured_at": utc_now().isoformat(),
    }


def build_calculated_snapshot(
    *,
    calc_result: dict[str, Any],
    quantity: int,
    override_unit_price_cents: Optional[int] = None,
    override_reason: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
) -> dict[str, Any]:
    """Build a snapshot for a price derived from the pricing calculator.

    `calc_result` is the dict returned by `services/pricing.calculate_pricing`.
    """
    calc_unit_dollars = calc_result.get("selling_price")
    calc_unit_cents = (
        dollars_to_cents(Decimal(str(calc_unit_dollars)))
        if calc_unit_dollars is not None
        else None
    )
    return {
        "source": "calculator",
        "pricing_method": calc_result.get("pricing_method_used"),
        "calculator_version": STARTER_DEFAULT_VERSION,
        "category": calc_result.get("category"),
        "quantity": int(quantity),
        "width_inches": calc_result.get("width_inches"),
        "height_inches": calc_result.get("height_inches"),
        "area_sqft_total": calc_result.get("area_sqft_total"),
        "material_key": calc_result.get("material_key"),
        "material_cost_dollars": calc_result.get("material_cost"),
        "labor_cost_dollars": calc_result.get("labor_cost"),
        "design_cost_dollars": calc_result.get("design_cost"),
        "install_cost_dollars": calc_result.get("install_cost"),
        "overhead_cost_dollars": calc_result.get("overhead_cost"),
        "true_cost_dollars": calc_result.get("true_cost"),
        "calculated_unit_price_cents": calc_unit_cents,
        "calculated_unit_price_dollars": calc_unit_dollars,
        "override_unit_price_cents": override_unit_price_cents,
        "override_reason": override_reason,
        "override_actor_user_id": actor_user_id,
        "override_actor_email": actor_email,
        "captured_at": utc_now().isoformat(),
    }


def apply_override(
    snapshot: dict[str, Any],
    *,
    override_unit_price_cents: int,
    reason: str,
    actor_user_id: str,
    actor_email: str,
) -> dict[str, Any]:
    """Return a new snapshot dict with override applied. Original preserved."""
    updated = dict(snapshot or {})
    updated["override_unit_price_cents"] = int(override_unit_price_cents)
    updated["override_reason"] = reason
    updated["override_actor_user_id"] = actor_user_id
    updated["override_actor_email"] = actor_email
    updated["override_applied_at"] = utc_now().isoformat()
    return updated
