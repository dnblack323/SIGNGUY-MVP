"""EC9 Phase 9I-S portable pricing configuration export/preview tests."""
from __future__ import annotations

from copy import deepcopy
import importlib
import ast
import inspect
from pathlib import Path
import subprocess
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.core.permissions import Perm
from app.deps import get_current_user
from app.services.pricing_config_export import export_portable_pricing_configuration
from app.services.pricing_engine_config_adapter import build_line_engine_configuration
from app.services.starter_defaults import build_starter_pack
from pricing_engine.adapters import build_legacy_line_result
from pricing_engine.config import CATEGORY_IDS
from pricing_engine.config_export import (
    PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID,
    PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION,
    build_portable_configuration,
    deserialize_portable_configuration,
    validate_portable_configuration,
)
from pricing_engine.line_engine import calculate_line
from pricing_engine.validation import ContractValidationError

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (  # noqa: E402
    AdapterExecutionResult,
    _cents_to_legacy_dollars,
    _dimension_to_legacy_inches,
    _project_cents_first_result_for_fixture,
    _quantity_to_legacy_int,
    compare_fixture_result,
    load_fixture_pack,
)


FORBIDDEN_KEYS = {
    "_id",
    "tenant_id",
    "actor_user_id",
    "actor_email",
    "email",
    "permissions",
    "db",
    "database",
    "collection",
    "request",
    "auth",
    "audit",
    "entitlements",
    "stripe",
    "license",
    "licensing",
    "secret",
    "token",
    "api_key",
}


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def _category_configs(settings: dict) -> dict[str, dict]:
    return {
        category: build_line_engine_configuration(settings=settings, category=category)
        for category in CATEGORY_IDS
    }


def _fixture_args(fixture, engine_settings_by_category: dict[str, dict]) -> dict:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    return {
        "settings": engine_settings_by_category[fixture.category],
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


def _walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _contains_typed_leaf(value: dict, contract: str) -> bool:
    return any(isinstance(item, dict) and item.get("contract") == contract for _, item in _walk(value))


def _assert_no_forbidden_or_float_values(value):
    for key, item in _walk(value):
        assert key not in FORBIDDEN_KEYS
        assert not isinstance(item, float)


def test_portable_export_contract_covers_all_categories_and_sanitizes_values():
    settings = build_starter_pack()
    settings.update({
        "_id": "mongo-id",
        "tenant_id": "tenant-a",
        "actor_email": "owner@example.com",
        "secret_token": "not-portable",
        "category_method_configurations": {"digital_print": {"configuration_version": 4}},
    })
    settings["category_defaults"]["digital_print"]["order_minimum"] = 47.25
    original = deepcopy(settings)

    portable = build_portable_configuration(
        category_configurations=_category_configs(settings),
        settings_version_evidence={"tenant_id": "tenant-a", "starter_default_version": "1.2.1"},
    )

    assert settings == original
    assert portable["schema_id"] == PORTABLE_PRICING_CONFIGURATION_SCHEMA_ID
    assert portable["schema_version"] == PORTABLE_PRICING_CONFIGURATION_SCHEMA_VERSION
    assert set(portable["category_configurations"]) == set(CATEGORY_IDS)
    _assert_no_forbidden_or_float_values(portable)
    assert _contains_typed_leaf(portable, "money_cents")
    assert _contains_typed_leaf(portable, "basis_points")
    assert _contains_typed_leaf(portable, "decimal_rate")

    digital_print = portable["category_configurations"]["digital_print"]["engine_settings"]
    order_minimum = digital_print["category_defaults"]["digital_print"]["order_minimum"]
    assert order_minimum == {"amount_cents": 4725, "contract": "money_cents", "currency": "USD"}

    second = build_portable_configuration(
        category_configurations=_category_configs(settings),
        settings_version_evidence={"tenant_id": "tenant-a", "starter_default_version": "1.2.1"},
    )
    assert second == portable


def test_portable_config_validation_rejects_unsafe_values_and_versions():
    portable = build_portable_configuration(
        category_configurations=_category_configs(build_starter_pack()),
        settings_version_evidence={},
    )

    with pytest.raises(ContractValidationError):
        validate_portable_configuration({**portable, "schema_version": "future"})

    missing = deepcopy(portable)
    missing["category_configurations"].pop("custom")
    with pytest.raises(ContractValidationError):
        validate_portable_configuration(missing)

    boolean_cents = deepcopy(portable)
    boolean_cents["category_configurations"]["banners"]["engine_settings"]["category_defaults"]["banners"]["minimum_charge"]["amount_cents"] = True
    with pytest.raises(ContractValidationError):
        validate_portable_configuration(boolean_cents)

    malformed_decimal = deepcopy(portable)
    malformed_decimal["category_configurations"]["banners"]["engine_settings"]["category_defaults"]["banners"]["default_markup_multiplier"]["value"] = "NaN"
    with pytest.raises(ContractValidationError):
        validate_portable_configuration(malformed_decimal)

    binary_float = deepcopy(portable)
    binary_float["category_configurations"]["banners"]["engine_settings"]["shop_defaults"]["production_hourly_rate"] = 28.0
    with pytest.raises(ContractValidationError):
        validate_portable_configuration(binary_float)


def test_exported_configuration_reproduces_shared_fixture_results_without_mongo(monkeypatch):
    settings = build_starter_pack()
    portable = build_portable_configuration(
        category_configurations=_category_configs(settings),
        settings_version_evidence={},
    )
    loaded = deserialize_portable_configuration(portable)
    categories = set()

    def deny_mongo(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("portable fixture execution must not touch Mongo")

    monkeypatch.setattr(db.pricing_settings, "find_one", deny_mongo)
    monkeypatch.setattr(db.pricing_settings, "insert_one", deny_mongo)
    monkeypatch.setattr(db.pricing_settings, "update_one", deny_mongo)

    for fixture in load_fixture_pack():
        raw = calculate_line(**_fixture_args(fixture, loaded["engine_settings_by_category"]))
        line_result = build_legacy_line_result(
            category_id=fixture.category,
            legacy_result=raw,
            normalized_input=fixture.document["normalized_inputs"]["calculator_request"],
        )
        compare_fixture_result(
            fixture,
            AdapterExecutionResult(
                adapter_id="portable_configuration_9is_fixture_runner",
                normalized_result=_project_cents_first_result_for_fixture(line_result),
                raw_result=raw,
            ),
        )
        categories.add(fixture.category)

    assert categories == set(CATEGORY_IDS)


def test_pure_portable_module_imports_without_saas_dependencies():
    module = importlib.import_module("pricing_engine.config_export")
    source = inspect.getsource(module)
    tree = ast.parse(source)

    forbidden_roots = {"app", "fastapi", "motor", "pymongo", "stripe", "openai"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".")[0].lower() for alias in node.names}
            assert imported.isdisjoint(forbidden_roots)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0].lower() not in forbidden_roots

    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import pricing_engine.config_export; print(any(name == 'app' or name.startswith('app.') for name in sys.modules))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert fresh.stdout.strip() == "False"


@pytest.mark.asyncio
async def test_export_and_preview_routes_are_tenant_scoped_permissioned_and_read_only(clean_db, seeded_users):
    user = seeded_users["user_a"]
    other = seeded_users["user_b"]
    settings = build_starter_pack()
    settings["tenant_id"] = user["tenant_id"]
    settings["category_defaults"]["banners"]["minimum_charge"] = 91.00
    await db.pricing_settings.insert_one(deepcopy(settings))

    try:
        async with await _client_as(user) as client:
            exported = await client.get("/api/pricing/settings/portable-configuration/export")
            assert exported.status_code == 200, exported.text
            portable = exported.json()
            assert portable["category_configurations"]["banners"]["engine_settings"]["category_defaults"]["banners"]["minimum_charge"]["amount_cents"] == 9100

            before = await db.pricing_settings.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
            preview = await client.post("/api/pricing/settings/portable-configuration/import-preview", json={"configuration": portable})
            assert preview.status_code == 200, preview.text
            body = preview.json()
            assert body["valid"] is True
            assert body["compatible"] is True
            assert body["preview_only"] is True
            assert body["applied"] is False
            assert body["calculation_ready"] is True
            assert body["comparison"]["summary"]["unchanged"] is True
            after = await db.pricing_settings.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
            assert after == before

            invalid = await client.post("/api/pricing/settings/portable-configuration/import-preview", json={"configuration": {"schema_id": "bad"}})
            assert invalid.status_code == 200, invalid.text
            assert invalid.json()["valid"] is False

            no_apply = await client.post("/api/pricing/settings/portable-configuration/import", json={"configuration": portable})
            assert no_apply.status_code == 404

        async with await _client_as(other) as client:
            other_export = await client.get("/api/pricing/settings/portable-configuration/export")
            assert other_export.status_code == 200, other_export.text
            other_portable = other_export.json()
            assert other_portable["category_configurations"]["banners"]["engine_settings"]["category_defaults"]["banners"]["minimum_charge"]["amount_cents"] != 9100

        no_read = {**user, "role": "no-pricing-access"}
        async with await _client_as(no_read) as client:
            denied = await client.get("/api/pricing/settings/portable-configuration/export")
            assert denied.status_code == 403

        read_only = {**user, "role": "read-only-pricing"}
        async with await _client_as(read_only) as client:
            allowed = await client.get("/api/pricing/settings/portable-configuration/export")
            assert allowed.status_code == 200
            denied_preview = await client.post("/api/pricing/settings/portable-configuration/import-preview", json={"configuration": portable})
            assert denied_preview.status_code == 403
    finally:
        _clear()


@pytest.fixture(autouse=True)
def _phase9is_test_roles(monkeypatch):
    from app import deps as deps_module
    from app.core.permissions import permissions_for_role as real_permissions_for_role

    def test_permissions_for_role(role: str) -> list[str]:
        if role == "no-pricing-access":
            return []
        if role == "read-only-pricing":
            return [Perm.PRICING_READ.value]
        return real_permissions_for_role(role)

    monkeypatch.setattr(deps_module, "permissions_for_role", test_permissions_for_role)
