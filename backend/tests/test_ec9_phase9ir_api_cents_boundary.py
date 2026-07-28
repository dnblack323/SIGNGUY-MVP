"""EC9 Phase 9I-R API cents-first boundary tests."""
from __future__ import annotations

import math

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.deps import get_current_user
from app.services.order_pricing import PricingTransferError, build_item_pricing_fields
from app.services.pricing_engine_adapter import PRICING_ENGINE_RESULT_FIELD


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_pricing_calculate_exposes_authoritative_integer_cents(seeded_users):
    user = seeded_users["user_a"]
    try:
        async with await _client_as(user) as client:
            response = await client.post("/api/pricing/calculate", json={
                "category": "banners",
                "width_inches": 96,
                "height_inches": 36,
                "quantity": 1,
                "category_inputs": {"selected_pricing_method": "square_foot_plus_addons"},
            })
        assert response.status_code == 200, response.text
        body = response.json()
        engine = body[PRICING_ENGINE_RESULT_FIELD]
        assert engine["status"] == "success"
        assert isinstance(engine["selling_price_cents"], int)
        assert not isinstance(engine["selling_price_cents"], bool)
        assert engine["selling_price_cents"] > 0
        assert engine["selling_price_cents"] == engine["selected_method_amount_cents"]
        assert body["selling_price"] is not None
    finally:
        _clear()


@pytest.mark.parametrize("bad_cents", [True, 1234.5, None])
def test_suggested_transfer_rejects_invalid_normalized_cents(bad_cents):
    with pytest.raises(PricingTransferError):
        build_item_pricing_fields(
            calc_result={
                "category": "banners",
                "selling_price": 99.99,
                PRICING_ENGINE_RESULT_FIELD: {
                    "status": "success",
                    "selling_price_cents": bad_cents,
                },
            },
            quantity=1,
            category="banners",
            category_inputs={},
            material_profile_id=None,
            pricing_component_ids=[],
            saved_item_id=None,
            manual_price_cents=None,
            selected_price_source="suggested",
            fallback_unit_price_cents=1,
            user_id="user-a",
            actor_email="owner@example.com",
            foundation_effective_at=None,
            manual_override_reason=None,
        )


@pytest.mark.parametrize("legacy_value", [math.nan, math.inf])
def test_invalid_legacy_float_cannot_become_transfer_price_without_valid_engine_cents(legacy_value):
    with pytest.raises(PricingTransferError):
        build_item_pricing_fields(
            calc_result={
                "category": "banners",
                "selling_price": legacy_value,
                PRICING_ENGINE_RESULT_FIELD: {
                    "status": "success",
                    "selling_price_cents": None,
                },
            },
            quantity=1,
            category="banners",
            category_inputs={},
            material_profile_id=None,
            pricing_component_ids=[],
            saved_item_id=None,
            manual_price_cents=None,
            selected_price_source="suggested",
            fallback_unit_price_cents=1,
            user_id="user-a",
            actor_email="owner@example.com",
            foundation_effective_at=None,
            manual_override_reason=None,
        )
