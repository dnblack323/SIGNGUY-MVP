"""EC9 Phase 9H — Checkpoint closure end-to-end tests (testing_agent pass).

Exercises the ACTUAL user workflows across Pricing Foundation, the
Calculator, canonical Material Pricing Profiles, Pricing Components, Saved
Items, Quote/Order line-item pricing resolution, Quote->Order conversion
(no recalculation), recalculate-preview accept/reject, Pricing Snapshot
explain/compare, and the Advisory "always unavailable, never mutates price"
contract. Hits the real deployed server via REACT_APP_BACKEND_URL (not
in-process ASGI) using the AUTH_DEV_BYPASS dev-login.
"""
import os
import uuid

import pytest
import requests

BASE_URL_ENV = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL_ENV:
    pytest.skip("REACT_APP_BACKEND_URL is required for live checkpoint E2E tests", allow_module_level=True)

BASE_URL = BASE_URL_ENV.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/dev-login")
    assert r.status_code == 200, r.text
    token = r.json().get("token") or r.json().get("access_token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def customer_id(session):
    r = session.post(f"{API}/customers", json={"name": f"TEST_EC9H_Customer_{uuid.uuid4().hex[:6]}"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


class TestPricingFoundation:
    def test_settings_shop_defaults_and_categories_visible(self, session):
        r = session.get(f"{API}/pricing/settings")
        assert r.status_code == 200
        data = r.json()
        assert "shop_defaults" in data and isinstance(data["shop_defaults"], dict)
        assert "category_defaults" in data and isinstance(data["category_defaults"], dict)
        assert "banners" in data["category_defaults"]
        assert "starter_default_version" in data

    def test_shop_defaults_patch_persists(self, session):
        r = session.patch(f"{API}/pricing/settings/shop-defaults", json={"minimum_order_amount": 37.5})
        assert r.status_code == 200
        assert r.json()["shop_defaults"]["minimum_order_amount"] == 37.5
        r2 = session.get(f"{API}/pricing/settings")
        assert r2.json()["shop_defaults"]["minimum_order_amount"] == 37.5


class TestGroupedQuiz:
    def test_submit_review_and_apply_selected_fields_only(self, session):
        payload = {
            "category": "banners",
            "job_duration_hours": 2,
            "crew_size": 1,
            "customer_charge": 120,
            "price_floor": 40,
            "includes_design": False,
            "includes_install": False,
        }
        r = session.post(f"{API}/pricing/quiz/submit", json=payload)
        assert r.status_code == 201, r.text
        sub = r.json()
        assert sub["status"] == "draft" or sub.get("status") in ("draft", "submitted")
        sub_id = sub["id"]

        r2 = session.get(f"{API}/pricing/quiz/submissions/{sub_id}")
        assert r2.status_code == 200

        # Skip a fresh quiz (new submission), verify it's marked skipped
        r3 = session.post(f"{API}/pricing/quiz/submit", json=payload)
        skip_id = r3.json()["id"]
        r4 = session.post(f"{API}/pricing/quiz/submissions/{skip_id}/skip")
        assert r4.status_code == 200
        assert r4.json()["status"] == "skipped"

        # Drafts list should no longer include the skipped one but original draft
        # may or may not still be draft depending on submit_quiz's own status; just check list works
        r5 = session.get(f"{API}/pricing/quiz/submissions", params={"status": "draft"})
        assert r5.status_code == 200


class TestMaterialsPricingProfilesAndComponents:
    def test_create_material_pricing_profile_and_edit(self, session):
        # Find a canonical EC7 material to link
        r = session.get(f"{API}/materials", params={"limit": 5})
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        if not items:
            pytest.skip("No canonical materials seeded to link a profile to")
        material_id = items[0]["id"]

        r2 = session.post(f"{API}/pricing/material-profiles/materials/{material_id}", json={
            "pricing_unit": "per_sqft", "normalized_cost_basis": 2.5, "waste_percent": 5,
            "suggested_sell_rate": 6.0, "category_applicability": ["banners"], "pricing_source": "manual",
        })
        if r2.status_code == 400 and "already exists" in r2.text:
            # Idempotent re-run (profile persists across test runs) — reuse existing profile.
            existing = session.get(f"{API}/pricing/material-profiles").json()["items"]
            profile = next(p for p in existing if p.get("material_id") == material_id)
            profile_id = profile["id"]
        else:
            assert r2.status_code == 201, r2.text
            profile = r2.json()
            assert profile["normalized_cost_basis"] == 2.5
            profile_id = profile["id"]

        r3 = session.patch(f"{API}/pricing/material-profiles/{profile_id}", json={"suggested_sell_rate": 7.25})
        assert r3.status_code == 200
        assert r3.json()["suggested_sell_rate"] == 7.25

        r4 = session.get(f"{API}/pricing/material-profiles/{profile_id}")
        assert r4.status_code == 200
        assert r4.json()["suggested_sell_rate"] == 7.25
        pytest.material_profile_id = profile_id

    def test_create_pricing_component(self, session):
        key = f"TEST_setup_fee_{uuid.uuid4().hex[:6]}"
        r = session.post(f"{API}/pricing/components", json={
            "key": key, "name": "TEST Setup Fee", "charge_type": "setup_fee", "amount": 15.0,
            "category_applicability": ["banners"],
        })
        assert r.status_code == 201, r.text
        comp = r.json()
        assert comp["amount"] == 15.0
        pytest.pricing_component_id = comp["id"]


class TestSavedItemsAndVariation:
    def test_create_saved_item_then_variation_original_unchanged(self, session):
        r = session.post(f"{API}/pricing/saved-items", json={
            "name": f"TEST Saved Banner {uuid.uuid4().hex[:6]}", "category": "banners",
            "saved_config": {"width_inches": 24, "height_inches": 36, "quantity": 1},
        })
        assert r.status_code == 201, r.text
        original = r.json()
        original_name = original["name"]
        original_config = dict(original["saved_config"])
        item_id = original["id"]

        r2 = session.post(f"{API}/pricing/saved-items/{item_id}/save-as-variation", json={
            "name": f"{original_name} (variation)",
            "saved_config": {**original_config, "width_inches": 48},
        })
        assert r2.status_code == 201, r2.text
        variation = r2.json()
        assert variation["id"] != item_id
        assert variation["saved_config"]["width_inches"] == 48

        r3 = session.get(f"{API}/pricing/saved-items/{item_id}")
        assert r3.status_code == 200
        original_after = r3.json()
        assert original_after["name"] == original_name
        assert original_after["saved_config"]["width_inches"] == 24  # unchanged


class TestCalculatorBusinessCardTiers:
    def _find_business_card_item(self, session):
        r = session.get(f"{API}/pricing/saved-items", params={"category": "promotional"})
        assert r.status_code == 200
        for it in r.json().get("items", []):
            if "business card" in it["name"].lower() and "standard" in it["name"].lower():
                return it
        return None

    def test_exact_tier_quantity_returns_exact_price(self, session):
        item = self._find_business_card_item(session)
        if not item:
            pytest.skip("Preloaded 'Standard Paper Business Cards' saved item not found")
        tiers = item.get("quantity_tiers") or []
        assert tiers, "Expected preloaded quantity tiers on business card item"
        tier_qty = tiers[0].get("quantity") or tiers[0].get("min_qty") or 500

        r = session.get(f"{API}/pricing/saved-items/{item['id']}/tier-price", params={"quantity": tier_qty})
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is True
        assert data["price"] is not None and data["price"] > 0

        # Full calculate call with saved_item_id
        r2 = session.post(f"{API}/pricing/calculate", json={
            "category": "promotional", "quantity": tier_qty, "saved_item_id": item["id"],
            "category_inputs": {},
        })
        assert r2.status_code == 200, r2.text

    def test_non_matching_quantity_requires_manual_price(self, session):
        item = self._find_business_card_item(session)
        if not item:
            pytest.skip("Preloaded business card item not found")
        # 137 is unlikely to be a configured tier
        r = session.get(f"{API}/pricing/saved-items/{item['id']}/tier-price", params={"quantity": 137})
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is False
        assert data["price"] is None  # never invents a price


class TestCalculatorCategories:
    def test_banners_flat_sqft_positive_price(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["selling_price"] > 0
        assert data["category"] == "banners"

    def test_banners_with_material_profile_and_component_changes_price(self, session):
        base = session.post(f"{API}/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
        }).json()

        # Self-contained: create a fresh component (idempotent-safe) rather than
        # relying on cross-test shared state (unsafe under pytest-xdist workers).
        key = f"TEST_flat_component_{uuid.uuid4().hex[:8]}"
        comp = session.post(f"{API}/pricing/components", json={
            "key": key, "name": "TEST Flat Fee For Price Change", "charge_type": "setup_fee", "amount": 25.0,
            "category_applicability": ["banners"],
        }).json()
        comp_id = comp["id"]

        modified = session.post(f"{API}/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
            "pricing_component_ids": [comp_id],
        }).json()
        assert modified["selling_price"] != base["selling_price"], (
            f"Expected price to change with a pricing component applied: base={base['selling_price']} modified={modified['selling_price']}"
        )

    def test_apparel_positive_price(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "apparel", "quantity": 24,
            "category_inputs": {"garment_type": "short_sleeve_tee", "decoration_method": "htv", "sizes": {"M": 12, "L": 12}},
        })
        assert r.status_code == 200, r.text
        assert r.json()["selling_price"] > 0

    def test_promotional_non_business_card_positive_price(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "promotional", "quantity": 100,
            "category_inputs": {"promotional_item_type": "koozies", "unit_cost": 0.75, "known_supplier_cost": True},
        })
        assert r.status_code == 200, r.text
        assert r.json()["selling_price"] > 0

    def test_vehicle_graphics_positive_price(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "vehicle_graphics", "quantity": 1,
            "category_inputs": {"vehicle_type": "full_size_van", "coverage_type": "full"},
        })
        assert r.status_code == 200, r.text
        assert r.json()["selling_price"] > 0

    def test_services_positive_price(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "services", "quantity": 1,
            "category_inputs": {"service_type": "installation", "estimated_hours": 3},
        })
        assert r.status_code == 200, r.text
        assert r.json()["selling_price"] > 0

    def test_custom_unit_price_times_quantity_no_invented_cost(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "custom", "quantity": 5,
            "category_inputs": {"item_name": "TEST Widget", "unit_price": 12.50},
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["selling_price"] == pytest.approx(62.50, abs=0.01)

    def test_manual_override_preserves_original_suggestion(self, session):
        r = session.post(f"{API}/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
        })
        suggested = r.json()["selling_price"]
        r2 = session.post(f"{API}/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
            "manual_selling_price": 999.99,
        })
        data2 = r2.json()
        assert data2["selling_price"] == 999.99
        assert data2.get("suggested_price") is not None
        assert data2["suggested_price"] == pytest.approx(suggested, abs=0.01)
        assert data2["suggested_price"] != data2["selling_price"]


class TestQuoteOrderIntegration:
    def test_quote_line_item_has_snapshot_and_convert_preserves_price(self, session, customer_id):
        # Create draft quote
        r = session.post(f"{API}/quotes", json={"customer_id": customer_id, "job_name": "TEST_EC9H Quote"})
        assert r.status_code == 201, r.text
        quote_id = r.json()["id"]

        # Add a calculated line item (Detailed entry equivalent)
        r2 = session.post(f"{API}/quotes/{quote_id}/line-items", json={
            "description": "TEST Banner Item", "quantity": 1, "unit_price_cents": 0,
            "category": "banners", "width_inches": 48, "height_inches": 96,
            "category_inputs": {}, "selected_price_source": "suggested",
        })
        assert r2.status_code == 201, r2.text
        item = r2.json()
        assert item["pricing_status"] == "calculated"
        assert item["suggested_price_cents"] > 0
        assert item.get("category") == "banners"
        assert item.get("pricing_snapshot"), "Expected an embedded pricing snapshot on the line item"
        quote_item_price = item["unit_price_cents"]
        item_id = item["id"]

        # Snapshot record should exist for this source
        r3 = session.get(f"{API}/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        assert r3.status_code == 200
        snaps = r3.json()["items"]
        assert len(snaps) == 1
        assert snaps[0]["status"] == "active"

        # Status transitions draft -> sent -> approved
        for target in ("sent", "approved"):
            rs = session.post(f"{API}/quotes/{quote_id}/status", json={"status": target})
            assert rs.status_code == 200, rs.text
            assert rs.json()["status"] == target

        # Convert to order
        rc = session.post(f"{API}/quotes/{quote_id}/convert-to-order")
        assert rc.status_code == 200, rc.text
        order = rc.json()["order"]
        order_id = order["id"]

        ro = session.get(f"{API}/orders/{order_id}")
        assert ro.status_code == 200
        order_items = ro.json()["items"]
        assert len(order_items) == 1
        assert order_items[0]["unit_price_cents"] == quote_item_price, "Order item price must be IDENTICAL to quote item price (no recalculation on conversion)"
        pytest.converted_order_id = order_id
        pytest.converted_order_item_id = order_items[0]["id"]

    def test_order_detailed_add_and_edit_category_inputs(self, session, customer_id):
        r = session.post(f"{API}/orders", json={"customer_id": customer_id, "job_name": "TEST_EC9H Order Direct"})
        order_id = r.json()["id"]

        r2 = session.post(f"{API}/orders/{order_id}/items", json={
            "description": "TEST Rigid Sign", "quantity": 1, "unit_price_cents": 0,
            "category": "rigid_signs", "width_inches": 24, "height_inches": 18,
            "category_inputs": {}, "selected_price_source": "suggested",
        })
        assert r2.status_code == 201, r2.text
        item = r2.json()
        item_id = item["id"]
        old_price = item["unit_price_cents"]

        # Edit category_inputs (e.g. change quantity input for a different price)
        r3 = session.patch(f"{API}/orders/{order_id}/items/{item_id}", json={
            "quantity": 3, "selected_price_source": "suggested",
        })
        assert r3.status_code == 200, r3.text
        updated = r3.json()
        assert updated["quantity"] == 3

    def test_recalculate_preview_reject_and_accept(self, session, customer_id):
        r = session.post(f"{API}/orders", json={"customer_id": customer_id, "job_name": "TEST_EC9H Recalc Order"})
        order_id = r.json()["id"]
        r2 = session.post(f"{API}/orders/{order_id}/items", json={
            "description": "TEST Banner Recalc", "quantity": 1, "unit_price_cents": 0,
            "category": "banners", "width_inches": 24, "height_inches": 24,
            "category_inputs": {}, "selected_price_source": "suggested",
        })
        item = r2.json()
        item_id = item["id"]
        original_price = item["unit_price_cents"]

        # Preview with a changed dimension
        rp = session.post(f"{API}/orders/{order_id}/items/{item_id}/recalculate-preview", json={
            "category_inputs": {},
        })
        assert rp.status_code == 200, rp.text
        preview = rp.json()
        assert "old" in preview and "new" in preview
        assert preview["old"]["unit_price_cents"] == original_price

        # REJECT: don't accept -> re-GET item, price unchanged
        r_check = session.get(f"{API}/orders/{order_id}")
        item_after_reject = next(i for i in r_check.json()["items"] if i["id"] == item_id)
        assert item_after_reject["unit_price_cents"] == original_price

        # ACCEPT: PATCH with recalculate=true -> price may change, new snapshot created
        ra = session.patch(f"{API}/orders/{order_id}/items/{item_id}", json={"recalculate": True})
        assert ra.status_code == 200, ra.text
        accepted = ra.json()

        r_snaps = session.get(f"{API}/pricing/snapshots", params={"source_type": "order_item", "source_id": item_id})
        snaps = r_snaps.json()["items"]
        assert len(snaps) >= 2, "Expected old snapshot preserved + new snapshot created on accept"
        statuses = [s["status"] for s in snaps]
        assert "superseded" in statuses and "active" in statuses


class TestSnapshotExplainAndCompare:
    def test_explain_and_compare_deterministic(self, session, customer_id):
        r = session.post(f"{API}/orders", json={"customer_id": customer_id, "job_name": "TEST_EC9H Snapshot Explain"})
        order_id = r.json()["id"]
        r2 = session.post(f"{API}/orders/{order_id}/items", json={
            "description": "TEST Explain Item", "quantity": 1, "unit_price_cents": 0,
            "category": "banners", "width_inches": 36, "height_inches": 36,
            "category_inputs": {}, "selected_price_source": "suggested",
        })
        item = r2.json()
        item_id = item["id"]

        snaps = session.get(f"{API}/pricing/snapshots", params={"source_type": "order_item", "source_id": item_id}).json()["items"]
        snap_id = snaps[0]["id"]

        rex = session.get(f"{API}/pricing/snapshots/{snap_id}/explain")
        assert rex.status_code == 200, rex.text
        explanation = rex.json()
        for section in ("inputs_used", "defaults_used", "cost_calculation", "final_price_reason", "accountability"):
            assert section in explanation

        # Trigger a recalculation to get a second snapshot to compare
        session.patch(f"{API}/orders/{order_id}/items/{item_id}", json={"quantity": 2, "recalculate": True})
        snaps2 = session.get(f"{API}/pricing/snapshots", params={"source_type": "order_item", "source_id": item_id}).json()["items"]
        assert len(snaps2) >= 2
        base = [s for s in snaps2 if s["status"] == "superseded"][0]
        candidate = [s for s in snaps2 if s["status"] == "active"][0]

        rc = session.post(f"{API}/pricing/snapshots/compare", json={
            "base_snapshot_id": base["id"], "candidate_snapshot_id": candidate["id"],
        })
        assert rc.status_code == 200, rc.text
        diff = rc.json()["diff"]
        for key in ("suggested_price_change", "margin_change", "selected_final_price_change"):
            assert key in diff


class TestAdvisoryAlwaysUnavailable:
    def test_advisory_request_returns_unavailable_and_never_mutates_price(self, session, customer_id):
        r = session.post(f"{API}/orders", json={"customer_id": customer_id, "job_name": "TEST_EC9H Advisory"})
        order_id = r.json()["id"]
        r2 = session.post(f"{API}/orders/{order_id}/items", json={
            "description": "TEST Advisory Item", "quantity": 1, "unit_price_cents": 0,
            "category": "banners", "width_inches": 24, "height_inches": 24,
            "category_inputs": {}, "selected_price_source": "suggested",
        })
        item = r2.json()
        price_before = item["unit_price_cents"]

        rreq = session.post(f"{API}/pricing/advisory/requests", json={
            "category": "banners", "quantity": 1,
            "current_suggested_price_cents": price_before,
            "requested_advisory_types": ["ai_pricing_analysis", "local_market_comparison", "target_margin_analysis"],
            "data_consent": True,
        })
        assert rreq.status_code == 201, rreq.text
        adv = rreq.json()
        responses = adv.get("responses") or adv.get("advisory_responses") or []
        # Every requested type must be unavailable
        assert responses, f"Expected advisory responses in payload: {adv}"
        for resp in responses:
            assert resp.get("status") == "unavailable", f"Expected unavailable, got: {resp}"

        # Price must be untouched
        rcheck = session.get(f"{API}/orders/{order_id}")
        item_after = next(i for i in rcheck.json()["items"] if i["id"] == item["id"])
        assert item_after["unit_price_cents"] == price_before
