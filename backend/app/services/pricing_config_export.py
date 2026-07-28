"""EC9 Phase 9I-S portable pricing configuration export/preview service."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ..core.db import db
from pricing_engine.config import CATEGORY_IDS
from pricing_engine.config_export import (
    PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID,
    PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION,
    build_portable_configuration,
    deserialize_portable_configuration,
    diff_portable_configurations,
    validate_portable_configuration,
)
from pricing_engine.validation import ContractValidationError

from .pricing_engine_config_adapter import build_line_engine_configuration
from .starter_defaults import STARTER_DEFAULT_VERSION, build_starter_pack


async def _read_settings_without_initializing(tenant_id: str) -> dict[str, Any]:
    doc = await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if doc:
        return deepcopy(doc)
    starter = build_starter_pack()
    starter["starter_default_version"] = starter.get("starter_default_version") or STARTER_DEFAULT_VERSION
    return starter


def _version_evidence(settings: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "starter_default_version": settings.get("starter_default_version") or STARTER_DEFAULT_VERSION,
        "settings_updated_at": settings.get("updated_at"),
        "category_method_configuration_versions": {
            category: (settings.get("category_method_configurations") or {}).get(category, {}).get("configuration_version")
            for category in CATEGORY_IDS
        },
    }


def _build_category_configurations(settings: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        category: build_line_engine_configuration(settings=settings, category=category)
        for category in CATEGORY_IDS
    }


async def export_portable_pricing_configuration(tenant_id: str) -> dict[str, Any]:
    """Export the tenant's normalized calculator configuration without writes."""

    settings = await _read_settings_without_initializing(tenant_id)
    return build_portable_configuration(
        category_configurations=_build_category_configurations(settings),
        settings_version_evidence=_version_evidence(settings),
    )


async def preview_portable_pricing_configuration_import(tenant_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and compare an uploaded config without applying or persisting it."""

    candidate = payload.get("configuration") if isinstance(payload.get("configuration"), Mapping) else payload
    errors: list[dict[str, str]] = []
    try:
        proposed = validate_portable_configuration(candidate)
        deserialize_portable_configuration(proposed)
    except ContractValidationError as exc:
        return {
            "schema_id": PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID,
            "schema_version": PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION,
            "valid": False,
            "compatible": False,
            "preview_only": True,
            "applied": False,
            "calculation_ready": False,
            "category_coverage": {"expected": list(CATEGORY_IDS), "provided": []},
            "errors": [{"field": "configuration", "message": str(exc)}],
            "warnings": [],
            "comparison": None,
        }

    current = await export_portable_pricing_configuration(tenant_id)
    comparison = diff_portable_configurations(current=current, proposed=proposed)
    return {
        "schema_id": proposed["schema_id"],
        "schema_version": proposed["schema_version"],
        "valid": True,
        "compatible": True,
        "preview_only": True,
        "applied": False,
        "calculation_ready": True,
        "category_coverage": {
            "expected": list(CATEGORY_IDS),
            "provided": list((proposed.get("category_configurations") or {}).keys()),
            "complete": set((proposed.get("category_configurations") or {}).keys()) == set(CATEGORY_IDS),
        },
        "errors": errors,
        "warnings": [],
        "comparison": comparison,
    }
