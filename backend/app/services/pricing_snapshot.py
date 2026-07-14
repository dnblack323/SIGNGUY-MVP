"""EC3 — Pricing snapshots. Extended in EC9 Phase 9B with the shop-level
Pricing Foundation "defaults_snapshot" + `foundation_effective_at` capture
and the formal `source` label taxonomy.

A pricing snapshot preserves the calculation basis for a Quote/Order line
item at the moment it was committed. It captures enough context to explain the
result later — even after shop pricing defaults change. Historical records
must never be silently re-priced.

Snapshots are stored on the line item document under `pricing_snapshot`.

`source` label taxonomy (EC09 controlling document, Phase 9B):
    manual          — legacy label, pre-Phase-9B manual entries (unchanged, kept for old records)
    user_entered    — a human typed the final price directly (current label for manual entry)
    calculator      — legacy label, pre-Phase-9B calculator use (unchanged, kept for old records)
    shop_default    — price/field came straight from unedited Pricing Foundation defaults
    saved_item      — price/field came from a PricingSavedItem (Phase 9D)
    ai_estimate     — price/field came from an AI estimation (Phase 9G; NOT implemented until EC16)
    historical_data — price/field came from historical invoice analysis (Phase 9G; NOT implemented until EC16)
    market_data     — price/field came from market/competitor comparison (Phase 9G; NOT implemented until EC16)
All values are additive — old snapshots with only "manual"/"calculator" remain valid and are never rewritten.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional

from ..core.money import dollars_to_cents
from ..core.time_utils import utc_now
from .starter_defaults import STARTER_DEFAULT_VERSION


def _now_iso() -> str:
    return utc_now().isoformat()


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
        "snapshot_id": str(uuid.uuid4()),
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
        "captured_at": _now_iso(),
    }


def build_calculated_snapshot(
    *,
    calc_result: dict[str, Any],
    quantity: int,
    override_unit_price_cents: Optional[int] = None,
    override_reason: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    foundation_effective_at: Optional[str] = None,
    # EC9 Phase 9F — Quote/Order/Order Item integration additions. Additive
    # only; every pre-existing key above is unchanged so old snapshots and
    # tests keep working.
    saved_item_id: Optional[str] = None,
    material_profile_id: Optional[str] = None,
    pricing_component_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build a snapshot for a price derived from the pricing calculator.

    `calc_result` is the dict returned by `services/pricing.calculate_pricing`.
    `foundation_effective_at` should be the tenant's `pricing_settings.updated_at`
    at calculation time — the "effective date" for the Pricing Foundation
    defaults baked into `defaults_snapshot` below (Phase 9B versioning).
    """
    calc_unit_dollars = calc_result.get("selling_price")
    calc_unit_cents = (
        dollars_to_cents(Decimal(str(calc_unit_dollars)))
        if calc_unit_dollars is not None
        else None
    )
    return {
        "snapshot_id": str(uuid.uuid4()),
        "source": "calculator",
        "pricing_method": calc_result.get("pricing_method_used"),
        "calculator_version": STARTER_DEFAULT_VERSION,
        "formula_version": STARTER_DEFAULT_VERSION,
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
        "suggested_price_dollars": calc_unit_dollars,
        "override_unit_price_cents": override_unit_price_cents,
        "override_reason": override_reason,
        "override_actor_user_id": actor_user_id,
        "override_actor_email": actor_email,
        # Phase 9B — shop-level Pricing Foundation values in effect at
        # calculation time (immutable copy; never re-read from live settings).
        "defaults_snapshot": calc_result.get("shop_defaults_used") or {},
        "foundation_effective_at": foundation_effective_at,
        # Phase 9F — explain-later context: raw calculator inputs used, why
        # each field resolved the way it did, and any calculation warnings.
        "category_inputs": calc_result.get("category_inputs_used") or {},
        "source_labels": calc_result.get("source_labels") or {},
        "calculation_warnings": calc_result.get("calculation_warnings") or [],
        "breakdown": calc_result.get("breakdown") or [],
        "saved_item_id": saved_item_id,
        "material_profile_id": material_profile_id,
        "pricing_component_ids": pricing_component_ids or [],
        # EC9 Phase 9G — frozen copies of the resolved reference objects +
        # category defaults, exactly as they were at calculation time. An
        # immutable historical `PricingSnapshotRecord` (see
        # `services/pricing_snapshot_records.py`) is built FROM these values,
        # never by re-reading the live Material/SavedItem/Component/Defaults
        # records later.
        "material_profile_snapshot": calc_result.get("material_profile_used"),
        "pricing_components_snapshot": calc_result.get("pricing_components_used") or [],
        "saved_item_snapshot": calc_result.get("saved_item_used"),
        "category_defaults_used": calc_result.get("category_defaults_used") or {},
        "captured_at": _now_iso(),
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
