"""EC9 Phase 9I-K versioned parity-fixture loader and test runner.

This module is test-only. Pure fixture discovery and schema validation do not
import FastAPI, MongoDB, SaaS services, or any production app module. The
current legacy/SaaS calculator is imported only inside its adapter run method.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from pricing_engine import CATEGORY_IDS, ROUNDING_POLICY_ID, decimal_dollars_to_cents


FIXTURE_SCHEMA_VERSION = "pricing_fixture_v1"
FIXTURE_ENGINE_VERSION = "pricing_engine_v1"
FIXTURE_FORMULA_VERSION = "ec9_current"
LEGACY_SAAS_ADAPTER_ID = "legacy_saas_calculator_v1"
LEGACY_SAAS_CENTS_FIRST_ADAPTER_ID = "legacy_saas_cents_first_compatibility_adapter_9il_v1"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pricing_engine"
SCHEMA_PATH = FIXTURE_ROOT / "schema.json"
REQUIRED_CATEGORY_IDS = tuple(CATEGORY_IDS)

SUPPORTED_UNITS = {
    "in",
    "ft",
    "sqft",
    "sqin",
    "each",
    "item",
    "piece",
    "hour",
    "minute",
    "USD",
    "USD_per_sqft",
    "USD_per_sqin",
    "USD_per_hour",
    "USD_per_minute",
    "USD_per_each",
    "percent",
    "basis_points",
    "ratio",
}


class FixtureValidationError(ValueError):
    """Raised when a shared pricing fixture is malformed or ambiguous."""


@dataclass(frozen=True, slots=True)
class PricingFixture:
    path: Path
    document: dict[str, Any]

    @property
    def case_id(self) -> str:
        return self.document["case_id"]

    @property
    def category(self) -> str:
        return self.document["category"]


@dataclass(frozen=True, slots=True)
class AdapterExecutionResult:
    adapter_id: str
    normalized_result: dict[str, Any]
    raw_result: dict[str, Any]


class PricingFixtureAdapter(Protocol):
    adapter_id: str

    def run(self, fixture: PricingFixture) -> AdapterExecutionResult:
        """Execute one fixture and return normalized assertion values."""


def discover_fixture_paths(root: Path = FIXTURE_ROOT) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.json")
        if path.name != "schema.json"
    )


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict[str, Any]:
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureValidationError(f"{schema_path}: malformed JSON: {exc.msg}") from exc


def load_fixture(path: Path) -> PricingFixture:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureValidationError(f"{path}: malformed JSON: {exc.msg}") from exc
    if not isinstance(document, dict):
        raise FixtureValidationError(f"{path}: fixture document must be an object")
    return PricingFixture(path=path, document=document)


def validate_fixture(fixture: PricingFixture, *, schema: dict[str, Any] | None = None) -> None:
    schema_doc = schema or load_schema()
    validator = Draft202012Validator(schema_doc)
    errors = sorted(validator.iter_errors(fixture.document), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        field = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise FixtureValidationError(f"{fixture.path}: {field}: {error.message}")

    document = fixture.document
    _require_version(fixture, "fixture_schema_version", FIXTURE_SCHEMA_VERSION)
    _require_version(fixture, "engine_version", FIXTURE_ENGINE_VERSION)
    _require_version(fixture, "formula_version", FIXTURE_FORMULA_VERSION)
    _validate_category_and_path(fixture)
    _reject_unexpected_floats(fixture.path, document)
    _reject_boolean_cents(fixture.path, document)
    _validate_decimal_evidence(fixture.path, document)
    _validate_rounding_evidence(fixture.path, document)
    _validate_expected_line_results(fixture.path, document)
    _validate_not_applicable_document_results(fixture.path, document)
    _validate_snapshot_evidence(fixture.path, document)


def load_fixture_pack(root: Path = FIXTURE_ROOT) -> list[PricingFixture]:
    schema = load_schema(root / "schema.json")
    fixtures = [load_fixture(path) for path in discover_fixture_paths(root)]
    seen: dict[str, Path] = {}
    for fixture in fixtures:
        validate_fixture(fixture, schema=schema)
        prior = seen.get(fixture.case_id)
        if prior is not None:
            raise FixtureValidationError(
                f"{fixture.path}: case_id: duplicate case_id '{fixture.case_id}' also found in {prior}"
            )
        seen[fixture.case_id] = fixture.path
    return fixtures


def assert_required_starter_coverage(fixtures: list[PricingFixture]) -> None:
    categories = {fixture.category for fixture in fixtures if fixture.document.get("case_scope") == "normal_line"}
    missing = sorted(set(REQUIRED_CATEGORY_IDS) - categories)
    extra = sorted(categories - set(REQUIRED_CATEGORY_IDS))
    if missing or extra:
        raise FixtureValidationError(f"starter category coverage mismatch; missing={missing}; extra={extra}")


class LegacySaasCalculatorAdapter:
    adapter_id = LEGACY_SAAS_ADAPTER_ID

    def run(self, fixture: PricingFixture) -> AdapterExecutionResult:
        from app.services.pricing import calculate_pricing
        from app.services.starter_defaults import build_starter_pack

        request = fixture.document["normalized_inputs"]["calculator_request"]
        result = calculate_pricing(
            settings=build_starter_pack(),
            category=fixture.category,
            width_inches=_dimension_to_legacy_inches(request.get("width")),
            height_inches=_dimension_to_legacy_inches(request.get("height")),
            quantity=_quantity_to_legacy_int(request["quantity"]),
            material_key=request.get("material_key"),
            design_needed=bool(request.get("design_needed", False)),
            install_needed=bool(request.get("install_needed", False)),
            manual_selling_price=_cents_to_legacy_dollars(request.get("manual_selling_price_cents")),
            category_inputs=request.get("category_inputs") or {},
            material_profile=None,
            pricing_components=[],
            saved_item=None,
        )
        return AdapterExecutionResult(
            adapter_id=self.adapter_id,
            normalized_result=_normalize_legacy_result(result),
            raw_result=result,
        )


class LegacySaasCentsFirstCompatibilityAdapter:
    adapter_id = LEGACY_SAAS_CENTS_FIRST_ADAPTER_ID

    def run(self, fixture: PricingFixture) -> AdapterExecutionResult:
        from pricing_engine.adapters import build_legacy_line_result

        legacy_execution = LegacySaasCalculatorAdapter().run(fixture)
        request = fixture.document["normalized_inputs"]["calculator_request"]
        line_result = build_legacy_line_result(
            category_id=fixture.category,
            legacy_result=legacy_execution.raw_result,
            normalized_input=request,
        )
        return AdapterExecutionResult(
            adapter_id=self.adapter_id,
            normalized_result=_project_cents_first_result_for_fixture(line_result),
            raw_result={
                "legacy_result": legacy_execution.raw_result,
                "pricing_engine_result": line_result,
            },
        )


def compare_fixture_result(fixture: PricingFixture, execution: AdapterExecutionResult) -> None:
    expected = fixture.document["expected_line_results"]
    actual = execution.normalized_result
    fields = (
        "status",
        "selling_price_cents",
        "suggested_price_cents",
        "true_cost_cents",
        "profit_amount_cents",
        "profit_margin_percent",
        "pricing_method_used",
        "canonical_method_id",
        "selected_method_id",
    )
    for field in fields:
        if actual.get(field) != expected.get(field):
            raise AssertionError(
                f"{fixture.path}: {execution.adapter_id}: {field}: expected {expected.get(field)!r}, got {actual.get(field)!r}"
            )
    if actual.get("warnings") != expected.get("warnings", []):
        raise AssertionError(f"{fixture.path}: {execution.adapter_id}: warnings mismatch")

    expected_rows = expected.get("method_rows") or []
    actual_rows = actual.get("method_rows") or []
    if actual_rows != expected_rows:
        raise AssertionError(f"{fixture.path}: {execution.adapter_id}: method_rows mismatch")


def _project_cents_first_result_for_fixture(result: dict[str, Any]) -> dict[str, Any]:
    selected_rows = [row for row in result.get("method_rows", []) if row.get("selected")]
    return {
        "status": result.get("status"),
        "selling_price_cents": result.get("selling_price_cents"),
        "suggested_price_cents": result.get("suggested_price_cents"),
        "true_cost_cents": result.get("true_cost_cents"),
        "profit_amount_cents": result.get("profit_amount_cents"),
        "profit_margin_percent": result.get("profit_margin_percent"),
        "pricing_method_used": result.get("pricing_method_used"),
        "canonical_method_id": result.get("canonical_method_id"),
        "selected_method_id": result.get("selected_method_id"),
        "warnings": list(result.get("warnings") or []),
        "method_rows": [
            {
                "method_id": row.get("method_id"),
                "selected": bool(row.get("selected")),
                "available": bool(row.get("available")),
                "amount_cents": row.get("amount_cents"),
                "status": list(row.get("status") or []),
            }
            for row in selected_rows
        ],
    }


def _normalize_legacy_result(result: dict[str, Any]) -> dict[str, Any]:
    selected_rows = [row for row in result.get("pricing_method_results", []) if row.get("selected")]
    selected_method_id = selected_rows[0]["method_id"] if selected_rows else None
    return {
        "status": "success" if result.get("selling_price") is not None else "unavailable",
        "selling_price_cents": _legacy_dollars_to_cents(result.get("selling_price")),
        "suggested_price_cents": _legacy_dollars_to_cents(result.get("suggested_price")),
        "true_cost_cents": _legacy_dollars_to_cents(result.get("true_cost")),
        "profit_amount_cents": _legacy_dollars_to_cents(result.get("profit_amount")),
        "profit_margin_percent": _decimal_string(result.get("profit_margin_percent"), scale=4),
        "pricing_method_used": result.get("pricing_method_used"),
        "canonical_method_id": result.get("canonical_method_id"),
        "selected_method_id": selected_method_id,
        "warnings": list(result.get("calculation_warnings") or []),
        "method_rows": [
            {
                "method_id": row.get("method_id"),
                "selected": bool(row.get("selected")),
                "available": bool(row.get("available")),
                "amount_cents": _legacy_dollars_to_cents(row.get("amount")),
                "status": list(row.get("status") or []),
            }
            for row in result.get("pricing_method_results", [])
            if row.get("selected")
        ],
    }


def _require_version(fixture: PricingFixture, field: str, expected: str) -> None:
    actual = fixture.document.get(field)
    if actual != expected:
        raise FixtureValidationError(f"{fixture.path}: {field}: unsupported version {actual!r}")


def _validate_category_and_path(fixture: PricingFixture) -> None:
    category = fixture.document.get("category")
    case_id = fixture.document.get("case_id")
    if category not in REQUIRED_CATEGORY_IDS:
        raise FixtureValidationError(f"{fixture.path}: category: unsupported category {category!r}")
    if not isinstance(case_id, str) or not case_id.strip():
        raise FixtureValidationError(f"{fixture.path}: case_id: missing or blank")
    if fixture.path.name != "<memory>":
        if fixture.path.parent.name != category:
            raise FixtureValidationError(f"{fixture.path}: category/path mismatch")
        if fixture.path.stem != case_id:
            raise FixtureValidationError(f"{fixture.path}: case_id/path mismatch")


def _reject_unexpected_floats(path: Path, value: Any, field: str = "<root>") -> None:
    if isinstance(value, float):
        raise FixtureValidationError(f"{path}: {field}: binary floats are prohibited")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_unexpected_floats(path, child, f"{field}.{key}" if field != "<root>" else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unexpected_floats(path, child, f"{field}[{index}]")


def _reject_boolean_cents(path: Path, value: Any, field: str = "<root>") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_field = f"{field}.{key}" if field != "<root>" else str(key)
            if key.endswith("_cents") and isinstance(child, bool):
                raise FixtureValidationError(f"{path}: {child_field}: cents values must not be boolean")
            _reject_boolean_cents(path, child, child_field)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_boolean_cents(path, child, f"{field}[{index}]")


def _validate_decimal_evidence(path: Path, document: dict[str, Any]) -> None:
    evidence = document.get("decimal_rate_evidence") or []
    for index, entry in enumerate(evidence):
        field = f"decimal_rate_evidence[{index}]"
        _parse_decimal_string(path, entry.get("value"), f"{field}.value")
        unit = entry.get("unit")
        if unit not in SUPPORTED_UNITS:
            raise FixtureValidationError(f"{path}: {field}.unit: unsupported unit {unit!r}")
    request = document["normalized_inputs"]["calculator_request"]
    for key in ("width", "height", "quantity"):
        item = request.get(key)
        if item is None:
            continue
        _parse_decimal_string(path, item.get("value"), f"normalized_inputs.calculator_request.{key}.value")
        if item.get("unit") not in SUPPORTED_UNITS:
            raise FixtureValidationError(f"{path}: normalized_inputs.calculator_request.{key}.unit: unsupported unit")
    margin = document["expected_line_results"].get("profit_margin_percent")
    if margin is not None:
        _parse_decimal_string(path, margin, "expected_line_results.profit_margin_percent")


def _validate_rounding_evidence(path: Path, document: dict[str, Any]) -> None:
    evidence = document.get("rounding_evidence") or {}
    if evidence.get("policy_id") != ROUNDING_POLICY_ID:
        raise FixtureValidationError(f"{path}: rounding_evidence.policy_id: invalid rounding policy")
    if evidence.get("mode") != "ROUND_HALF_UP":
        raise FixtureValidationError(f"{path}: rounding_evidence.mode: invalid rounding mode")
    if evidence.get("boundary") != "final_cents":
        raise FixtureValidationError(f"{path}: rounding_evidence.boundary: invalid rounding boundary")


def _validate_expected_line_results(path: Path, document: dict[str, Any]) -> None:
    expected = document.get("expected_line_results") or {}
    if document.get("case_scope") == "normal_line" and not expected:
        raise FixtureValidationError(f"{path}: expected_line_results: required for executable line fixtures")
    if expected.get("status") == "success" and expected.get("selling_price_cents") is None:
        raise FixtureValidationError(f"{path}: expected_line_results.selling_price_cents: required for success")


def _validate_not_applicable_document_results(path: Path, document: dict[str, Any]) -> None:
    expected = document.get("expected_document_results") or {}
    if expected.get("applicability") == "not_applicable":
        if expected.get("status") != "not_calculated" or expected.get("total_cents") is not None:
            raise FixtureValidationError(f"{path}: expected_document_results: incoherent not_applicable section")


def _validate_snapshot_evidence(path: Path, document: dict[str, Any]) -> None:
    snapshot = document.get("snapshot_evidence") or {}
    if snapshot.get("applicability") == "shape_only" and snapshot.get("snapshot_created") is not False:
        raise FixtureValidationError(f"{path}: snapshot_evidence.snapshot_created: starter fixtures must not create snapshots")


def _parse_decimal_string(path: Path, value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, str) or not value.strip():
        raise FixtureValidationError(f"{path}: {field}: must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise FixtureValidationError(f"{path}: {field}: malformed Decimal string") from exc
    if not parsed.is_finite():
        raise FixtureValidationError(f"{path}: {field}: non-finite Decimal string")
    return parsed


def _dimension_to_legacy_inches(value: dict[str, Any] | None) -> float | None:
    if value is None:
        return None
    amount = Decimal(value["value"])
    unit = value["unit"]
    if unit in {"in", "ft"}:
        return float(amount)
    raise FixtureValidationError(Path("<adapter>"), f"dimension.unit: unsupported unit {unit!r}")


def _quantity_to_legacy_int(value: dict[str, Any]) -> int:
    parsed = Decimal(value["value"])
    if parsed != parsed.to_integral_value():
        raise FixtureValidationError(Path("<adapter>"), "quantity.value: starter fixtures require whole quantities")
    return int(parsed)


def _cents_to_legacy_dollars(value: int | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(value) / Decimal("100"))


def _legacy_dollars_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    return decimal_dollars_to_cents(str(value)).to_json()


def _decimal_string(value: Any, *, scale: int) -> str | None:
    if value is None:
        return None
    quantum = Decimal("1").scaleb(-scale)
    return format(Decimal(str(value)).quantize(quantum), f".{scale}f")
