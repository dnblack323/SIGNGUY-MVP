"""Pure portable pricing-configuration export and preview contracts."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .config import CATEGORY_IDS
from .contracts import (
    CATEGORY_CONFIGURATION_VERSION,
    CONTRACT_SCHEMA_VERSION,
    ENGINE_VERSION,
    FORMULA_VERSION_UNMIGRATED,
)
from .money import ROUNDING_POLICY_ID, decimal_dollars_to_cents
from .validation import ContractValidationError, validate_integer, validate_decimal


PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID = "pricing_portable_configuration_9is"
PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION = "pricing_portable_configuration_9is_v1"
PORTABLE_CONFIGURATION_GENERATOR_ID = "pricing_portable_configuration_export_9is_v1"
SAAS_ENGINE_CONFIGURATION_CONTRACT_VERSION = "pricing_engine_saas_configuration_9iq_v1"
SAAS_CONFIGURATION_ADAPTER_ID = "saas_configuration_adapter_9iq_v1"

_FORBIDDEN_KEY_PARTS = {
    "_id",
    "tenant_id",
    "tenant",
    "user_id",
    "user",
    "email",
    "customer",
    "db",
    "database",
    "collection",
    "request",
    "auth",
    "permission",
    "permissions",
    "audit",
    "audit_service",
    "entitlement",
    "entitlements",
    "subscription",
    "stripe",
    "license",
    "licensing",
    "secret",
    "token",
    "api_key",
    "environment",
}

_PERCENT_KEY_MARKERS = ("percent", "margin")
_MONEY_KEY_MARKERS = (
    "amount",
    "charge",
    "cost",
    "fee",
    "minimum",
    "price",
    "pricing",
)
_RATE_KEY_MARKERS = ("rate", "hourly", "per_sqft", "per_sqin", "per_hour", "per_minute", "per_each")
_DECIMAL_KEY_MARKERS = (
    "area",
    "coverage",
    "factor",
    "height",
    "hour",
    "inch",
    "margin",
    "markup",
    "multiplier",
    "quantity",
    "sqft",
    "sqin",
    "tier",
    "time",
    "waste",
    "weight",
    "width",
)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def serialize_portable_configuration(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic JSON-safe portable configuration data."""

    return _canonical(validate_portable_configuration(configuration))


def _safe_decimal(value: Any, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, (int, str)):
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation as exc:
            raise ContractValidationError(f"{field_name} must be decimal-compatible") from exc
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ContractValidationError(f"{field_name} must be finite")
        decimal_value = Decimal(str(value))
    else:
        raise ContractValidationError(f"{field_name} must be decimal-compatible")
    if not decimal_value.is_finite():
        raise ContractValidationError(f"{field_name} must be finite")
    return decimal_value


def _decimal_string(value: Any, *, field_name: str, max_scale: int = 6) -> str:
    decimal_value = validate_decimal(
        str(_safe_decimal(value, field_name=field_name)),
        field_name=field_name,
        max_scale=max_scale,
        max_precision=18,
        minimum=Decimal("0"),
    )
    return format(decimal_value, f".{max_scale}f")


def _basis_points(value: Any, *, field_name: str) -> int:
    decimal_value = _safe_decimal(value, field_name=field_name)
    bps = int((decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return validate_integer(bps, field_name=field_name, minimum=0, maximum=100000)


def _money_cents(value: Any, *, field_name: str) -> int:
    decimal_value = _safe_decimal(value, field_name=field_name)
    if decimal_value < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return decimal_dollars_to_cents(str(decimal_value)).to_json()


def _field_unit(path: tuple[str, ...], key: str) -> str:
    text = ".".join((*path, key)).lower()
    if "sqin" in text:
        return "sqin"
    if "sqft" in text or "square_foot" in text:
        return "sqft"
    if "hour" in text:
        return "hour"
    if "minute" in text:
        return "minute"
    if "inch" in text or "width" in text or "height" in text:
        return "inch"
    if "mile" in text:
        return "mile"
    if "quantity" in text:
        return "each"
    if "markup" in text or "multiplier" in text or "factor" in text:
        return "ratio"
    return "unit"


def _rate_unit(path: tuple[str, ...], key: str) -> str:
    text = ".".join((*path, key)).lower()
    if "sqin" in text:
        return "USD_per_sqin"
    if "sqft" in text or "square_foot" in text:
        return "USD_per_sqft"
    if "hour" in text or "hourly" in text:
        return "USD_per_hour"
    if "minute" in text:
        return "USD_per_minute"
    if "mile" in text:
        return "USD_per_mile"
    return "USD_per_each"


def _is_forbidden_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in _FORBIDDEN_KEY_PARTS or any(part in normalized for part in _FORBIDDEN_KEY_PARTS)


def _is_percent_key(text: str) -> bool:
    return any(marker in text for marker in _PERCENT_KEY_MARKERS)


def _is_money_key(text: str) -> bool:
    return any(marker in text for marker in _MONEY_KEY_MARKERS) and not any(marker in text for marker in _RATE_KEY_MARKERS)


def _is_rate_key(text: str) -> bool:
    return any(marker in text for marker in _RATE_KEY_MARKERS)


def _is_decimal_key(text: str) -> bool:
    return any(marker in text for marker in _DECIMAL_KEY_MARKERS)


def _portable_leaf(value: Any, *, path: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _is_forbidden_key(key):
                continue
            normalized[key] = _portable_leaf(raw_value, path=(*path, key))
        return normalized
    if isinstance(value, list):
        return [_portable_leaf(item, path=path) for item in value]
    if isinstance(value, tuple):
        return [_portable_leaf(item, path=path) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return deepcopy(value)
    if isinstance(value, (int, float, Decimal)):
        key = path[-1] if path else "value"
        text = ".".join(path).lower()
        if _is_percent_key(text):
            return {"contract": "basis_points", "basis_points": _basis_points(value, field_name=text)}
        if _is_rate_key(text):
            return {
                "contract": "decimal_rate",
                "value": _decimal_string(value, field_name=text),
                "unit": _rate_unit(path[:-1], key),
            }
        if _is_money_key(text):
            return {"contract": "money_cents", "amount_cents": _money_cents(value, field_name=text), "currency": "USD"}
        if isinstance(value, int):
            return validate_integer(value, field_name=text or "integer", minimum=0)
        if isinstance(value, float) or isinstance(value, Decimal) or _is_decimal_key(text):
            return {
                "contract": "decimal_value",
                "value": _decimal_string(value, field_name=text),
                "unit": _field_unit(path[:-1], key),
            }
        return validate_integer(value, field_name=text or "integer", minimum=0)
    raise ContractValidationError(f"Unsupported portable value at {'.'.join(path)}")


def _legacy_leaf(value: Any) -> Any:
    if isinstance(value, Mapping) and "contract" in value:
        contract = value.get("contract")
        if contract == "money_cents":
            return validate_integer(value.get("amount_cents"), field_name="amount_cents", minimum=0) / 100
        if contract == "basis_points":
            return validate_integer(value.get("basis_points"), field_name="basis_points", minimum=0, maximum=100000) / 100
        if contract in {"decimal_rate", "decimal_value"}:
            decimal_value = validate_decimal(
                value.get("value"),
                field_name="decimal_value",
                max_scale=6,
                max_precision=18,
                minimum=Decimal("0"),
            )
            unit = value.get("unit")
            if not isinstance(unit, str) or not unit:
                raise ContractValidationError("decimal unit must be a non-empty string")
            return float(decimal_value)
        raise ContractValidationError(f"Unsupported portable value contract: {contract}")
    if isinstance(value, Mapping):
        return {str(key): _legacy_leaf(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_legacy_leaf(item) for item in value]
    return deepcopy(value)


def _validate_leaf(value: Any, *, path: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        if "contract" in value:
            return _validate_typed_leaf(value, path=path)
        return {str(key): _validate_leaf(item, path=(*path, str(key))) for key, item in value.items()}
    if isinstance(value, list):
        return [_validate_leaf(item, path=path) for item in value]
    if isinstance(value, float):
        raise ContractValidationError(f"{'.'.join(path)} must not contain binary floats")
    if isinstance(value, bool) or value is None or isinstance(value, str) or isinstance(value, int):
        return deepcopy(value)
    raise ContractValidationError(f"Unsupported portable value at {'.'.join(path)}")


def _validate_typed_leaf(value: Mapping[str, Any], *, path: tuple[str, ...]) -> dict[str, Any]:
    contract = value.get("contract")
    if contract == "money_cents":
        return {
            "contract": "money_cents",
            "amount_cents": validate_integer(value.get("amount_cents"), field_name="amount_cents", minimum=0),
            "currency": value.get("currency") or "USD",
        }
    if contract == "basis_points":
        return {
            "contract": "basis_points",
            "basis_points": validate_integer(value.get("basis_points"), field_name="basis_points", minimum=0, maximum=100000),
        }
    if contract in {"decimal_rate", "decimal_value"}:
        decimal_value = validate_decimal(
            value.get("value"),
            field_name="decimal_value",
            max_scale=6,
            max_precision=18,
            minimum=Decimal("0"),
        )
        unit = value.get("unit")
        if not isinstance(unit, str) or not unit:
            raise ContractValidationError("decimal unit must be a non-empty string")
        return {"contract": str(contract), "value": format(decimal_value, ".6f"), "unit": unit}
    raise ContractValidationError(f"Unsupported portable value contract at {'.'.join(path)}")


def build_portable_configuration(
    *,
    category_configurations: Mapping[str, Mapping[str, Any]],
    settings_version_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sanitized, versioned portable configuration from SaaS adapter output."""

    if set(category_configurations) != set(CATEGORY_IDS):
        missing = sorted(set(CATEGORY_IDS) - set(category_configurations))
        unknown = sorted(set(category_configurations) - set(CATEGORY_IDS))
        raise ContractValidationError(f"Portable configuration must include exactly all categories; missing={missing}; unknown={unknown}")

    portable_categories: dict[str, Any] = {}
    for category in CATEGORY_IDS:
        adapter_config = deepcopy(dict(category_configurations[category]))
        if adapter_config.get("contract_version") != SAAS_ENGINE_CONFIGURATION_CONTRACT_VERSION:
            raise ContractValidationError(f"{category} has unsupported engine configuration contract")
        if adapter_config.get("adapter_id") != SAAS_CONFIGURATION_ADAPTER_ID:
            raise ContractValidationError(f"{category} has unsupported adapter")
        if adapter_config.get("category_id") != category:
            raise ContractValidationError(f"{category} configuration category mismatch")
        engine_settings = adapter_config.get("engine_settings")
        if not isinstance(engine_settings, Mapping):
            raise ContractValidationError(f"{category} engine_settings must be an object")
        portable_categories[category] = {
            "category_id": category,
            "adapter_contract_version": adapter_config["contract_version"],
            "adapter_id": adapter_config["adapter_id"],
            "engine_settings": _portable_leaf(engine_settings, path=("category_configurations", category, "engine_settings")),
            "lineage": _portable_leaf(adapter_config.get("lineage") or {}, path=("category_configurations", category, "lineage")),
        }

    payload = {
        "schema_id": PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID,
        "schema_version": PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION,
        "generator_id": PORTABLE_CONFIGURATION_GENERATOR_ID,
        "versions": {
            "contract_schema_version": CONTRACT_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "formula_version": FORMULA_VERSION_UNMIGRATED,
            "rounding_policy_version": ROUNDING_POLICY_ID,
            "category_configuration_version": CATEGORY_CONFIGURATION_VERSION,
        },
        "category_ids": list(CATEGORY_IDS),
        "settings_version_evidence": _portable_leaf(settings_version_evidence or {}, path=("settings_version_evidence",)),
        "category_configurations": portable_categories,
    }
    return serialize_portable_configuration(payload)


def validate_portable_configuration(configuration: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(configuration, Mapping):
        raise ContractValidationError("Portable configuration must be an object")
    payload = deepcopy(dict(configuration))
    if payload.get("schema_id") != PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID:
        raise ContractValidationError("Unsupported portable configuration schema id")
    if payload.get("schema_version") != PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION:
        raise ContractValidationError("Unsupported portable configuration schema version")
    versions = payload.get("versions")
    if not isinstance(versions, Mapping):
        raise ContractValidationError("Portable configuration versions must be an object")
    expected_versions = {
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "formula_version": FORMULA_VERSION_UNMIGRATED,
        "rounding_policy_version": ROUNDING_POLICY_ID,
        "category_configuration_version": CATEGORY_CONFIGURATION_VERSION,
    }
    for key, expected in expected_versions.items():
        if versions.get(key) != expected:
            raise ContractValidationError(f"Unsupported portable configuration {key}")
    if tuple(payload.get("category_ids") or ()) != tuple(CATEGORY_IDS):
        raise ContractValidationError("Portable configuration category_ids are unsupported")
    categories = payload.get("category_configurations")
    if not isinstance(categories, Mapping):
        raise ContractValidationError("Portable configuration category_configurations must be an object")
    if set(categories) != set(CATEGORY_IDS):
        missing = sorted(set(CATEGORY_IDS) - set(categories))
        unknown = sorted(set(categories) - set(CATEGORY_IDS))
        raise ContractValidationError(f"Portable configuration must include exactly all categories; missing={missing}; unknown={unknown}")
    normalized_categories: dict[str, Any] = {}
    for category in CATEGORY_IDS:
        category_config = categories.get(category)
        if not isinstance(category_config, Mapping):
            raise ContractValidationError(f"{category} configuration must be an object")
        if category_config.get("category_id") != category:
            raise ContractValidationError(f"{category} configuration category mismatch")
        if category_config.get("adapter_contract_version") != SAAS_ENGINE_CONFIGURATION_CONTRACT_VERSION:
            raise ContractValidationError(f"{category} adapter contract version is unsupported")
        if category_config.get("adapter_id") != SAAS_CONFIGURATION_ADAPTER_ID:
            raise ContractValidationError(f"{category} adapter id is unsupported")
        normalized_categories[category] = {
            "category_id": category,
            "adapter_contract_version": category_config["adapter_contract_version"],
            "adapter_id": category_config["adapter_id"],
            "engine_settings": _validate_leaf(category_config.get("engine_settings"), path=("category_configurations", category, "engine_settings")),
            "lineage": _validate_leaf(category_config.get("lineage") or {}, path=("category_configurations", category, "lineage")),
        }
    return {
        "schema_id": payload["schema_id"],
        "schema_version": payload["schema_version"],
        "generator_id": str(payload.get("generator_id") or ""),
        "versions": dict(expected_versions),
        "category_ids": list(CATEGORY_IDS),
        "settings_version_evidence": _validate_leaf(payload.get("settings_version_evidence") or {}, path=("settings_version_evidence",)),
        "category_configurations": normalized_categories,
    }


def deserialize_portable_configuration(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a portable config and reconstruct pure-engine settings by category."""

    payload = validate_portable_configuration(configuration)
    return {
        "configuration": payload,
        "engine_settings_by_category": {
            category: _legacy_leaf(payload["category_configurations"][category]["engine_settings"])
            for category in CATEGORY_IDS
        },
    }


def diff_portable_configurations(
    *,
    current: Mapping[str, Any],
    proposed: Mapping[str, Any],
    max_changes: int = 200,
) -> dict[str, Any]:
    current_payload = validate_portable_configuration(current)
    proposed_payload = validate_portable_configuration(proposed)
    changes: list[dict[str, Any]] = []
    counts = {"added": 0, "removed": 0, "changed": 0}

    def walk(path: tuple[str, ...], left: Any, right: Any) -> None:
        if len(changes) >= max_changes:
            return
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            keys = sorted(set(left) | set(right))
            for key in keys:
                if key not in left:
                    counts["added"] += 1
                    changes.append({"path": ".".join((*path, str(key))), "change_type": "added", "proposed": right[key]})
                elif key not in right:
                    counts["removed"] += 1
                    changes.append({"path": ".".join((*path, str(key))), "change_type": "removed", "current": left[key]})
                else:
                    walk((*path, str(key)), left[key], right[key])
                if len(changes) >= max_changes:
                    break
        elif isinstance(left, list) and isinstance(right, list):
            if left != right:
                counts["changed"] += 1
                changes.append({"path": ".".join(path), "change_type": "changed", "current": left, "proposed": right})
        elif left != right:
            counts["changed"] += 1
            changes.append({"path": ".".join(path), "change_type": "changed", "current": left, "proposed": right})

    walk(("category_configurations",), current_payload["category_configurations"], proposed_payload["category_configurations"])
    truncated = sum(counts.values()) > len(changes)
    return {
        "summary": {
            **counts,
            "total_changes": sum(counts.values()),
            "unchanged": sum(counts.values()) == 0,
            "truncated": truncated,
        },
        "changes": changes,
    }
