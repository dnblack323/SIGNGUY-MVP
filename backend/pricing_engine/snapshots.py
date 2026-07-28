"""EC9 Phase 9I-N pricing snapshot money contracts and legacy readers.

Pure helpers only. This module does not import FastAPI, MongoDB, app
services, tenant models, or live calculator code.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .adapters import (
    LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
    LEGACY_SAAS_CALCULATOR_SOURCE_ID,
    build_legacy_line_result,
)
from .contracts import CATEGORY_IDS
from .money import ROUNDING_MODE, ROUNDING_POLICY_ID, MoneyCents
from .validation import ContractValidationError


PRICING_ENGINE_RESULT_FIELD = "pricing_engine_result"
PRICING_SNAPSHOT_SCHEMA_FIELD = "pricing_snapshot_schema_version"
PRICING_SNAPSHOT_SCHEMA_VERSION = "pricing_snapshot_money_contract_9in_v1"
LEGACY_SNAPSHOT_READER_ID = "legacy_pricing_snapshot_reader_9in_v1"

_DOLLAR_FIELDS = (
    "calculated_unit_price_dollars",
    "selected_selling_price_dollars",
    "suggested_price_dollars",
    "true_cost_dollars",
    "material_cost_dollars",
    "labor_cost_dollars",
    "design_cost_dollars",
    "install_cost_dollars",
    "overhead_cost_dollars",
)
_CALC_RESULT_DOLLAR_FIELDS = (
    "selling_price",
    "suggested_price",
    "true_cost",
    "material_cost",
    "labor_cost",
    "design_cost",
    "install_cost",
    "overhead_cost",
)


def validate_nonnegative_cents(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    if not isinstance(value, int):
        raise ContractValidationError(f"{field_name} must be integer cents")
    return MoneyCents.nonnegative(value).to_json()


def validate_signed_cents(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    if not isinstance(value, int):
        raise ContractValidationError(f"{field_name} must be integer cents")
    return MoneyCents.signed(value).to_json()


def legacy_dollars_to_cents(value: Any, *, field_name: str, allow_negative: bool = False) -> int:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be a valid legacy dollar amount") from exc
    if not amount.is_finite():
        raise ContractValidationError(f"{field_name} must be finite")
    if not allow_negative and amount < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    cents = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUNDING_MODE))
    return validate_signed_cents(cents, field_name=field_name) if allow_negative else validate_nonnegative_cents(cents, field_name=field_name)


def successful_pricing_engine_result(calc_result: Mapping[str, Any], *, result_field: str = PRICING_ENGINE_RESULT_FIELD) -> dict[str, Any]:
    engine_result = calc_result.get(result_field)
    if not isinstance(engine_result, Mapping):
        raise ContractValidationError("Calculated snapshot requires pricing_engine_result")
    normalized = deepcopy(dict(engine_result))
    if normalized.get("status") != "success":
        raise ContractValidationError("Calculated snapshot requires a successful pricing_engine_result")
    cents = validate_nonnegative_cents(
        normalized.get("selling_price_cents"),
        field_name="pricing_engine_result.selling_price_cents",
    )
    normalized["selling_price_cents"] = cents
    normalized.setdefault("rounding_policy_version", ROUNDING_POLICY_ID)
    normalized.setdefault("adapter_source_id", LEGACY_SAAS_CALCULATOR_SOURCE_ID)
    normalized.setdefault("legacy_source", {}).setdefault("stored_normalized", True)
    return normalized


def normalize_calculated_snapshot_fields(calc_result: Mapping[str, Any]) -> dict[str, Any]:
    engine_result = successful_pricing_engine_result(calc_result)
    return {
        PRICING_SNAPSHOT_SCHEMA_FIELD: PRICING_SNAPSHOT_SCHEMA_VERSION,
        PRICING_ENGINE_RESULT_FIELD: engine_result,
        "calculated_selling_price_cents": validate_nonnegative_cents(
            engine_result["selling_price_cents"],
            field_name="pricing_engine_result.selling_price_cents",
        ),
        "suggested_price_cents_authoritative": _optional_nonnegative_cents(
            engine_result.get("suggested_price_cents"),
            field_name="pricing_engine_result.suggested_price_cents",
        ),
        "true_cost_cents": _optional_nonnegative_cents(
            engine_result.get("true_cost_cents"),
            field_name="pricing_engine_result.true_cost_cents",
        ),
        "profit_amount_cents": _optional_signed_cents(
            engine_result.get("profit_amount_cents"),
            field_name="pricing_engine_result.profit_amount_cents",
        ),
        "selected_method_amount_cents": _optional_nonnegative_cents(
            engine_result.get("selected_method_amount_cents"),
            field_name="pricing_engine_result.selected_method_amount_cents",
        ),
        "method_amounts_cents": _copy_amount_rows(engine_result.get("method_rows") or []),
        "breakdown_amounts_cents": _copy_amount_rows(engine_result.get("breakdown_amounts") or [], allow_negative=True),
        "component_amounts_cents": _copy_component_amounts(engine_result.get("component_amounts") or []),
        "rounding_policy_version": engine_result.get("rounding_policy_version") or ROUNDING_POLICY_ID,
        "pricing_engine_dto_version": engine_result.get("dto_version"),
        "pricing_engine_adapter_source": engine_result.get("adapter_source_id"),
        "pricing_engine_adapter_execution_path": engine_result.get("adapter_execution_path"),
        "pricing_engine_calculation_source": engine_result.get("calculation_source"),
        "legacy_calculator_source": LEGACY_SAAS_CALCULATOR_SOURCE_ID,
        "decimal_rate_evidence": decimal_rate_evidence(calc_result),
    }


def normalize_manual_snapshot_fields(*, unit_price_cents: Any) -> dict[str, Any]:
    return {
        PRICING_SNAPSHOT_SCHEMA_FIELD: PRICING_SNAPSHOT_SCHEMA_VERSION,
        "manual_authoritative_unit_price_cents": validate_nonnegative_cents(
            unit_price_cents,
            field_name="unit_price_cents",
        ),
        PRICING_ENGINE_RESULT_FIELD: None,
        "rounding_policy_version": ROUNDING_POLICY_ID,
    }


def selected_final_price_cents(
    *,
    calculated_cents: Any | None = None,
    override_cents: Any | None = None,
    manual_cents: Any | None = None,
) -> int:
    if override_cents is not None:
        return validate_nonnegative_cents(override_cents, field_name="override_unit_price_cents")
    if manual_cents is not None:
        return validate_nonnegative_cents(manual_cents, field_name="manual_price_cents")
    return validate_nonnegative_cents(calculated_cents, field_name="calculated_selling_price_cents")


def read_embedded_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    return _read_snapshot(snapshot, snapshot_kind="embedded")


def read_snapshot_record(record: Mapping[str, Any] | None) -> dict[str, Any]:
    return _read_snapshot(record, snapshot_kind="record")


def decimal_rate_evidence(calc_result: Mapping[str, Any]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    _append_decimal(evidence, "quantity", calc_result.get("quantity"), "each")
    _append_decimal(evidence, "width_inches", calc_result.get("width_inches"), "in")
    _append_decimal(evidence, "height_inches", calc_result.get("height_inches"), "in")
    _append_decimal(evidence, "area_sqft_total", calc_result.get("area_sqft_total"), "sqft")
    _append_decimal(evidence, "profit_margin_percent", calc_result.get("profit_margin_percent"), "percent")
    for key in _CALC_RESULT_DOLLAR_FIELDS:
        if key in calc_result:
            unit = "USD"
            if key.endswith("_cost") or key.endswith("_price"):
                _append_decimal(evidence, key, calc_result.get(key), unit)
    return evidence


def _read_snapshot(snapshot: Mapping[str, Any] | None, *, snapshot_kind: str) -> dict[str, Any]:
    doc = deepcopy(dict(snapshot or {}))
    if not doc:
        return doc
    try:
        if doc.get(PRICING_ENGINE_RESULT_FIELD) is None and _is_manual_snapshot(doc):
            cents = _manual_snapshot_cents(doc)
            doc["snapshot_money_authority"] = _authority(
                cents=cents,
                source_field="manual_integer_cents",
                stored_normalized=doc.get(PRICING_SNAPSHOT_SCHEMA_FIELD) == PRICING_SNAPSHOT_SCHEMA_VERSION,
                snapshot_kind=snapshot_kind,
            )
            doc["historical_selling_price_cents"] = cents
            return doc

        authority = _calculated_snapshot_authority(doc, snapshot_kind=snapshot_kind)
        doc[PRICING_ENGINE_RESULT_FIELD] = authority
        doc["historical_selling_price_cents"] = authority["selling_price_cents"]
        doc.setdefault(PRICING_SNAPSHOT_SCHEMA_FIELD, doc.get(PRICING_SNAPSHOT_SCHEMA_FIELD))
    except ContractValidationError as exc:
        doc["pricing_snapshot_compatibility_error"] = str(exc)
    return doc


def _calculated_snapshot_authority(doc: Mapping[str, Any], *, snapshot_kind: str) -> dict[str, Any]:
    stored = doc.get(PRICING_ENGINE_RESULT_FIELD)
    if isinstance(stored, Mapping):
        engine = successful_pricing_engine_result({PRICING_ENGINE_RESULT_FIELD: stored})
        engine.setdefault("snapshot_compatibility", {}).update({
            "source_field": PRICING_ENGINE_RESULT_FIELD,
            "stored_normalized": True,
            "snapshot_kind": snapshot_kind,
        })
        return engine

    for field in ("calculated_selling_price_cents", "selected_final_price_cents", "suggested_price_cents", "calculated_unit_price_cents"):
        value = doc.get(field)
        if value is None:
            continue
        cents = validate_nonnegative_cents(value, field_name=field)
        warnings = _legacy_disagreement_warnings(doc, cents)
        return _minimal_engine_result(
            doc=doc,
            cents=cents,
            source_field=field,
            warnings=warnings,
            snapshot_kind=snapshot_kind,
        )

    for field in ("calculated_unit_price_dollars", "selected_selling_price_dollars", "suggested_price_dollars"):
        if doc.get(field) is None:
            continue
        legacy_result = _legacy_result_from_snapshot(doc, selling_price_field=field)
        engine = build_legacy_line_result(
            category_id=str(doc.get("category") or ""),
            legacy_result=legacy_result,
            normalized_input=doc.get("category_inputs") or {},
            adapter_source_id=LEGACY_SNAPSHOT_READER_ID,
            execution_path=f"stored_{snapshot_kind}_pricing_snapshot_legacy_fields",
        )
        engine.setdefault("legacy_source", {})["stored_normalized"] = False
        engine.setdefault("legacy_source", {})["source_field"] = field
        engine.setdefault("snapshot_compatibility", {}).update({
            "source_field": field,
            "stored_normalized": False,
            "snapshot_kind": snapshot_kind,
        })
        return engine

    raise ContractValidationError("Snapshot has no trustworthy historical selling price")


def _minimal_engine_result(
    *,
    doc: Mapping[str, Any],
    cents: int,
    source_field: str,
    warnings: list[str] | None = None,
    snapshot_kind: str,
) -> dict[str, Any]:
    category = str(doc.get("category") or "custom")
    if category not in CATEGORY_IDS:
        category = "custom"
    return {
        "dto_version": LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
        "snapshot_schema_version": PRICING_SNAPSHOT_SCHEMA_VERSION,
        "category_id": category,
        "status": "success",
        "selling_price_cents": cents,
        "selected_method_amount_cents": cents,
        "true_cost_cents": None,
        "suggested_price_cents": None,
        "profit_amount_cents": None,
        "pricing_method_used": None,
        "canonical_method_id": None,
        "selected_method_id": None,
        "method_rows": [],
        "breakdown_amounts": [],
        "component_amounts": [],
        "warnings": list(warnings or []),
        "errors": [],
        "rounding_policy_version": ROUNDING_POLICY_ID,
        "adapter_source_id": LEGACY_SNAPSHOT_READER_ID,
        "adapter_execution_path": f"stored_{snapshot_kind}_pricing_snapshot_integer_cents",
        "calculation_source": "legacy_pricing_snapshot_read_compatibility",
        "legacy_source": {
            "adapter_id": LEGACY_SNAPSHOT_READER_ID,
            "source_field": source_field,
            "stored_normalized": False,
        },
        "snapshot_compatibility": {
            "source_field": source_field,
            "stored_normalized": False,
            "snapshot_kind": snapshot_kind,
        },
        "persistent_entities_created": [],
        "mutated": False,
    }


def _authority(*, cents: int, source_field: str, stored_normalized: bool, snapshot_kind: str) -> dict[str, Any]:
    return {
        "source_field": source_field,
        "stored_normalized": bool(stored_normalized),
        "snapshot_kind": snapshot_kind,
        "selling_price_cents": cents,
        "rounding_policy_version": ROUNDING_POLICY_ID,
        "mutated": False,
    }


def _manual_snapshot_cents(doc: Mapping[str, Any]) -> int:
    for field in ("manual_authoritative_unit_price_cents", "unit_price_cents", "override_unit_price_cents", "manual_price_cents", "selected_final_price_cents"):
        value = doc.get(field)
        if value is not None:
            return validate_nonnegative_cents(value, field_name=field)
    for field in ("manual_price_dollars", "selected_selling_price_dollars"):
        if doc.get(field) is not None:
            return legacy_dollars_to_cents(doc.get(field), field_name=field)
    raise ContractValidationError("Manual snapshot has no trustworthy historical price")


def _is_manual_snapshot(doc: Mapping[str, Any]) -> bool:
    source = str(doc.get("source") or "").lower()
    method = str(doc.get("pricing_method") or "").lower()
    return source in {"manual", "user_entered"} or method == "manual" or doc.get("selected_price_source") == "manual"


def _legacy_result_from_snapshot(doc: Mapping[str, Any], *, selling_price_field: str) -> dict[str, Any]:
    result = {
        "category": doc.get("category") or "custom",
        "selling_price": doc.get(selling_price_field),
        "suggested_price": doc.get("suggested_price_dollars") or doc.get(selling_price_field),
        "true_cost": doc.get("true_cost_dollars"),
        "pricing_method_used": doc.get("pricing_method"),
        "pricing_method_results": doc.get("pricing_method_results") or [],
        "breakdown": doc.get("breakdown") or [],
        "calculation_warnings": doc.get("calculation_warnings") or [],
    }
    if result["category"] not in CATEGORY_IDS:
        result["category"] = "custom"
    return result


def _legacy_disagreement_warnings(doc: Mapping[str, Any], cents: int) -> list[str]:
    warnings: list[str] = []
    for field in _DOLLAR_FIELDS:
        if doc.get(field) is None:
            continue
        try:
            legacy_cents = legacy_dollars_to_cents(doc.get(field), field_name=field)
        except ContractValidationError:
            continue
        if legacy_cents != cents:
            warnings.append(f"Legacy {field} differs from stored integer cents; integer cents preserved as historical authority.")
            break
    return warnings


def _copy_amount_rows(rows: Any, *, allow_negative: bool = False) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, Mapping):
            raise ContractValidationError(f"amount row {index} must be an object")
        item = deepcopy(dict(row))
        amount = item.get("amount_cents")
        if amount is not None:
            item["amount_cents"] = (
                validate_signed_cents(amount, field_name=f"amount_rows[{index}].amount_cents")
                if allow_negative
                else validate_nonnegative_cents(amount, field_name=f"amount_rows[{index}].amount_cents")
            )
        copied.append(item)
    return copied


def _copy_component_amounts(rows: Any) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, Mapping):
            raise ContractValidationError(f"component amount row {index} must be an object")
        item = deepcopy(dict(row))
        amount = item.get("amount_cents")
        if amount is not None:
            allow_negative = str(item.get("field") or "").endswith("_adjustment")
            item["amount_cents"] = (
                validate_signed_cents(amount, field_name=f"component_amounts[{index}].amount_cents")
                if allow_negative
                else validate_nonnegative_cents(amount, field_name=f"component_amounts[{index}].amount_cents")
            )
        copied.append(item)
    return copied


def _optional_nonnegative_cents(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    return validate_nonnegative_cents(value, field_name=field_name)


def _optional_signed_cents(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    return validate_signed_cents(value, field_name=field_name)


def _append_decimal(evidence: list[dict[str, str]], field: str, value: Any, unit: str) -> None:
    if value is None or isinstance(value, bool):
        return
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return
    if not decimal_value.is_finite():
        return
    evidence.append({"field": field, "value": format(decimal_value.normalize(), "f"), "unit": unit})
