"""EC9 Phase 9I-T standalone adapter contract-harness tests."""
from __future__ import annotations

from copy import deepcopy
import builtins
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.services.pricing_engine_config_adapter import build_line_engine_configuration
from pricing_engine.config import CATEGORY_IDS, build_starter_pack
from pricing_engine.config_export import (
    build_portable_configuration,
    serialize_portable_configuration,
)
from pricing_engine.validation import ContractValidationError

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (  # noqa: E402
    LegacySaasCentsFirstCompatibilityAdapter,
    compare_fixture_result,
    load_fixture_pack,
)
from standalone_pricing_adapter_harness import (  # noqa: E402
    STANDALONE_ADAPTER_ID,
    StandalonePricingAdapter,
)


FORBIDDEN_RESULT_KEYS = {
    "_id",
    "tenant_id",
    "tenant",
    "user_id",
    "user",
    "email",
    "permissions",
    "db",
    "database",
    "request",
    "auth",
    "audit",
    "entitlement",
    "entitlements",
    "stripe",
    "license",
    "licensing",
    "secret",
    "token",
    "api_key",
}


def _portable_configuration() -> dict:
    settings = build_starter_pack()
    return build_portable_configuration(
        category_configurations={
            category: build_line_engine_configuration(settings=settings, category=category)
            for category in CATEGORY_IDS
        },
        settings_version_evidence={"starter_default_version": settings["starter_default_version"]},
    )


def _walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_harness_implements_existing_fixture_adapter_protocol_and_versioned_id():
    adapter = StandalonePricingAdapter(_portable_configuration())

    assert isinstance(adapter.adapter_id, str)
    assert callable(adapter.run)
    assert adapter.adapter_id == STANDALONE_ADAPTER_ID
    assert STANDALONE_ADAPTER_ID == "standalone_portable_configuration_adapter_9it_v1"
    signature = inspect.signature(StandalonePricingAdapter.__init__)
    assert set(signature.parameters) == {"self", "portable_configuration"}
    run_parameters = set(inspect.signature(StandalonePricingAdapter.run).parameters)
    assert run_parameters == {"self", "fixture"}


def test_valid_portable_mapping_and_json_load_without_mutation(tmp_path):
    portable = _portable_configuration()
    original = deepcopy(portable)
    adapter = StandalonePricingAdapter(portable)

    assert portable == original
    assert set(adapter.engine_settings_by_category) == set(CATEGORY_IDS)

    config_path = tmp_path / "portable-pricing.json"
    config_path.write_text(json.dumps(serialize_portable_configuration(portable)), encoding="utf-8")
    loaded = StandalonePricingAdapter.from_json_file(config_path)

    assert loaded.portable_configuration == adapter.portable_configuration
    assert json.loads(config_path.read_text(encoding="utf-8")) == serialize_portable_configuration(portable)


def test_json_loading_requires_object_and_malformed_json_fails_safely(tmp_path):
    list_path = tmp_path / "list.json"
    list_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ContractValidationError, match="root must be an object"):
        StandalonePricingAdapter.from_json_file(list_path)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ContractValidationError, match="malformed JSON"):
        StandalonePricingAdapter.from_json_file(malformed)


@pytest.mark.parametrize(
    "mutator,error",
    [
        (lambda doc: doc.update({"schema_id": "wrong"}), "schema id"),
        (lambda doc: doc.update({"schema_version": "future"}), "schema version"),
        (lambda doc: doc["versions"].update({"engine_version": "future"}), "engine_version"),
        (lambda doc: doc["versions"].update({"formula_version": "future"}), "formula_version"),
        (lambda doc: doc["versions"].update({"rounding_policy_version": "future"}), "rounding_policy_version"),
        (lambda doc: doc["versions"].update({"category_configuration_version": "future"}), "category_configuration_version"),
        (lambda doc: doc["category_configurations"]["banners"].update({"adapter_contract_version": "future"}), "adapter contract"),
        (lambda doc: doc["category_configurations"]["banners"].update({"adapter_id": "future"}), "adapter id"),
        (lambda doc: doc["category_configurations"].pop("custom"), "missing"),
        (lambda doc: doc["category_configurations"].update({"unknown": {}}), "unknown"),
        (lambda doc: doc.update({"category_ids": list(CATEGORY_IDS) + ["banners"]}), "category_ids"),
        (
            lambda doc: doc["category_configurations"]["banners"]["engine_settings"].pop("category_defaults"),
            "category_defaults",
        ),
    ],
)
def test_unsupported_versions_and_malformed_categories_fail_safely(mutator, error):
    portable = _portable_configuration()
    mutator(portable)
    with pytest.raises(ContractValidationError, match=error):
        StandalonePricingAdapter(portable)


def test_all_nine_categories_match_fixed_fixture_expectations_and_saas_adapter():
    fixtures = load_fixture_pack()
    standalone = StandalonePricingAdapter(_portable_configuration())
    saas = LegacySaasCentsFirstCompatibilityAdapter()
    categories = set()

    for fixture in fixtures:
        standalone_execution = standalone.run(fixture)
        saas_execution = saas.run(fixture)

        compare_fixture_result(fixture, standalone_execution)
        compare_fixture_result(fixture, saas_execution)
        assert standalone_execution.normalized_result == saas_execution.normalized_result
        assert standalone_execution.normalized_result["selling_price_cents"] == fixture.document["expected_line_results"]["selling_price_cents"]
        assert standalone_execution.normalized_result["suggested_price_cents"] == fixture.document["expected_line_results"]["suggested_price_cents"]
        assert standalone_execution.normalized_result["true_cost_cents"] == fixture.document["expected_line_results"]["true_cost_cents"]
        assert standalone_execution.normalized_result["profit_amount_cents"] == fixture.document["expected_line_results"]["profit_amount_cents"]
        assert standalone_execution.normalized_result["profit_margin_percent"] == fixture.document["expected_line_results"]["profit_margin_percent"]
        assert standalone_execution.raw_result["pricing_engine_result"]["rounding_policy_version"] == fixture.document["rounding_evidence"]["policy_id"]
        assert standalone_execution.raw_result["pricing_engine_result"]["formula_version"] == fixture.document["formula_version"]
        assert standalone_execution.raw_result["pricing_engine_result"]["fixture_engine_version"] == fixture.document["engine_version"]
        categories.add(fixture.category)

    assert categories == set(CATEGORY_IDS)


def test_fixture_execution_is_deterministic_and_does_not_mutate_inputs_or_configuration():
    portable = _portable_configuration()
    portable_before = deepcopy(portable)
    standalone = StandalonePricingAdapter(portable)
    deserialized_before = standalone.engine_settings_by_category
    fixture = load_fixture_pack()[0]
    fixture_before = deepcopy(fixture.document)

    first = standalone.run(fixture)
    second = standalone.run(fixture)

    assert first.normalized_result == second.normalized_result
    assert fixture.document == fixture_before
    assert portable == portable_before
    assert standalone.engine_settings_by_category == deserialized_before


def test_harness_uses_category_specific_deserialized_engine_settings(monkeypatch):
    import standalone_pricing_adapter_harness as harness

    fixture = next(item for item in load_fixture_pack() if item.category == "digital_print")
    adapter = StandalonePricingAdapter(_portable_configuration())
    seen = []
    real_calculate_line = harness.calculate_line

    def spy_calculate_line(**kwargs):
        seen.append(deepcopy(kwargs["settings"]))
        return real_calculate_line(**kwargs)

    monkeypatch.setattr(harness, "calculate_line", spy_calculate_line)
    adapter.run(fixture)

    assert seen
    assert set(seen[0]["category_defaults"]) == {fixture.category}


def test_valid_zero_cents_survive_and_malformed_authoritative_money_fails(monkeypatch):
    import standalone_pricing_adapter_harness as harness

    fixture = next(item for item in load_fixture_pack() if item.category == "custom")
    adapter = StandalonePricingAdapter(_portable_configuration())
    real_calculate_line = harness.calculate_line

    def zero_result(**kwargs):
        result = real_calculate_line(**kwargs)
        result.update(
            {
                "selling_price": 0,
                "suggested_price": 0,
                "true_cost": 0,
                "profit_amount": 0,
                "profit_margin_percent": 0,
                "pricing_method_results": [
                    {
                        "method_id": "unit_price_x_quantity",
                        "selected": True,
                        "available": True,
                        "amount": 0,
                        "status": ["selected", "authoritative_total"],
                    }
                ],
            }
        )
        return result

    monkeypatch.setattr(harness, "calculate_line", zero_result)
    assert adapter.run(fixture).normalized_result["selling_price_cents"] == 0

    def malformed_result(**kwargs):
        result = real_calculate_line(**kwargs)
        result["selling_price"] = True
        return result

    monkeypatch.setattr(harness, "calculate_line", malformed_result)
    with pytest.raises(ContractValidationError, match="selling_price"):
        adapter.run(fixture)


def test_harness_results_expose_no_identity_permission_secret_or_license_fields():
    adapter = StandalonePricingAdapter(_portable_configuration())
    fixture = load_fixture_pack()[0]
    execution = adapter.run(fixture)

    for key, item in _walk(execution.raw_result):
        assert key not in FORBIDDEN_RESULT_KEYS
        if isinstance(item, str):
            lowered = item.lower()
            assert "stripe" not in lowered
            assert "license" not in lowered
            assert "secret" not in lowered
            assert "token" not in lowered


def test_no_filesystem_writes_or_network_operations_during_fixture_execution(tmp_path, monkeypatch):
    import socket

    portable = _portable_configuration()
    config_path = tmp_path / "portable-pricing.json"
    config_path.write_text(json.dumps(portable), encoding="utf-8")
    adapter = StandalonePricingAdapter.from_json_file(config_path)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    real_open = builtins.open

    def deny_write_open(file, mode="r", *args, **kwargs):
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
            raise AssertionError(f"standalone harness attempted filesystem write: {file}")
        return real_open(file, mode, *args, **kwargs)

    def deny_socket(*args, **kwargs):
        raise AssertionError("standalone harness attempted network access")

    monkeypatch.setattr(builtins, "open", deny_write_open)
    monkeypatch.setattr(socket, "socket", deny_socket)

    for fixture in load_fixture_pack():
        compare_fixture_result(fixture, adapter.run(fixture))

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before


def test_harness_source_has_no_saas_imports_or_hardcoded_digital_print_minimums():
    source = Path("backend/tests/standalone_pricing_adapter_harness.py").read_text(encoding="utf-8")
    forbidden_imports = (
        "from app",
        "import app",
        "server",
        "fastapi",
        "motor",
        "pymongo",
        "requests",
        "httpx",
        "stripe",
        "openai",
        "license",
        "licensing",
    )
    for token in forbidden_imports:
        assert token not in source
    assert "$20" not in source
    assert "$40" not in source
    assert "2000" not in source
    assert "4000" not in source


def test_standalone_isolation_subprocess_runs_all_fixtures_without_saas_startup(tmp_path):
    config_path = tmp_path / "portable-pricing.json"
    config_path.write_text(json.dumps(_portable_configuration()), encoding="utf-8")
    code = r"""
import json
import pathlib
import sys

sys.path.insert(0, "tests")

from pricing_engine.config import CATEGORY_IDS
from pricing_engine_fixture_runner import compare_fixture_result, load_fixture_pack
from standalone_pricing_adapter_harness import StandalonePricingAdapter

adapter = StandalonePricingAdapter.from_json_file(pathlib.Path(sys.argv[1]))
categories = set()
for fixture in load_fixture_pack(pathlib.Path("tests/fixtures/pricing_engine")):
    compare_fixture_result(fixture, adapter.run(fixture))
    categories.add(fixture.category)

blocked = sorted(
    name for name in sys.modules
    if name == "app"
    or name.startswith("app.")
    or name in {
        "server", "fastapi", "motor", "pymongo", "requests", "httpx",
        "stripe", "openai", "sqlite3", "tkinter", "PyQt5", "PySide6",
    }
)
assert blocked == [], blocked
print(json.dumps({"categories": sorted(categories), "blocked": blocked}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(config_path)],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["categories"] == sorted(CATEGORY_IDS)
    assert payload["blocked"] == []


def test_phase_9it_expected_cents_remain_authoritative_only_in_shared_fixtures():
    source = Path(__file__).read_text(encoding="utf-8")
    for fixture in load_fixture_pack():
        cents = fixture.document["expected_line_results"]["selling_price_cents"]
        if cents is not None:
            assert f"== {cents}" not in source
            assert f": {cents}" not in source
