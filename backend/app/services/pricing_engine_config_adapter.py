"""SaaS-to-pure-pricing-engine configuration adapter.

Phase 9I-Q keeps tenant settings, reference lookup, permissions, persistence,
and audits in the SaaS layer. This adapter converts a tenant-scoped pricing
settings document plus already-resolved references into the narrow plain-data
shape consumed by ``pricing_engine.line_engine``.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .starter_defaults import CATEGORY_IDS, STARTER_DEFAULT_VERSION, build_starter_pack


SAAS_CONFIGURATION_ADAPTER_ID = "saas_configuration_adapter_9iq_v1"
ENGINE_CONFIGURATION_CONTRACT_VERSION = "pricing_engine_saas_configuration_9iq_v1"

SAAS_ONLY_KEYS = {
    "_id",
    "tenant_id",
    "user_id",
    "actor_user_id",
    "actor_email",
    "permissions",
    "permission",
    "db",
    "database",
    "request",
    "router",
    "audit",
    "audit_service",
    "entitlements",
    "license",
    "licensing",
}


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Deep-copy a mapping while removing SaaS-only transport fields."""

    cleaned: dict[str, Any] = {}
    for key, raw in dict(value or {}).items():
        if key in SAAS_ONLY_KEYS:
            continue
        if isinstance(raw, Mapping):
            cleaned[key] = _clean_mapping(raw)
        elif isinstance(raw, list):
            cleaned[key] = [
                _clean_mapping(item) if isinstance(item, Mapping) else deepcopy(item)
                for item in raw
            ]
        else:
            cleaned[key] = deepcopy(raw)
    return cleaned


def _merge_defaults(starter_values: Mapping[str, Any], stored_values: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(dict(starter_values or {}))
    merged.update(_clean_mapping(stored_values))
    return merged


def _selected_materials(
    *,
    materials: Mapping[str, Any],
    starter_materials: Mapping[str, Any],
    category_defaults: Mapping[str, Any],
    material_key: str | None,
    material_profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if material_profile:
        return {}
    selected_key = material_key or category_defaults.get("default_material")
    if not selected_key:
        return {}
    source = materials if selected_key in materials else starter_materials
    if selected_key not in source:
        return {}
    return {str(selected_key): _clean_mapping(source.get(selected_key) or {})}


def _field_sources_for_category(field_sources: Mapping[str, Any], category: str) -> dict[str, Any]:
    category_prefix = f"category_defaults.{category}."
    method_prefix = f"category_method_configurations.{category}."
    return {
        str(key): deepcopy(value)
        for key, value in dict(field_sources or {}).items()
        if str(key).startswith("shop_defaults.")
        or str(key).startswith(category_prefix)
        or str(key).startswith(method_prefix)
    }


def _reference_lineage(
    *,
    material_profile: Mapping[str, Any] | None,
    pricing_components: list[Mapping[str, Any]] | None,
    saved_item: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "material_profile": (
            {
                "id": material_profile.get("id"),
                "material_id": material_profile.get("material_id"),
                "active": material_profile.get("active", True),
            }
            if material_profile
            else None
        ),
        "pricing_components": [
            {
                "id": component.get("id"),
                "key": component.get("key"),
                "charge_type": component.get("charge_type"),
                "active": component.get("active", True),
            }
            for component in pricing_components or []
        ],
        "saved_item": (
            {
                "id": saved_item.get("id"),
                "category": saved_item.get("category"),
                "default_pricing_method": saved_item.get("default_pricing_method"),
                "active": saved_item.get("active", True),
            }
            if saved_item
            else None
        ),
    }


def build_line_engine_configuration(
    *,
    settings: Mapping[str, Any],
    category: str,
    material_key: str | None = None,
    material_profile: Mapping[str, Any] | None = None,
    pricing_components: list[Mapping[str, Any]] | None = None,
    saved_item: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized plain data for the pure line engine.

    The returned ``engine_settings`` intentionally has no tenant id, Mongo id,
    request object, permission object, audit handle, entitlement data, or
    unresolved references. It contains only the selected category defaults,
    shop defaults, and formula-required legacy material row.
    """

    if category not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {category}")

    source = deepcopy(dict(settings or {}))
    starter = build_starter_pack()
    source_categories = source.get("category_defaults") or {}
    source_category = source_categories.get(category) or {}
    starter_category = (starter.get("category_defaults") or {}).get(category) or {}
    category_defaults = _merge_defaults(starter_category, source_category)
    shop_defaults = _merge_defaults(starter.get("shop_defaults") or {}, source.get("shop_defaults") or {})
    source_materials = _clean_mapping(source.get("materials") or {})
    starter_materials = _clean_mapping(starter.get("materials") or {})
    method_configuration = _clean_mapping((source.get("category_method_configurations") or {}).get(category) or {})

    engine_settings = {
        "shop_defaults": shop_defaults,
        "category_defaults": {category: category_defaults},
        "materials": _selected_materials(
            materials=source_materials,
            starter_materials=starter_materials,
            category_defaults=category_defaults,
            material_key=material_key,
            material_profile=material_profile,
        ),
    }

    return {
        "contract_version": ENGINE_CONFIGURATION_CONTRACT_VERSION,
        "adapter_id": SAAS_CONFIGURATION_ADAPTER_ID,
        "category_id": category,
        "engine_settings": engine_settings,
        "lineage": {
            "settings_updated_at": source.get("updated_at"),
            "starter_default_version": source.get("starter_default_version") or STARTER_DEFAULT_VERSION,
            "category_method_configuration_version": method_configuration.get("configuration_version"),
            "field_sources": _field_sources_for_category(source.get("field_sources") or {}, category),
            "reference_lineage": _reference_lineage(
                material_profile=material_profile,
                pricing_components=pricing_components,
                saved_item=saved_item,
            ),
        },
    }


def public_configuration_lineage(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Return response/snapshot-safe adapter evidence without formulas."""

    return {
        "contract_version": configuration.get("contract_version"),
        "adapter_id": configuration.get("adapter_id"),
        "category_id": configuration.get("category_id"),
        **deepcopy(dict(configuration.get("lineage") or {})),
    }
