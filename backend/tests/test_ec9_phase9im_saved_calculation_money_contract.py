"""EC9 Phase 9I-M saved-calculation money/result normalization tests."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent))

from app.core.db import db
from app.core.permissions import Perm, permissions_for_role as real_permissions_for_role
from app.deps import get_current_user
import app.deps as deps_module
import app.services.pricing_saved_calculations as saved_service
from app.services.pricing_saved_calculations import (
    SAVED_CALCULATION_CONTRACT_VERSION,
    LEGACY_SAVED_CALCULATION_READER_ID,
    SavedCalculationError,
    create_saved_calculation,
)
from pricing_engine import ROUNDING_POLICY_ID
from pricing_engine.adapters import (
    LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
    LEGACY_SAAS_CALCULATOR_SOURCE_ID,
)
from pricing_engine_fixture_runner import (
    FIXTURE_ROOT,
    LegacySaasCentsFirstCompatibilityAdapter,
    compare_fixture_result,
    load_fixture_pack,
)
from server import app


DEFERRED_COLLECTIONS = [
    "pricing_calculation_records",
    "webstores",
    "webstore_products",
    "wrap_lab_projects",
    "wrap_lab_jobs",
    "quotes",
    "orders",
    "quote_line_items",
    "order_items",
    "work_orders",
    "pricing_snapshot_records",
]


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _dimension(value: dict | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(value["value"]))


def _quantity(value: dict) -> int:
    return int(Decimal(value["value"]))


def _manual_price(value: int | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(value) / Decimal("100"))


def _payload_from_fixture(fixture) -> dict:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    return {
        "category": fixture.category,
        "width_inches": _dimension(request.get("width")),
        "height_inches": _dimension(request.get("height")),
        "quantity": _quantity(request["quantity"]),
        "material_key": request.get("material_key"),
        "design_needed": bool(request.get("design_needed", False)),
        "install_needed": bool(request.get("install_needed", False)),
        "manual_selling_price": _manual_price(request.get("manual_selling_price_cents")),
        "category_inputs": deepcopy(request.get("category_inputs") or {}),
    }


async def _save(client: AsyncClient, fixture) -> dict:
    response = await client.post(
        "/api/pricing/saved-calculations",
        json={
            "name": f"{fixture.category} {uuid.uuid4().hex[:6]}",
            "notes": "9I-M normalized save",
            "calculation_inputs": _payload_from_fixture(fixture),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _tenant_counts(tenant_id: str) -> dict[str, int]:
    return {
        name: await db[name].count_documents({"tenant_id": tenant_id})
        for name in DEFERRED_COLLECTIONS
    }


@pytest.mark.asyncio
async def test_all_nine_categories_store_pricing_engine_result_and_recalculate_fresh(seeded_users):
    user = seeded_users["user_a"]
    fixtures = load_fixture_pack()
    adapter = LegacySaasCentsFirstCompatibilityAdapter()
    async with await _client_as(user) as client:
        for fixture in fixtures:
            execution = adapter.run(fixture)
            compare_fixture_result(fixture, execution)
            expected = fixture.document["expected_line_results"]
            saved = await _save(client, fixture)
            engine = saved["pricing_engine_result"]

            assert saved["saved_calculation_contract_version"] == SAVED_CALCULATION_CONTRACT_VERSION
            assert saved["selling_price"] is not None
            assert isinstance(saved["selling_price_cents"], int)
            assert not isinstance(saved["selling_price_cents"], bool)
            assert saved["selling_price_cents"] == engine["selling_price_cents"] == expected["selling_price_cents"]
            assert engine["dto_version"] == LEGACY_RESULT_COMPATIBILITY_DTO_VERSION
            assert engine["rounding_policy_version"] == ROUNDING_POLICY_ID
            assert engine["adapter_source_id"] == LEGACY_SAAS_CALCULATOR_SOURCE_ID
            assert engine["adapter_execution_path"] == "app.services.pricing.calculate_pricing"
            assert saved["pricing_reproducibility_ref"]["saved_calculation_contract_version"] == SAVED_CALCULATION_CONTRACT_VERSION
            assert saved["calculation_result"]["selling_price"] == saved["selling_price"]
            assert "pricing_engine_result" not in saved["calculation_result"]

            raw_before = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": saved["id"]}, {"_id": 0})
            reopened_response = await client.get(f"/api/pricing/saved-calculations/{saved['id']}")
            assert reopened_response.status_code == 200, reopened_response.text
            reopened = reopened_response.json()
            assert reopened["pricing_engine_result"] == saved["pricing_engine_result"]
            raw_after = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": saved["id"]}, {"_id": 0})
            assert raw_after == raw_before

            reuse = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
            assert reuse.status_code == 200, reuse.text
            reused = reuse.json()
            assert reused["current_pricing_engine_result"]["selling_price_cents"] == expected["selling_price_cents"]
            assert reused["current_selling_price_cents"] == expected["selling_price_cents"]
            assert reused["saved_selling_price_cents"] == expected["selling_price_cents"]
            assert reused["price_changed"] is False
            assert reused["transferable"] is True
    _clear()


@pytest.mark.asyncio
async def test_legacy_reader_authority_order_and_non_mutating_behavior(seeded_users):
    user = seeded_users["user_a"]
    tenant_id = user["tenant_id"]
    cents_id = f"legacy-cents-{uuid.uuid4().hex[:8]}"
    float_id = f"legacy-float-{uuid.uuid4().hex[:8]}"
    bad_id = f"legacy-bad-{uuid.uuid4().hex[:8]}"
    now = "2026-07-28T00:00:00+00:00"
    await db.pricing_saved_calculations.insert_many(
        [
            {
                "id": cents_id,
                "tenant_id": tenant_id,
                "name": "Legacy cents",
                "category": "custom",
                "calculation_inputs": {"category": "custom", "quantity": 1, "category_inputs": {}},
                "selling_price": 12.34,
                "selling_price_cents": 999,
                "calculation_result": {"category": "custom", "selling_price": 12.34},
                "source_context": "pricing_calculator",
                "created_by_user_id": user["id"],
                "archived": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": float_id,
                "tenant_id": tenant_id,
                "name": "Legacy float",
                "category": "custom",
                "calculation_inputs": {"category": "custom", "quantity": 1, "category_inputs": {}},
                "selling_price": 12.345,
                "calculation_result": {"category": "custom", "selling_price": 12.345},
                "source_context": "pricing_calculator",
                "created_by_user_id": user["id"],
                "archived": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": bad_id,
                "tenant_id": tenant_id,
                "name": "Legacy bad",
                "category": "custom",
                "calculation_inputs": {"category": "custom", "quantity": 1, "category_inputs": {}},
                "calculation_result": {"category": "custom"},
                "source_context": "pricing_calculator",
                "created_by_user_id": user["id"],
                "archived": False,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )

    raw_before = {
        item["id"]: item
        for item in await db.pricing_saved_calculations.find({"tenant_id": tenant_id, "id": {"$in": [cents_id, float_id, bad_id]}}, {"_id": 0}).to_list(None)
    }
    async with await _client_as(user) as client:
        cents_response = await client.get(f"/api/pricing/saved-calculations/{cents_id}")
        float_response = await client.get(f"/api/pricing/saved-calculations/{float_id}")
        bad_response = await client.get(f"/api/pricing/saved-calculations/{bad_id}")

    assert cents_response.status_code == 200, cents_response.text
    cents_doc = cents_response.json()
    assert cents_doc["pricing_engine_result"]["selling_price_cents"] == 999
    assert cents_doc["pricing_engine_result"]["adapter_source_id"] == LEGACY_SAVED_CALCULATION_READER_ID
    assert "differs" in cents_doc["pricing_engine_result"]["warnings"][0]

    assert float_response.status_code == 200, float_response.text
    float_doc = float_response.json()
    assert float_doc["pricing_engine_result"]["selling_price_cents"] == 1235
    assert float_doc["pricing_engine_result"]["legacy_source"]["source_field"] == "calculation_result.selling_price"

    assert bad_response.status_code == 200, bad_response.text
    assert "pricing_engine_result_compatibility_error" in bad_response.json()

    raw_after = {
        item["id"]: item
        for item in await db.pricing_saved_calculations.find({"tenant_id": tenant_id, "id": {"$in": [cents_id, float_id, bad_id]}}, {"_id": 0}).to_list(None)
    }
    assert raw_after == raw_before
    _clear()


@pytest.mark.asyncio
async def test_metadata_archive_restore_and_duplicate_preserve_immutable_result_evidence(seeded_users):
    user = seeded_users["user_a"]
    fixture = next(item for item in load_fixture_pack() if item.category == "custom")
    async with await _client_as(user) as client:
        saved = await _save(client, fixture)
        immutable_fields = {
            key: deepcopy(saved[key])
            for key in (
                "calculation_inputs",
                "calculation_result",
                "pricing_engine_result",
                "selling_price",
                "selling_price_cents",
                "pricing_method_results",
                "breakdown",
                "detail_sections",
                "pricing_reproducibility_ref",
            )
        }
        patch = await client.patch(f"/api/pricing/saved-calculations/{saved['id']}", json={"name": "Renamed", "notes": "notes only"})
        archive = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/archive")
        restore = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/restore")
        for response in (patch, archive, restore):
            assert response.status_code == 200, response.text
            for key, expected in immutable_fields.items():
                assert response.json()[key] == expected

        duplicate = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/duplicate", json={"name": "Duplicate"})
        assert duplicate.status_code == 201, duplicate.text
        duplicated = duplicate.json()
        assert duplicated["id"] != saved["id"]
        assert duplicated["duplicated_from_id"] == saved["id"]
        for key, expected in immutable_fields.items():
            assert duplicated[key] == expected

        legacy_id = f"legacy-dup-{uuid.uuid4().hex[:8]}"
        await db.pricing_saved_calculations.insert_one(
            {
                "id": legacy_id,
                "tenant_id": user["tenant_id"],
                "name": "Legacy duplicate source",
                "category": "custom",
                "calculation_inputs": {"category": "custom", "quantity": 1, "category_inputs": {}},
                "selling_price_cents": 1234,
                "calculation_result": {"category": "custom", "selling_price": 99.99},
                "source_context": "pricing_calculator",
                "created_by_user_id": user["id"],
                "archived": False,
            }
        )
        raw_legacy_before = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": legacy_id}, {"_id": 0})
        legacy_duplicate = await client.post(f"/api/pricing/saved-calculations/{legacy_id}/duplicate", json={"name": "Legacy Duplicate"})
        assert legacy_duplicate.status_code == 201, legacy_duplicate.text
        duplicated_legacy = legacy_duplicate.json()
        assert duplicated_legacy["pricing_engine_result"]["selling_price_cents"] == 1234
        assert duplicated_legacy["pricing_engine_result"]["adapter_source_id"] == LEGACY_SAVED_CALCULATION_READER_ID
        raw_legacy_after = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": legacy_id}, {"_id": 0})
        assert raw_legacy_after == raw_legacy_before
        duplicate_raw = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": duplicated_legacy["id"]}, {"_id": 0})
        assert duplicate_raw["pricing_engine_result"]["selling_price_cents"] == 1234
    _clear()


@pytest.mark.asyncio
async def test_create_rejects_missing_failed_or_invalid_normalized_authority(monkeypatch, seeded_users):
    user = seeded_users["user_a"]

    async with await _client_as(user) as client:
        failed = await client.post(
            "/api/pricing/saved-calculations",
            json={
                "name": "No tier",
                "calculation_inputs": {
                    "category": "promotional",
                    "quantity": 125,
                    "category_inputs": {"pricing_method": "tier_pricing"},
                },
            },
        )
        assert failed.status_code == 400

    def invalid_result(**kwargs):
        return {
            "category": "custom",
            "selling_price": 1.23,
            "pricing_engine_result": {
                "status": "success",
                "selling_price_cents": True,
                "category_id": "custom",
            },
        }

    monkeypatch.setattr(saved_service, "calculate_pricing_with_cents_first_envelope", invalid_result)
    with pytest.raises(SavedCalculationError, match="boolean"):
        await create_saved_calculation(
            user["tenant_id"],
            user,
            {
                "name": "Boolean cents",
                "calculation_inputs": {"category": "custom", "quantity": 1, "category_inputs": {"unit_price": "1.23"}},
            },
        )
    _clear()


@pytest.mark.asyncio
async def test_recalculate_uses_fresh_cents_blocks_archived_and_does_not_mutate_saved_record(seeded_users):
    user = seeded_users["user_a"]
    fixture = next(item for item in load_fixture_pack() if item.category == "services")
    async with await _client_as(user) as client:
        saved = await _save(client, fixture)
        raw_before = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": saved["id"]}, {"_id": 0})
        archived = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/archive")
        assert archived.status_code == 200, archived.text
        blocked = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
        assert blocked.status_code == 400
        restored = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/restore")
        assert restored.status_code == 200, restored.text
        reuse = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
        assert reuse.status_code == 200, reuse.text
        data = reuse.json()
        assert data["current_pricing_engine_result"]["status"] == "success"
        assert data["pricing_engine_result"] == data["current_pricing_engine_result"]
        assert data["current_selling_price_cents"] == data["current_pricing_engine_result"]["selling_price_cents"]
        assert data["saved_selling_price_cents"] == saved["pricing_engine_result"]["selling_price_cents"]
        assert data["price_changed"] is False
        assert data["transferable"] is True
        raw_after = await db.pricing_saved_calculations.find_one({"tenant_id": user["tenant_id"], "id": saved["id"]}, {"_id": 0})
        for key in ("calculation_inputs", "calculation_result", "pricing_engine_result", "selling_price_cents"):
            assert raw_after[key] == raw_before[key]
    _clear()


@pytest.mark.asyncio
async def test_tenant_permission_audit_and_no_unrelated_persistence(monkeypatch, seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    before_deferred = await _tenant_counts(user_a["tenant_id"])
    audit_before = await db.audit_events.count_documents({"tenant_id": user_a["tenant_id"], "action": {"$regex": "^pricing.saved_calculation"}})
    fixture = next(item for item in load_fixture_pack() if item.category == "banners")
    async with await _client_as(user_a) as client:
        saved = await _save(client, fixture)
        patch = await client.patch(f"/api/pricing/saved-calculations/{saved['id']}", json={"name": "Audit name"})
        duplicate = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/duplicate", json={"name": "Audit duplicate"})
        archive = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/archive")
        restore = await client.post(f"/api/pricing/saved-calculations/{saved['id']}/restore")
        assert all(response.status_code in {200, 201} for response in (patch, duplicate, archive, restore))

    async with await _client_as(user_b) as client:
        assert (await client.get(f"/api/pricing/saved-calculations/{saved['id']}")).status_code == 404
        assert (await client.patch(f"/api/pricing/saved-calculations/{saved['id']}", json={"name": "wrong"})).status_code == 404
        assert (await client.post(f"/api/pricing/saved-calculations/{saved['id']}/duplicate", json={"name": "wrong"})).status_code == 404
        assert (await client.post(f"/api/pricing/saved-calculations/{saved['id']}/archive")).status_code == 404
        assert (await client.post(f"/api/pricing/saved-calculations/{saved['id']}/restore")).status_code == 404
        assert (await client.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")).status_code == 404

    def test_permissions_for_role(role: str) -> list[str]:
        if role == "pricing-read-only":
            return [Perm.PRICING_READ.value]
        return real_permissions_for_role(role)

    monkeypatch.setattr(deps_module, "permissions_for_role", test_permissions_for_role)
    read_only = {**user_a, "role": "pricing-read-only"}
    async with await _client_as(read_only) as client:
        assert (await client.get("/api/pricing/saved-calculations")).status_code == 200
        assert (await client.post("/api/pricing/saved-calculations", json={"name": "Denied", "calculation_inputs": _payload_from_fixture(fixture)})).status_code == 403
        assert (await client.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")).status_code == 403

    audit_after = await db.audit_events.count_documents({"tenant_id": user_a["tenant_id"], "action": {"$regex": "^pricing.saved_calculation"}})
    assert audit_after >= audit_before + 5
    after_deferred = await _tenant_counts(user_a["tenant_id"])
    assert after_deferred == before_deferred
    _clear()


def test_phase_9im_expected_values_are_stored_only_in_shared_fixtures():
    source = Path(__file__).read_text(encoding="utf-8")
    fixture_values = {
        str(fixture.document["expected_line_results"]["selling_price_cents"])
        for fixture in load_fixture_pack()
        if fixture.document["expected_line_results"]["selling_price_cents"] is not None
    }
    assert fixture_values
    assert FIXTURE_ROOT.exists()
    for value in fixture_values:
        assert f"== {value}" not in source
        assert f": {value}" not in source
