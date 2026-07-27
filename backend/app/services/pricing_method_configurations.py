"""EC9 Phase 9I-B tenant pricing-method configuration services.

The configuration lives inside the existing tenant-scoped `pricing_settings`
document so it stays separate from live formulas, quote/order line items, and
historical pricing snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import HTTPException, status

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from .audit import list_audit, record_audit
from .pricing import get_or_init_pricing_settings
from .pricing_contracts import (
    MAX_COMPARISON_METHODS,
    PRICING_CONTRACT_VERSION,
    PricingContractError,
    TenantCategoryMethodConfiguration,
    validate_tenant_method_configuration,
)
from .pricing_method_registry import (
    get_category_definition,
    get_method_definition,
    list_category_definitions,
)


RECOMMENDATION_VERSION = f"{PRICING_CONTRACT_VERSION}.9i-b"
CONFIG_PATH = "category_method_configurations"

LEGACY_METHOD_ALIASES: dict[str, str] = {
    "per_sqft": "per_sqft",
    "cost_plus_labor": "cost_plus",
    "cost_plus": "cost_plus",
    "square_foot_plus_addons": "square_foot_plus_addons",
    "tier_pricing": "tier_pricing",
    "flat_fee": "flat_fee",
    "unit_price_x_quantity": "unit_price_x_quantity",
}


class PricingMethodConfigurationError(ValueError):
    def __init__(self, field: str, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


class StalePricingMethodConfigurationError(PricingMethodConfigurationError):
    def __init__(self, message: str = "Pricing method configuration has changed; reload before saving."):
        super().__init__(
            "expected_configuration_version",
            "stale_configuration",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


@dataclass(frozen=True)
class AvailabilityResult:
    method_id: str
    supported: bool
    available: bool
    reason: str | None = None
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        method = get_method_definition(self.method_id)
        return {
            "method_id": self.method_id,
            "method": method.to_dict(),
            "supported": self.supported,
            "available": self.available,
            "reason": self.reason,
            "explanation": self.explanation,
        }


def _now_iso() -> str:
    return utc_now().isoformat()


def _normalize_method_id(method_id: Any) -> str:
    raw = str(method_id or "").strip()
    if not raw:
        raise PricingMethodConfigurationError("enabled_method_ids", "required", "Method ID is required.")
    if raw == "common_job_prices":
        raise PricingMethodConfigurationError(
            "enabled_method_ids",
            "ambiguous_legacy_method",
            "Legacy method 'common_job_prices' is reference data and cannot be mapped to a pricing method.",
        )
    mapped = LEGACY_METHOD_ALIASES.get(raw, raw)
    get_method_definition(mapped)
    return mapped


def _normalize_method_ids(values: list[str] | tuple[str, ...] | None, field: str) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or []:
        try:
            out.append(_normalize_method_id(value))
        except PricingMethodConfigurationError as exc:
            raise PricingMethodConfigurationError(field, exc.code, exc.message, status_code=exc.status_code) from exc
        except PricingContractError as exc:
            raise PricingMethodConfigurationError(field, "unknown_method", str(exc)) from exc
    return tuple(out)


def _normalize_single_method_id(value: Any, field: str) -> str:
    try:
        return _normalize_method_id(value)
    except PricingMethodConfigurationError as exc:
        raise PricingMethodConfigurationError(field, exc.code, exc.message, status_code=exc.status_code) from exc
    except PricingContractError as exc:
        raise PricingMethodConfigurationError(field, "unknown_method", str(exc)) from exc


async def _tenant_has_promotional_tiers(tenant_id: str) -> bool:
    return bool(
        await db.pricing_saved_items.find_one(
            {
                "tenant_id": tenant_id,
                "category": "promotional",
                "active": True,
                "quantity_tiers.0": {"$exists": True},
            },
            {"_id": 0, "id": 1},
        )
    )


async def resolve_method_availability(
    tenant_id: str,
    category_id: str,
    *,
    category_inputs: Mapping[str, Any] | None = None,
    saved_item: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    settings = await get_or_init_pricing_settings(tenant_id)
    category = get_category_definition(category_id)
    category_defaults = (settings.get("category_defaults") or {}).get(category_id) or {}
    inputs = dict(category_inputs or {})
    saved = dict(saved_item or {})
    results: list[AvailabilityResult] = []

    for method_id in category.supported_method_ids:
        available = True
        reason = None
        explanation = None
        if category_id == "vehicle_graphics" and method_id == "vehicle_benchmark":
            benchmarks = category_defaults.get("benchmark_prices") or {}
            vehicle_type = inputs.get("vehicle_type")
            coverage_type = inputs.get("coverage_type")
            if not benchmarks:
                available = False
                reason = "missing_vehicle_benchmark"
                explanation = "No approved vehicle benchmark prices are configured for this tenant."
            elif vehicle_type and coverage_type and coverage_type not in (benchmarks.get(vehicle_type) or {}):
                available = False
                reason = "missing_vehicle_benchmark_for_context"
                explanation = "No approved benchmark exists for the selected vehicle and coverage."
        if category_id == "promotional":
            if method_id == "tier_pricing":
                has_tiers = bool(saved.get("quantity_tiers") or category_defaults.get("quantity_tiers"))
                if not has_tiers:
                    has_tiers = await _tenant_has_promotional_tiers(tenant_id)
                if not has_tiers:
                    available = False
                    reason = "missing_promotional_tiers"
                    explanation = "No active promotional saved item or category tier pricing is configured."
            elif method_id == "per_piece":
                if inputs.get("unit_cost") is None and category_defaults.get("unit_cost") is None:
                    available = False
                    reason = "missing_unit_cost"
                    explanation = "Per-piece pricing requires a configured supplier unit cost."
            elif method_id == "flat_fee":
                if inputs.get("flat_fee_price") is None and category_defaults.get("flat_fee_price") is None:
                    available = False
                    reason = "missing_flat_fee"
                    explanation = "Flat-fee pricing requires a configured flat selling price."
        results.append(AvailabilityResult(method_id, True, available, reason, explanation))

    return {
        "tenant_id": tenant_id,
        "category_id": category_id,
        "supported_method_ids": list(category.supported_method_ids),
        "available_method_ids": [item.method_id for item in results if item.available],
        "methods": [item.to_dict() for item in results],
        "recommendation_version": RECOMMENDATION_VERSION,
    }


async def _validate_configuration(
    tenant_id: str,
    category_id: str,
    enabled_method_ids: tuple[str, ...],
    primary_method_id: str | None,
    comparison_order: tuple[str, ...],
    *,
    compare_automatically: bool,
    configuration_mode: str,
    method_configuration_refs: Mapping[str, str] | None = None,
    validation_warnings: tuple[str, ...] = (),
) -> TenantCategoryMethodConfiguration:
    category = get_category_definition(category_id)
    refs = dict(method_configuration_refs or {})
    if not enabled_method_ids:
        raise PricingMethodConfigurationError(
            "enabled_method_ids",
            "required",
            "At least one enabled pricing method is required.",
        )
    if len(enabled_method_ids) > MAX_COMPARISON_METHODS:
        raise PricingMethodConfigurationError(
            "enabled_method_ids",
            "too_many_methods",
            "No more than three methods can be enabled.",
        )
    availability = await resolve_method_availability(tenant_id, category_id)
    unavailable = set(enabled_method_ids) - set(availability["available_method_ids"])
    if unavailable:
        details = {
            item["method_id"]: item
            for item in availability["methods"]
            if item["method_id"] in unavailable
        }
        first = next(iter(unavailable))
        reason = details.get(first, {}).get("reason") or "method_unavailable"
        explanation = details.get(first, {}).get("explanation") or "The method is not currently available for this tenant/category."
        raise PricingMethodConfigurationError("enabled_method_ids", reason, explanation)
    unknown_ref_methods = set(refs) - set(enabled_method_ids)
    if unknown_ref_methods:
        raise PricingMethodConfigurationError(
            "method_configuration_refs",
            "reference_method_not_enabled",
            "Method-specific configuration references may only be set for enabled methods.",
        )
    try:
        return validate_tenant_method_configuration(
            TenantCategoryMethodConfiguration(
                tenant_id=tenant_id,
                category_id=category_id,
                enabled_method_ids=enabled_method_ids,
                primary_method_id=primary_method_id,
                comparison_order=comparison_order,
                compare_automatically=compare_automatically,
                configuration_mode=configuration_mode,  # type: ignore[arg-type]
                recommended_configuration_version=RECOMMENDATION_VERSION,
                method_configuration_refs=refs,
                validation_warnings=validation_warnings,
                config_version=RECOMMENDATION_VERSION,
            ),
            category,
        )
    except PricingContractError as exc:
        message = str(exc)
        field = "configuration"
        if "duplicate" in message:
            field = "enabled_method_ids"
        elif "Unsupported" in message:
            field = "enabled_method_ids"
        elif "primary_method_id" in message:
            field = "primary_method_id"
        elif "comparison_order" in message:
            field = "comparison_order"
        raise PricingMethodConfigurationError(field, "invalid_configuration", message) from exc


def _config_from_doc(settings: Mapping[str, Any], category_id: str) -> dict[str, Any] | None:
    config = (settings.get(CONFIG_PATH) or {}).get(category_id)
    return dict(config) if isinstance(config, Mapping) else None


def _logical_config(config: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not config:
        return None
    keys = (
        "category_id",
        "configuration_mode",
        "enabled_method_ids",
        "primary_method_id",
        "comparison_order",
        "compare_automatically",
        "recommended_configuration_version",
        "method_configuration_refs",
        "validation_warnings",
    )
    return {key: config.get(key) for key in keys}


def _stored_config(
    *,
    tenant_id: str,
    cfg: TenantCategoryMethodConfiguration,
    existing: Mapping[str, Any] | None,
    actor: Mapping[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    version = int((existing or {}).get("configuration_version") or 0) + 1
    return {
        "tenant_id": tenant_id,
        "category_id": cfg.category_id,
        "configuration_mode": cfg.configuration_mode,
        "enabled_method_ids": list(cfg.enabled_method_ids),
        "primary_method_id": cfg.primary_method_id,
        "comparison_order": list(cfg.comparison_order),
        "compare_automatically": cfg.compare_automatically,
        "recommended_configuration_version": cfg.recommended_configuration_version,
        "method_configuration_refs": dict(cfg.method_configuration_refs),
        "validation_warnings": list(cfg.validation_warnings),
        "configuration_version": version,
        "config_version": cfg.config_version,
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "created_by_user_id": (existing or {}).get("created_by_user_id") or actor["id"],
        "created_by_email": (existing or {}).get("created_by_email") or actor["email"],
        "updated_by_user_id": actor["id"],
        "updated_by_email": actor["email"],
    }


def _audit_diff(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "before": _logical_config(before),
        "after": _logical_config(after),
        "changed_fields": [
            key for key, value in (_logical_config(after) or {}).items()
            if (_logical_config(before) or {}).get(key) != value
        ],
    }


async def _persist_configuration(
    *,
    tenant_id: str,
    category_id: str,
    next_config: TenantCategoryMethodConfiguration,
    actor: Mapping[str, Any],
    action: str,
    summary: str,
    expected_configuration_version: int | None,
    no_op_ok: bool = True,
) -> dict[str, Any]:
    settings = await get_or_init_pricing_settings(tenant_id)
    existing = _config_from_doc(settings, category_id)
    stored = _stored_config(tenant_id=tenant_id, cfg=next_config, existing=existing, actor=actor)

    if _logical_config(existing) == _logical_config(stored):
        return existing if no_op_ok and existing else stored

    if existing and expected_configuration_version is None:
        raise StalePricingMethodConfigurationError("expected_configuration_version is required when updating an existing configuration.")
    if existing and int(existing.get("configuration_version") or 0) != int(expected_configuration_version or -1):
        raise StalePricingMethodConfigurationError()

    filter_doc: dict[str, Any] = {"tenant_id": tenant_id}
    if existing:
        filter_doc[f"{CONFIG_PATH}.{category_id}.configuration_version"] = expected_configuration_version
    else:
        filter_doc[f"{CONFIG_PATH}.{category_id}"] = {"$exists": False}

    result = await db.pricing_settings.update_one(
        filter_doc,
        {
            "$set": {
                f"{CONFIG_PATH}.{category_id}": stored,
                f"{CONFIG_PATH}_updated_at": stored["updated_at"],
                "updated_at": stored["updated_at"],
            }
        },
    )
    if result.matched_count != 1:
        raise StalePricingMethodConfigurationError()

    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=str(actor["id"]),
        actor_email=str(actor["email"]),
        action=action,
        entity_type="pricing_method_configuration",
        entity_id=category_id,
        summary=summary,
        diff=_audit_diff(existing, stored),
    )
    return stored


async def list_category_method_configurations(tenant_id: str) -> dict[str, Any]:
    settings = await get_or_init_pricing_settings(tenant_id)
    configs = settings.get(CONFIG_PATH) or {}
    return {
        "tenant_id": tenant_id,
        "items": [serialize_doc(configs[category.id]) for category in list_category_definitions() if category.id in configs],
    }


async def get_category_method_configuration(tenant_id: str, category_id: str) -> dict[str, Any] | None:
    get_category_definition(category_id)
    settings = await get_or_init_pricing_settings(tenant_id)
    return serialize_doc(_config_from_doc(settings, category_id))


async def preview_simple_setup(tenant_id: str, category_id: str) -> dict[str, Any]:
    category = get_category_definition(category_id)
    availability = await resolve_method_availability(tenant_id, category_id)
    available = set(availability["available_method_ids"])
    recommended = [mid for mid in category.recommended_simple_setup_method_ids if mid in available][:2]
    warnings: list[dict[str, str]] = []
    if len(recommended) == 1:
        warnings.append({
            "code": "single_method_available",
            "message": "Only one recommended method is currently available; no second comparison method was invented.",
        })
    if not recommended:
        warnings.append({
            "code": "no_recommended_methods_available",
            "message": "No recommended method is currently available for this tenant/category configuration.",
        })
    primary = category.recommended_primary_method_id if category.recommended_primary_method_id in recommended else (recommended[0] if recommended else None)
    return {
        "tenant_id": tenant_id,
        "category_id": category_id,
        "recommendation_version": RECOMMENDATION_VERSION,
        "recommended_method_ids": recommended,
        "recommended_primary_method_id": primary,
        "comparison_order": recommended,
        "compare_automatically": len(recommended) > 1 and category.supports_comparison,
        "warnings": warnings,
        "availability": availability,
        "mutated": False,
    }


async def apply_simple_setup(
    tenant_id: str,
    category_id: str,
    *,
    actor: Mapping[str, Any],
    expected_configuration_version: int | None = None,
    replace_advanced: bool = False,
) -> dict[str, Any]:
    existing = await get_category_method_configuration(tenant_id, category_id)
    if existing and existing.get("configuration_mode") == "advanced" and not replace_advanced:
        raise PricingMethodConfigurationError(
            "replace_advanced",
            "advanced_configuration_conflict",
            "Simple Setup cannot replace an Advanced configuration without explicit confirmation.",
            status_code=status.HTTP_409_CONFLICT,
        )
    preview = await preview_simple_setup(tenant_id, category_id)
    methods = tuple(preview["recommended_method_ids"])
    warnings = tuple(w["code"] for w in preview["warnings"])
    cfg = await _validate_configuration(
        tenant_id,
        category_id,
        methods,
        preview["recommended_primary_method_id"],
        tuple(preview["comparison_order"]),
        compare_automatically=bool(preview["compare_automatically"]),
        configuration_mode="simple",
        validation_warnings=warnings,
    )
    action = "pricing.method_config.simple.replace_advanced" if existing and existing.get("configuration_mode") == "advanced" else "pricing.method_config.simple.apply"
    summary = f"Applied Simple Setup pricing-method recommendation for '{category_id}'"
    if action.endswith("replace_advanced"):
        summary = f"Replaced Advanced pricing-method configuration with Simple Setup for '{category_id}'"
    return await _persist_configuration(
        tenant_id=tenant_id,
        category_id=category_id,
        next_config=cfg,
        actor=actor,
        action=action,
        summary=summary,
        expected_configuration_version=expected_configuration_version,
    )


async def save_advanced_setup(
    tenant_id: str,
    category_id: str,
    *,
    enabled_method_ids: list[str],
    primary_method_id: str,
    comparison_order: list[str],
    compare_automatically: bool,
    method_configuration_refs: Mapping[str, str] | None,
    actor: Mapping[str, Any],
    expected_configuration_version: int | None = None,
) -> dict[str, Any]:
    enabled = _normalize_method_ids(enabled_method_ids, "enabled_method_ids")
    primary = _normalize_single_method_id(primary_method_id, "primary_method_id")
    order = _normalize_method_ids(comparison_order or enabled_method_ids, "comparison_order")
    cfg = await _validate_configuration(
        tenant_id,
        category_id,
        enabled,
        primary,
        order,
        compare_automatically=compare_automatically,
        configuration_mode="advanced",
        method_configuration_refs=method_configuration_refs,
    )
    return await _persist_configuration(
        tenant_id=tenant_id,
        category_id=category_id,
        next_config=cfg,
        actor=actor,
        action="pricing.method_config.advanced.save",
        summary=f"Saved Advanced pricing-method configuration for '{category_id}'",
        expected_configuration_version=expected_configuration_version,
    )


async def restore_recommended_configuration(
    tenant_id: str,
    category_id: str,
    *,
    actor: Mapping[str, Any],
    expected_configuration_version: int | None = None,
    replace_advanced: bool = False,
) -> dict[str, Any]:
    existing = await get_category_method_configuration(tenant_id, category_id)
    if existing and existing.get("configuration_mode") == "advanced" and not replace_advanced:
        raise PricingMethodConfigurationError(
            "replace_advanced",
            "advanced_configuration_conflict",
            "Restoring recommendations cannot replace an Advanced configuration without explicit confirmation.",
            status_code=status.HTTP_409_CONFLICT,
        )
    preview = await preview_simple_setup(tenant_id, category_id)
    cfg = await _validate_configuration(
        tenant_id,
        category_id,
        tuple(preview["recommended_method_ids"]),
        preview["recommended_primary_method_id"],
        tuple(preview["comparison_order"]),
        compare_automatically=bool(preview["compare_automatically"]),
        configuration_mode="simple",
        validation_warnings=tuple(w["code"] for w in preview["warnings"]),
    )
    return await _persist_configuration(
        tenant_id=tenant_id,
        category_id=category_id,
        next_config=cfg,
        actor=actor,
        action="pricing.method_config.restore_recommendations",
        summary=f"Restored recommended pricing-method configuration for '{category_id}'",
        expected_configuration_version=expected_configuration_version,
    )


async def list_category_method_configuration_audit(tenant_id: str, category_id: str, limit: int = 100) -> dict[str, Any]:
    get_category_definition(category_id)
    items = await list_audit(
        tenant_id=tenant_id,
        entity_type="pricing_method_configuration",
        entity_id=category_id,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


def raise_http(exc: Exception) -> None:
    if isinstance(exc, PricingMethodConfigurationError):
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())
    if isinstance(exc, PricingContractError):
        raise HTTPException(status_code=404, detail={"field": "category_id", "code": "unknown_category", "message": str(exc)})
    raise exc
