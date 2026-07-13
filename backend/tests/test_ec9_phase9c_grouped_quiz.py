"""EC9 Phase 9C — Grouped Pricing Setup Quiz tests.

Additive setup path alongside the existing detailed CategorySetupWizard.
Covers: grouped questions save correctly, derived suggestions calculate
correctly, owner can edit before applying, rejected suggestions are not
applied, existing values are not overwritten silently, skip/resume, the
detailed wizard still works, source labels persist, tenant isolation,
integer-cents money boundary, and applied-settings-snapshot preservation.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing_quiz import derive_quiz_suggestions
from app.services.starter_defaults import SHOP_DEFAULTS


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec9c_ctx():
    ta = f"t-ec9-9c-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec9-9cb-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


SAMPLE_ANSWERS = {
    "category": "banners", "job_duration_hours": 4, "crew_size": 2,
    "material_cost_estimate": 30, "customer_charge": 400, "price_floor": 250,
    "includes_design": True, "includes_install": False, "includes_setup": False,
    "includes_finishing": False, "difficulty": "typical",
}


def test_derive_suggestions_pure_function_math():
    suggestions, math_shown = derive_quiz_suggestions(dict(SAMPLE_ANSWERS), SHOP_DEFAULTS)
    # total_person_hours = 4 * 2 = 8; baseline = 400 (typical, mult=1.0)
    # design_allowance = 15% of 400 = 60; remaining = 340; material=30 -> labor_dollars=310
    # labor_rate = 310/8 = 38.75
    assert suggestions["labor_rate"] == 38.75
    assert suggestions["effective_shop_rate"] == 50.0  # 400/8
    assert suggestions["minimum_charge"] == 250.0
    assert suggestions["design_allowance"] == 60.0
    assert suggestions["install_allowance"] is None
    assert suggestions["category_assumptions"]["total_person_hours"] == 8.0
    assert len(math_shown) >= 5
    assert "suggested_shop_defaults_map" in suggestions
    assert suggestions["suggested_shop_defaults_map"]["production_hourly_rate"] == 38.75
    assert suggestions["suggested_shop_defaults_map"]["minimum_order_amount"] == 250.0


@pytest.mark.asyncio
async def test_grouped_questions_save_correctly(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        assert r.status_code == 201
        doc = r.json()
        assert doc["status"] == "draft"
        assert doc["answers"]["customer_charge"] == 400
        assert doc["category"] == "banners"
        assert "math_shown" in doc and len(doc["math_shown"]) > 0
        # Stored and retrievable for later review/resume
        got = await c.get(f"/api/pricing/quiz/submissions/{doc['id']}")
        assert got.status_code == 200
        assert got.json()["id"] == doc["id"]
    _clear()


@pytest.mark.asyncio
async def test_owner_can_edit_before_applying_and_reject_others(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        sub_id = submit.json()["id"]
        suggested_labor_rate = submit.json()["derived_suggestions"]["suggested_shop_defaults_map"]["production_hourly_rate"]
        assert suggested_labor_rate == 38.75
        # Owner EDITS the labor rate before applying, and REJECTS minimum_order_amount (omits it)
        apply = await c.post(f"/api/pricing/quiz/submissions/{sub_id}/apply", json={
            "accepted_shop_defaults": {"production_hourly_rate": 42.0},
        })
        assert apply.status_code == 200
        applied_doc = apply.json()
        assert applied_doc["status"] == "applied"
        assert applied_doc["applied_fields"] == {"production_hourly_rate": 42.0}
        # Confirm the EDITED value (42.0, not the raw suggestion 38.75) is what actually landed
        settings = await c.get("/api/pricing/settings")
        assert settings.json()["shop_defaults"]["production_hourly_rate"] == 42.0
        # Rejected field (minimum_order_amount) was NOT changed from its prior value
        assert settings.json()["shop_defaults"]["minimum_order_amount"] == 25.00
    _clear()


@pytest.mark.asyncio
async def test_existing_values_not_overwritten_silently_by_submit(ec9c_ctx):
    """Merely SUBMITTING the quiz (getting suggestions) must never itself change shop_defaults."""
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        before = (await c.get("/api/pricing/settings")).json()["shop_defaults"]["production_hourly_rate"]
        await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        after = (await c.get("/api/pricing/settings")).json()["shop_defaults"]["production_hourly_rate"]
        assert before == after == 28.00
    _clear()


@pytest.mark.asyncio
async def test_skip_and_resume_later(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        sub_id = submit.json()["id"]
        skip = await c.post(f"/api/pricing/quiz/submissions/{sub_id}/skip")
        assert skip.status_code == 200
        assert skip.json()["status"] == "skipped"
        # Skipping does not delete it — it's resumable/reviewable later
        lst = await c.get("/api/pricing/quiz/submissions")
        assert any(i["id"] == sub_id and i["status"] == "skipped" for i in lst.json()["items"])
        # A fresh quiz can still be started (return later / start again)
        submit2 = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        assert submit2.status_code == 201
        assert submit2.json()["status"] == "draft"
    _clear()


@pytest.mark.asyncio
async def test_detailed_wizard_still_works_alongside_quiz(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        suggestions = await c.post("/api/pricing/settings/categories/banners/wizard/suggestions", json={"answers": {"price_3x6": 60}})
        assert suggestions.status_code == 200
        applied = await c.post("/api/pricing/settings/categories/banners/wizard/apply", json={
            "suggestions": [{"target_field": "waste_percent", "suggested": 12.0, "apply": True}],
            "mark_setup_complete": False,
        })
        assert applied.status_code == 200
    _clear()


@pytest.mark.asyncio
async def test_source_labels_persist_for_quiz_wizard_and_manual(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        # grouped quiz source
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        sub_id = submit.json()["id"]
        await c.post(f"/api/pricing/quiz/submissions/{sub_id}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 40.0}})
        # detailed wizard source
        await c.post("/api/pricing/settings/categories/banners/wizard/apply", json={
            "suggestions": [{"target_field": "waste_percent", "suggested": 11.0, "apply": True}],
            "mark_setup_complete": False,
        })
        # user_entered (direct patch) source
        await c.patch("/api/pricing/settings/shop-defaults", json={"install_hourly_rate": 100.0})
        settings = (await c.get("/api/pricing/settings")).json()
        sources = settings["field_sources"]
        assert sources["shop_defaults.production_hourly_rate"] == "grouped_quiz"
        assert sources["category_defaults.banners.waste_percent"] == "detailed_wizard"
        assert sources["shop_defaults.install_hourly_rate"] == "user_entered"
    _clear()


@pytest.mark.asyncio
async def test_tenant_isolation_on_quiz_submission(ec9c_ctx):
    ua, ub = ec9c_ctx["ua"], ec9c_ctx["ub"]
    async with await _client(ua) as c:
        sub = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        sub_id = sub.json()["id"]
    _clear()
    async with await _client(ub) as c:
        got = await c.get(f"/api/pricing/quiz/submissions/{sub_id}")
        assert got.status_code == 404
        apply = await c.post(f"/api/pricing/quiz/submissions/{sub_id}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 99.0}})
        assert apply.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_money_remains_integer_cents_downstream(ec9c_ctx):
    """Quiz outputs are dollar-based config (correct, per money policy) — but
    the downstream Quote/Order snapshot path they feed into must still land
    in integer cents, unaffected by the quiz."""
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        await c.post(f"/api/pricing/quiz/submissions/{submit.json()['id']}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 33.33}})
        cust = await c.post("/api/customers", json={"name": "9C Test Customer"})
        q = await c.post("/api/quotes", json={"customer_id": cust.json()["id"], "job_name": "9C Job"})
        li = await c.post(f"/api/quotes/{q.json()['id']}/line-items", json={
            "category": "banners", "description": "Test", "quantity": 1, "unit_price_cents": 4000,
        })
        assert li.json()["unit_price_cents"] == 4000
        assert isinstance(li.json()["unit_price_cents"], int)
    _clear()


@pytest.mark.asyncio
async def test_applied_settings_snapshot_preserved_on_submission(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        sub_id = submit.json()["id"]
        raw_suggestion = submit.json()["derived_suggestions"]["suggested_shop_defaults_map"]["production_hourly_rate"]
        apply = await c.post(f"/api/pricing/quiz/submissions/{sub_id}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 45.0}})
        applied_doc = apply.json()
        # The ORIGINAL suggestion snapshot is preserved unchanged for audit...
        assert applied_doc["derived_suggestions"]["suggested_shop_defaults_map"]["production_hourly_rate"] == raw_suggestion == 38.75
        # ...distinct from what was ACTUALLY applied (owner edited it to 45.0)
        assert applied_doc["applied_fields"]["production_hourly_rate"] == 45.0
        assert applied_doc["applied_at"] is not None
    _clear()


@pytest.mark.asyncio
async def test_no_fields_accepted_rejects_apply(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        submit = await c.post("/api/pricing/quiz/submit", json=SAMPLE_ANSWERS)
        r = await c.post(f"/api/pricing/quiz/submissions/{submit.json()['id']}/apply", json={"accepted_shop_defaults": {}})
        assert r.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_missing_required_answer_rejected(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        bad = dict(SAMPLE_ANSWERS)
        bad["category"] = "not_a_real_category"
        r = await c.post("/api/pricing/quiz/submit", json=bad)
        assert r.status_code == 400
    _clear()
