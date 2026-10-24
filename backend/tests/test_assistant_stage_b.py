"""Stage B real text/tool boundary: every paid provider call is mocked."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import uuid

import httpx
import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.core.db import db
from app.core.security import hash_password
from app.core.time_utils import utc_now
from app.deps import get_current_user
from app.services import (
    ai_gateway,
    assistant_context,
    assistant_personality,
    assistant_tools,
    business_assistant as svc,
    invoice_reconciliation,
    openai_assistant_provider,
)
from app.services.entitlements import _upsert_entitlement_for_tests
from server import app


@pytest_asyncio.fixture
async def ctx(monkeypatch):
    suffix = uuid.uuid4().hex[:12]
    tenant = f"t-assistant-b-{suffix}"
    user = {
        "id": f"u-{suffix}",
        "tenant_id": tenant,
        "email": f"u-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
        "full_name": "Assistant Test",
        "password_hash": hash_password("isolated-test-password"),
    }
    other = {**user, "id": f"other-{suffix}", "email": f"other-{suffix}@example.com"}
    foreign = {
        **user,
        "id": f"foreign-{suffix}",
        "tenant_id": f"foreign-{tenant}",
        "email": f"foreign-{suffix}@example.com",
    }
    await db.tenants.insert_many(
        [
            {"id": tenant, "slug": tenant, "name": "Disposable Assistant Shop"},
            {
                "id": foreign["tenant_id"],
                "slug": foreign["tenant_id"],
                "name": "Foreign Shop",
            },
        ]
    )
    await db.users.insert_many([user, other, foreign])
    for shop in (tenant, foreign["tenant_id"]):
        await _upsert_entitlement_for_tests(
            tenant_id=shop, feature_key="business_assistant", enabled=True
        )
    profile = {
        "id": f"model-{suffix}",
        "provider_config_id": f"provider-{suffix}",
        "provider_key": "openai",
        "model_key": "mock-tool-model",
        "status": "active",
        "metadata": {
            "input_usd_per_million_tokens": "1",
            "output_usd_per_million_tokens": "2",
            "pricing_source": "mock fixture, not a production price",
        },
    }
    await db.ai_provider_configs.insert_one(
        {
            "id": profile["provider_config_id"],
            "provider_key": f"fixture-{suffix}",
            "status": "active",
        }
    )
    await db.ai_model_profiles.insert_one(profile)
    await db.ai_capabilities.update_one(
        {"capability_key": "assistant.chat"},
        {
            "$set": {
                "id": f"cap-{suffix}",
                "capability_key": "assistant.chat",
                "status": "active",
                "feature_key": "business_assistant",
                "action_key": "chat",
                "billable": True,
                "default_credit_charge": 1,
                "entitlement_feature_key": "business_assistant",
                "allowed_model_profile_ids": [profile["id"]],
            }
        },
        upsert=True,
    )
    await db.ai_governance_policies.insert_one(
        {
            "id": f"policy-{suffix}",
            "scope_type": "tenant",
            "scope_key": tenant,
            "tenant_id": tenant,
            "status": "active",
            "max_cost_micros_per_day": 1000000,
        }
    )
    admin = {**user, "platform_admin": True, "platform_role": "admin"}
    await ai_gateway.grant_credits(
        admin, tenant, {"included_credits": 20, "reason": "Disposable mocked test"}
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "assistant_text_enabled", True)
    monkeypatch.setattr(settings, "assistant_text_model_profile_id", profile["id"])
    monkeypatch.setattr(settings, "openai_api_key", "mock-not-a-live-key")
    calls = []

    async def forbidden(payload):
        raise AssertionError("Test must explicitly script every paid provider call")

    monkeypatch.setattr(openai_assistant_provider, "respond", forbidden)
    yield {
        "user": user,
        "other": other,
        "foreign": foreign,
        "tenant": tenant,
        "profile": profile,
        "settings": settings,
        "calls": calls,
    }
    app.dependency_overrides.pop(get_current_user, None)


def text(value="A useful general answer.", *, event=None, usage=True):
    return {
        "id": event or f"resp-{uuid.uuid4().hex}",
        "status": "completed",
        "usage": {"input_tokens": 100, "output_tokens": 20} if usage else None,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": value}],
            }
        ],
    }


def tool(name, **arguments):
    result = text()
    result["output"] = [
        {
            "type": "function_call",
            "name": name,
            "call_id": uuid.uuid4().hex,
            "arguments": json.dumps(arguments),
        }
    ]
    return result


def script(monkeypatch, ctx, *responses):
    pending = list(responses)

    async def respond(payload):
        ctx["calls"].append(deepcopy(payload))
        assert pending, "Unexpected extra paid request"
        value = pending.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(openai_assistant_provider, "respond", respond)


async def ask(
    ctx,
    message="How can you help?",
    *,
    key=None,
    conversation_id=None,
    user=None,
    context=None,
):
    return await svc.ask_assistant(
        user or ctx["user"],
        {
            "message": message,
            "idempotency_key": key or uuid.uuid4().hex,
            "conversation_id": conversation_id,
            "mode": "owner",
            "context": context or {},
        },
    )


async def invoice(ctx, invoice_id="invoice", **changes):
    row = {
        "id": f"{invoice_id}-{ctx['tenant']}",
        "order_id": f"order-{invoice_id}-{ctx['tenant']}",
        "tenant_id": ctx["tenant"],
        "number": invoice_id,
        "document_status": "issued",
        "total_cents": 10000,
        "due_date": (utc_now().date() - timedelta(days=2)).isoformat(),
        "created_at": utc_now().isoformat(),
        **changes,
    }
    await db.invoices.insert_one(row)
    return row


@pytest.mark.asyncio
async def test_provider_tools_followup_resume_citations_and_accounting(
    ctx, monkeypatch
):
    inv = await invoice(ctx)
    await db.payments.insert_many(
        [
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "invoice_id": inv["id"],
                "status": "confirmed",
                "amount_cents": 6000,
            },
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "invoice_id": inv["id"],
                "status": "confirmed",
                "amount_cents": 1000,
                "refund_of_payment_id": "original",
            },
        ]
    )
    before = await db.invoices.find_one({"id": inv["id"]})
    script(
        monkeypatch,
        ctx,
        tool("invoices", invoice_filter="overdue"),
        text(
            "Invoice invoice has $50.00 overdue. [Open invoice](/invoices/"
            + inv["id"]
            + ")"
        ),
        tool("invoices", invoice_filter="overdue"),
        text("That is the oldest returned invoice; its current balance is $50.00."),
    )
    first = await ask(ctx, "Who still owes us money past the due date?", key="first")
    assert first["sources"][0]["source_id"] == inv["id"]
    output = json.loads(ctx["calls"][1]["input"][-1]["output"])
    assert output["items"][0]["balance_due_cents"] == 5000
    assert ctx["calls"][0]["store"] is False
    second = await ask(
        ctx,
        "Which is the oldest?",
        conversation_id=first["conversation"]["id"],
        key="second",
    )
    assert "past the due date" in json.dumps(ctx["calls"][2]["input"])
    assert second["conversation"]["id"] == first["conversation"]["id"]
    assert await db.invoices.find_one({"id": inv["id"]}) == before
    replay = await ask(ctx, "Who still owes us money past the due date?", key="first")
    assert replay["assistant_message"]["id"] == first["assistant_message"]["id"]
    assert len(ctx["calls"]) == 4
    assert (await ai_gateway.get_credit_account(ctx["tenant"]))[
        "included_balance_credits"
    ] == 18
    costs = [
        r
        async for r in db.ai_provider_cost_ledger_entries.find(
            {"tenant_id": ctx["tenant"]}
        )
    ]
    assert len(costs) == 2
    assert all(
        r["actual_cost_micros"] is None and r["status"] == "estimated" for r in costs
    )
    assert all(r["estimated_cost_micros"] == 280 for r in costs)
    history = await svc.get_conversation(ctx["user"], first["conversation"]["id"])
    assert len(history["messages"]) == 4


@pytest.mark.asyncio
async def test_private_conversations_memory_preferences_and_indirect_refs(
    ctx, monkeypatch
):
    convo = await svc.create_conversation(ctx["user"], {})
    memory = await svc.upsert_memory(
        ctx["user"], {"memory_key": "format", "content_text": "Concise updates"}
    )
    for actor in (ctx["other"], ctx["foreign"]):
        assert (await svc.list_conversations(actor))["items"] == []
        with pytest.raises(svc.BusinessAssistantError) as denied:
            await svc.get_conversation(actor, convo["id"])
        assert denied.value.status_code == 404
        with pytest.raises(svc.BusinessAssistantError):
            await svc.delete_memory(actor, memory["id"])
        with pytest.raises(svc.BusinessAssistantError):
            await ask(ctx, conversation_id=convo["id"], user=actor)
    foreign_id = uuid.uuid4().hex
    await db.customers.insert_one(
        {
            "id": foreign_id,
            "tenant_id": ctx["foreign"]["tenant_id"],
            "name": "Must not disclose",
        }
    )
    with pytest.raises(svc.BusinessAssistantError):
        await ask(
            ctx,
            context={"source_entity_type": "customer", "source_entity_id": foreign_id},
        )
    assert not ctx["calls"]


@pytest.mark.asyncio
async def test_permission_loss_hides_history_and_denies_tool_and_retry(
    ctx, monkeypatch
):
    script(monkeypatch, ctx, text("Private earlier answer"))
    result = await ask(ctx, key="private")
    restricted = {**ctx["user"], "role": "staff", "permissions": ["ai_assistant:use"]}
    await db.users.update_one(
        {"id": restricted["id"], "tenant_id": ctx["tenant"]},
        {"$set": {"role": "staff", "permissions": restricted["permissions"]}},
    )
    history = await svc.get_conversation(restricted, result["conversation"]["id"])
    assert "Private earlier answer" not in json.dumps(history)
    assert (
        await assistant_context.history(restricted, result["conversation"]["id"], 20)
        == []
    )
    with pytest.raises(assistant_tools.ToolError):
        await assistant_tools.execute(restricted, "invoices", {})
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, user=restricted, key="private")
    assert len(ctx["calls"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("personality", list(assistant_personality.PRESETS))
async def test_each_personality_applied_and_preferences_survive_login(
    ctx, monkeypatch, personality
):
    conversation = await svc.create_conversation(ctx["user"], {})
    memory = await svc.upsert_memory(
        ctx["user"], {"memory_key": "format", "content_text": "Short updates"}
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={
                "tenant_slug": ctx["tenant"],
                "email": ctx["user"]["email"],
                "password": "isolated-test-password",
            },
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        saved = await client.put(
            "/api/assistant/preferences",
            json={
                "personality_key": personality,
                "voice": "ash",
            },
        )
        assert saved.status_code == 200, saved.text
        assert len(saved.json()["options"]) == 5
        assert (
            await client.put("/api/assistant/preferences", json={"role": "admin"})
        ).status_code == 422
        await client.post("/api/auth/logout")
        relogin = await client.post(
            "/api/auth/login",
            json={
                "tenant_slug": ctx["tenant"],
                "email": ctx["user"]["email"],
                "password": "isolated-test-password",
            },
        )
        client.headers["Authorization"] = "Bearer " + relogin.json()["access_token"]
        current = (await client.get("/api/assistant/preferences")).json()["preferences"]
        assert (
            current["personality_key"] == personality
            and current["voice"] == "ash"
        )
    assert (await svc.get_conversation(ctx["user"], conversation["id"]))[
        "conversation"
    ]["id"] == conversation["id"]
    assert (await svc.list_memory(ctx["user"]))["items"][0]["id"] == memory["id"]
    script(monkeypatch, ctx, text())
    await ask(ctx)
    instructions = ctx["calls"][0]["instructions"]
    assert assistant_personality.PRESETS[personality][2] in instructions
    assert "medical issues" in instructions and "neutral professional" in instructions
    assert (await svc.get_preferences(ctx["other"]))["preferences"][
        "personality_key"
    ] == "ops_partner"
    assert (await svc.get_preferences(ctx["foreign"]))["preferences"][
        "personality_key"
    ] == "ops_partner"
    await svc.update_preferences(ctx["foreign"], {"personality_key": "wise_mentor"})
    assert (await svc.get_preferences(ctx["user"]))["preferences"][
        "personality_key"
    ] == personality


@pytest.mark.asyncio
async def test_customer_history_orders_and_work_order_stages(ctx):
    customer = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "name": "ABC Plumbing",
        "secret": "never return",
    }
    order = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "customer_id": customer["id"],
        "number": "O1",
        "status": "in_production",
    }
    wo = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "order_id": order["id"],
        "number": "WO1",
    }
    await db.customers.insert_one(customer)
    await db.orders.insert_one(order)
    await db.work_orders.insert_one(wo)
    await db.production_stage_instances.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": ctx["tenant"],
            "work_order_id": wo["id"],
            "stage_name": "Print",
            "status": "waiting",
            "waiting_reason": "Artwork approval",
            "sequence": 1,
        }
    )
    found = await assistant_tools.execute(
        ctx["user"], "find_customers", {"query": "ABC"}
    )
    assert found["items"][0]["id"] == customer["id"] and "secret" not in json.dumps(
        found
    )
    history = await assistant_tools.execute(
        ctx["user"], "customer_history", {"record_id": customer["id"]}
    )
    assert history["items"][0]["id"] == order["id"]
    status = await assistant_tools.execute(
        ctx["user"], "work_order_status", {"record_id": wo["id"]}
    )
    assert status["items"][0]["stages"][0]["waiting_reason"] == "Artwork approval"
    assert status["items"][0]["stages"][0]["stage_name"] == "Print"
    limited = {**ctx["user"], "role": "staff", "permissions": ["customer:read"]}
    with pytest.raises(assistant_tools.ToolError):
        await assistant_tools.execute(
            limited, "customer_history", {"record_id": customer["id"]}
        )


@pytest.mark.asyncio
async def test_due_dates_canonical_refunds_and_read_only_financials(ctx):
    overdue = await invoice(ctx, "old")
    await invoice(ctx, "today", due_date=utc_now().date().isoformat())
    await invoice(ctx, "unknown", due_date=None)
    await invoice(ctx, "void", document_status="void")
    paid = await invoice(ctx, "paid")
    await db.payments.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": ctx["tenant"],
            "invoice_id": paid["id"],
            "amount_cents": 10000,
            "status": "confirmed",
        }
    )
    result = await assistant_tools.execute(
        ctx["user"], "invoices", {"invoice_filter": "overdue"}
    )
    assert [r["id"] for r in result["items"]] == [overdue["id"]]
    assert result["items"][0]["balance_due_cents"] == 10000
    projected = await invoice_reconciliation.read_financials(
        tenant_id=ctx["tenant"], invoice=overdue
    )
    reconciled = await invoice_reconciliation.reconcile(
        tenant_id=ctx["tenant"], invoice_id=overdue["id"]
    )
    assert all(reconciled[k] == value for k, value in projected.items())


@pytest.mark.asyncio
async def test_quotes_tasks_and_shop_schedule_today_tomorrow(ctx):
    today = utc_now().date()
    await db.quotes.insert_many(
        [
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "number": "sent",
                "status": "sent",
            },
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "number": "accepted",
                "status": "accepted",
            },
        ]
    )
    for offset in (0, 1):
        day = (today + timedelta(days=offset)).isoformat()
        await db.tasks.insert_one(
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "title": f"Task {offset}",
                "due_at": day + "T12:00:00+00:00",
                "status": "not_started",
                "archived_at": None,
            }
        )
        await db.calendar_events.insert_one(
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "title": f"Install {offset}",
                "start_at": day + "T14:00:00+00:00",
                "end_at": day + "T15:00:00+00:00",
                "status": "scheduled",
                "visibility": "staff",
                "archived_at": None,
            }
        )
    quotes = await assistant_tools.execute(ctx["user"], "quote_followups", {})
    assert [r["number"] for r in quotes["items"]] == ["sent"]
    for day, expected in (("today", "0"), ("tomorrow", "1")):
        tasks = await assistant_tools.execute(ctx["user"], "tasks", {"day": day})
        schedule = await assistant_tools.execute(
            ctx["user"], "shop_schedule", {"day": day}
        )
        assert tasks["items"][0]["title"] == f"Task {expected}"
        assert any(r["title"] == f"Install {expected}" for r in schedule["items"])
        assert all("private" not in json.dumps(r) for r in schedule["items"])


@pytest.mark.asyncio
async def test_missing_config_limits_and_provider_failure_never_repeat(
    ctx, monkeypatch
):
    monkeypatch.setattr(ctx["settings"], "assistant_text_enabled", False)
    with pytest.raises(svc.BusinessAssistantError) as unconfigured:
        await ask(ctx)
    assert unconfigured.value.status_code == 503 and not ctx["calls"]
    monkeypatch.setattr(ctx["settings"], "assistant_text_enabled", True)
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]}, {"$set": {"max_cost_micros_per_day": 1}}
    )
    with pytest.raises(svc.BusinessAssistantError) as budget:
        await ask(ctx)
    assert budget.value.code == "ai_cost_limit_exceeded" and not ctx["calls"]
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]}, {"$set": {"max_cost_micros_per_day": 1000000}}
    )
    script(monkeypatch, ctx, httpx.ReadTimeout("mock timeout"))
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="timeout")
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="timeout")
    assert len(ctx["calls"]) == 1
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"tenant_id": ctx["tenant"]}
    )
    assert (
        cost["actual_cost_micros"] is None
        and cost["reconciliation_status"] == "incomplete_reserved_maximum"
    )
    assert (await ai_gateway.get_credit_account(ctx["tenant"]))[
        "included_balance_credits"
    ] == 20


@pytest.mark.asyncio
async def test_concurrent_turn_and_retry_charge_once(ctx, monkeypatch):
    convo = await svc.create_conversation(ctx["user"], {})
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(payload):
        ctx["calls"].append(payload)
        entered.set()
        await release.wait()
        return text()

    monkeypatch.setattr(openai_assistant_provider, "respond", slow)
    first = asyncio.create_task(ask(ctx, key="same", conversation_id=convo["id"]))
    await asyncio.wait_for(entered.wait(), 10)
    with pytest.raises(svc.BusinessAssistantError) as busy:
        await ask(ctx, key="same", conversation_id=convo["id"])
    assert busy.value.status_code == 409
    release.set()
    await first
    await ask(ctx, key="same", conversation_id=convo["id"])
    assert len(ctx["calls"]) == 1
    assert (await ai_gateway.get_credit_account(ctx["tenant"]))[
        "included_balance_credits"
    ] == 19


@pytest.mark.asyncio
async def test_tool_validation_and_timezone_dst_bounds(ctx):
    with pytest.raises(ValueError):
        await assistant_tools.execute(ctx["user"], "invoices", {"tenant_id": "foreign"})
    assert (
        assistant_tools._local_date(
            "2026-03-08T04:30:00Z", __import__("zoneinfo").ZoneInfo("America/New_York")
        ).isoformat()
        == "2026-03-07"
    )
    with pytest.raises(ValueError):
        await svc.update_preferences(ctx["user"], {"timezone": "not/a/timezone"})


@pytest.mark.asyncio
async def test_missing_usage_retains_estimate_and_numeric_lookup(ctx, monkeypatch):
    inv = await invoice(ctx, "numeric", number=1201)
    found = await assistant_tools.execute(ctx["user"], "invoices", {"query": "1201"})
    assert found["items"][0]["id"] == inv["id"]
    script(monkeypatch, ctx, text(usage=False))
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="no-usage")
    assert len(ctx["calls"]) == 1  # Incomplete accounting stops without another dispatch.
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"tenant_id": ctx["tenant"]}
    )
    usage = await db.ai_usage_ledger_entries.find_one({"tenant_id": ctx["tenant"]})
    assert cost["reconciliation_status"] == "incomplete_reserved_maximum"
    assert cost["estimated_cost_micros"] > 140 and cost["actual_cost_micros"] is None
    assert cost["pricing_snapshot"]["pricing_source"].startswith("mock fixture")
    assert usage["usage_source"] == "incomplete"


@pytest.mark.asyncio
async def test_history_bounded_and_deleted_source_not_replayed(ctx, monkeypatch):
    inv = await invoice(ctx)
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id=inv["id"]),
        text("Invoice information"),
    )
    first = await ask(ctx, key="source")
    await db.invoices.delete_one({"tenant_id": ctx["tenant"], "id": inv["id"]})
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="source")
    assert all(
        m["role"] != "assistant"
        for m in await assistant_context.history(
            ctx["user"], first["conversation"]["id"], 20
        )
    )
    for n in range(30):
        await svc._insert_message(
            ctx["user"],
            conversation_id=first["conversation"]["id"],
            role="user",
            content_text=f"Turn {n}",
            mode="owner",
            metadata={
                "permission_signature": assistant_context.permission_signature(
                    ctx["user"]
                ),
                "sources": [],
            },
        )
    assert (
        len(
            await assistant_context.history(
                ctx["user"], first["conversation"]["id"], 20
            )
        )
        == 20
    )
    assert len(ctx["calls"]) == 2


@pytest.mark.asyncio
async def test_schedule_visibility_applies_to_tool_and_saved_history(ctx):
    now = utc_now().date().isoformat()
    row = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "title": "Private appointment",
        "start_at": now + "T14:00:00+00:00",
        "end_at": now + "T15:00:00+00:00",
        "status": "scheduled",
        "visibility": "internal",
        "created_by_user_id": ctx["other"]["id"],
        "archived_at": None,
    }
    await db.calendar_events.insert_one(row)
    schedule = await assistant_tools.execute(ctx["user"], "shop_schedule", {})
    assert "Private appointment" not in json.dumps(schedule)
    assert not await assistant_tools.reference_allowed(
        ctx["user"], assistant_tools.reference("calendar_event", row)
    )


@pytest.mark.asyncio
async def test_provider_http_transport_without_network(ctx, monkeypatch):
    real_client = httpx.AsyncClient
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json=text("Transport verified"))

    monkeypatch.setattr(
        openai_assistant_provider.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    # The fixture blocks the orchestration transport; explicitly use its real adapter with a mock HTTP transport.
    from importlib import reload

    adapter = reload(openai_assistant_provider)
    result = await adapter.respond(
        {"model": "mock-tool-model", "input": [], "store": False}
    )
    assert result["output"][0]["content"][0]["text"] == "Transport verified"
    assert str(captured[0].url) == "https://api.openai.com/v1/responses"
    assert captured[0].headers["authorization"] == "Bearer mock-not-a-live-key"


@pytest.mark.asyncio
async def test_invalid_provider_output_fails_without_redispatch(ctx, monkeypatch):
    script(monkeypatch, ctx, {"id": "malformed", "output": [None]})
    with pytest.raises(svc.BusinessAssistantError) as failed:
        await ask(ctx, key="malformed")
    assert failed.value.status_code == 502
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="malformed")
    assert len(ctx["calls"]) == 1
    assert (await ai_gateway.get_credit_account(ctx["tenant"]))["reserved_credits"] == 0


@pytest.mark.asyncio
async def test_inflight_budget_blocks_other_conversation(ctx, monkeypatch):
    from app.services.ai_gateway_execution import estimate

    maximum = estimate(
        ctx["profile"], (ctx["settings"].assistant_max_context_bytes + 1024) * 3, 3000
    )
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]}, {"$set": {"max_cost_micros_per_day": maximum + 1}}
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def waiting(payload):
        ctx["calls"].append(payload)
        entered.set()
        await release.wait()
        return text()

    monkeypatch.setattr(openai_assistant_provider, "respond", waiting)
    first = asyncio.create_task(ask(ctx, key="inflight"))
    await asyncio.wait_for(entered.wait(), 10)
    try:
        with pytest.raises(svc.BusinessAssistantError) as denied:
            await ask(ctx, key="other-conversation")
        assert denied.value.code == "ai_cost_limit_exceeded"
    finally:
        release.set()
        await first
    assert len(ctx["calls"]) == 1


@pytest.mark.asyncio
async def test_model_cannot_execute_actions_or_import_foreign_memory(ctx, monkeypatch):
    await svc.upsert_memory(
        ctx["other"],
        {"memory_key": "private", "content_text": "Other user's private preference"},
    )
    await svc.upsert_memory(
        ctx["user"], {"memory_key": "format", "content_text": "Concise summaries"}
    )
    script(
        monkeypatch,
        ctx,
        tool("execute_assistant_action", action_type="internal_task"),
        text("I can help review a task; nothing was created."),
    )
    await ask(ctx)
    payload = json.dumps(ctx["calls"][0])
    assert (
        "Other user's private preference" not in payload
        and "Concise summaries" in payload
    )
    assert "not permitted" in ctx["calls"][1]["input"][-1]["output"]
    assert await db.tasks.count_documents({"tenant_id": ctx["tenant"]}) == 0
    assert await db.email_logs.count_documents({"tenant_id": ctx["tenant"]}) == 0


@pytest.mark.asyncio
async def test_source_memory_is_rechecked_after_permission_loss(ctx):
    inv = await invoice(ctx)
    await db.assistant_memory_entries.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": ctx["tenant"],
            "user_id": ctx["user"]["id"],
            "memory_key": "invoice-fact",
            "content_text": "Restricted invoice context",
            "source_type": "invoice",
            "source_id": inv["id"],
            "status": "active",
        }
    )
    restricted = {**ctx["user"], "role": "staff", "permissions": ["ai_assistant:use"]}
    await db.users.update_one({"id": ctx["user"]["id"], "tenant_id": ctx["tenant"]}, {"$set": {"role": "staff", "permissions": ["ai_assistant:use"]}})
    assert (await svc.list_memory(restricted))["items"] == []
    assert await assistant_context.memories(restricted) == []


@pytest.mark.asyncio
async def test_accounting_failure_never_redispatches_or_charges_twice(ctx, monkeypatch):
    script(monkeypatch, ctx, text())

    async def unavailable(*args, **kwargs):
        raise RuntimeError("Mock accounting interruption")

    monkeypatch.setattr(ai_gateway, "_commit_credits", unavailable)
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="accounting-interrupted")
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="accounting-interrupted")
    assert len(ctx["calls"]) == 1
    request = await db.ai_action_requests.find_one({"tenant_id": ctx["tenant"]})
    assert request["finalization_incomplete"] is True
    assert (
        await db.ai_usage_ledger_entries.count_documents({"tenant_id": ctx["tenant"]})
        == 1
    )
    account = await ai_gateway.get_credit_account(ctx["tenant"])
    assert (
        account["included_balance_credits"] == 20 and account["reserved_credits"] == 1
    )


@pytest.mark.asyncio
async def test_generic_gateway_history_and_retry_cannot_leak_private_answers(
    ctx, monkeypatch
):
    script(monkeypatch, ctx, text("Private conversation content"))
    await ask(ctx, key="private-gateway")
    assert (await ai_gateway.list_action_history(ctx["other"]))["items"] == []
    own = await ai_gateway.list_action_history(ctx["user"])
    assert len(own["items"]) == 1
    assert "Private conversation content" not in json.dumps(own)
    assert "assistant_result" not in own["items"][0]
    for actor in (ctx["user"], ctx["other"]):
        with pytest.raises(ai_gateway.AIGatewayError):
            await ai_gateway.create_gateway_request(
                actor,
                {"idempotency_key": f"assistant:{ctx['user']['id']}:private-gateway"},
            )
    dashboard = await ai_gateway.platform_dashboard(
        {**ctx["user"], "platform_admin": True}
    )
    assert dashboard["external_provider_calls"] >= 1
    assert dashboard["estimated_unverified_provider_cost_micros"] >= 140


@pytest.mark.asyncio
async def test_other_private_child_records_and_missing_money_fail_closed(ctx):
    convo = await svc.create_conversation(ctx["user"], {})
    proposal = await svc._save_proposal(
        ctx["user"],
        convo["id"],
        "owner",
        {
            "action_type": "navigation",
            "title": "Private title",
            "idempotency_key": "private-proposal",
        },
        status="proposed",
        warnings=[],
        required_permissions=[],
    )
    await db.assistant_voice_sessions.insert_one(
        {
            "id": "private-voice",
            "tenant_id": ctx["tenant"],
            "user_id": ctx["user"]["id"],
        }
    )
    await db.assistant_insights.insert_one(
        {
            "id": "private-insight",
            "tenant_id": ctx["tenant"],
            "user_id": ctx["user"]["id"],
            "status": "new",
            "summary": "Private insight",
        }
    )
    for actor in (ctx["other"], ctx["foreign"]):
        with pytest.raises(svc.BusinessAssistantError):
            await svc._proposal(actor, proposal["id"])
        with pytest.raises(svc.BusinessAssistantError):
            await svc.record_voice_usage(
                actor, "private-voice", {"provider_event_id": "no-dispatch"}
            )
        with pytest.raises(svc.BusinessAssistantError):
            await svc.dismiss_insight(actor, "private-insight")
        assert (await svc.list_insights(actor))["items"] == []
    with pytest.raises(ValueError, match="never invent"):
        await invoice_reconciliation.read_financials(
            tenant_id=ctx["tenant"],
            invoice={"id": "unknown", "tenant_id": ctx["tenant"]},
        )


@pytest.mark.asyncio
async def test_multiple_invoice_partial_refund_zero_and_offset_dates(ctx, monkeypatch):
    monkeypatch.setattr(
        assistant_tools,
        "utc_now",
        lambda: datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc),
    )
    partial = await invoice(ctx, "partial", due_date="2026-10-19")
    refunded = await invoice(ctx, "refund", due_date="2026-10-18")
    offset = await invoice(ctx, "offset", due_date="2026-10-21T00:30:00+14:00")
    await invoice(ctx, "zero", total_cents=0, due_date="2026-10-01")
    await invoice(ctx, "due-today", due_date="2026-10-21")
    await db.payments.insert_many(
        [
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "invoice_id": partial["id"],
                "amount_cents": 2500,
                "status": "confirmed",
            },
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "invoice_id": refunded["id"],
                "amount_cents": 10000,
                "status": "confirmed",
            },
            {
                "id": uuid.uuid4().hex,
                "tenant_id": ctx["tenant"],
                "invoice_id": refunded["id"],
                "amount_cents": 2000,
                "status": "confirmed",
                "refund_of_payment_id": "original",
            },
        ]
    )
    result = await assistant_tools.execute(
        ctx["user"],
        "invoices",
        {"invoice_filter": "overdue"},
        timezone_name="Asia/Kolkata",
    )
    balances = {r["id"]: r["balance_due_cents"] for r in result["items"]}
    assert balances == {partial["id"]: 7500, refunded["id"]: 2000, offset["id"]: 10000}
    assert result["complete"] is True
    foreign = {
        **offset,
        "id": "foreign-invoice",
        "order_id": "foreign-order",
        "tenant_id": ctx["foreign"]["tenant_id"],
    }
    foreign.pop("_id", None)
    await db.invoices.insert_one(foreign)
    assert (
        await assistant_tools.execute(
            ctx["user"], "invoices", {"record_id": foreign["id"]}
        )
    )["items"] == []


@pytest.mark.asyncio
async def test_credit_rate_budget_and_retry_payload_limits(ctx, monkeypatch):
    script(monkeypatch, ctx, text())
    await ask(ctx, key="fingerprint")
    with pytest.raises(svc.BusinessAssistantError) as conflict:
        await ask(ctx, "Different message", key="fingerprint")
    assert conflict.value.code == "assistant_retry_conflict" and len(ctx["calls"]) == 1
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]}, {"$set": {"max_credits_per_day": 1}}
    )
    with pytest.raises(svc.BusinessAssistantError) as daily:
        await ask(ctx)
    assert daily.value.code == "ai_credit_limit_exceeded" and len(ctx["calls"]) == 1
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]},
        {"$unset": {"max_credits_per_day": "", "max_cost_micros_per_day": ""}},
    )
    with pytest.raises(svc.BusinessAssistantError) as no_budget:
        await ask(ctx)
    assert no_budget.value.code == "assistant_budget_missing"
    await db.ai_model_profiles.update_one(
        {"id": ctx["profile"]["id"]}, {"$unset": {"metadata.pricing_source": ""}}
    )
    with pytest.raises(svc.BusinessAssistantError) as no_rates:
        await ask(ctx)
    assert no_rates.value.code == "assistant_rates_missing" and len(ctx["calls"]) == 1


@pytest.mark.asyncio
async def test_provider_request_round_limit_stops_without_success_charge(
    ctx, monkeypatch
):
    script(
        monkeypatch,
        ctx,
        tool("recent_orders"),
        tool("recent_orders"),
        tool("recent_orders"),
    )
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="round-limit")
    assert len(ctx["calls"]) == 3
    assert (await ai_gateway.get_credit_account(ctx["tenant"]))[
        "included_balance_credits"
    ] == 20
    usage = await db.ai_usage_ledger_entries.find_one({"tenant_id": ctx["tenant"]})
    assert usage["usage_source"] == "provider_reported"
    assert usage["input_units"] == 300 and usage["output_units"] == 60
    assert (
        await db.ai_usage_ledger_entries.count_documents(
            {"tenant_id": ctx["tenant"], "result_status": "failed"}
        )
        == 1
    )


@pytest.mark.asyncio
async def test_followup_inherits_access_dependencies_without_another_tool(
    ctx, monkeypatch
):
    inv = await invoice(ctx)
    script(
        monkeypatch,
        ctx,
        tool("invoices"),
        text("Original invoice context"),
        text("An explanation using that invoice context"),
    )
    first = await ask(ctx, key="referenced")
    followup = await ask(
        ctx, "Explain that", key="explain", conversation_id=first["conversation"]["id"]
    )
    assert (
        followup["assistant_message"]["metadata"]["sources"][0]["source_id"]
        == inv["id"]
    )
    await db.invoices.delete_one({"tenant_id": ctx["tenant"], "id": inv["id"]})
    history = await svc.get_conversation(ctx["user"], first["conversation"]["id"])
    assert "An explanation using that invoice context" not in json.dumps(history)
    with pytest.raises(svc.BusinessAssistantError):
        await ask(
            ctx,
            "Explain that",
            key="explain",
            conversation_id=first["conversation"]["id"],
        )
    assert len(ctx["calls"]) == 3


@pytest.mark.asyncio
async def test_context_failure_before_dispatch_has_no_provider_usage_or_liability(
    ctx, monkeypatch
):
    monkeypatch.setattr(ctx["settings"], "assistant_max_context_bytes", 1)
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="no-dispatch")
    assert ctx["calls"] == []
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"tenant_id": ctx["tenant"]}
    )
    usage = await db.ai_usage_ledger_entries.find_one({"tenant_id": ctx["tenant"]})
    assert cost["estimated_cost_micros"] == 0 and cost["actual_cost_micros"] is None
    assert cost["reconciliation_status"] == "no_dispatch"
    assert (
        usage["usage_source"] == "no_provider_request" and usage["credits_charged"] == 0
    )


@pytest.mark.asyncio
async def test_permission_revoked_while_provider_responds_is_not_returned_or_saved(
    ctx, monkeypatch
):
    calls = 0

    async def revoke_during_completion(payload):
        nonlocal calls
        calls += 1
        await db.users.update_one(
            {"tenant_id": ctx["tenant"], "id": ctx["user"]["id"]},
            {"$set": {"role": "staff", "permissions": ["ai_assistant:use"]}},
        )
        return text("Restricted completion must never reach the user")

    monkeypatch.setattr(openai_assistant_provider, "respond", revoke_during_completion)
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx, key="revoked-in-flight")
    assert calls == 1
    assert (
        await db.assistant_messages.count_documents(
            {"tenant_id": ctx["tenant"], "role": "assistant"}
        )
        == 0
    )
    action = await db.ai_action_requests.find_one({"tenant_id": ctx["tenant"]})
    assert action["status"] == "failed" and "assistant_result" not in action
    account = await ai_gateway.get_credit_account(ctx["tenant"])
    assert (
        account["reserved_credits"] == 0 and account["included_balance_credits"] == 20
    )
