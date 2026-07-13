"""EC9 Phase 9E-2 — Apparel & Promotional Items calculators.

Covers: Apparel garment tier tables (HTV/screen-print), sizes/plus-size,
decoration method cost-plus paths, setup/personalization/specialty/rush,
hidden-field no-op behavior, manual price; Promotional Items pricing methods
(tier/per-piece/flat/manual), progressive-disclosure charges (setup,
decoration, personalization, shipping), Business Card exact-tier reuse
through the real `/api/pricing/calculate` endpoint (never invents a price
for a non-matching quantity), and tenant isolation / integer-cents money.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing
from app.services.starter_defaults import build_starter_pack


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def e2_ctx():
    ta = f"t-9e2-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "T9E2"})
    yield {"ua": ua, "ta": ta}
    _clear()


# ---------- Apparel ----------

def test_apparel_htv_table_based_price_at_gildan_5000_qty25_front():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=25,
                          category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"})
    assert r["decoration_table_based"] is True
    assert r["decoration_table_revenue"] == 225.00  # 25 x $9.00 (25-49 tier, front)
    assert r["selling_price"] >= 225.00


def test_apparel_quantity_changes_tier():
    settings = build_starter_pack()
    qty1 = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"})
    qty100 = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=100,
                               category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"})
    assert qty1["decoration_table_revenue"] == 12.00       # 1 x $12.00 (1-4 tier)
    assert qty100["decoration_table_revenue"] == 775.00     # 100 x $7.75 (100+ tier)


def test_apparel_blank_product_cost_affects_estimated_cost():
    settings = build_starter_pack()
    tee = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                            category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000"})
    hoodie = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                               category_inputs={"garment_type": "hoodie", "brand": "gildan_18500"})
    assert hoodie["material_cost"] > tee["material_cost"]
    assert hoodie["true_cost"] > tee["true_cost"]


def test_apparel_customer_supplied_zeroes_blank_cost():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "customer_supplied": True})
    assert r["material_cost"] == 0.0


def test_apparel_decoration_method_affects_pricing():
    settings = build_starter_pack()
    embroidery = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                                   category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "embroidery", "stitch_count": 5000})
    dtg = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                            category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "dtg"})
    assert embroidery["decoration_material_cost"] != dtg["decoration_material_cost"]
    assert embroidery["setup_cost"] == 25.00
    assert dtg["setup_cost"] == 5.00


def test_apparel_placement_locations_affect_pricing():
    settings = build_starter_pack()
    front = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                              category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"})
    both = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                             category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_back"})
    assert both["decoration_table_revenue"] > front["decoration_table_revenue"]


def test_apparel_hat_uses_hat_tier_table_and_blank_cost():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=5,
                          category_inputs={"garment_type": "premium_cap", "placement": "front_only"})
    assert r["is_hat"] is True
    assert r["decoration_table_revenue"] == 65.00  # 5 x $13.00 (5-24 tier, front)


def test_apparel_setup_and_personalization_add_to_totals():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                             category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000"})
    with_name = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                                  category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000",
                                                   "custom_name_number": True, "custom_name_number_count": 10})
    assert with_name["personalization_cost"] > base["personalization_cost"] == 0
    assert with_name["true_cost"] > base["true_cost"]


def test_apparel_plus_size_upcharge_auto_counted_from_sizes():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"garment_type": "hoodie", "brand": "gildan_18500",
                                          "sizes": {"M": 3, "L": 2, "2XL": 4, "3XL": 1}})
    assert r["plus_size_count"] == 5
    assert r["quantity"] == 10  # sum of all sizes


def test_apparel_rush_affects_final_pricing():
    settings = build_starter_pack()
    normal = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                               category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000"})
    rushed = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                               category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "rush": True})
    assert rushed["rush_applied"] is True
    assert rushed["selling_price"] > normal["selling_price"]


def test_apparel_manual_price_remains_available():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=10,
                          category_inputs={"garment_type": "hoodie", "brand": "gildan_18500"}, manual_selling_price=500.0)
    assert r["selling_price"] == 500.0
    assert r["pricing_method_used"] == "manual_override"
    assert r["suggested_price"] > 0


def test_apparel_hidden_fields_do_not_affect_pricing():
    """two_tone_hat_finish / leather_patch are hat-only — supplying them on a
    non-hat garment must be a silent no-op, never a hidden price change."""
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000"})
    with_hat_fields = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                                        category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000",
                                                         "two_tone_hat_finish": True, "leather_patch": True})
    assert base["true_cost"] == with_hat_fields["true_cost"]


# ---------- Promotional Items ----------

def test_promotional_per_piece_pricing_scales_with_quantity_and_unit_cost():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=50,
                          category_inputs={"pricing_method": "per_piece", "known_supplier_cost": True, "unit_cost": 2.00})
    assert r["material_cost"] == 100.00
    assert r["true_cost"] > 0
    assert r["selling_price"] > r["true_cost"]


def test_promotional_setup_decoration_personalization_shipping_hidden_until_toggled():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=10,
                             category_inputs={"pricing_method": "per_piece", "unit_cost": 1.00})
    with_extras = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=10,
                                    category_inputs={
                                        "pricing_method": "per_piece", "unit_cost": 1.00,
                                        "setup_required": True, "setup_fee": 15.00,
                                        "decoration_fee_required": True, "decoration_fee_type": "per_piece", "decoration_fee_amount": 0.50,
                                        "personalization_required": True, "personalization_count": 10, "personalization_fee": 0.25,
                                        "shipping_required": True, "shipping_cost": 8.00,
                                    })
    assert base["setup_cost"] == 0.0
    assert with_extras["setup_cost"] == 15.00
    assert with_extras["finishing_cost"] == 5.00       # decoration: 10 x $0.50
    assert with_extras["personalization_cost"] == 2.50  # 10 x $0.25
    assert with_extras["shipping_cost"] == 8.00
    assert with_extras["true_cost"] > base["true_cost"]


def test_promotional_flat_fee_pricing_method():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"pricing_method": "flat_fee", "flat_fee_price": 42.00})
    assert r["selling_price"] == 42.00
    assert r["pricing_method_used"] == "flat_fee"


def test_promotional_manual_price_separate_from_suggested():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"pricing_method": "per_piece", "unit_cost": 5.00}, manual_selling_price=99.0)
    assert r["selling_price"] == 99.0
    assert r["suggested_price"] is not None and r["suggested_price"] != 99.0


def test_promotional_tier_pricing_without_saved_item_requires_manual_price():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=100,
                          category_inputs={"pricing_method": "tier_pricing"}, saved_item=None)
    assert r["requires_manual_price"] is True
    assert r["selling_price"] is None
    assert r["suggested_price"] is None


# ---------- Business Cards (through the real /api/pricing/calculate endpoint) ----------

@pytest.mark.asyncio
async def test_business_card_calculate_endpoint_exact_tier_matches(e2_ctx):
    ua = e2_ctx["ua"]
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        std_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Standard Paper Business Cards")
        mag_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Magnetic Business Cards")

        for qty, expected in [(100, 25.0), (250, 45.0), (500, 75.0), (1000, 125.0), (2000, 175.0), (2500, 225.0)]:
            r = await c.post("/api/pricing/calculate", json={
                "category": "promotional", "quantity": qty, "saved_item_id": std_id,
                "category_inputs": {"pricing_method": "tier_pricing"},
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["tier_match"] is True
            assert body["selling_price"] == expected, f"qty={qty} expected {expected} got {body['selling_price']}"

        for qty, expected in [(25, 25.0), (50, 50.0), (100, 75.0), (200, 100.0), (500, 175.0), (1000, 275.0)]:
            r = await c.post("/api/pricing/calculate", json={
                "category": "promotional", "quantity": qty, "saved_item_id": mag_id,
                "category_inputs": {"pricing_method": "tier_pricing"},
            })
            assert r.status_code == 200
            assert r.json()["selling_price"] == expected
    _clear()


@pytest.mark.asyncio
async def test_business_card_calculate_endpoint_nonmatching_quantity_never_invents_price(e2_ctx):
    ua = e2_ctx["ua"]
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        std_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Standard Paper Business Cards")
        r = await c.post("/api/pricing/calculate", json={
            "category": "promotional", "quantity": 300, "saved_item_id": std_id,
            "category_inputs": {"pricing_method": "tier_pricing"},
        })
        assert r.status_code == 200
        body = r.json()
        assert body["tier_match"] is False
        assert body["requires_manual_price"] is True
        assert body["selling_price"] is None
        # manual pricing must remain available on the same request
        r2 = await c.post("/api/pricing/calculate", json={
            "category": "promotional", "quantity": 300, "saved_item_id": std_id,
            "category_inputs": {"pricing_method": "tier_pricing"}, "manual_selling_price": 60.0,
        })
        assert r2.json()["selling_price"] == 60.0
    _clear()


@pytest.mark.asyncio
async def test_calculate_rejects_unknown_saved_item_id(e2_ctx):
    ua = e2_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/calculate", json={
            "category": "promotional", "quantity": 100, "saved_item_id": "nonexistent-saved-item",
        })
        assert r.status_code == 404
    _clear()


@pytest.mark.asyncio
async def test_promotional_tenant_isolation_on_saved_item_reference(e2_ctx):
    """A saved item id from one tenant must 404 when calculated under another tenant."""
    ua = e2_ctx["ua"]
    other_tenant = f"t-9e2-other-{uuid.uuid4().hex[:6]}"
    other_user = {"id": f"u-o-{uuid.uuid4().hex[:6]}", "tenant_id": other_tenant,
                  "email": f"o-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": other_tenant, "slug": other_tenant, "name": "OTHER"})
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        std_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Standard Paper Business Cards")
    async with await _client(other_user) as c2:
        r = await c2.post("/api/pricing/calculate", json={
            "category": "promotional", "quantity": 100, "saved_item_id": std_id,
        })
        assert r.status_code == 404
    _clear()


def test_promotional_flat_fee_snapshot_uses_integer_cents():
    """Shared: selling_price is float dollars from the calculator itself
    (matches every other category — cents conversion happens one layer up,
    in `pricing_snapshot.build_calculated_snapshot`)."""
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="promotional", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"pricing_method": "flat_fee", "flat_fee_price": 42.00})
    from app.services.pricing_snapshot import build_calculated_snapshot
    snap = build_calculated_snapshot(calc_result=r, quantity=1)
    assert snap["calculated_unit_price_cents"] == 4200
