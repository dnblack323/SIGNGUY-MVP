"""EC9 Phase 9I-K versioned parity fixture framework tests."""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path
import pkgutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine import CATEGORY_IDS

from pricing_engine_fixture_runner import (
    FIXTURE_ENGINE_VERSION,
    FIXTURE_FORMULA_VERSION,
    FIXTURE_ROOT,
    FIXTURE_SCHEMA_VERSION,
    LEGACY_SAAS_ADAPTER_ID,
    FixtureValidationError,
    LegacySaasCalculatorAdapter,
    PricingFixture,
    assert_required_starter_coverage,
    compare_fixture_result,
    discover_fixture_paths,
    load_fixture,
    load_fixture_pack,
    load_schema,
    validate_fixture,
)


def _memory_fixture(document: dict) -> PricingFixture:
    return PricingFixture(path=Path("<memory>"), document=document)


def _valid_document() -> dict:
    return deepcopy(load_fixture(discover_fixture_paths()[0]).document)


def test_fixture_schema_loads_successfully():
    schema = load_schema()
    assert schema["title"] == "EC9 Phase 9I-K Pricing Engine Parity Fixture"
    assert schema["properties"]["fixture_schema_version"]["const"] == FIXTURE_SCHEMA_VERSION
    assert schema["properties"]["engine_version"]["const"] == FIXTURE_ENGINE_VERSION
    assert schema["properties"]["formula_version"]["const"] == FIXTURE_FORMULA_VERSION


def test_fixture_discovery_is_deterministic_and_excludes_schema():
    first = discover_fixture_paths()
    second = discover_fixture_paths()
    assert first == sorted(first)
    assert first == second
    assert first
    assert all(path.name != "schema.json" for path in first)


def test_all_fixture_files_validate_and_case_ids_are_unique():
    fixtures = load_fixture_pack()
    assert len(fixtures) == 9
    assert len({fixture.case_id for fixture in fixtures}) == len(fixtures)
    assert all(fixture.document["applicable_adapters"] == [LEGACY_SAAS_ADAPTER_ID] for fixture in fixtures)


def test_required_category_directories_and_starter_fixtures_exist():
    fixtures = load_fixture_pack()
    assert_required_starter_coverage(fixtures)
    for category in CATEGORY_IDS:
        path = FIXTURE_ROOT / category / f"{category}_normal.json"
        assert path.exists()
    assert [fixture.category for fixture in fixtures] == sorted(CATEGORY_IDS)


def test_duplicate_fixture_ids_are_rejected(tmp_path):
    root = tmp_path / "pricing_engine"
    first_dir = root / "banners"
    second_dir = root / "custom"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (root / "schema.json").write_text(json.dumps(load_schema()), encoding="utf-8")

    first = deepcopy(load_fixture(FIXTURE_ROOT / "banners" / "banners_normal.json").document)
    first["case_id"] = "duplicate_case"
    second = deepcopy(load_fixture(FIXTURE_ROOT / "custom" / "custom_normal.json").document)
    second["case_id"] = "duplicate_case"
    second["category"] = "custom"

    (first_dir / "duplicate_case.json").write_text(json.dumps(first), encoding="utf-8")
    (second_dir / "duplicate_case.json").write_text(json.dumps(second), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="duplicate case_id"):
        load_fixture_pack(root)


@pytest.mark.parametrize(
    "mutator,error",
    [
        (lambda doc: doc.pop("fixture_schema_version"), "fixture_schema_version"),
        (lambda doc: doc.update({"fixture_schema_version": "future"}), "fixture_schema_version"),
        (lambda doc: doc.update({"engine_version": "future"}), "engine_version"),
        (lambda doc: doc.update({"formula_version": "future"}), "formula_version"),
        (lambda doc: doc.update({"case_id": ""}), "case_id"),
        (lambda doc: doc.update({"category": "bad_category"}), "category"),
        (lambda doc: doc["rounding_evidence"].update({"policy_id": "wrong"}), "rounding_evidence.policy_id"),
        (lambda doc: doc.update({"unexpected": "field"}), "unexpected"),
    ],
)
def test_schema_and_version_validation_rejects_malformed_core_fields(mutator, error):
    document = _valid_document()
    mutator(document)
    with pytest.raises(FixtureValidationError, match=error):
        validate_fixture(_memory_fixture(document))


def test_category_path_mismatch_is_rejected():
    document = _valid_document()
    document["category"] = "banners"
    fixture = PricingFixture(path=FIXTURE_ROOT / "custom" / "banners_normal.json", document=document)
    with pytest.raises(FixtureValidationError, match="category/path mismatch"):
        validate_fixture(fixture)


def test_case_id_path_mismatch_is_rejected():
    document = _valid_document()
    fixture = PricingFixture(path=FIXTURE_ROOT / document["category"] / "other_name.json", document=document)
    with pytest.raises(FixtureValidationError, match="case_id/path mismatch"):
        validate_fixture(fixture)


def test_malformed_json_reports_path(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid", encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="bad.json: malformed JSON"):
        load_fixture(bad)


@pytest.mark.parametrize(
    "mutator,error",
    [
        (
            lambda doc: doc["expected_line_results"].update({"selling_price_cents": True}),
            "expected_line_results.selling_price_cents",
        ),
        (
            lambda doc: doc["expected_line_results"].update({"selling_price_cents": 192.00}),
            "binary floats are prohibited",
        ),
        (
            lambda doc: doc["decimal_rate_evidence"][0].update({"value": "NaN"}),
            "non-finite Decimal string",
        ),
        (
            lambda doc: doc["decimal_rate_evidence"][0].update({"value": "not-a-decimal"}),
            r"decimal_rate_evidence\[0\].value",
        ),
        (
            lambda doc: doc["decimal_rate_evidence"][0].update({"unit": "dollars"}),
            "decimal_rate_evidence.0.unit",
        ),
    ],
)
def test_money_decimal_and_unit_validation_rejects_ambiguous_fixture_values(mutator, error):
    document = _valid_document()
    mutator(document)
    with pytest.raises(FixtureValidationError, match=error):
        validate_fixture(_memory_fixture(document))


def test_executable_line_fixtures_require_expected_results():
    document = _valid_document()
    document["expected_line_results"] = {}
    with pytest.raises(FixtureValidationError, match="expected_line_results"):
        validate_fixture(_memory_fixture(document))


def test_document_and_snapshot_empty_sections_are_validated():
    document = _valid_document()
    document["expected_document_results"]["status"] = "success"
    with pytest.raises(FixtureValidationError, match="expected_document_results"):
        validate_fixture(_memory_fixture(document))

    document = _valid_document()
    document["snapshot_evidence"]["snapshot_created"] = True
    with pytest.raises(FixtureValidationError, match="snapshot_evidence.snapshot_created"):
        validate_fixture(_memory_fixture(document))


def test_validation_import_does_not_initialize_application_runtime():
    code = (
        "import pathlib, sys; "
        "sys.path.insert(0, 'tests'); "
        "from pricing_engine_fixture_runner import load_fixture_pack, assert_required_starter_coverage; "
        "fixtures=load_fixture_pack(pathlib.Path('tests/fixtures/pricing_engine')); "
        "assert_required_starter_coverage(fixtures); "
        "blocked=[m for m in sys.modules if m == 'app' or m.startswith('app.') or m in {'server','motor','pymongo','fastapi'}]; "
        "assert blocked == [], blocked; "
        "print(len(fixtures))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "9"


def test_legacy_saas_adapter_executes_all_starter_fixtures_against_fixed_expectations():
    fixtures = load_fixture_pack()
    adapter = LegacySaasCalculatorAdapter()
    executed_categories = set()
    for fixture in fixtures:
        execution = adapter.run(fixture)
        compare_fixture_result(fixture, execution)
        assert execution.adapter_id == LEGACY_SAAS_ADAPTER_ID
        assert execution.raw_result["category"] == fixture.category
        executed_categories.add(fixture.category)
    assert executed_categories == set(CATEGORY_IDS)


def test_identical_fixture_input_produces_deterministic_normalized_legacy_output():
    fixture = load_fixture(FIXTURE_ROOT / "custom" / "custom_normal.json")
    validate_fixture(fixture)
    adapter = LegacySaasCalculatorAdapter()
    first = adapter.run(fixture).normalized_result
    second = adapter.run(fixture).normalized_result
    assert first == second


def test_expected_values_are_stored_once_in_shared_fixtures_not_adapter_tests():
    source = Path(__file__).read_text(encoding="utf-8")
    fixtures = load_fixture_pack()
    fixture_values = {
        str(fixture.document["expected_line_results"]["selling_price_cents"])
        for fixture in fixtures
        if fixture.document["expected_line_results"]["selling_price_cents"] is not None
    }
    assert fixture_values
    for value in fixture_values:
        assert f"== {value}" not in source
        assert f": {value}" not in source


def test_pricing_engine_pure_package_still_has_no_prohibited_saas_imports():
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


def test_phase_9ik_does_not_claim_future_engine_or_standalone_adapter_parity():
    fixtures = load_fixture_pack()
    adapter_ids = {adapter for fixture in fixtures for adapter in fixture.document["applicable_adapters"]}
    assert adapter_ids == {LEGACY_SAAS_ADAPTER_ID}
