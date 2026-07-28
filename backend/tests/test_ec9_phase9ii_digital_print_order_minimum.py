"""EC9 Phase 9I-I - Digital Print document-level order minimum enforcement."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.order_pricing import compute_document_totals_with_pricing_adjustments
from app.services.pricing import calculate_pricing, get_or_init_pricing_settings
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.starter_defaults import build_starter_pack


COUNTED_COLLECTIONS = [
    "pricing_settings",
    "audit_events",
    "pricing_snapshot_records",
    "pricing_saved_calculations",
    "quotes",
    "quote_line_items",
    "orders",
    "order_items",
    "work_orders",
]


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_customer(tenant_id: str) -> str:
    customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    await db.customers.insert_one({
        "id": customer_id,
        "tenant_id": tenant_id,
        "name": "Digital Print Buyer",
        "email": "buyer@example.com",
    })
    return customer_id


async def _new_quote(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/quotes", json={"customer_id": customer_id, "job_name": "Digital Print minimum quote"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _new_order(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/orders", json={"customer_id": customer_id, "job_name": "Digital Print minimum order"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _tenant_counts(tenant_id: str) -> dict[str, int]:
    return {
        name: await getattr(db, name).count_documents({"tenant_id": tenant_id})
        for name in COUNTED_COLLECTIONS
    }


def _settings_for_minimums(*, item_minimum: float = 20.0, order_minimum: float = 40.0) -> dict:
    settings = build_starter_pack()
    digital = settings["category_defaults"]["digital_print"]
    digital["item_minimum"] = item_minimum
    digital["order_minimum"] = order_minimum
    settings["shop_defaults"]["minimum_order_amount"] = 0.0
    return settings


def _calc(settings: dict, *, quantity: int = 1, width: float = 6, height: float = 6, manual: float | None = None, inputs: dict | None = None) -> dict:
    return calculate_pricing(
        settings=settings,
        category="digital_print",
        width_inches=width,
        height_inches=height,
        quantity=quantity,
        manual_selling_price=manual,
        category_inputs=inputs or {},
    )


def _digital_payload(**overrides) -> dict:
    payload = {
        "description": "Tiny digital print",
        "quantity": 1,
        "unit_price_cents": 1,
        "category": "digital_print",
        "width_inches": 6,
        "height_inches": 6,
        "selected_price_source": "suggested",
    }
    payload.update(overrides)
    return payload


def _banner_payload(**overrides) -> dict:
    payload = {
        "description": "Banner line",
        "quantity": 1,
        "unit_price_cents": 10000,
        "category": "banners",
        "selected_price_source": "manual",
        "manual_price_cents": 10000,
    }
    payload.update(overrides)
    return payload


def _assert_doc_minimum(doc: dict, *, eligible: int, order_minimum: int, adjustment: int, total: int):
    evidence = doc["digital_print_minimum"]
    assert evidence["policy"] == "digital_print_document_order_minimum"
    assert evidence["scope"] == "quote_or_order_document"
    assert evidence["eligible_subtotal_cents"] == eligible
    assert evidence["order_minimum_cents"] == order_minimum
    assert evidence["order_minimum_adjustment_cents"] == adjustment
    assert evidence["adjustment_applied"] is (adjustment > 0)
    assert evidence["adjustment_count"] == (1 if adjustment > 0 else 0)
    assert doc["digital_print_order_minimum_adjustment_cents"] == adjustment
    assert doc["document_pricing_adjustment_cents"] == adjustment
    assert doc["subtotal_cents"] == total
    assert doc["total_cents"] == total


async def _get_quote(client: AsyncClient, quote_id: str) -> dict:
    response = await client.get(f"/api/quotes/{quote_id}")
    assert response.status_code == 200, response.text
    return response.json()["quote"]


async def _get_order(client: AsyncClient, order_id: str) -> dict:
    response = await client.get(f"/api/orders/{order_id}")
    assert response.status_code == 200, response.text
    return response.json()["order"]


def test_standalone_digital_print_applies_item_minimum_only_and_reports_document_rule():
    result = _calc(_settings_for_minimums(), quantity=1)

    assert result["pre_minimum_selling_price"] == 16.45
    assert result["selling_price"] == 20.0
    assert result["suggested_price"] == 20.0
    assert result["minimum_policy"] == "digital_print_item_minimum_document_order_minimum"
    assert result["minimum_scope"] == "digital_print_line_item"
    assert result["item_minimum"] == 20.0
    assert result["order_minimum"] == 40.0
    assert result["item_minimum_total"] == 20.0
    assert result["minimum_charge_applied"] is True
    assert result["minimum_adjustment"] == 3.55
    assert result["minimum_applied_reason"] == "item_minimum"
    assert any(row["label"] == "Digital Print item minimum adjustment" for row in result["breakdown"])
    assert not any(row["label"] == "Digital Print minimum adjustment" for row in result["breakdown"])
    assert any("document level" in warning for warning in result["calculation_warnings"])


def test_standalone_quantity_two_uses_item_floor_without_order_floor():
    result = _calc(_settings_for_minimums(), quantity=2)

    assert result["selling_price"] == 40.0
    assert result["item_minimum_total"] == 40.0
    assert result["order_minimum"] == 40.0
    assert result["minimum_applied_reason"] == "item_minimum"


@pytest.mark.parametrize(
    "width,height,expected_line_total,expected_adjustment",
    [
        (6, 6, 20.00, 20.00),
        (18, 18, 21.38, 18.62),
        (24, 24, 38.00, 2.00),
        (48, 96, 304.00, 0.00),
    ],
)
def test_document_minimum_helper_uses_stored_line_amounts_and_applies_once(width, height, expected_line_total, expected_adjustment):
    result = _calc(_settings_for_minimums(), quantity=1, width=width, height=height)
    snapshot = build_calculated_snapshot(calc_result=result, quantity=1)
    item = {
        "id": f"line-{width}-{height}",
        "category": "digital_print",
        "quantity": 1,
        "unit_price_cents": round(expected_line_total * 100),
        "line_subtotal_cents": round(expected_line_total * 100),
        "line_total_cents": round(expected_line_total * 100),
        "selected_price_source": "suggested",
        "pricing_status": "calculated",
        "pricing_snapshot": snapshot,
    }

    totals = compute_document_totals_with_pricing_adjustments([item])

    _assert_doc_minimum(
        totals,
        eligible=round(expected_line_total * 100),
        order_minimum=4000,
        adjustment=round(expected_adjustment * 100),
        total=4000 if expected_adjustment else round(expected_line_total * 100),
    )


def test_document_minimum_helper_counts_multiple_digital_print_lines_once():
    one = {
        "id": "dp-1", "category": "digital_print", "quantity": 1, "unit_price_cents": 2000,
        "line_subtotal_cents": 2000, "line_total_cents": 2000,
        "pricing_snapshot": build_calculated_snapshot(calc_result=_calc(_settings_for_minimums()), quantity=1),
    }
    two = {**one, "id": "dp-2"}

    totals = compute_document_totals_with_pricing_adjustments([one, two])

    _assert_doc_minimum(totals, eligible=4000, order_minimum=4000, adjustment=0, total=4000)
    assert totals["digital_print_minimum"]["eligible_line_item_ids"] == ["dp-1", "dp-2"]


def test_document_minimum_helper_excludes_non_digital_print_amounts():
    dp = {
        "id": "dp", "category": "digital_print", "quantity": 1, "unit_price_cents": 2000,
        "line_subtotal_cents": 2000, "line_total_cents": 2000,
        "pricing_snapshot": build_calculated_snapshot(calc_result=_calc(_settings_for_minimums()), quantity=1),
    }
    banner = {
        "id": "banner", "category": "banners", "quantity": 1, "unit_price_cents": 10000,
        "line_subtotal_cents": 10000, "line_total_cents": 10000, "pricing_snapshot": {},
    }

    totals = compute_document_totals_with_pricing_adjustments([dp, banner])

    _assert_doc_minimum(totals, eligible=2000, order_minimum=4000, adjustment=2000, total=14000)
    assert totals["line_subtotal_cents"] == 12000


def test_digital_print_setup_finishing_and_rounding_remain_inside_line_subtotal():
    result = _calc(_settings_for_minimums(), width=18, height=18, inputs={
        "laminate": True,
        "contour_cut": True,
        "piece_separation": True,
        "file_cleanup_needed": True,
    })

    assert result["selling_price"] > 21.38
    assert any(row["label"] == "Finishing" for row in result["breakdown"])
    assert any(row["label"] == "File cleanup" for row in result["breakdown"])
    assert result["order_minimum"] == 40.0


@pytest.mark.parametrize(
    "bad_update,message",
    [
        ({"item_minimum": None}, "item_minimum"),
        ({"order_minimum": None}, "order_minimum"),
        ({"item_minimum": -1}, "item_minimum"),
        ({"order_minimum": -1}, "order_minimum"),
    ],
)
def test_digital_print_missing_or_invalid_minimum_config_fails_clearly(bad_update, message):
    settings = _settings_for_minimums()
    settings["category_defaults"]["digital_print"].update(bad_update)

    with pytest.raises(ValueError, match=message):
        _calc(settings)


@pytest.mark.asyncio
async def test_digital_print_minimum_is_tenant_scoped_and_config_based(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    async with await _client_as(user_a) as client:
        response = await client.patch(
            "/api/pricing/settings/categories/digital_print",
            json={"extras": {"item_minimum": 55.0, "order_minimum": 125.0}},
        )
        assert response.status_code == 200, response.text
        customer_id = await _seed_customer(user_a["tenant_id"])
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        assert line.json()["unit_price_cents"] == 5500
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=5500, order_minimum=12500, adjustment=7000, total=12500)

    async with await _client_as(user_b) as client:
        customer_id = await _seed_customer(user_b["tenant_id"])
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        assert line.json()["unit_price_cents"] == 2000
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_digital_print_minimum_calculation_is_non_mutating(clean_db):
    tenant_id = f"tenant-{uuid.uuid4().hex}"
    before = await _tenant_counts(tenant_id)

    result = _calc(_settings_for_minimums(), quantity=2)

    assert result["mutated"] is False
    assert result["persistent_entities_created"] == []
    assert await _tenant_counts(tenant_id) == before


@pytest.mark.asyncio
async def test_existing_tenant_settings_receive_new_minimum_keys_by_additive_merge(seeded_users):
    user = seeded_users["user_a"]
    stale_pack = build_starter_pack()
    stale_pack["tenant_id"] = user["tenant_id"]
    stale_pack["starter_default_version"] = "1.2.0"
    stale_pack["category_defaults"]["digital_print"].pop("item_minimum", None)
    stale_pack["category_defaults"]["digital_print"].pop("order_minimum", None)
    stale_pack["category_defaults"]["digital_print"]["minimum_charge"] = 77.0
    await db.pricing_settings.delete_many({"tenant_id": user["tenant_id"]})
    await db.pricing_settings.insert_one(stale_pack)

    merged = await get_or_init_pricing_settings(user["tenant_id"])

    digital = merged["category_defaults"]["digital_print"]
    assert digital["item_minimum"] == 20.0
    assert digital["order_minimum"] == 40.0
    assert digital["minimum_charge"] == 77.0


@pytest.mark.asyncio
async def test_quote_and_order_apply_document_minimum_once(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        order_id = await _new_order(client, customer_id)
        quote_line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        order_line = await client.post(f"/api/orders/{order_id}/items", json=_digital_payload())

        assert quote_line.status_code == 201, quote_line.text
        assert order_line.status_code == 201, order_line.text
        for item in (quote_line.json(), order_line.json()):
            assert item["unit_price_cents"] == 2000
            assert item["suggested_price_cents"] == 2000
            assert item["line_subtotal_cents"] == 2000
            assert item["pricing_snapshot"]["selected_selling_price_dollars"] == 20.0
            assert item["pricing_snapshot"]["order_minimum"] == 40.0
        _assert_doc_minimum(await _get_quote(client, quote_id), eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
        _assert_doc_minimum(await _get_order(client, order_id), eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_quantity_two_line_satisfies_document_minimum_without_adjustment(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        response = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload(quantity=2))
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["unit_price_cents"] == 2000
        assert item["line_subtotal_cents"] == 4000
        _assert_doc_minimum(await _get_quote(client, quote_id), eligible=4000, order_minimum=4000, adjustment=0, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_two_separate_digital_print_lines_equaling_minimum_do_not_double_apply(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        first = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload(description="First tiny print"))
        second = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload(description="Second tiny print"))
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=4000, order_minimum=4000, adjustment=0, total=4000)
        assert quote["digital_print_minimum"]["adjustment_count"] == 0
    _clear()


@pytest.mark.asyncio
async def test_multiple_line_update_and_delete_recompute_aggregate(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        order_id = await _new_order(client, customer_id)
        first = await client.post(f"/api/orders/{order_id}/items", json=_digital_payload(description="First tiny print"))
        second = await client.post(f"/api/orders/{order_id}/items", json=_digital_payload(description="Second tiny print"))
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        _assert_doc_minimum(await _get_order(client, order_id), eligible=4000, order_minimum=4000, adjustment=0, total=4000)

        updated = await client.patch(
            f"/api/orders/{order_id}/items/{first.json()['id']}",
            json={"width_inches": 24, "height_inches": 24, "recalculate": True},
        )
        assert updated.status_code == 200, updated.text
        quote_after_update = await _get_order(client, order_id)
        _assert_doc_minimum(quote_after_update, eligible=5800, order_minimum=4000, adjustment=0, total=5800)

        deleted = await client.delete(f"/api/orders/{order_id}/items/{first.json()['id']}")
        assert deleted.status_code == 204, deleted.text
        _assert_doc_minimum(await _get_order(client, order_id), eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_mixed_digital_print_and_banner_keeps_banner_out_of_minimum(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        dp = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        banner = await client.post(f"/api/quotes/{quote_id}/line-items", json=_banner_payload())
        assert dp.status_code == 201, dp.text
        assert banner.status_code == 201, banner.text
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=2000, order_minimum=4000, adjustment=2000, total=14000)
        assert quote["digital_print_minimum"]["eligible_line_item_ids"] == [dp.json()["id"]]
    _clear()


@pytest.mark.asyncio
async def test_document_minimum_is_applied_before_existing_line_discount_and_tax(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        response = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload(discount_cents=500, tax_cents=300))
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["line_subtotal_cents"] == 2000
        assert item["line_total_cents"] == 1800
        quote = await _get_quote(client, quote_id)
        assert quote["discount_cents"] == 500
        assert quote["tax_cents"] == 300
        assert quote["digital_print_order_minimum_adjustment_cents"] == 2000
        assert quote["subtotal_cents"] == 4000
        assert quote["total_cents"] == 3800
    _clear()


@pytest.mark.asyncio
async def test_quote_revision_captures_document_minimum_snapshot(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        sent = await client.post(f"/api/quotes/{quote_id}/status", json={"status": "sent"})
        assert sent.status_code == 200, sent.text
        patched = await client.patch(
            f"/api/quotes/{quote_id}/line-items/{line.json()['id']}",
            json={"width_inches": 48, "height_inches": 96, "recalculate": True},
        )
        assert patched.status_code == 200, patched.text
        revision = await client.get(f"/api/quotes/{quote_id}/revisions/1")
        assert revision.status_code == 200, revision.text
        old_snapshot = revision.json()
        _assert_doc_minimum(old_snapshot, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
        current = await _get_quote(client, quote_id)
        _assert_doc_minimum(current, eligible=30400, order_minimum=4000, adjustment=0, total=30400)
    _clear()


@pytest.mark.asyncio
async def test_quote_to_order_conversion_preserves_document_minimum_without_recalculation(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        before_quote = await _get_quote(client, quote_id)
        assert before_quote["digital_print_order_minimum_adjustment_cents"] == 2000

        await client.patch(
            "/api/pricing/settings/categories/digital_print",
            json={"extras": {"item_minimum": 55.0, "order_minimum": 125.0}},
        )
        converted = await client.post(f"/api/quotes/{quote_id}/convert-to-order", json={})
        assert converted.status_code == 200, converted.text
        order = converted.json()["order"]
        _assert_doc_minimum(order, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
        order_id = order["id"]
        stored_order = await _get_order(client, order_id)
        _assert_doc_minimum(stored_order, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_historical_snapshot_stability_after_defaults_change(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        original_snapshot = line.json()["pricing_snapshot"]
        assert original_snapshot["order_minimum"] == 40.0
        await client.patch(
            "/api/pricing/settings/categories/digital_print",
            json={"extras": {"item_minimum": 55.0, "order_minimum": 125.0}},
        )
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)
        stored_line = await db.quote_line_items.find_one({"id": line.json()["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
        assert stored_line["pricing_snapshot"] == original_snapshot
    _clear()


@pytest.mark.asyncio
async def test_cross_tenant_records_and_forged_minimum_payloads_are_rejected_or_ignored(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    customer_id = await _seed_customer(user_a["tenant_id"])
    async with await _client_as(user_a) as client:
        quote_id = await _new_quote(client, customer_id)
        payload = _digital_payload(
            digital_print_minimum={"eligible_subtotal_cents": 999999},
            document_pricing_adjustment_cents=-999999,
            subtotal_cents=1,
            total_cents=1,
        )
        response = await client.post(f"/api/quotes/{quote_id}/line-items", json=payload)
        assert response.status_code == 201, response.text
        quote = await _get_quote(client, quote_id)
        _assert_doc_minimum(quote, eligible=2000, order_minimum=4000, adjustment=2000, total=4000)

    async with await _client_as(user_b) as client:
        response = await client.get(f"/api/quotes/{quote_id}")
        assert response.status_code == 404
    _clear()


@pytest.mark.asyncio
async def test_authorized_manual_override_keeps_reason_and_document_minimum(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        order_id = await _new_order(client, customer_id)
        response = await client.post(f"/api/orders/{order_id}/items", json=_digital_payload(
            description="Owner-approved sample print",
            manual_price_cents=500,
            selected_price_source="manual",
            manual_override_reason="manager-approved sample",
        ))
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["unit_price_cents"] == 500
        assert item["suggested_price_cents"] == 2000
        assert item["pricing_snapshot"]["override_reason"] == "manager-approved sample"
        order = await _get_order(client, order_id)
        _assert_doc_minimum(order, eligible=500, order_minimum=4000, adjustment=3500, total=4000)
    _clear()


@pytest.mark.asyncio
async def test_manual_override_below_digital_print_minimum_without_reason_is_rejected(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        response = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload(
            description="Unexplained sample print",
            manual_price_cents=500,
            selected_price_source="manual",
        ))
        assert response.status_code == 400
        assert "Override reason required" in response.text
    _clear()


@pytest.mark.asyncio
async def test_legacy_quote_and_order_records_without_minimum_fields_remain_readable(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    quote_id = f"legacy-quote-{uuid.uuid4().hex[:8]}"
    order_id = f"legacy-order-{uuid.uuid4().hex[:8]}"
    await db.quotes.insert_one({
        "id": quote_id, "tenant_id": user["tenant_id"], "number": 9001, "customer_id": customer_id,
        "job_name": "Legacy quote", "revision_number": 1, "status": "draft", "created_by": user["id"],
        "subtotal_cents": 2000, "discount_cents": 0, "tax_cents": 0, "total_cents": 2000,
    })
    await db.orders.insert_one({
        "id": order_id, "tenant_id": user["tenant_id"], "number": 9002, "customer_id": customer_id,
        "job_name": "Legacy order", "status": "draft", "created_by": user["id"],
        "subtotal_cents": 2000, "discount_cents": 0, "tax_cents": 0, "total_cents": 2000, "balance_cents": 2000,
    })
    await db.quote_line_items.insert_one({
        "id": f"qli-{uuid.uuid4().hex[:8]}", "tenant_id": user["tenant_id"], "quote_id": quote_id,
        "revision_number": 1, "position": 0, "description": "Legacy DP", "category": "digital_print",
        "quantity": 1, "unit_price_cents": 2000, "line_subtotal_cents": 2000, "line_total_cents": 2000,
        "pricing_snapshot": {},
    })
    await db.order_items.insert_one({
        "id": f"oi-{uuid.uuid4().hex[:8]}", "tenant_id": user["tenant_id"], "order_id": order_id,
        "position": 0, "description": "Legacy DP", "category": "digital_print",
        "quantity": 1, "unit_price_cents": 2000, "line_subtotal_cents": 2000, "line_total_cents": 2000,
        "pricing_snapshot": {},
    })

    async with await _client_as(user) as client:
        quote_response = await client.get(f"/api/quotes/{quote_id}")
        order_response = await client.get(f"/api/orders/{order_id}")
        assert quote_response.status_code == 200, quote_response.text
        assert order_response.status_code == 200, order_response.text
        _assert_doc_minimum(quote_response.json()["totals"], eligible=2000, order_minimum=0, adjustment=0, total=2000)
        _assert_doc_minimum(order_response.json()["totals"], eligible=2000, order_minimum=0, adjustment=0, total=2000)
    _clear()


def test_digital_print_minimum_snapshot_fields_are_line_level_context_only():
    result = _calc(_settings_for_minimums(), quantity=1)

    snapshot = build_calculated_snapshot(calc_result=result, quantity=1)

    assert snapshot["selected_selling_price_dollars"] == 20.0
    assert snapshot["minimum_policy"] == "digital_print_item_minimum_document_order_minimum"
    assert snapshot["minimum_scope"] == "digital_print_line_item"
    assert snapshot["pre_minimum_selling_price"] == result["pre_minimum_selling_price"]
    assert snapshot["item_minimum"] == 20.0
    assert snapshot["order_minimum"] == 40.0
    assert snapshot["item_minimum_total"] == 20.0
    assert snapshot["order_minimum_total"] == 40.0
    assert snapshot["minimum_charge_applied"] is True
    assert snapshot["minimum_adjustment"] == 3.55
    assert snapshot["minimum_applied_reason"] == "item_minimum"


def test_banner_behavior_remains_unchanged_by_digital_print_minimums():
    settings = build_starter_pack()
    before = calculate_pricing(
        settings=settings,
        category="banners",
        width_inches=96,
        height_inches=36,
        quantity=1,
        category_inputs={"selected_pricing_method": "square_foot_plus_addons"},
    )
    after = calculate_pricing(
        settings=settings,
        category="banners",
        width_inches=96,
        height_inches=36,
        quantity=1,
        category_inputs={"selected_pricing_method": "square_foot_plus_addons"},
    )

    assert after == before
    assert "minimum_policy" not in after
