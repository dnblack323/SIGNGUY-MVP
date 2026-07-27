"""EC9 Phase 9I-G - saved calculation library service."""
from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any, Mapping, Optional

from pymongo import ReturnDocument

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.pricing_saved_calculation import PricingSavedCalculation
from .order_pricing import resolve_references
from .pricing import calculate_pricing, get_or_init_pricing_settings
from .pricing_method_comparisons import PricingMethodComparisonError, compare_pricing_methods
from .starter_defaults import CATEGORY_IDS, STARTER_DEFAULT_VERSION


class SavedCalculationError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now_iso() -> str:
    return utc_now().isoformat()


def _money_cents(value: Any) -> int:
    amount = float(value)
    if not math.isfinite(amount):
        raise SavedCalculationError("Calculation selling price is not valid")
    return int(round(amount * 100))


def _clean_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    category = str(inputs.get("category") or "")
    if category not in CATEGORY_IDS:
        raise SavedCalculationError(f"Unknown category: {category}")
    quantity = max(1, int(inputs.get("quantity") or 1))
    return {
        "category": category,
        "width_inches": inputs.get("width_inches"),
        "height_inches": inputs.get("height_inches"),
        "quantity": quantity,
        "material_key": inputs.get("material_key"),
        "design_needed": bool(inputs.get("design_needed", False)),
        "install_needed": bool(inputs.get("install_needed", False)),
        "manual_selling_price": inputs.get("manual_selling_price"),
        "category_inputs": deepcopy(dict(inputs.get("category_inputs") or {})),
        "material_profile_id": inputs.get("material_profile_id"),
        "pricing_component_ids": list(inputs.get("pricing_component_ids") or []),
        "saved_item_id": inputs.get("saved_item_id"),
    }


def _selected_method_id(result: Mapping[str, Any], comparison: Mapping[str, Any] | None) -> str | None:
    if comparison:
        return comparison.get("selected_method_id") or comparison.get("primary_method_id")
    selected_row = next((row for row in result.get("pricing_method_results") or [] if row.get("selected")), None)
    return (
        (selected_row or {}).get("method_id")
        or result.get("selected_method_id")
        or result.get("pricing_method_used")
        or result.get("selected_pricing_method")
    )


def _method_availability(result: Mapping[str, Any], comparison: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw = result.get("method_availability") or []
    if isinstance(raw, list):
        rows.extend(deepcopy(raw))
    comp_availability = (comparison or {}).get("availability")
    if isinstance(comp_availability, Mapping):
        rows.extend(deepcopy(list(comp_availability.get("methods") or [])))
    elif isinstance(comp_availability, list):
        rows.extend(deepcopy(comp_availability))
    return rows


async def calculate_saved_calculation_result(
    tenant_id: str,
    inputs: Mapping[str, Any],
    *,
    selected_method_id: str | None = None,
) -> dict[str, Any]:
    clean = _clean_inputs(inputs)
    settings = await get_or_init_pricing_settings(tenant_id)
    try:
        material_profile, pricing_components, saved_item = await resolve_references(
            tenant_id=tenant_id,
            material_profile_id=clean.get("material_profile_id"),
            pricing_component_ids=clean.get("pricing_component_ids") or [],
            saved_item_id=clean.get("saved_item_id"),
        )
    except ValueError as exc:
        if str(exc) == "material_profile_not_found":
            raise SavedCalculationError("Material pricing profile not found", status_code=404) from exc
        if str(exc) == "saved_item_not_found":
            raise SavedCalculationError("Saved item not found", status_code=404) from exc
        raise

    try:
        result = calculate_pricing(
            settings=settings,
            category=clean["category"],
            width_inches=clean.get("width_inches"),
            height_inches=clean.get("height_inches"),
            quantity=clean["quantity"],
            material_key=clean.get("material_key"),
            design_needed=clean.get("design_needed", False),
            install_needed=clean.get("install_needed", False),
            manual_selling_price=clean.get("manual_selling_price"),
            category_inputs=clean.get("category_inputs") or {},
            material_profile=material_profile,
            pricing_components=pricing_components,
            saved_item=saved_item,
        )
    except ValueError as exc:
        raise SavedCalculationError(str(exc)) from exc

    comparison = None
    if clean["category"] == "banners":
        try:
            comparison = await compare_pricing_methods(
                tenant_id=tenant_id,
                category_id=clean["category"],
                width_inches=clean.get("width_inches"),
                height_inches=clean.get("height_inches"),
                quantity=clean["quantity"],
                material_key=clean.get("material_key"),
                design_needed=clean.get("design_needed", False),
                install_needed=clean.get("install_needed", False),
                manual_selling_price=clean.get("manual_selling_price"),
                category_inputs=clean.get("category_inputs") or {},
                material_profile_id=clean.get("material_profile_id"),
                pricing_component_ids=clean.get("pricing_component_ids") or [],
                saved_item_id=clean.get("saved_item_id"),
                use_saved_configuration=True,
                primary_method_id=selected_method_id or None,
            )
        except PricingMethodComparisonError:
            comparison = None

    amount = result.get("selling_price")
    if amount is None:
        raise SavedCalculationError("Only successful calculations with a selling price can be saved or reused")
    selling_price_cents = _money_cents(amount)
    selected = _selected_method_id(result, comparison)
    return {
        "calculation_inputs": clean,
        "calculation_result": deepcopy(result),
        "comparison_result": deepcopy(comparison),
        "selling_price": float(amount),
        "selling_price_cents": selling_price_cents,
        "canonical_method_id": (comparison or {}).get("canonical_method_id") or result.get("canonical_method_id") or result.get("pricing_method_used") or result.get("selected_pricing_method"),
        "selected_method_id": selected,
        "pricing_method_results": deepcopy((comparison or {}).get("comparison_results") or result.get("pricing_method_results") or []),
        "method_availability": _method_availability(result, comparison),
        "warnings": deepcopy(result.get("calculation_warnings") or result.get("warnings") or []),
        "errors": deepcopy(result.get("errors") or []),
        "breakdown": deepcopy(result.get("breakdown") or []),
        "detail_sections": deepcopy(result.get("detail_sections") or []),
        "pricing_reproducibility_ref": {
            "settings_updated_at": settings.get("updated_at"),
            "starter_default_version": settings.get("starter_default_version") or STARTER_DEFAULT_VERSION,
            "category_method_configuration_version": ((settings.get("category_method_configurations") or {}).get(clean["category"]) or {}).get("configuration_version"),
            "formula_version": result.get("formula_version"),
            "pricing_contract_version": result.get("pricing_contract_version"),
        },
    }


async def create_saved_calculation(tenant_id: str, actor: Mapping[str, Any], fields: Mapping[str, Any]) -> dict[str, Any]:
    name = str(fields.get("name") or "").strip()
    if not name:
        raise SavedCalculationError("Name is required")
    calculated = await calculate_saved_calculation_result(
        tenant_id,
        fields.get("calculation_inputs") or {},
        selected_method_id=fields.get("selected_method_id"),
    )
    doc = PricingSavedCalculation(
        tenant_id=tenant_id,
        name=name,
        notes=(str(fields.get("notes")).strip() if fields.get("notes") is not None else None),
        category=calculated["calculation_inputs"]["category"],
        source_context=fields.get("source_context") or "pricing_calculator",
        created_by_user_id=str(actor.get("id") or ""),
        created_by_email=actor.get("email"),
        **calculated,
    ).model_dump()
    await db.pricing_saved_calculations.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def list_saved_calculations(
    tenant_id: str,
    *,
    search: str | None = None,
    category: str | None = None,
    archived: bool | None = False,
) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if archived is not None:
        filt["archived"] = archived
    if category:
        if category not in CATEGORY_IDS:
            raise SavedCalculationError(f"Unknown category: {category}")
        filt["category"] = category
    if search:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        filt["$or"] = [{"name": pattern}, {"notes": pattern}]
    return [serialize_doc(doc) async for doc in db.pricing_saved_calculations.find(filt, {"_id": 0}).sort("updated_at", -1)]


async def get_saved_calculation(tenant_id: str, calculation_id: str) -> Optional[dict[str, Any]]:
    doc = await db.pricing_saved_calculations.find_one({"tenant_id": tenant_id, "id": calculation_id}, {"_id": 0})
    return serialize_doc(doc)


async def update_saved_calculation_metadata(
    tenant_id: str,
    calculation_id: str,
    actor: Mapping[str, Any],
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    allowed: dict[str, Any] = {}
    if "name" in updates:
        name = str(updates.get("name") or "").strip()
        if not name:
            raise SavedCalculationError("Name is required")
        allowed["name"] = name
    if "notes" in updates:
        allowed["notes"] = str(updates["notes"]).strip() if updates.get("notes") is not None else None
    if not allowed:
        raise SavedCalculationError("No metadata updates provided")
    allowed["updated_at"] = _now_iso()
    allowed["updated_by_user_id"] = actor.get("id")
    result = await db.pricing_saved_calculations.find_one_and_update(
        {"tenant_id": tenant_id, "id": calculation_id},
        {"$set": prepare_for_mongo(allowed)},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise SavedCalculationError("Saved calculation not found", status_code=404)
    return serialize_doc(result)


async def archive_saved_calculation(tenant_id: str, calculation_id: str, actor: Mapping[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    result = await db.pricing_saved_calculations.find_one_and_update(
        {"tenant_id": tenant_id, "id": calculation_id},
        {"$set": {"archived": True, "archived_at": now, "updated_at": now, "updated_by_user_id": actor.get("id")}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise SavedCalculationError("Saved calculation not found", status_code=404)
    return serialize_doc(result)


async def restore_saved_calculation(tenant_id: str, calculation_id: str, actor: Mapping[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    result = await db.pricing_saved_calculations.find_one_and_update(
        {"tenant_id": tenant_id, "id": calculation_id},
        {"$set": {"archived": False, "restored_at": now, "updated_at": now, "updated_by_user_id": actor.get("id")}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise SavedCalculationError("Saved calculation not found", status_code=404)
    return serialize_doc(result)


async def duplicate_saved_calculation(
    tenant_id: str,
    calculation_id: str,
    actor: Mapping[str, Any],
    *,
    name: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    source = await get_saved_calculation(tenant_id, calculation_id)
    if not source:
        raise SavedCalculationError("Saved calculation not found", status_code=404)
    base = {k: deepcopy(v) for k, v in source.items() if k not in ("id", "created_at", "updated_at", "tenant_id", "archived_at", "restored_at")}
    base["name"] = str(name or f"{source['name']} Copy").strip()
    base["notes"] = notes if notes is not None else source.get("notes")
    base["archived"] = False
    base["duplicated_from_id"] = calculation_id
    base["created_by_user_id"] = str(actor.get("id") or "")
    base["created_by_email"] = actor.get("email")
    base["updated_by_user_id"] = actor.get("id")
    doc = PricingSavedCalculation(tenant_id=tenant_id, **base).model_dump()
    await db.pricing_saved_calculations.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def recalculate_saved_calculation(tenant_id: str, calculation_id: str) -> dict[str, Any]:
    saved = await get_saved_calculation(tenant_id, calculation_id)
    if not saved:
        raise SavedCalculationError("Saved calculation not found", status_code=404)
    if saved.get("archived"):
        raise SavedCalculationError("Archived saved calculations must be restored before use")
    calculated = await calculate_saved_calculation_result(
        tenant_id,
        saved.get("calculation_inputs") or {},
        selected_method_id=saved.get("selected_method_id"),
    )
    return {
        "saved_calculation": saved,
        "current_result": calculated["calculation_result"],
        "comparison_result": calculated["comparison_result"],
        "saved_price": saved.get("selling_price"),
        "current_price": calculated["selling_price"],
        "price_changed": int(saved.get("selling_price_cents") or 0) != int(calculated["selling_price_cents"]),
        "current_selling_price_cents": calculated["selling_price_cents"],
        "warnings": calculated["warnings"],
        "errors": calculated["errors"],
        "transferable": True,
    }
