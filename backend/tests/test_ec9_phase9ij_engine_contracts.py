"""EC9 Phase 9I-J pure pricing-engine contract foundation tests."""
from __future__ import annotations

import importlib
import json
import pkgutil
import subprocess
import sys
from decimal import Decimal

import pytest

from pricing_engine import (
    CATEGORY_IDS,
    CONTRACT_SCHEMA_VERSION,
    ENGINE_VERSION,
    ROUNDING_POLICY_ID,
    Area,
    AreaUnit,
    BasisPoints,
    CalculationEvidenceMetadata,
    CalculationInput,
    CategoryConfiguration,
    CategoryId,
    ContractValidationError,
    ContractVersionMetadata,
    CurrencyRateDecimal,
    CurrencyRateUnit,
    Dimension,
    DimensionUnit,
    LineCalculationResult,
    Margin,
    Markup,
    MoneyCents,
    PercentDecimal,
    PortableConfigExport,
    Quantity,
    QuantityUnit,
    RoundingEvidence,
    TimeAmount,
    TimeUnit,
    WasteFactor,
    WasteFactorUnit,
    decimal_dollars_to_cents,
    validate_category_id,
)


def test_package_imports_without_initializing_application_runtime():
    code = (
        "import sys; "
        "import pricing_engine; "
        "blocked=[m for m in sys.modules if m == 'app' or m.startswith('app.')]; "
        "print(pricing_engine.ROUNDING_POLICY_ID); "
        "assert blocked == []"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == ROUNDING_POLICY_ID


def test_pure_package_has_no_prohibited_dependency_imports():
    prohibited_roots = {
        "app",
        "fastapi",
        "motor",
        "pymongo",
        "stripe",
        "requests",
        "httpx",
        "openai",
    }
    imported_roots: set[str] = set()
    package = importlib.import_module("pricing_engine")
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        imported = importlib.import_module(module.name)
        for value in imported.__dict__.values():
            module_name = getattr(value, "__module__", "")
            root = module_name.split(".", 1)[0]
            if root in prohibited_roots:
                imported_roots.add(root)
    assert imported_roots == set()


def test_money_cents_serialize_as_json_integer_and_reject_bool():
    money = MoneyCents.nonnegative(12500)
    assert money.to_json() == 12500
    assert json.loads(json.dumps({"amount_cents": money.to_json()}))["amount_cents"] == 12500
    assert isinstance(money.to_json(), int)

    with pytest.raises(ContractValidationError, match="boolean"):
        MoneyCents.nonnegative(True)


def test_money_nonnegative_and_signed_boundaries():
    assert MoneyCents.nonnegative(0).to_json() == 0
    with pytest.raises(ContractValidationError, match=">= 0"):
        MoneyCents.nonnegative(-1)
    assert MoneyCents.signed(-125).to_json() == -125


def test_decimal_string_values_are_canonical_and_json_safe():
    rate = CurrencyRateDecimal("1.2345", CurrencyRateUnit.USD_PER_SQFT)
    percent = PercentDecimal("12.5")
    assert rate.value == Decimal("1.234500")
    assert rate.to_json() == {"value": "1.234500", "unit": "USD_per_sqft"}
    assert percent.to_json() == "12.500000"
    assert json.loads(json.dumps(rate.to_json()))["value"] == "1.234500"


@pytest.mark.parametrize("bad", [1.25, float("nan"), float("inf"), True])
def test_authoritative_decimal_contracts_reject_binary_floats_and_bool(bad):
    with pytest.raises(ContractValidationError):
        CurrencyRateDecimal(bad, CurrencyRateUnit.USD_PER_SQFT)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "not-a-decimal"])
def test_authoritative_decimal_contracts_reject_nonfinite_or_malformed_strings(bad):
    with pytest.raises(ContractValidationError):
        PercentDecimal(bad)


def test_decimal_precision_and_scale_boundaries_are_enforced():
    assert CurrencyRateDecimal("123456789012.123456", "USD_per_sqft").to_json()["value"] == "123456789012.123456"
    with pytest.raises(ContractValidationError, match="scale"):
        CurrencyRateDecimal("1.1234567", "USD_per_sqft")
    with pytest.raises(ContractValidationError, match="precision"):
        CurrencyRateDecimal("1234567890123.123456", "USD_per_sqft")


def test_basis_points_are_integer_percent_units_with_explicit_conversion():
    bps = BasisPoints(2500)
    assert bps.to_json() == 2500
    assert bps.as_percent_decimal() == Decimal("25")
    with pytest.raises(ContractValidationError):
        BasisPoints("25")
    with pytest.raises(ContractValidationError):
        BasisPoints(10001)


def test_percent_markup_margin_and_waste_are_distinct_contracts():
    percent = PercentDecimal("12.5")
    markup = Markup("2.5")
    margin = Margin(4000)
    waste = WasteFactor("0.125", WasteFactorUnit.RATIO)
    assert percent.to_json() == "12.500000"
    assert markup.to_json() == "2.500000"
    assert margin.to_json() == 4000
    assert waste.to_json() == {"value": "0.125000", "unit": "ratio"}
    with pytest.raises(ContractValidationError):
        Margin(10000)


def test_dimension_area_time_and_quantity_require_explicit_valid_units():
    assert Dimension("96", DimensionUnit.INCH).to_json() == {"value": "96.0000", "unit": "in"}
    assert Area("24", AreaUnit.SQUARE_FOOT).to_json() == {"value": "24.0000", "unit": "sqft"}
    assert TimeAmount("1.5", TimeUnit.HOUR).to_json() == {"value": "1.5000", "unit": "hour"}
    assert Quantity("3", QuantityUnit.EACH).to_json() == {"value": "3.0000", "unit": "each"}
    with pytest.raises(ContractValidationError):
        Dimension("96", "inch")
    with pytest.raises(ContractValidationError):
        Area("-1", AreaUnit.SQUARE_FOOT)
    with pytest.raises(ContractValidationError):
        TimeAmount("1", "hours")


def test_all_and_only_nine_category_identifiers_validate():
    expected = (
        "banners",
        "rigid_signs",
        "cut_vinyl",
        "digital_print",
        "vehicle_graphics",
        "apparel",
        "promotional",
        "services",
        "custom",
    )
    assert CATEGORY_IDS == expected
    assert [validate_category_id(value).value for value in expected] == list(expected)
    assert validate_category_id(CategoryId.BANNERS) is CategoryId.BANNERS
    with pytest.raises(ContractValidationError):
        validate_category_id("banner")


def test_rounding_policy_half_up_boundary_values_and_negative_adjustments():
    assert decimal_dollars_to_cents("1.234").to_json() == 123
    assert decimal_dollars_to_cents("1.235").to_json() == 124
    assert decimal_dollars_to_cents("0.005").to_json() == 1
    assert decimal_dollars_to_cents("-1.235", allow_negative=True).to_json() == -124
    with pytest.raises(ContractValidationError):
        decimal_dollars_to_cents(1.235)
    assert RoundingEvidence().to_json() == {
        "policy_id": "pricing_rounding_v1_round_half_up_final_cents",
        "mode": "ROUND_HALF_UP",
        "boundary": "final_cents",
    }


def test_repeated_conversions_are_not_required_to_preserve_authoritative_result():
    cents = decimal_dollars_to_cents("19.995").to_json()
    assert cents == 2000
    assert MoneyCents.nonnegative(cents).to_json() == 2000


def test_version_and_rounding_metadata_serialize_and_round_trip():
    versions = ContractVersionMetadata()
    payload = versions.to_json()
    assert payload["contract_schema_version"] == CONTRACT_SCHEMA_VERSION
    assert payload["engine_version"] == ENGINE_VERSION
    assert payload["rounding_policy_version"] == ROUNDING_POLICY_ID
    assert ContractVersionMetadata(**payload).to_json() == payload
    with pytest.raises(ContractValidationError):
        ContractVersionMetadata(contract_schema_version="old")
    with pytest.raises(ContractValidationError):
        RoundingEvidence(policy_id="other")


def test_base_contract_envelopes_are_json_safe_and_validated():
    evidence = CalculationEvidenceMetadata("digital_print", warnings=("item minimum context only",))
    calculation_input = CalculationInput("digital_print")
    category_config = CategoryConfiguration("digital_print")
    line_result = LineCalculationResult(
        "digital_print",
        status="success",
        selling_price=MoneyCents.nonnegative(4000),
        evidence=evidence,
    )
    export = PortableConfigExport(category_configurations={"digital_print": category_config})

    assert calculation_input.to_json()["category_id"] == "digital_print"
    assert line_result.to_json()["selling_price_cents"] == 4000
    assert line_result.to_json()["evidence"]["rounding"]["policy_id"] == ROUNDING_POLICY_ID
    assert export.category_configurations["digital_print"] == category_config
    json.dumps(line_result.to_json())
    with pytest.raises(ContractValidationError):
        LineCalculationResult("digital_print", status="success")
    with pytest.raises(ContractValidationError):
        PortableConfigExport(category_configurations={"banners": category_config})


def test_deterministic_normalization_for_identical_inputs():
    first = {
        "rate": CurrencyRateDecimal("1.2", "USD_per_sqft").to_json(),
        "dimension": Dimension("96", "in").to_json(),
        "metadata": CalculationEvidenceMetadata("banners").to_json(),
    }
    second = {
        "rate": CurrencyRateDecimal("1.2000", "USD_per_sqft").to_json(),
        "dimension": Dimension("96.0", "in").to_json(),
        "metadata": CalculationEvidenceMetadata("banners").to_json(),
    }
    assert first == second
