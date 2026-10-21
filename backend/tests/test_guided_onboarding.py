"""Guided Onboarding V1 — completion is derived from the records that own each setting."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


async def _client_as(user: dict) -> AsyncClient:
    async def _get():
        return {**user}

    app.dependency_overrides[get_current_user] = _get
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _mk_tenant(prefix: str) -> dict:
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-go-{prefix}-{suffix}"
    owner = {"id": f"owner-{prefix}-{suffix}", "tenant_id": tenant_id, "email": f"o-{prefix}-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": f"GO {prefix}"})
    await db.users.insert_one(owner)
    return owner


@pytest_asyncio.fixture
async def ctx():
    owner = await _mk_tenant("a")
    other = await _mk_tenant("b")
    yield {"owner": owner, "other": other}
    app.dependency_overrides.pop(get_current_user, None)


def _task(dash: dict, key: str) -> dict:
    return next(t for t in dash["tasks"] if t["task_key"] == key)


async def _dash(client: AsyncClient) -> dict:
    res = await client.get("/api/onboarding/dashboard")
    assert res.status_code == 200, res.text
    return res.json()


async def _counts(tenant_id: str) -> tuple[int, int, int]:
    return (
        await db.orders.count_documents({"tenant_id": tenant_id}),
        await db.customers.count_documents({"tenant_id": tenant_id}),
        await db.employees.count_documents({"tenant_id": tenant_id}),
    )


@pytest.mark.asyncio
async def test_new_tenant_starts_empty_with_three_stages_and_blocked_reasons(ctx):
    async with await _client_as(ctx["owner"]) as c:
        dash = await _dash(c)
    assert [s["key"] for s in dash["stages"]] == ["quick_start", "standard", "advanced"]
    assert dash["progress"]["completed_tasks"] == 0
    assert dash["prompt"]["show"] is True
    order = _task(dash, "first_order")
    assert order["status"] == "blocked" and "First customer" in order["blocked_reason"]
    assert _task(dash, "company_profile")["status"] == "not_started"
    # Paid/optional integrations never gate the Quick Start stage.
    assert not any(t["feature_key"] for t in dash["tasks"] if t["stage"] == "quick_start")


@pytest.mark.asyncio
async def test_completion_follows_real_records_and_settings_edits(ctx):
    async with await _client_as(ctx["owner"]) as c:
        saved = await c.put("/api/settings/company_profile", json={"shop_name": "Acme Signs", "phone": "555-0100", "address_line1": "1 Main St"})
        assert saved.status_code == 200, saved.text
        dash = await _dash(c)
        assert _task(dash, "company_profile")["status"] == "completed"
        assert _task(dash, "company_contact")["status"] == "completed"
        assert _task(dash, "labor_rates")["status"] == "not_started"

        # Pricing Foundation contract: labor rates come from the existing shop-defaults route.
        rates = await c.patch("/api/pricing/settings/shop-defaults", json={"production_hourly_rate": 55, "design_hourly_rate": 70})
        assert rates.status_code == 200, rates.text
        assert _task(await _dash(c), "labor_rates")["status"] == "completed"

        # Clearing the shop name later in Settings un-completes the step (no stale onboarding copy).
        await c.put("/api/settings/company_profile", json={"shop_name": "", "legal_name": ""})
        assert _task(await _dash(c), "company_profile")["status"] == "not_started"


@pytest.mark.asyncio
async def test_real_employee_customer_order_and_workflow_complete_steps_without_duplicates(ctx):
    tenant_id = ctx["owner"]["tenant_id"]
    async with await _client_as(ctx["owner"]) as c:
        emp = await c.post("/api/employees", json={"name": "Pat Printer", "email": "pat@example.com"})
        assert emp.status_code == 201, emp.text
        cust = await c.post("/api/customers", json={"name": "Jane Buyer", "company": "Buyer Co"})
        assert cust.status_code == 201, cust.text
        dash = await _dash(c)
        assert _task(dash, "first_employee")["status"] == "completed"
        assert _task(dash, "first_customer")["status"] == "completed"
        assert _task(dash, "first_order")["status"] == "not_started"

        order = await c.post("/api/orders", json={"customer_id": cust.json()["id"], "job_name": "Lobby sign"})
        assert order.status_code in {200, 201}, order.text
        assert (await c.get("/api/production-workflows")).status_code == 200
        before = await _counts(tenant_id)
        dash = await _dash(c)
        await _dash(c)  # reading progress is idempotent and never creates business records
        assert before == await _counts(tenant_id) == (1, 1, 1)
        assert _task(dash, "first_order")["status"] == "completed"
        assert _task(dash, "production_workflow")["status"] == "completed"
        assert await db.tenant_onboarding_instances.count_documents({"tenant_id": tenant_id}) == 1


@pytest.mark.asyncio
async def test_skip_defer_reviewed_rules_and_position(ctx):
    async with await _client_as(ctx["owner"]) as c:
        assert (await c.post("/api/onboarding/tasks/company_profile/status", json={"status": "skipped"})).status_code == 400
        assert (await c.post("/api/onboarding/tasks/company_profile/status", json={"status": "completed"})).status_code == 409
        assert (await c.post("/api/onboarding/tasks/branding/status", json={"status": "skipped", "reason": "later"})).status_code == 200
        assert (await c.post("/api/onboarding/tasks/company_profile/status", json={"status": "deferred"})).status_code == 200
        assert (await c.post("/api/onboarding/tasks/time_clock/status", json={"status": "completed"})).status_code == 200
        assert (await c.post("/api/onboarding/tasks/nope/status", json={"status": "skipped"})).status_code == 404
        assert (await c.post("/api/onboarding/tasks/branding/status", json={"status": "bogus"})).status_code == 400
        dash = await _dash(c)
        assert _task(dash, "branding")["status"] == "skipped"
        assert _task(dash, "company_profile")["status"] == "deferred"
        assert _task(dash, "time_clock")["status"] == "completed"

        pos = await c.post("/api/onboarding/position", json={"task_key": "labor_rates"})
        assert pos.json()["current_task_key"] == "labor_rates"
        assert (await c.post("/api/onboarding/position", json={"task_key": "nope"})).status_code == 404
        assert (await _dash(c))["prompt"]["resume_task_key"] == "labor_rates"
        await c.post("/api/onboarding/position", json={"dismiss_prompt": True})
        assert (await _dash(c))["prompt"]["show"] is False


@pytest.mark.asyncio
async def test_entitlement_availability_blocks_only_optional_steps_and_tenants_are_isolated(ctx):
    async with await _client_as(ctx["owner"]) as c:
        wrap = _task(await _dash(c), "wrap_lab")
        assert wrap["status"] == "blocked" and wrap["availability"]["available"] is False
        assert wrap["level"] == "optional"
        await c.put("/api/settings/company_profile", json={"shop_name": "Only A"})
    async with await _client_as(ctx["other"]) as c:
        dash = await _dash(c)
        assert _task(dash, "company_profile")["status"] == "not_started"
        assert dash["instance"]["tenant_id"] == ctx["other"]["tenant_id"]
