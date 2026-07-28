"""EC9 Phase 9I-O pure line-engine extraction tests."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import importlib
import inspect
from pathlib import Path
import pkgutil
import subprocess
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
import app.services.pricing as pricing_service
from app.services.pricing_engine_adapter import (
    PRICING_ENGINE_RESULT_FIELD,
    calculate_pricing_with_cents_first_envelope,
)
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.pricing_snapshot_records import create_snapshot_record
from pricing_engine.adapters import build_legacy_line_result
from pricing_engine.config import build_starter_pack
from pricing_engine.line_engine import calculate_line
from pricing_engine.saved_items import BUSINESS_CARD_STARTER_ITEMS
from pricing_engine.snapshots import PRICING_SNAPSHOT_SCHEMA_FIELD, PRICING_SNAPSHOT_SCHEMA_VERSION

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (
    compare_fixture_result,
    load_fixture_pack,
    _cents_to_legacy_dollars,
    _dimension_to_legacy_inches,
    _project_cents_first_result_for_fixture,
    _quantity_to_legacy_int,
)


PROHIBITED_IMPORT_ROOTS = {
    "app",
    "fastapi",
    "motor",
    "pymongo",
    "requests",
    "httpx",
    "stripe",
    "openai",
}


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _legacy_args_from_fixture(fixture) -> dict:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    return {
        "settings": build_starter_pack(),
        "category": fixture.category,
        "width_inches": _dimension_to_legacy_inches(request.get("width")),
        "height_inches": _dimension_to_legacy_inches(request.get("height")),
        "quantity": _quantity_to_legacy_int(request["quantity"]),
        "material_key": request.get("material_key"),
        "design_needed": bool(request.get("design_needed", False)),
        "install_needed": bool(request.get("install_needed", False)),
        "manual_selling_price": _cents_to_legacy_dollars(request.get("manual_selling_price_cents")),
        "category_inputs": deepcopy(request.get("category_inputs") or {}),
        "material_profile": None,
        "pricing_components": [],
        "saved_item": None,
    }


def _pure_fixture_execution(fixture) -> dict:
    raw = calculate_line(**_legacy_args_from_fixture(fixture))
    line_result = build_legacy_line_result(
        category_id=fixture.category,
        legacy_result=raw,
        normalized_input=fixture.document["normalized_inputs"]["calculator_request"],
        execution_path="pricing_engine.line_engine.calculate_line",
    )
    return {
        "raw": raw,
        "line_result": line_result,
        "normalized": _project_cents_first_result_for_fixture(line_result),
    }


def test_pure_line_engine_imports_without_saas_startup():
    code = (
        "import sys; "
        "from pricing_engine.line_engine import calculate_line; "
        "blocked=[m for m in sys.modules if m == 'app' or m.startswith('app.')]; "
        "assert blocked == [], blocked; "
        "print(calculate_line.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "calculate_line"


def test_pure_line_engine_contract_accepts_no_saas_identity_or_database_inputs():
    parameter_names = set(inspect.signature(calculate_line).parameters)
    prohibited = {
        "tenant_id",
        "user_id",
        "actor_user_id",
        "permissions",
        "db",
        "database",
        "request",
        "router",
        "audit",
        "entitlements",
        "license",
    }
    assert parameter_names.isdisjoint(prohibited)


def test_pure_pricing_engine_package_has_no_prohibited_runtime_imports():
    package = importlib.import_module("pricing_engine")
    imported_roots: set[str] = set()
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        imported = importlib.import_module(module.name)
        for value in imported.__dict__.values():
            module_name = getattr(value, "__module__", "")
            root = module_name.split(".", 1)[0]
            if root in PROHIBITED_IMPORT_ROOTS:
                imported_roots.add(root)
    assert imported_roots == set()


def test_all_nine_fixtures_execute_through_pure_line_engine_with_exact_expected_results():
    categories = set()
    for fixture in load_fixture_pack():
        execution = _pure_fixture_execution(fixture)
        compare_fixture_result(
            fixture,
            type("Execution", (), {
                "adapter_id": "pure_line_engine_9io_v1",
                "normalized_result": execution["normalized"],
            })(),
        )
        expected = fixture.document["expected_line_results"]
        assert execution["line_result"]["selling_price_cents"] == expected["selling_price_cents"]
        assert execution["line_result"]["suggested_price_cents"] == expected["suggested_price_cents"]
        assert execution["line_result"]["true_cost_cents"] == expected["true_cost_cents"]
        assert execution["line_result"]["profit_amount_cents"] == expected["profit_amount_cents"]
        assert execution["line_result"]["selected_method_id"] == expected["selected_method_id"]
        assert execution["line_result"]["warnings"] == expected["warnings"]
        assert execution["raw"]["selling_price"] is not None
        assert execution["raw"]["breakdown"]
        assert execution["raw"].get("persistent_entities_created", []) == []
        categories.add(fixture.category)
    assert categories == {fixture.category for fixture in load_fixture_pack()}


def test_saas_calculate_pricing_delegates_to_pure_line_engine(monkeypatch):
    fixture = next(item for item in load_fixture_pack() if item.category == "banners")
    calls = []
    real_calculate_line = pricing_service.calculate_line

    def spy_calculate_line(**kwargs):
        calls.append(kwargs["category"])
        return real_calculate_line(**kwargs)

    monkeypatch.setattr(pricing_service, "calculate_line", spy_calculate_line)

    result = pricing_service.calculate_pricing(**_legacy_args_from_fixture(fixture))

    assert calls == [fixture.category]
    assert result["selling_price"] is not None


def test_legacy_saas_and_pure_line_outputs_match_for_shared_fixtures():
    for fixture in load_fixture_pack():
        args = _legacy_args_from_fixture(fixture)
        pure = calculate_line(**args)
        saas = pricing_service.calculate_pricing(**args)
        for field in (
            "selling_price",
            "suggested_price",
            "true_cost",
            "profit_amount",
            "profit_margin_percent",
            "pricing_method_used",
            "canonical_method_id",
            "pricing_method_results",
            "breakdown",
            "detail_sections",
        ):
            assert pure.get(field) == saas.get(field)


@pytest.mark.asyncio
async def test_pricing_calculate_endpoint_and_snapshots_remain_compatible(seeded_users):
    user = seeded_users["user_a"]
    fixture = next(item for item in load_fixture_pack() if item.category == "digital_print")
    args = _legacy_args_from_fixture(fixture)
    expected = fixture.document["expected_line_results"]
    snapshots_before = await db.pricing_snapshot_records.count_documents({"tenant_id": user["tenant_id"]})
    try:
        async with await _client_as(user) as client:
            response = await client.post(
                "/api/pricing/calculate",
                json={
                    "category": args["category"],
                    "width_inches": args["width_inches"],
                    "height_inches": args["height_inches"],
                    "quantity": args["quantity"],
                    "material_key": args["material_key"],
                    "design_needed": args["design_needed"],
                    "install_needed": args["install_needed"],
                    "category_inputs": args["category_inputs"],
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
        assert body.get("minimum_policy") == "digital_print_item_minimum_document_order_minimum"
        assert await db.pricing_snapshot_records.count_documents({"tenant_id": user["tenant_id"]}) == snapshots_before

        snapshot = build_calculated_snapshot(calc_result=body, quantity=args["quantity"])
        record = await create_snapshot_record(
            tenant_id=user["tenant_id"],
            source_type="quote_line_item",
            source_id=f"line-9io-{uuid.uuid4().hex[:8]}",
            quote_id=f"quote-9io-{uuid.uuid4().hex[:8]}",
            item_doc={
                "id": f"line-9io-{uuid.uuid4().hex[:8]}",
                "tenant_id": user["tenant_id"],
                "category": fixture.category,
                "description": "9I-O digital print",
                "quantity": args["quantity"],
                "unit_price_cents": expected["selling_price_cents"],
                "suggested_price_cents": expected["selling_price_cents"],
                "selected_price_source": "suggested",
                "pricing_status": "calculated",
                "pricing_snapshot": snapshot,
            },
            calculated_by_user_id=user["id"],
        )
        assert snapshot[PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
        assert snapshot[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
        assert record[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_saved_calculation_path_uses_pure_engine_without_mutating_unrelated_records(seeded_users):
    user = seeded_users["user_a"]
    fixture = next(item for item in load_fixture_pack() if item.category == "custom")
    args = _legacy_args_from_fixture(fixture)
    saved_before = await db.pricing_saved_calculations.count_documents({"tenant_id": user["tenant_id"]})
    result = calculate_pricing_with_cents_first_envelope(**args)

    assert result[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == fixture.document["expected_line_results"]["selling_price_cents"]
    assert await db.pricing_saved_calculations.count_documents({"tenant_id": user["tenant_id"]}) == saved_before


def test_promotional_saved_item_tier_and_missing_tier_behavior_match_saas_path():
    saved_item = BUSINESS_CARD_STARTER_ITEMS[0]
    settings = build_starter_pack()
    base = {
        "settings": settings,
        "category": "promotional",
        "width_inches": None,
        "height_inches": None,
        "quantity": int(saved_item["quantity_tiers"][0]["quantity"]),
        "category_inputs": {"pricing_method": "tier_pricing"},
        "saved_item": deepcopy(saved_item),
    }
    pure_tier = calculate_line(**base)
    saas_tier = pricing_service.calculate_pricing(**base)
    assert pure_tier["selling_price"] == saas_tier["selling_price"]
    assert pure_tier["tier_match"] is True

    missing = {**base, "quantity": int(saved_item["quantity_tiers"][0]["quantity"]) + 1}
    pure_missing = calculate_line(**missing)
    saas_missing = pricing_service.calculate_pricing(**missing)
    assert pure_missing["selling_price"] is None
    assert pure_missing["requires_manual_price"] is True
    assert pure_missing["pricing_method_used"] == saas_missing["pricing_method_used"]


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), float("-inf"), "not-a-number"])
def test_boolean_malformed_and_nonfinite_money_remain_rejected_by_cents_adapter(bad):
    raw = calculate_line(
        settings=build_starter_pack(),
        category="custom",
        width_inches=None,
        height_inches=None,
        quantity=1,
        category_inputs={"unit_price": "1.00"},
    )
    raw["selling_price"] = bad
    with pytest.raises(Exception):
        build_legacy_line_result(category_id="custom", legacy_result=raw)


def test_phase_9io_expected_cents_are_not_duplicated_in_this_test_file():
    source = Path(__file__).read_text(encoding="utf-8")
    for fixture in load_fixture_pack():
        cents = fixture.document["expected_line_results"]["selling_price_cents"]
        if cents is not None:
            assert str(cents) not in source
