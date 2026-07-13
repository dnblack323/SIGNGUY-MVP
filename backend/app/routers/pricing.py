from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc, utc_now
from ..deps import require_permission
from ..services.audit import record_audit
from ..services.pricing import (
    calculate_pricing,
    get_or_init_pricing_settings,
    reset_category_to_starter,
    update_category,
    update_shop_defaults,
    wizard_suggestions,
)
from ..services.starter_defaults import CATEGORY_IDS

router = APIRouter(prefix="/pricing", tags=["pricing"])


class ShopDefaultsIn(BaseModel):
    design_hourly_rate: Optional[float] = Field(None, ge=0)
    production_hourly_rate: Optional[float] = Field(None, ge=0)
    install_hourly_rate: Optional[float] = Field(None, ge=0)
    removal_hourly_rate: Optional[float] = Field(None, ge=0)
    travel_hourly_rate: Optional[float] = Field(None, ge=0)
    admin_hourly_rate: Optional[float] = Field(None, ge=0)
    consultation_hourly_rate: Optional[float] = Field(None, ge=0)
    site_survey_hourly_rate: Optional[float] = Field(None, ge=0)
    finishing_hourly_rate: Optional[float] = Field(None, ge=0)
    default_overhead_percent: Optional[float] = Field(None, ge=0, le=200)
    labor_burden_percent: Optional[float] = Field(None, ge=0, le=200)
    target_profit_margin_percent: Optional[float] = Field(None, ge=0, le=99.9)
    minimum_order_amount: Optional[float] = Field(None, ge=0)
    deposit_percentage: Optional[float] = Field(None, ge=0, le=100)
    default_markup_multiplier: Optional[float] = Field(None, ge=1)
    default_waste_percent: Optional[float] = Field(None, ge=0, le=100)
    rush_fee_percent: Optional[float] = Field(None, ge=0, le=200)
    install_minimum_charge: Optional[float] = Field(None, ge=0)
    setup_fee_default: Optional[float] = Field(None, ge=0)


class CategoryUpdateIn(BaseModel):
    pricing_method: Optional[Literal["per_sqft", "cost_plus_labor", "common_job_prices"]] = None
    minimum_charge: Optional[float] = Field(None, ge=0)
    base_sell_rate_per_sqft: Optional[float] = Field(None, ge=0)
    default_markup_multiplier: Optional[float] = Field(None, ge=1)
    target_margin_percent: Optional[float] = Field(None, ge=0, le=99.9)
    waste_percent: Optional[float] = Field(None, ge=0, le=100)
    default_material: Optional[str] = None
    design_included: Optional[bool] = None
    install_included: Optional[bool] = None
    hems_grommets_included: Optional[bool] = None
    common_job_prices: Optional[dict[str, Any]] = None
    quantity_tiers: Optional[list[dict[str, Any]]] = None
    extras: Optional[dict[str, Any]] = None  # bag for future untyped keys
    mark_setup_complete: bool = False


class CalcIn(BaseModel):
    category: Literal["banners", "rigid_signs", "cut_vinyl", "digital_print",
                      "vehicle_graphics", "apparel", "services", "promotional", "custom"]
    width_inches: Optional[float] = Field(None, ge=0)
    height_inches: Optional[float] = Field(None, ge=0)
    quantity: int = Field(1, ge=1)
    material_key: Optional[str] = None
    design_needed: bool = False
    install_needed: bool = False
    manual_selling_price: Optional[float] = Field(None, ge=0)


class WizardSuggestIn(BaseModel):
    answers: dict[str, Any]


class ApplySuggestionsIn(BaseModel):
    suggestions: list[dict[str, Any]]
    mark_setup_complete: bool = True


@router.get("/settings")
async def get_settings(user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_or_init_pricing_settings(user["tenant_id"])
    return serialize_doc(doc)


@router.patch("/settings/shop-defaults")
async def patch_shop_defaults(payload: ShopDefaultsIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    doc = await update_shop_defaults(user["tenant_id"], updates)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.shop_defaults.update", entity_type="pricing_settings", entity_id=user["tenant_id"],
        summary="Updated shop pricing defaults", diff={"changes": updates},
    )
    return serialize_doc(doc)


@router.patch("/settings/categories/{category_id}")
async def patch_category(category_id: str, payload: CategoryUpdateIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    if category_id not in CATEGORY_IDS:
        raise HTTPException(status_code=404, detail="Unknown category")
    updates = payload.model_dump(exclude_none=True)
    mark_complete = updates.pop("mark_setup_complete", False)
    extras = updates.pop("extras", None)
    if extras and isinstance(extras, dict):
        updates.update(extras)
    if mark_complete:
        updates["__mark_setup_complete__"] = True
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    doc = await update_category(user["tenant_id"], category_id, updates)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.category.update", entity_type="pricing_category", entity_id=category_id,
        summary=f"Updated pricing category '{category_id}'", diff={"changes": updates},
    )
    return serialize_doc(doc)


@router.post("/settings/categories/{category_id}/reset")
async def reset_category(category_id: str, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    if category_id not in CATEGORY_IDS:
        raise HTTPException(status_code=404, detail="Unknown category")
    doc = await reset_category_to_starter(user["tenant_id"], category_id)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.category.reset", entity_type="pricing_category", entity_id=category_id,
        summary=f"Reset pricing category '{category_id}' to starter defaults",
    )
    return serialize_doc(doc)


@router.post("/settings/categories/{category_id}/wizard/suggestions")
async def wizard_suggest(category_id: str, payload: WizardSuggestIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    if category_id not in CATEGORY_IDS:
        raise HTTPException(status_code=404, detail="Unknown category")
    settings = await get_or_init_pricing_settings(user["tenant_id"])
    suggestions = wizard_suggestions(category_id, payload.answers, settings)
    return {"category": category_id, "suggestions": suggestions}


@router.post("/settings/categories/{category_id}/wizard/apply")
async def wizard_apply(category_id: str, payload: ApplySuggestionsIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    if category_id not in CATEGORY_IDS:
        raise HTTPException(status_code=404, detail="Unknown category")
    # Merge only suggestions the user explicitly kept (apply=True) into category settings.
    updates: dict[str, Any] = {}
    applied: list[dict] = []
    for s in payload.suggestions:
        if not s.get("apply"):
            continue
        field = s.get("target_field")
        val = s.get("suggested")
        if not field:
            continue
        updates[field] = val
        applied.append({"field": field, "suggested": val})
    if payload.mark_setup_complete:
        updates["__mark_setup_complete__"] = True
    if not updates:
        raise HTTPException(status_code=400, detail="No suggestions selected to apply")
    doc = await update_category(user["tenant_id"], category_id, updates, source="detailed_wizard")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.wizard.apply", entity_type="pricing_category", entity_id=category_id,
        summary=f"Applied {len(applied)} wizard suggestion(s) to '{category_id}'", diff={"applied": applied},
    )
    return serialize_doc(doc)


@router.post("/calculate")
async def calculate(payload: CalcIn, user: dict = Depends(require_permission(Perm.PRICING_CALCULATE))) -> dict:
    settings = await get_or_init_pricing_settings(user["tenant_id"])
    try:
        return calculate_pricing(
            settings=settings,
            category=payload.category,
            width_inches=payload.width_inches,
            height_inches=payload.height_inches,
            quantity=payload.quantity,
            material_key=payload.material_key,
            design_needed=payload.design_needed,
            install_needed=payload.install_needed,
            manual_selling_price=payload.manual_selling_price,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
