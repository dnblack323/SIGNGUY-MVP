"""EC9 Phase 9G — Immutable Pricing Snapshot Records: creation, lineage,
deterministic explanation, and deterministic comparison.

Append-only. `create_snapshot_record` is the ONLY function that inserts a
`PricingSnapshotRecord`; nothing else in the codebase should write to the
`pricing_snapshot_records` collection. Every field EXCEPT `status` /
`status_changed_at` / `superseded_by_snapshot_id` is written once and never
touched again — editing a live Material / MaterialPricingProfile / SavedItem /
PricingComponent / Pricing Foundation default afterward never changes a
stored record.

`explain_snapshot` / `compare_snapshots` are pure, deterministic functions
built only from already-stored fields — no AI, no live lookups.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.money import dollars_to_cents
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.pricing_snapshot_record import PricingSnapshotRecord


def _now_iso() -> str:
    return utc_now().isoformat()


def _cents_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return dollars_to_cents(v)
    except (TypeError, ValueError):
        return None


async def create_snapshot_record(
    *,
    tenant_id: str,
    source_type: str,
    source_id: str,
    item_doc: dict[str, Any],
    quote_id: Optional[str] = None,
    order_id: Optional[str] = None,
    calculated_by_user_id: Optional[str] = None,
    status: str = "active",
    previous_snapshot_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build + insert one immutable historical record from the FINAL item
    document (post pricing-fields merge) and its embedded `pricing_snapshot`
    dict (built by `services/pricing_snapshot.py`).

    If an "active" record already exists for this exact (source_type,
    source_id), it is relabeled "superseded" (metadata-only `$set` — its
    pricing data is never touched) and the new record's `previous_snapshot_id`
    points at it. Otherwise the caller-supplied `previous_snapshot_id` is used
    as-is (e.g. Quote→Order conversion linking a brand-new Order Item's first
    snapshot back to the source Quote Line Item's snapshot).
    """
    snap = dict(item_doc.get("pricing_snapshot") or {})
    material_profile_id = item_doc.get("material_profile_id")
    material_profile_snapshot = snap.get("material_profile_snapshot") or {}
    material_id = material_profile_snapshot.get("material_id") if material_profile_snapshot else None

    prev = await db.pricing_snapshot_records.find_one(
        {"tenant_id": tenant_id, "source_type": source_type, "source_id": source_id, "status": "active"},
        {"_id": 0},
    )
    resolved_previous_id = prev.get("id") if prev else previous_snapshot_id

    record = PricingSnapshotRecord(
        tenant_id=tenant_id,
        source_type=source_type,
        source_id=source_id,
        quote_id=quote_id,
        order_id=order_id,
        order_item_id=source_id if source_type == "order_item" else None,
        category=item_doc.get("category"),
        item_name=item_doc.get("item_name"),
        description=item_doc.get("description"),
        quantity=int(item_doc.get("quantity") or 1),
        category_inputs=dict(item_doc.get("category_inputs") or {}),
        material_ids=[material_id] if material_id else [],
        material_profile_ids=[material_profile_id] if material_profile_id else [],
        material_values_used=material_profile_snapshot,
        saved_item_id=item_doc.get("saved_item_id"),
        saved_item_values_used=snap.get("saved_item_snapshot") or {},
        pricing_component_ids=list(item_doc.get("pricing_component_ids") or []),
        pricing_component_values_used=snap.get("pricing_components_snapshot") or [],
        shop_defaults_used=snap.get("defaults_snapshot") or {},
        category_defaults_used=snap.get("category_defaults_used") or {},
        formula_version=snap.get("formula_version"),
        starter_default_version=snap.get("calculator_version"),
        pricing_foundation_effective_at=snap.get("foundation_effective_at"),
        suggested_price_cents=item_doc.get("suggested_price_cents"),
        manual_price_cents=item_doc.get("manual_price_cents"),
        selected_final_price_cents=int(item_doc.get("unit_price_cents") or 0),
        selected_price_source=item_doc.get("selected_price_source") or "manual",
        cost_breakdown=[
            {"label": row.get("label"), "amount_cents": _cents_or_none(row.get("amount")) or 0}
            for row in (snap.get("breakdown") or [])
        ],
        labor_breakdown_cents={
            "labor_cost_cents": _cents_or_none(snap.get("labor_cost_dollars")),
            "design_cost_cents": _cents_or_none(snap.get("design_cost_dollars")),
            "install_cost_cents": _cents_or_none(snap.get("install_cost_dollars")),
        },
        overhead_cost_cents=_cents_or_none(snap.get("overhead_cost_dollars")),
        minimum_applied=bool(snap.get("minimum_charge_applied", False)),
        discount_cents=int(item_doc.get("discount_cents") or 0),
        rush_adjustment_applied=bool(snap.get("rush_applied", False)),
        estimated_profit_cents=item_doc.get("estimated_profit_cents"),
        estimated_margin_percent=item_doc.get("estimated_margin_percent"),
        source_labels=dict(item_doc.get("source_labels") or {}),
        assumptions=[
            w for w in (item_doc.get("calculation_warnings") or [])
            if "provisional" in str(w).lower() or "assumption" in str(w).lower()
        ],
        calculation_warnings=list(item_doc.get("calculation_warnings") or []),
        calculated_by_user_id=calculated_by_user_id,
        price_selected_by_user_id=item_doc.get("price_selected_by_user_id"),
        recalculated_at=item_doc.get("last_recalculated_at"),
        previous_snapshot_id=resolved_previous_id,
        status=status,
    ).model_dump()

    await db.pricing_snapshot_records.insert_one(prepare_for_mongo(dict(record)))

    if prev:
        await db.pricing_snapshot_records.update_one(
            {"id": prev["id"], "tenant_id": tenant_id},
            {"$set": {
                "status": "superseded",
                "superseded_by_snapshot_id": record["id"],
                "status_changed_at": _now_iso(),
            }},
        )

    record.pop("_id", None)
    return record


async def get_snapshot_record(tenant_id: str, snapshot_id: str) -> Optional[dict[str, Any]]:
    return await db.pricing_snapshot_records.find_one({"tenant_id": tenant_id, "id": snapshot_id}, {"_id": 0})


async def list_snapshot_records(
    tenant_id: str, *, source_type: Optional[str] = None, source_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if source_type:
        filt["source_type"] = source_type
    if source_id:
        filt["source_id"] = source_id
    return [d async for d in db.pricing_snapshot_records.find(filt, {"_id": 0}).sort("created_at", 1)]


def _num_diff(a: Any, b: Any) -> Optional[dict[str, Any]]:
    if a is None and b is None:
        return None
    return {"from": a, "to": b, "delta": (b or 0) - (a or 0)}


def _breakdown_amount(record: dict[str, Any], label_substr: str) -> Optional[int]:
    for row in record.get("cost_breakdown") or []:
        if label_substr.lower() in str(row.get("label") or "").lower():
            return row.get("amount_cents")
    return None


def compare_snapshots(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Deterministic diff between two snapshot records (EC9 Phase 9G §7).
    Frontend never has to reverse-engineer differences."""
    return {
        "material_cost_change": _num_diff(_breakdown_amount(base, "material"), _breakdown_amount(candidate, "material")),
        "labor_cost_change": _num_diff(
            (base.get("labor_breakdown_cents") or {}).get("labor_cost_cents"),
            (candidate.get("labor_breakdown_cents") or {}).get("labor_cost_cents"),
        ),
        "overhead_change": _num_diff(base.get("overhead_cost_cents"), candidate.get("overhead_cost_cents")),
        "suggested_price_change": _num_diff(base.get("suggested_price_cents"), candidate.get("suggested_price_cents")),
        "manual_price_change": _num_diff(base.get("manual_price_cents"), candidate.get("manual_price_cents")),
        "selected_final_price_change": _num_diff(base.get("selected_final_price_cents"), candidate.get("selected_final_price_cents")),
        "margin_change": _num_diff(base.get("estimated_margin_percent"), candidate.get("estimated_margin_percent")),
        "changed_defaults": bool(
            base.get("shop_defaults_used") != candidate.get("shop_defaults_used")
            or base.get("category_defaults_used") != candidate.get("category_defaults_used")
        ),
        "changed_materials": base.get("material_profile_ids") != candidate.get("material_profile_ids"),
        "changed_components": base.get("pricing_component_ids") != candidate.get("pricing_component_ids"),
        "changed_warnings": base.get("calculation_warnings") != candidate.get("calculation_warnings"),
        "changed_formula_version": base.get("formula_version") != candidate.get("formula_version"),
    }


def explain_snapshot(record: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Deterministic, non-AI explanation built purely from stored snapshot
    fields (EC9 Phase 9G §6). Never calls any AI/provider."""
    price_source = record.get("selected_price_source")
    if price_source == "suggested":
        final_price_reason = (
            f"The backend-computed suggested price ({record.get('suggested_price_cents')} cents) was selected."
        )
    else:
        final_price_reason = (
            f"A manual price ({record.get('selected_final_price_cents')} cents) was explicitly chosen "
            "over the calculator's suggested price."
        )
    sections: dict[str, Any] = {
        "inputs_used": {
            "category": record.get("category"),
            "quantity": record.get("quantity"),
            "category_inputs": record.get("category_inputs"),
        },
        "defaults_used": {
            "shop_defaults": record.get("shop_defaults_used"),
            "category_defaults": record.get("category_defaults_used"),
            "formula_version": record.get("formula_version"),
            "starter_default_version": record.get("starter_default_version"),
            "pricing_foundation_effective_at": record.get("pricing_foundation_effective_at"),
        },
        "materials_and_components": {
            "material_ids": record.get("material_ids"),
            "material_profile_ids": record.get("material_profile_ids"),
            "material_values_used": record.get("material_values_used"),
            "saved_item_id": record.get("saved_item_id"),
            "saved_item_values_used": record.get("saved_item_values_used"),
            "pricing_component_ids": record.get("pricing_component_ids"),
            "pricing_component_values_used": record.get("pricing_component_values_used"),
        },
        "cost_calculation": {
            "cost_breakdown": record.get("cost_breakdown"),
            "labor_breakdown_cents": record.get("labor_breakdown_cents"),
            "overhead_cost_cents": record.get("overhead_cost_cents"),
            "minimum_applied": record.get("minimum_applied"),
            "rush_adjustment_applied": record.get("rush_adjustment_applied"),
        },
        "suggested_price_calculation": {
            "suggested_price_cents": record.get("suggested_price_cents"),
            "estimated_profit_cents": record.get("estimated_profit_cents"),
            "estimated_margin_percent": record.get("estimated_margin_percent"),
        },
        "manual_adjustments": (
            {"manual_price_cents": record.get("manual_price_cents")}
            if record.get("manual_price_cents") is not None else None
        ),
        "final_price_reason": final_price_reason,
        "assumptions_and_warnings": {
            "assumptions": record.get("assumptions"),
            "calculation_warnings": record.get("calculation_warnings"),
        },
        "accountability": {
            "calculated_by_user_id": record.get("calculated_by_user_id"),
            "price_selected_by_user_id": record.get("price_selected_by_user_id"),
            "created_at": record.get("created_at"),
            "recalculated_at": record.get("recalculated_at"),
        },
        "status": {"status": record.get("status"), "previous_snapshot_id": record.get("previous_snapshot_id")},
    }
    if previous:
        sections["changes_from_previous"] = compare_snapshots(previous, record)
    else:
        sections["changes_from_previous"] = None
    return sections
