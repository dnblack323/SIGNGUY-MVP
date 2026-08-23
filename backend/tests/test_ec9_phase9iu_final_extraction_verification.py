"""EC9 Phase 9I-U final all-category extraction verification tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import ast
import sys
from typing import Any

import pricing_engine
from app.services.pricing import calculate_pricing
from app.services.pricing_engine_config_adapter import (
    SAAS_CONFIGURATION_ADAPTER_ID,
    build_line_engine_configuration,
)
from pricing_engine.adapters import build_legacy_line_result
from pricing_engine.config import CATEGORY_IDS, build_starter_pack
from pricing_engine.config_export import build_portable_configuration
from pricing_engine.line_engine import calculate_line

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (  # noqa: E402
    AdapterExecutionResult,
    LEGACY_SAAS_CENTS_FIRST_ADAPTER_ID,
    LegacySaasCentsFirstCompatibilityAdapter,
    PricingFixture,
    _cents_to_legacy_dollars,
    _dimension_to_legacy_inches,
    _project_cents_first_result_for_fixture,
    _quantity_to_legacy_int,
    assert_required_starter_coverage,
    compare_fixture_result,
    load_fixture_pack,
)
from standalone_pricing_adapter_harness import (  # noqa: E402
    STANDALONE_ADAPTER_ID,
    StandalonePricingAdapter,
)


PURE_LINE_ENGINE_ADAPTER_ID = "pure_line_engine_9io_v1"
SAAS_RUNTIME_CONFIGURATION_ADAPTER_ID = SAAS_CONFIGURATION_ADAPTER_ID
PROHIBITED_ENGINE_IMPORT_ROOTS = {
    "app",
    "fastapi",
    "motor",
    "pymongo",
    "requests",
    "httpx",
    "stripe",
    "openai",
}
PROHIBITED_RESULT_KEYS = {
    "_id",
    "tenant_id",
    "user_id",
    "actor_user_id",
    "actor_email",
    "permissions",
    "db",
    "database",
    "request",
    "router",
    "audit",
    "entitlements",
    "license",
    "licensing",
    "secret",
    "token",
    "api_key",
}


def _legacy_args_from_fixture(fixture: PricingFixture, *, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    return {
        "settings": deepcopy(settings or build_starter_pack()),
        "category": fixture.category,
        "width_inches": _dimension_to_legacy_inches(request.get("width")),
        "height_inches": _dimension_to_legacy_inches(request.get("height")),
        "quantity": _quantity_to_legacy_int(request["quantity"]),
        "material_key": request.get("material_key"),
        "design_needed": bool(request.get("design_needed", False)),
        "install_needed": bool(request.get("install_needed", False)),
        "manual_selling_price": _cents_to_legacy_dollars(request.get("manual_selling_price_cents")),
        "category_inputs": deepcopy(request.get("category_inputs") or {}),
        "material_profile": deepcopy(request.get("material_profile")),
        "pricing_components": deepcopy(request.get("pricing_components") or []),
        "saved_item": deepcopy(request.get("saved_item")),
    }


def _portable_configuration() -> dict[str, Any]:
    settings = build_starter_pack()
    return build_portable_configuration(
        category_configurations={
            category: build_line_engine_configuration(settings=settings, category=category)
            for category in CATEGORY_IDS
        },
        settings_version_evidence={"starter_default_version": settings["starter_default_version"]},
    )


def _pure_line_engine_execution(fixture: PricingFixture) -> AdapterExecutionResult:
    args = _legacy_args_from_fixture(fixture)
    raw_result = calculate_line(**args)
    line_result = build_legacy_line_result(
        category_id=fixture.category,
        legacy_result=raw_result,
        normalized_input=fixture.document["normalized_inputs"]["calculator_request"],
        adapter_source_id=PURE_LINE_ENGINE_ADAPTER_ID,
        execution_path="pricing_engine.line_engine.calculate_line",
    )
    return AdapterExecutionResult(
        adapter_id=PURE_LINE_ENGINE_ADAPTER_ID,
        normalized_result=_project_cents_first_result_for_fixture(line_result),
        raw_result={
            "legacy_result": raw_result,
            "pricing_engine_result": line_result,
        },
    )


def _saas_runtime_configuration_execution(fixture: PricingFixture) -> AdapterExecutionResult:
    raw_result = calculate_pricing(**_legacy_args_from_fixture(fixture))
    line_result = build_legacy_line_result(
        category_id=fixture.category,
        legacy_result=raw_result,
        normalized_input=fixture.document["normalized_inputs"]["calculator_request"],
        adapter_source_id=SAAS_RUNTIME_CONFIGURATION_ADAPTER_ID,
        execution_path="app.services.pricing.calculate_pricing",
    )
    return AdapterExecutionResult(
        adapter_id=SAAS_RUNTIME_CONFIGURATION_ADAPTER_ID,
        normalized_result=_project_cents_first_result_for_fixture(line_result),
        raw_result={
            "legacy_result": raw_result,
            "pricing_engine_result": line_result,
        },
    )


def _walk(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_phase_9iu_discovers_all_fixture_categories_and_required_adapter_ids():
    fixtures = load_fixture_pack()
    assert_required_starter_coverage(fixtures)

    categories = {fixture.category for fixture in fixtures}
    adapter_ids = {
        PURE_LINE_ENGINE_ADAPTER_ID,
        SAAS_RUNTIME_CONFIGURATION_ADAPTER_ID,
        LEGACY_SAAS_CENTS_FIRST_ADAPTER_ID,
        STANDALONE_ADAPTER_ID,
    }

    assert categories == set(CATEGORY_IDS)
    assert adapter_ids == {
        "pure_line_engine_9io_v1",
        "saas_configuration_adapter_9iq_v1",
        "legacy_saas_cents_first_compatibility_adapter_9il_v1",
        "standalone_portable_configuration_adapter_9it_v1",
    }


def test_all_nine_categories_match_across_engine_saas_compatibility_and_standalone_harness():
    fixtures = load_fixture_pack()
    standalone = StandalonePricingAdapter(_portable_configuration())
    legacy_cents_first = LegacySaasCentsFirstCompatibilityAdapter()
    observed_categories = set()

    for fixture in fixtures:
        executions = [
            _pure_line_engine_execution(fixture),
            _saas_runtime_configuration_execution(fixture),
            legacy_cents_first.run(fixture),
            standalone.run(fixture),
        ]
        normalized_results = [execution.normalized_result for execution in executions]

        for execution in executions:
            compare_fixture_result(fixture, execution)
            engine_result = execution.raw_result["pricing_engine_result"]
            assert engine_result["fixture_engine_version"] == fixture.document["engine_version"]
            assert engine_result["formula_version"] == fixture.document["formula_version"]
            assert engine_result["rounding_policy_version"] == fixture.document["rounding_evidence"]["policy_id"]
            assert engine_result["normalized_input"] == fixture.document["normalized_inputs"]["calculator_request"]
            assert execution.raw_result["legacy_result"].get("persistent_entities_created", []) == []

        assert all(result == normalized_results[0] for result in normalized_results[1:])
        observed_categories.add(fixture.category)

    assert observed_categories == set(CATEGORY_IDS)


def test_fixture_execution_is_deterministic_and_does_not_mutate_inputs_configuration_or_results():
    fixture = load_fixture_pack()[0]
    fixture_before = deepcopy(fixture.document)
    portable = _portable_configuration()
    portable_before = deepcopy(portable)
    standalone = StandalonePricingAdapter(portable)

    first = [
        _pure_line_engine_execution(fixture),
        _saas_runtime_configuration_execution(fixture),
        LegacySaasCentsFirstCompatibilityAdapter().run(fixture),
        standalone.run(fixture),
    ]
    second = [
        _pure_line_engine_execution(fixture),
        _saas_runtime_configuration_execution(fixture),
        LegacySaasCentsFirstCompatibilityAdapter().run(fixture),
        standalone.run(fixture),
    ]

    assert [execution.normalized_result for execution in first] == [
        execution.normalized_result for execution in second
    ]
    assert fixture.document == fixture_before
    assert portable == portable_before
    assert standalone.portable_configuration == portable_before


def test_final_gate_results_expose_no_saas_identity_credentials_or_licensing_fields():
    standalone = StandalonePricingAdapter(_portable_configuration())
    fixture = load_fixture_pack()[0]

    for execution in (
        _pure_line_engine_execution(fixture),
        _saas_runtime_configuration_execution(fixture),
        LegacySaasCentsFirstCompatibilityAdapter().run(fixture),
        standalone.run(fixture),
    ):
        for key, _ in _walk(execution.normalized_result):
            assert key not in PROHIBITED_RESULT_KEYS
        engine_result = execution.raw_result["pricing_engine_result"]
        for key, _ in _walk(engine_result):
            assert key not in PROHIBITED_RESULT_KEYS


def test_pure_engine_and_standalone_harness_remain_free_of_saas_runtime_imports():
    repo_root = Path(__file__).resolve().parents[2]
    embedded_engine_dir = repo_root / "backend" / "pricing_engine"
    package_root = Path(pricing_engine.__file__).resolve().parent
    assert not embedded_engine_dir.exists()
    assert not package_root.is_relative_to(embedded_engine_dir)
    assert "site-packages" in package_root.parts or "dist-packages" in package_root.parts
    roots = [
        *package_root.rglob("*.py"),
        Path("backend/tests/standalone_pricing_adapter_harness.py"),
    ]
    findings: list[tuple[str, int, str]] = []

    for path in roots:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in PROHIBITED_ENGINE_IMPORT_ROOTS:
                        findings.append((str(path), node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".", 1)[0]
                if root in PROHIBITED_ENGINE_IMPORT_ROOTS:
                    findings.append((str(path), node.lineno, module))

    assert findings == []
