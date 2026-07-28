"""EC9 Phase 9I-N - pricing snapshot schema normalization."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing_snapshot import build_calculated_snapshot, build_manual_snapshot
from app.services.pricing_snapshot_records import create_snapshot_record, get_snapshot_record
sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (
    LegacySaasCentsFirstCompatibilityAdapter,
    assert_required_starter_coverage,
    load_fixture_pack,
)
from pricing_engine import ContractValidationError
from pricing_engine.snapshots import (
    LEGACY_SNAPSHOT_READER_ID,
    PRICING_ENGINE_RESULT_FIELD,
    PRICING_SNAPSHOT_SCHEMA_FIELD,
    PRICING_SNAPSHOT_SCHEMA_VERSION,
    read_embedded_snapshot,
)


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _fixture_calc(fixture) -> dict:
    execution = LegacySaasCentsFirstCompatibilityAdapter().run(fixture)
    return {
        **execution.raw_result["legacy_result"],
        PRICING_ENGINE_RESULT_FIELD: execution.raw_result[PRICING_ENGINE_RESULT_FIELD],
    }


def _fixture_quantity(fixture) -> int:
    raw = fixture.document["normalized_inputs"]["calculator_request"]["quantity"]["value"]
    return int(Decimal(raw))


def _fixture_payload(fixture) -> dict:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    width = request.get("width")
    height = request.get("height")
    return {
        "description": f"9I-N {fixture.category}",
        "unit_price_cents": 1,
        "selected_price_source": "suggested",
        "category": fixture.category,
        "quantity": _fixture_quantity(fixture),
        "width_inches": float(Decimal(width["value"])) if width else None,
        "height_inches": float(Decimal(height["value"])) if height else None,
        "material_key": request.get("material_key"),
        "design_needed": bool(request.get("design_needed", False)),
        "install_needed": bool(request.get("install_needed", False)),
        "category_inputs": deepcopy(request.get("category_inputs") or {}),
    }


async def _seed_customer(tenant_id: str) -> str:
    customer_id = f"cust-9in-{uuid.uuid4().hex[:8]}"
    await db.customers.insert_one({
        "id": customer_id,
        "tenant_id": tenant_id,
        "name": "Phase 9I-N Customer",
        "email": "phase9in@example.com",
    })
    return customer_id


@pytest.mark.asyncio
async def test_all_nine_categories_create_normalized_embedded_and_record_snapshots(seeded_users):
    user = seeded_users["user_a"]
    fixtures = load_fixture_pack()
    assert_required_starter_coverage(fixtures)

    for fixture in fixtures:
        expected = fixture.document["expected_line_results"]
        calc = _fixture_calc(fixture)
        quantity = _fixture_quantity(fixture)
        snapshot = build_calculated_snapshot(calc_result=calc, quantity=quantity)

        assert snapshot[PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
        assert snapshot[PRICING_ENGINE_RESULT_FIELD]["status"] == "success"
        assert snapshot[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
        assert snapshot["calculated_selling_price_cents"] == expected["selling_price_cents"]
        assert snapshot["pricing_engine_adapter_source"] == "legacy_saas_calculator_v1"
        assert snapshot["pricing_engine_calculation_source"] == "existing_legacy_saas_calculator_result"
        assert snapshot["rounding_policy_version"] == "pricing_rounding_v1_round_half_up_final_cents"
        assert isinstance(snapshot["decimal_rate_evidence"], list)
        assert "selected_selling_price_dollars" in snapshot

        item_doc = {
            "id": f"item-9in-{fixture.case_id}",
            "tenant_id": user["tenant_id"],
            "category": fixture.category,
            "description": fixture.document["description"],
            "quantity": quantity,
            "unit_price_cents": expected["selling_price_cents"],
            "suggested_price_cents": expected["selling_price_cents"],
            "selected_price_source": "suggested",
            "pricing_status": "calculated",
            "category_inputs": deepcopy(fixture.document["normalized_inputs"]["calculator_request"].get("category_inputs") or {}),
            "pricing_snapshot": snapshot,
        }
        record = await create_snapshot_record(
            tenant_id=user["tenant_id"],
            source_type="quote_line_item",
            source_id=item_doc["id"],
            quote_id=f"quote-9in-{fixture.case_id}",
            item_doc=item_doc,
            calculated_by_user_id=user["id"],
        )

        assert record[PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
        assert record[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
        assert record["calculated_selling_price_cents"] == snapshot["calculated_selling_price_cents"]
        assert record["selected_final_price_cents"] == item_doc["unit_price_cents"]
        assert record["pricing_engine_adapter_source"] == snapshot["pricing_engine_adapter_source"]
        assert record["breakdown_amounts_cents"] == snapshot["breakdown_amounts_cents"]
        assert record["component_amounts_cents"] == snapshot["component_amounts_cents"]

        raw_before = await db.pricing_snapshot_records.find_one({"id": record["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
        reopened = await get_snapshot_record(user["tenant_id"], record["id"])
        raw_after = await db.pricing_snapshot_records.find_one({"id": record["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
        assert reopened[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
        assert raw_after == raw_before


def test_new_calculated_snapshot_rejects_missing_failed_or_malformed_engine_result():
    base = {"category": "banners", "selling_price": 12.34, "pricing_method_used": "per_sqft"}
    with pytest.raises(ContractValidationError):
        build_calculated_snapshot(calc_result=base, quantity=1)
    with pytest.raises(ContractValidationError):
        build_calculated_snapshot(
            calc_result={**base, PRICING_ENGINE_RESULT_FIELD: {"status": "failed", "selling_price_cents": 1234}},
            quantity=1,
        )
    with pytest.raises(ContractValidationError):
        build_calculated_snapshot(
            calc_result={**base, PRICING_ENGINE_RESULT_FIELD: {"status": "success", "selling_price_cents": True}},
            quantity=1,
        )


def test_manual_snapshots_use_integer_cents_without_fake_engine_result():
    snapshot = build_manual_snapshot(
        unit_price_cents=4321,
        quantity=2,
        reason="manual quote",
        actor_user_id="u-9in",
        actor_email="u9in@example.com",
        source="user_entered",
    )
    assert snapshot[PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
    assert snapshot[PRICING_ENGINE_RESULT_FIELD] is None
    assert snapshot["manual_authoritative_unit_price_cents"] == 4321
    assert snapshot["selected_final_price_cents"] == 4321
    with pytest.raises(ContractValidationError):
        build_manual_snapshot(unit_price_cents=True, quantity=1)


def test_legacy_embedded_snapshot_reader_is_non_mutating_and_honest():
    cents_snapshot = {
        "source": "calculator",
        "category": "banners",
        "pricing_method": "legacy",
        "calculated_unit_price_cents": 999,
        "calculated_unit_price_dollars": 12.34,
    }
    original = deepcopy(cents_snapshot)
    read = read_embedded_snapshot(cents_snapshot)
    assert cents_snapshot == original
    assert read[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == 999
    assert "differs" in read[PRICING_ENGINE_RESULT_FIELD]["warnings"][0]

    dollar_snapshot = {
        "source": "calculator",
        "category": "banners",
        "pricing_method": "legacy",
        "calculated_unit_price_dollars": 12.345,
    }
    read_dollar = read_embedded_snapshot(dollar_snapshot)
    assert read_dollar[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == 1235
    assert read_dollar[PRICING_ENGINE_RESULT_FIELD]["adapter_source_id"] == LEGACY_SNAPSHOT_READER_ID
    assert read_dollar[PRICING_ENGINE_RESULT_FIELD]["legacy_source"]["stored_normalized"] is False

    bad = read_embedded_snapshot({"source": "calculator", "category": "banners"})
    assert "pricing_snapshot_compatibility_error" in bad
    assert bad.get(PRICING_ENGINE_RESULT_FIELD) is None


@pytest.mark.asyncio
async def test_legacy_snapshot_record_reader_does_not_backfill_or_mutate(seeded_users):
    user = seeded_users["user_a"]
    raw = {
        "id": f"snap-legacy-9in-{uuid.uuid4().hex[:8]}",
        "tenant_id": user["tenant_id"],
        "source_type": "quote_line_item",
        "source_id": "legacy-line-9in",
        "quote_id": "legacy-quote-9in",
        "category": "banners",
        "quantity": 1,
        "selected_price_source": "suggested",
        "selected_final_price_cents": 777,
        "suggested_price_dollars": 12.34,
        "status": "active",
        "created_at": "2026-07-28T00:00:00+00:00",
        "updated_at": "2026-07-28T00:00:00+00:00",
    }
    await db.pricing_snapshot_records.insert_one(deepcopy(raw))
    before = await db.pricing_snapshot_records.find_one({"id": raw["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
    read = await get_snapshot_record(user["tenant_id"], raw["id"])
    after = await db.pricing_snapshot_records.find_one({"id": raw["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
    assert read[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == raw["selected_final_price_cents"]
    assert read[PRICING_ENGINE_RESULT_FIELD]["adapter_source_id"] == LEGACY_SNAPSHOT_READER_ID
    assert after == before


@pytest.mark.asyncio
async def test_quote_order_revision_and_conversion_preserve_normalized_snapshot_evidence(seeded_users):
    user = seeded_users["user_a"]
    banner = next(fixture for fixture in load_fixture_pack() if fixture.category == "banners")
    payload = _fixture_payload(banner)
    expected = banner.document["expected_line_results"]
    customer_id = await _seed_customer(user["tenant_id"])

    try:
        async with await _client_as(user) as client:
            quote = (await client.post("/api/quotes", json={"customer_id": customer_id, "job_name": "9I-N quote"})).json()
            order = (await client.post("/api/orders", json={"customer_id": customer_id, "job_name": "9I-N order"})).json()

            quote_item_response = await client.post(f"/api/quotes/{quote['id']}/line-items", json=payload)
            order_item_response = await client.post(f"/api/orders/{order['id']}/items", json=payload)
            assert quote_item_response.status_code == 201, quote_item_response.text
            assert order_item_response.status_code == 201, order_item_response.text

            quote_item = quote_item_response.json()
            order_item = order_item_response.json()
            for item in (quote_item, order_item):
                snapshot = item["pricing_snapshot"]
                assert snapshot[PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
                assert snapshot[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
                assert item["unit_price_cents"] == expected["selling_price_cents"]

            quote_records = (await client.get(
                "/api/pricing/snapshots",
                params={"source_type": "quote_line_item", "source_id": quote_item["id"]},
            )).json()["items"]
            order_records = (await client.get(
                "/api/pricing/snapshots",
                params={"source_type": "order_item", "source_id": order_item["id"]},
            )).json()["items"]
            assert quote_records[0][PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
            assert order_records[0][PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]

            await client.post(f"/api/quotes/{quote['id']}/status", json={"status": "sent"})
            await client.patch(f"/api/quotes/{quote['id']}/line-items/{quote_item['id']}", json={"notes": "force revision"})
            revision = await client.get(f"/api/quotes/{quote['id']}/revisions/1")
            assert revision.status_code == 200
            assert revision.json()["line_items"][0]["pricing_snapshot"][PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]

            await client.post(f"/api/quotes/{quote['id']}/status", json={"status": "approved"})
            converted = await client.post(f"/api/quotes/{quote['id']}/convert-to-order")
            assert converted.status_code == 200, converted.text
            converted_order = converted.json()["order"]
            converted_order_read = await client.get(f"/api/orders/{converted_order['id']}")
            converted_item = converted_order_read.json()["items"][0]
            assert converted_item["pricing_snapshot"][PRICING_SNAPSHOT_SCHEMA_FIELD] == PRICING_SNAPSHOT_SCHEMA_VERSION
            assert converted_item["pricing_snapshot"][PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
            converted_records = (await client.get(
                "/api/pricing/snapshots",
                params={"source_type": "order_item", "source_id": converted_item["id"]},
            )).json()["items"]
            assert converted_records[0]["previous_snapshot_id"] == quote_records[0]["id"]
            assert converted_records[0][PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] == expected["selling_price_cents"]
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_cross_tenant_snapshot_records_remain_isolated(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    fixture = next(fixture for fixture in load_fixture_pack() if fixture.category == "services")
    expected = fixture.document["expected_line_results"]
    snapshot = build_calculated_snapshot(calc_result=_fixture_calc(fixture), quantity=_fixture_quantity(fixture))
    record = await create_snapshot_record(
        tenant_id=user_a["tenant_id"],
        source_type="quote_line_item",
        source_id=f"tenant-a-line-{uuid.uuid4().hex[:8]}",
        quote_id="tenant-a-quote",
        item_doc={
            "category": fixture.category,
            "description": "tenant scoped",
            "quantity": _fixture_quantity(fixture),
            "unit_price_cents": expected["selling_price_cents"],
            "suggested_price_cents": expected["selling_price_cents"],
            "selected_price_source": "suggested",
            "pricing_snapshot": snapshot,
        },
        calculated_by_user_id=user_a["id"],
    )
    assert await get_snapshot_record(user_a["tenant_id"], record["id"]) is not None
    assert await get_snapshot_record(user_b["tenant_id"], record["id"]) is None


def test_phase_9in_expected_cents_are_not_duplicated_in_this_test_file():
    source = __file__
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    for fixture in load_fixture_pack():
        cents = fixture.document["expected_line_results"]["selling_price_cents"]
        if cents is not None:
            assert str(cents) not in text
