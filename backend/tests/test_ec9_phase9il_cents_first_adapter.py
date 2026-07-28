"""EC9 Phase 9I-L cents-first compatibility DTO tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import importlib
import json
import pkgutil
import subprocess
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent))

from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing
from app.services.pricing_engine_adapter import (
    PRICING_ENGINE_RESULT_FIELD,
    attach_cents_first_compatibility_envelope,
)
from app.services.starter_defaults import build_starter_pack
from pricing_engine import ROUNDING_POLICY_ID, ContractValidationError
from pricing_engine.adapters import (
    LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
    LEGACY_SAAS_CALCULATOR_SOURCE_ID,
    build_legacy_line_result,
)
from pricing_engine_fixture_runner import (
    FIXTURE_ENGINE_VERSION,
    FIXTURE_FORMULA_VERSION,
    FIXTURE_SCHEMA_VERSION,
    LegacySaasCalculatorAdapter,
    LegacySaasCentsFirstCompatibilityAdapter,
    compare_fixture_result,
    load_fixture,
    load_fixture_pack,
)


def _override(user):
    async def _get():
        return {**user}

    return _get


async def _client(user):
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_auth_override():
    app.dependency_overrides.pop(get_current_user, None)


def _legacy_success_result(**overrides):
    result = {
        "category": "custom",
        "selling_price": 12.345,
        "suggested_price": 12.345,
        "true_cost": 2.225,
        "profit_amount": 10.12,
        "profit_margin_percent": 81.977,
        "pricing_method_used": "unit_price_x_quantity",
        "canonical_method_id": "unit_price_x_quantity",
        "calculation_warnings": [],
        "pricing_method_results": [
            {
                "method_id": "unit_price_x_quantity",
                "selected": True,
                "available": True,
                "amount": 12.345,
                "status": ["selected", "authoritative_total"],
            }
        ],
        "breakdown": [{"label": "Manual line", "amount": 1.235}],
        "material_cost": 1.115,
    }
    result.update(overrides)
    return result


def test_pure_legacy_adapter_imports_without_application_startup():
    code = (
        "import sys; "
        "from pricing_engine.adapters import build_legacy_line_result; "
        "blocked=[m for m in sys.modules if m == 'app' or m.startswith('app.')]; "
        "assert blocked == [], blocked; "
        "print(build_legacy_line_result.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "build_legacy_line_result"


def test_pure_adapter_has_no_prohibited_saas_imports():
    prohibited_roots = {"app", "fastapi", "motor", "pymongo", "stripe", "requests", "httpx", "openai"}
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


def test_adapter_does_not_mutate_legacy_result_and_preserves_legacy_fields():
    legacy = _legacy_success_result()
    original = deepcopy(legacy)

    wrapped = attach_cents_first_compatibility_envelope(legacy_result=legacy)

    assert legacy == original
    assert wrapped["selling_price"] == original["selling_price"]
    assert wrapped["true_cost"] == original["true_cost"]
    assert wrapped["breakdown"] == original["breakdown"]
    assert wrapped[PRICING_ENGINE_RESULT_FIELD]["legacy_result_mutated"] is False


def test_valid_legacy_money_maps_to_integer_cents_with_round_half_up():
    result = build_legacy_line_result(category_id="custom", legacy_result=_legacy_success_result())

    assert result["selling_price_cents"] == 1235
    assert result["suggested_price_cents"] == 1235
    assert result["true_cost_cents"] == 223
    assert result["method_rows"][0]["amount_cents"] == 1235
    assert result["breakdown_amounts"][0]["amount_cents"] == 124
    assert result["component_amounts"][0]["amount_cents"] is not None


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), float("-inf"), "not-a-number"])
def test_boolean_nonfinite_and_malformed_monetary_values_are_rejected(bad):
    with pytest.raises(ContractValidationError):
        build_legacy_line_result(
            category_id="custom",
            legacy_result=_legacy_success_result(selling_price=bad),
        )


def test_signed_values_are_allowed_only_for_permitted_signed_components():
    result = build_legacy_line_result(
        category_id="custom",
        legacy_result=_legacy_success_result(
            profit_amount=-1.235,
            breakdown=[{"label": "Profit", "amount": -1.235}],
        ),
    )
    assert result["profit_amount_cents"] == -124
    assert result["breakdown_amounts"][0]["amount_cents"] == -124

    with pytest.raises(ContractValidationError, match="selling_price"):
        build_legacy_line_result(
            category_id="custom",
            legacy_result=_legacy_success_result(selling_price=-1.235),
        )


def test_unavailable_result_does_not_become_successful_zero_price():
    result = build_legacy_line_result(
        category_id="custom",
        legacy_result={
            "category": "custom",
            "selling_price": None,
            "pricing_method_used": "unit_price_x_quantity",
            "pricing_method_results": [
                {
                    "method_id": "unit_price_x_quantity",
                    "selected": False,
                    "available": False,
                    "amount": None,
                    "status": ["unavailable"],
                }
            ],
        },
    )

    assert result["status"] == "unavailable"
    assert result["selling_price_cents"] is None
    assert result["selected_method_amount_cents"] is None
    assert result["method_rows"][0]["amount_cents"] is None


def test_version_rounding_and_source_metadata_are_json_safe():
    result = build_legacy_line_result(category_id="custom", legacy_result=_legacy_success_result())

    assert result["dto_version"] == LEGACY_RESULT_COMPATIBILITY_DTO_VERSION
    assert result["fixture_schema_version"] == FIXTURE_SCHEMA_VERSION
    assert result["fixture_engine_version"] == FIXTURE_ENGINE_VERSION
    assert result["formula_version"] == FIXTURE_FORMULA_VERSION
    assert result["rounding_policy_version"] == ROUNDING_POLICY_ID
    assert result["adapter_source_id"] == LEGACY_SAAS_CALCULATOR_SOURCE_ID
    assert result["legacy_source"]["execution_path"] == "app.services.pricing.calculate_pricing"
    json.dumps(result)


def test_all_nine_fixtures_execute_through_cents_first_adapter_against_shared_expectations():
    fixtures = load_fixture_pack()
    adapter = LegacySaasCentsFirstCompatibilityAdapter()
    legacy_adapter = LegacySaasCalculatorAdapter()
    categories = set()
    for fixture in fixtures:
        legacy_execution = legacy_adapter.run(fixture)
        execution = adapter.run(fixture)
        compare_fixture_result(fixture, execution)
        assert execution.raw_result["legacy_result"] == legacy_execution.raw_result
        assert execution.raw_result["pricing_engine_result"]["adapter_source_id"] == LEGACY_SAAS_CALCULATOR_SOURCE_ID
        assert execution.raw_result["pricing_engine_result"]["selling_price_cents"] == fixture.document["expected_line_results"]["selling_price_cents"]
        categories.add(fixture.category)
    assert categories == {fixture.category for fixture in fixtures}


def test_identical_fixture_input_produces_deterministic_cents_first_output():
    fixture = load_fixture(Path(__file__).parent / "fixtures" / "pricing_engine" / "custom" / "custom_normal.json")
    adapter = LegacySaasCentsFirstCompatibilityAdapter()
    first = adapter.run(fixture).normalized_result
    second = adapter.run(fixture).normalized_result
    assert first == second


def test_fixture_expected_values_are_not_duplicated_in_adapter_tests():
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


@pytest.mark.asyncio
async def test_pricing_calculate_endpoint_returns_additive_envelope_without_persistence():
    tenant_id = f"t-9il-{uuid.uuid4().hex[:8]}"
    user = {
        "id": f"u-9il-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id,
        "email": f"u-{uuid.uuid4().hex[:8]}@example.com",
        "role": "owner",
        "is_active": True,
    }
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "T9IL"})
    fixture = load_fixture(Path(__file__).parent / "fixtures" / "pricing_engine" / "banners" / "banners_normal.json")
    request = fixture.document["normalized_inputs"]["calculator_request"]
    saved_before = await db.pricing_saved_calculations.count_documents({"tenant_id": tenant_id})
    snapshots_before = await db.pricing_snapshot_records.count_documents({"tenant_id": tenant_id})
    try:
        async with await _client(user) as client:
            response = await client.post(
                "/api/pricing/calculate",
                json={
                    "category": fixture.category,
                    "width_inches": 8,
                    "height_inches": 3,
                    "quantity": 1,
                    "category_inputs": request["category_inputs"],
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        legacy = calculate_pricing(
            settings=build_starter_pack(),
            category=fixture.category,
            width_inches=8,
            height_inches=3,
            quantity=1,
            category_inputs=request["category_inputs"],
        )
        for field in ("selling_price", "suggested_price", "true_cost", "breakdown", "pricing_method_used"):
            assert body[field] == legacy[field]
        envelope = body[PRICING_ENGINE_RESULT_FIELD]
        assert envelope["status"] == "success"
        assert envelope["selling_price_cents"] == fixture.document["expected_line_results"]["selling_price_cents"]
        assert envelope["selected_method_amount_cents"] == fixture.document["expected_line_results"]["selling_price_cents"]
        assert envelope["adapter_source_id"] == LEGACY_SAAS_CALCULATOR_SOURCE_ID
        assert envelope["legacy_source"]["adapter_id"] == LEGACY_SAAS_CALCULATOR_SOURCE_ID
        assert await db.pricing_saved_calculations.count_documents({"tenant_id": tenant_id}) == saved_before
        assert await db.pricing_snapshot_records.count_documents({"tenant_id": tenant_id}) == snapshots_before
    finally:
        _clear_auth_override()
