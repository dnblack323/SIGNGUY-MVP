"""EC9 Phase 9I-L adapter from legacy calculator results to cents-first DTOs.

The adapter accepts an already-computed legacy SaaS calculator result. It does
not call calculators, resolve tenant data, import application services, or
persist anything.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from pricing_engine.contracts import (
    ContractVersionMetadata,
    CalculationEvidenceMetadata,
    LineCalculationResult,
)
from pricing_engine.money import MoneyCents, ROUNDING_MODE, ROUNDING_POLICY_ID, RoundingEvidence
from pricing_engine.validation import ContractValidationError, parse_decimal_string


LEGACY_RESULT_COMPATIBILITY_DTO_VERSION = "pricing_engine_cents_first_compatibility_9il_v1"
LEGACY_SAAS_CALCULATOR_SOURCE_ID = "legacy_saas_calculator_v1"
LEGACY_SAAS_EXECUTION_PATH = "app.services.pricing.calculate_pricing"
FIXTURE_SCHEMA_VERSION = "pricing_fixture_v1"
FIXTURE_ENGINE_VERSION = "pricing_engine_v1"
FIXTURE_FORMULA_VERSION = "ec9_current"

_PRIMARY_MONEY_FIELDS = (
    "selling_price",
    "suggested_price",
    "true_cost",
    "profit_amount",
)
_SIGNED_MONEY_FIELDS = {
    "profit_amount",
    "minimum_adjustment",
}
_MONEY_FIELD_SUFFIXES = (
    "_cost",
    "_price",
    "_amount",
    "_charge",
    "_fee",
    "_revenue",
    "_total",
    "_minimum",
)
_NON_MONEY_FIELD_NAMES = {
    "pricing_method_used",
    "canonical_method_id",
    "selected_method_id",
    "category",
    "quantity",
}


def build_legacy_line_result(
    *,
    category_id: str,
    legacy_result: Mapping[str, Any],
    normalized_input: Mapping[str, Any] | None = None,
    adapter_source_id: str = LEGACY_SAAS_CALCULATOR_SOURCE_ID,
    execution_path: str = LEGACY_SAAS_EXECUTION_PATH,
) -> dict[str, Any]:
    """Build a JSON-safe cents-first line-result DTO from a legacy result."""

    immutable_result = deepcopy(dict(legacy_result))
    selling_price_cents = _money_cents_or_none(
        immutable_result.get("selling_price"),
        field_name="selling_price",
    )
    status = "success" if selling_price_cents is not None else "unavailable"

    versions = ContractVersionMetadata(formula_version=FIXTURE_FORMULA_VERSION)
    evidence = CalculationEvidenceMetadata(
        category_id,
        versions=versions,
        rounding=RoundingEvidence(),
        formula_source=adapter_source_id,
        warnings=_string_list(immutable_result.get("calculation_warnings") or immutable_result.get("warnings") or []),
    )
    line_result = LineCalculationResult(
        category_id,
        status=status,
        selling_price=MoneyCents.nonnegative(selling_price_cents) if selling_price_cents is not None else None,
        versions=versions,
        evidence=evidence,
    ).to_json()

    method_rows = _method_rows(immutable_result)
    selected_method_id = _selected_method_id(method_rows)
    selected_method_amount_cents = _selected_method_amount_cents(method_rows, selling_price_cents)

    line_result.update(
        {
            "dto_version": LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
            "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
            "fixture_engine_version": FIXTURE_ENGINE_VERSION,
            "formula_version": FIXTURE_FORMULA_VERSION,
            "rounding_policy_version": ROUNDING_POLICY_ID,
            "rounding": RoundingEvidence().to_json(),
            "adapter_source_id": adapter_source_id,
            "adapter_execution_path": execution_path,
            "calculation_source": "existing_legacy_saas_calculator_result",
            "legacy_result_mutated": False,
            "category_id": category_id,
            "pricing_method_used": immutable_result.get("pricing_method_used"),
            "canonical_method_id": immutable_result.get("canonical_method_id"),
            "selected_method_id": selected_method_id,
            "selected_method_amount_cents": selected_method_amount_cents,
            "suggested_price_cents": _money_cents_or_none(
                immutable_result.get("suggested_price"),
                field_name="suggested_price",
            ),
            "true_cost_cents": _money_cents_or_none(immutable_result.get("true_cost"), field_name="true_cost"),
            "profit_amount_cents": _money_cents_or_none(
                immutable_result.get("profit_amount"),
                field_name="profit_amount",
                allow_negative=True,
            ),
            "profit_margin_percent": _decimal_string_or_none(
                immutable_result.get("profit_margin_percent"),
                field_name="profit_margin_percent",
                scale=4,
            ),
            "warnings": _string_list(immutable_result.get("calculation_warnings") or immutable_result.get("warnings") or []),
            "errors": _string_list(immutable_result.get("errors") or []),
            "method_rows": method_rows,
            "breakdown_amounts": _breakdown_amounts(immutable_result),
            "component_amounts": _component_amounts(immutable_result),
            "category_details": deepcopy(immutable_result.get("detail_sections") or []),
            "legacy_source": {
                "adapter_id": adapter_source_id,
                "execution_path": execution_path,
                "legacy_result_fields": sorted(str(key) for key in immutable_result.keys()),
                "legacy_dollar_fields": [field for field in _PRIMARY_MONEY_FIELDS if field in immutable_result],
            },
            "normalized_input": deepcopy(dict(normalized_input or {})),
            "persistent_entities_created": [],
            "mutated": False,
        }
    )
    return _json_safe(line_result)


def _legacy_money_to_cents(value: Any, *, field_name: str, allow_negative: bool = False) -> int:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be a valid legacy dollar amount") from exc
    if not decimal_value.is_finite():
        raise ContractValidationError(f"{field_name} must be finite")
    if not allow_negative and decimal_value < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    cents_decimal = (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUNDING_MODE)
    cents = int(cents_decimal)
    return MoneyCents.signed(cents).to_json() if allow_negative else MoneyCents.nonnegative(cents).to_json()


def _money_cents_or_none(value: Any, *, field_name: str, allow_negative: bool = False) -> int | None:
    if value is None:
        return None
    return _legacy_money_to_cents(value, field_name=field_name, allow_negative=allow_negative)


def _decimal_string_or_none(value: Any, *, field_name: str, scale: int) -> str | None:
    if value is None:
        return None
    decimal_value = parse_decimal_string(str(value), field_name=field_name)
    quantum = Decimal("1").scaleb(-scale)
    return format(decimal_value.quantize(quantum), f".{scale}f")


def _method_rows(legacy_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(legacy_result.get("pricing_method_results") or []):
        if not isinstance(row, Mapping):
            raise ContractValidationError(f"pricing_method_results[{index}] must be an object")
        amount = row.get("amount")
        method_id = row.get("method_id") or row.get("method")
        rows.append(
            {
                "method_id": method_id,
                "selected": bool(row.get("selected")),
                "available": bool(row.get("available")),
                "amount_cents": _money_cents_or_none(
                    amount,
                    field_name=f"pricing_method_results[{index}].amount",
                ),
                "status": _string_list(row.get("status") or []),
                "warnings": _string_list(row.get("warnings") or []),
                "errors": _string_list(row.get("errors") or []),
                "source_amount_field": "pricing_method_results.amount",
            }
        )
    return rows


def _selected_method_id(method_rows: list[Mapping[str, Any]]) -> str | None:
    selected = [row.get("method_id") for row in method_rows if row.get("selected")]
    return str(selected[0]) if selected else None


def _selected_method_amount_cents(method_rows: list[Mapping[str, Any]], selling_price_cents: int | None) -> int | None:
    selected_amounts = [row.get("amount_cents") for row in method_rows if row.get("selected")]
    if selected_amounts:
        return selected_amounts[0]
    return selling_price_cents


def _breakdown_amounts(legacy_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for index, row in enumerate(legacy_result.get("breakdown") or []):
        if not isinstance(row, Mapping):
            raise ContractValidationError(f"breakdown[{index}] must be an object")
        mapped.append(
            {
                "label": row.get("label"),
                "amount_cents": _money_cents_or_none(
                    row.get("amount"),
                    field_name=f"breakdown[{index}].amount",
                    allow_negative=_breakdown_allows_negative(row),
                ),
                "source_amount_field": "breakdown.amount",
            }
        )
    return mapped


def _component_amounts(legacy_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    amounts: list[dict[str, Any]] = []
    for field, value in legacy_result.items():
        if not _is_top_level_money_field(field, value):
            continue
        amounts.append(
            {
                "field": str(field),
                "amount_cents": _money_cents_or_none(
                    value,
                    field_name=str(field),
                    allow_negative=field in _SIGNED_MONEY_FIELDS or str(field).endswith("_adjustment"),
                ),
                "source_amount_field": str(field),
            }
        )
    return amounts


def _is_top_level_money_field(field: Any, value: Any) -> bool:
    if value is None or isinstance(value, bool) or isinstance(value, (Mapping, list, tuple)):
        return False
    key = str(field)
    if key in _NON_MONEY_FIELD_NAMES or key.endswith("_percent") or key.endswith("_rate") or "_per_" in key:
        return False
    return key in _PRIMARY_MONEY_FIELDS or key.endswith(_MONEY_FIELD_SUFFIXES)


def _breakdown_allows_negative(row: Mapping[str, Any]) -> bool:
    label = str(row.get("label") or "").lower()
    return any(token in label for token in ("profit", "adjustment", "discount", "credit", "reversal"))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [str(value)]
    try:
        items = list(value)
    except TypeError:
        return [str(value)]
    return [str(item) for item in items]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [_json_safe(child) for child in value]
    if isinstance(value, Decimal):
        return str(value)
    return value
