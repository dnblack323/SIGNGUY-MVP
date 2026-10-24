"""Live findings reproduced with fictional records and mocked providers only."""

from copy import deepcopy
from decimal import Decimal
import json
import uuid

import pytest

from app.core.db import db
from app.services import assistant_context, assistant_tools, ai_text_pricing
from app.services import business_assistant as svc
from tests.test_assistant_stage_b import ctx  # noqa: F401
from tests.test_assistant_stage_b import (
    ask,
    invoice,
    script,
    text,
    tool,
)  # noqa: F401
from tests.test_assistant_stage_d import v, start, utterance, answer  # noqa: F401


def luna():
    return {
        "model_key": "gpt-6-luna",
        "metadata": {
            "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6-luna",
            ai_text_pricing.INPUT: "0.10",
            ai_text_pricing.OUTPUT: "0.50",
            ai_text_pricing.CACHED: "0.01",
            ai_text_pricing.WRITE: "0.125",
            ai_text_pricing.WRITE12: "0.25",
        },
    }


def usage(n, out, reads=0, writes=0, lifetimes=None, tier="default"):
    details = {"cached_tokens": reads, "cache_write_tokens": writes}
    if lifetimes is not None:
        details["cache_write_tokens_details"] = lifetimes
    return {
        "id": uuid.uuid4().hex,
        "service_tier": tier,
        "usage": {
            "input_tokens": n,
            "output_tokens": out,
            "input_tokens_details": details,
        },
    }


def test_exact_live_usage_cost_and_no_double_counting():
    amounts = [
        ai_text_pricing.cost(luna(), usage(n, out, writes=w))[0]
        for n, out, w in (
            (846, 48, 0),
            (1113, 76, 1110),
            (954, 52, 0),
            (1098, 47, 1095),
        )
    ]
    assert sum(amounts) == Decimal("567.725")
    assert ai_text_pricing.cost(luna(), usage(4011, 223, writes=2205))[0] == sum(
        amounts
    )
    amount, detail = ai_text_pricing.cost(
        luna(),
        usage(
            12000,
            100,
            reads=4000,
            writes=7000,
            lifetimes={"ttl_30m_tokens": 3000, "ttl_12h_tokens": 4000},
        ),
    )
    assert amount == Decimal("1565")  # 100 + 40 + 375 + 1000 + 50 microdollars.
    assert detail["ordinary_input_tokens"] == 1000


@pytest.mark.parametrize(
    "details",
    [
        {"cached_tokens": 8, "cache_write_tokens": 5},
        {"cached_tokens": -1},
        {"cache_write_tokens": True},
        {
            "cache_write_tokens": 5,
            "cache_write_tokens_details": {"ttl_30m_tokens": 2, "ttl_12h_tokens": 2},
        },
        {"cache_write_tokens": 5, "cache_write_tokens_details": {"ttl_48h_tokens": 5}},
    ],
)
def test_invalid_usage_is_unpriced(details):
    response = usage(10, 2)
    response["usage"]["input_tokens_details"] = details
    with pytest.raises(ValueError):
        ai_text_pricing.cost(luna(), response)


def test_tiers_models_reservations_and_unknown_prices():
    profile = luna()
    base = deepcopy(profile["metadata"])
    profile["metadata"]["processing_tiers"] = {
        "priority": {k: str(Decimal(base[k]) * 2) for k in ai_text_pricing.RATE_KEYS}
    }
    assert ai_text_pricing.cost(profile, usage(1000, 100, tier="fast"))[0] == Decimal(
        "300"
    )
    assert ai_text_pricing.reserve(profile, 1000, 100) == Decimal("600")
    with pytest.raises(ValueError):
        ai_text_pricing.cost(profile, usage(1000, 100, tier="unpriced"))
    # Older configured model without write pricing still works for ordinary input.
    legacy = {
        "model_key": "older-profile",
        "metadata": {
            "pricing_source": "fixture",
            ai_text_pricing.INPUT: "2",
            ai_text_pricing.OUTPUT: "8",
        },
    }
    assert ai_text_pricing.cost(legacy, usage(100, 10))[0] == 280
    with pytest.raises(ValueError):
        ai_text_pricing.cost(legacy, usage(100, 10, writes=50))
    profile["metadata"]["service_tier"] = "auto"
    with pytest.raises(ValueError):
        ai_text_pricing.request_options(profile)


def test_sourced_long_context_and_model_mismatch():
    profile = luna()
    profile["metadata"].update(
        long_context_threshold_tokens=272000,
        long_context_pricing={
            ai_text_pricing.INPUT: ".20",
            ai_text_pricing.OUTPUT: ".75",
            ai_text_pricing.CACHED: ".02",
            ai_text_pricing.WRITE: ".25",
            ai_text_pricing.WRITE12: ".50",
        },
    )
    assert ai_text_pricing.cost(profile, usage(300000, 100))[0] == 60075
    assert ai_text_pricing.reserve(profile, 300000, 100) == 150075
    response = usage(100, 10)
    response["model"] = "another-model"
    with pytest.raises(ValueError):
        ai_text_pricing.cost(profile, response)


@pytest.mark.asyncio
async def test_real_ledger_rounds_per_turn_preserves_usage_and_unknown_actual_cost(ctx):
    await db.ai_model_profiles.update_one(
        {"id": ctx["profile"]["id"]}, {"$set": luna()}
    )
    first = text("One invoice.")
    first.update(usage(846, 48))
    second = text("A follow-up.")
    second.update(usage(1113, 76, writes=1110))
    script_ctx = ctx
    # Two mocked provider responses in one normal Gateway action, like a tool/answer pair.
    first["output"] = tool("invoices")["output"]
    from unittest.mock import patch

    pending = [first, second]

    async def respond(payload):
        assert payload["service_tier"] == "default"
        return pending.pop(0)

    with patch("app.services.openai_assistant_provider.respond", respond):
        result = await ask(script_ctx)
    action = await db.ai_action_requests.find_one(
        {"id": result["action_request"]["id"]}
    )
    row = await db.ai_provider_cost_ledger_entries.find_one(
        {"action_request_id": action["id"]}
    )
    assert row["estimated_cost_micros"] == 286  # ceil(108.6 + 177.05), once per action.
    assert row["actual_cost_micros"] is None
    assert (
        action["provider_attempts"][1]["usage_detail"]["provider_usage"]
        == second["usage"]
    )
    follow_tool = tool("invoices")
    follow_tool.update(usage(954, 52))
    follow_answer = text("Current follow-up result.")
    follow_answer.update(usage(1098, 47, writes=1095))
    pending[:] = [follow_tool, follow_answer]
    with patch("app.services.openai_assistant_provider.respond", respond):
        await ask(ctx, conversation_id=result["conversation"]["id"])
    costs = await db.ai_provider_cost_ledger_entries.find(
        {"tenant_id": ctx["tenant"]}
    ).to_list(length=10)
    assert sorted(r["estimated_cost_micros"] for r in costs) == [283, 286]
    assert sum(r["estimated_cost_micros"] for r in costs) == 569


@pytest.mark.asyncio
async def test_invoice_followups_current_money_structured_ids_and_resume(
    ctx, monkeypatch
):
    inv = await invoice(ctx, "EVAL-INVOICE-1", total_cents=12500, due_date="2026-01-01")
    script(
        monkeypatch,
        ctx,
        tool("invoices", query=inv["number"]),
        text("EVAL-INVOICE-1 has $125 unpaid."),
    )
    first = await ask(ctx, "Show the invoice")
    cid = first["conversation"]["id"]
    saved = await svc.get_conversation(ctx["user"], cid)
    assert len(saved["messages"]) == 2
    await db.payments.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": ctx["tenant"],
            "invoice_id": inv["id"],
            "status": "confirmed",
            "amount_cents": 2500,
        }
    )
    for question in (
        "When was that due?",
        "How much have they paid?",
        "What remains unpaid?",
    ):
        script(
            monkeypatch,
            ctx,
            tool("invoices", record_id="discussed"),
            text("Current application result."),
        )
        await ask(ctx, question, conversation_id=cid)
        output = json.loads(ctx["calls"][-1]["input"][-1]["output"])
        assert output["items"][0]["balance_due_cents"] == 10000
        assert output["items"][0]["due_date"] == "2026-01-01"
        context = json.loads(ctx["calls"][-2]["input"][-1]["content"])
        assert context["record_references"][0]["source_id"] == inv["id"]
        assert "balance_due_cents" not in json.dumps(context["record_references"])
    assert len((await svc.get_conversation(ctx["user"], cid))["messages"]) == 8
    monkeypatch.setattr(ctx["settings"], "assistant_max_history_messages", 1)
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id="discussed"),
        text("Current result after bounded history."),
    )
    await ask(ctx, "And that due date?", conversation_id=cid)
    assert (
        json.loads(ctx["calls"][-2]["input"][-1]["content"])["record_references"][0][
            "source_id"
        ]
        == inv["id"]
    )
    await db.payments.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": ctx["tenant"],
            "invoice_id": inv["id"],
            "status": "confirmed",
            "amount_cents": 10000,
        }
    )
    current = await assistant_tools.execute(
        ctx["user"], "invoices", {"record_id": "discussed"}, conversation_id=cid
    )
    assert current["items"][0]["balance_due_cents"] == 0
    assert current["items"][0]["overdue"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("same_customer", [True, False])
async def test_multiple_invoices_never_arbitrarily_resolve_discussed(
    ctx, monkeypatch, same_customer
):
    c1, c2 = "c1-" + ctx["tenant"], "c2-" + ctx["tenant"]
    await db.customers.insert_many(
        [
            {"tenant_id": ctx["tenant"], "id": c1, "name": "First Customer"},
            {"tenant_id": ctx["tenant"], "id": c2, "name": "Second Customer"},
        ]
    )
    await invoice(ctx, "one", customer_id=c1)
    await invoice(ctx, "two", customer_id=c1 if same_customer else c2)
    script(
        monkeypatch, ctx, tool("invoices"), text("There are two outstanding invoices.")
    )
    first = await ask(ctx)
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id="discussed", invoice_filter="latest"),
        text("Which invoice do you mean?"),
    )
    result = await ask(
        ctx, "When was that due?", conversation_id=first["conversation"]["id"]
    )
    output = json.loads(ctx["calls"][-1]["input"][-1]["output"])
    assert output["needs_clarification"] and output["items"] == []
    assert result["sources"] == []
    # A model selecting one internal ID must not bypass an ambiguous follow-up.
    first_id = first["sources"][0]["source_id"]
    # Restore the two-record focus explicitly through a normal list turn.
    script(monkeypatch, ctx, tool("invoices"), text("Two invoices remain."))
    await ask(
        ctx, "Show all overdue invoices", conversation_id=first["conversation"]["id"]
    )
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id=first_id),
        text("Which invoice do you mean?"),
    )
    await ask(ctx, "When was that due?", conversation_id=first["conversation"]["id"])
    assert json.loads(ctx["calls"][-1]["input"][-1]["output"])["needs_clarification"]


@pytest.mark.asyncio
async def test_customer_order_invoice_related_records_and_exact_number(
    ctx, monkeypatch
):
    customer_id, order_id = "customer-" + ctx["tenant"], "order-" + ctx["tenant"]
    customer = {
        "id": customer_id,
        "tenant_id": ctx["tenant"],
        "name": "Smith Construction",
    }
    await db.customers.insert_one(customer)
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": ctx["tenant"],
            "customer_id": customer_id,
            "number": "ORD-1",
            "status": "confirmed",
        }
    )
    inv = await invoice(ctx, "INV-1", order_id=order_id, customer_id=customer_id)
    script(
        monkeypatch,
        ctx,
        tool("find_customers", query="Smith"),
        text("Found Smith Construction."),
    )
    first = await ask(ctx)
    cid = first["conversation"]["id"]
    for name, question, ident in (
        ("recent_orders", "Which Order is theirs?", order_id),
        ("invoices", "Show its invoice", inv["id"]),
        ("recent_orders", "Which Order was that for?", order_id),
    ):
        script(
            monkeypatch,
            ctx,
            tool(name, record_id="discussed"),
            text("Current linked record."),
        )
        await ask(ctx, question, conversation_id=cid)
        output = json.loads(ctx["calls"][-1]["input"][-1]["output"])
        assert [row["id"] for row in output["items"]] == [ident]
    found = await assistant_tools.execute(
        ctx["user"], "invoices", {"record_id": "INV-1"}
    )
    assert found["items"][0]["id"] == inv["id"]
    await db.customers.insert_one(
        {
            "tenant_id": ctx["tenant"],
            "id": "other-customer-" + ctx["tenant"],
            "name": "Smith Construction",
        }
    )
    assert (
        await assistant_tools.execute(
            ctx["user"], "customer_history", {"record_id": "Smith Construction"}
        )
    )["needs_clarification"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["delete", "soft_delete", "permission"])
async def test_deleted_or_permission_changed_context_cannot_return_stale_money(
    ctx, monkeypatch, change
):
    inv = await invoice(ctx)
    script(monkeypatch, ctx, tool("invoices"), text("Invoice has $100 unpaid."))
    first = await ask(ctx)
    cid = first["conversation"]["id"]
    if change == "delete":
        await db.invoices.delete_one({"tenant_id": ctx["tenant"], "id": inv["id"]})
    elif change == "soft_delete":
        await db.invoices.update_one(
            {"tenant_id": ctx["tenant"], "id": inv["id"]},
            {"$set": {"deleted_at": "2026-10-23"}},
        )
    else:
        await db.users.update_one(
            {"tenant_id": ctx["tenant"], "id": ctx["user"]["id"]},
            {"$set": {"role": "staff", "permissions": ["ai_assistant:use"]}},
        )
    user = await assistant_context.fresh_actor(ctx["user"])
    history, _, data = await assistant_context.inputs(user, cid, 10)
    assert data["record_references"] == []
    assert "$100" not in json.dumps(history)
    if change != "permission":
        result = await assistant_tools.execute(
            user, "invoices", {"record_id": "discussed"}, conversation_id=cid
        )
        assert result["needs_clarification"]
    else:
        with pytest.raises(assistant_tools.ToolError):
            await assistant_tools.execute(
                user, "invoices", {"record_id": inv["id"]}, conversation_id=cid
            )
    with pytest.raises(assistant_tools.ToolError):
        await assistant_tools.execute(
            ctx["other"], "invoices", {"record_id": inv["id"]}, conversation_id=cid
        )
    foreign = await assistant_tools.execute(
        ctx["foreign"], "invoices", {"record_id": inv["id"]}
    )
    assert foreign["items"] == []


@pytest.mark.asyncio
async def test_text_voice_text_share_record_focus(v, monkeypatch):
    inv = await invoice(v)
    script(monkeypatch, v, tool("invoices"), text("Invoice context."))
    first = await ask(v)
    cid = first["conversation"]["id"]
    _, runtime, _ = await start(v, conversation_id=cid)
    assert runtime.record_references[0]["source_id"] == inv["id"]
    await utterance(runtime, "When was that due?")
    output = tool("invoices", record_id="discussed")["output"]
    await answer(runtime, response="tool-result", output=output)
    sent = [
        r
        for r in v["sockets"][0].sent
        if r["type"] == "conversation.item.create"
        and r["item"]["type"] == "function_call_output"
    ]
    assert json.loads(sent[-1]["item"]["output"])["items"][0]["id"] == inv["id"]
    await answer(runtime, response="spoken-answer", text="Current invoice record.")
    await runtime.close("user_ended")
    _, _, context = await assistant_context.inputs(v["user"], cid, 10)
    assert context["record_references"][0]["source_id"] == inv["id"]


@pytest.mark.asyncio
async def test_diagnostics_do_not_store_raw_selectors_or_business_values(ctx):
    convo = await svc.create_conversation(ctx["user"], {})
    secret_query = "sensitive-customer-query-should-not-be-logged"
    await assistant_tools.execute(
        ctx["user"],
        "invoices",
        {"record_id": secret_query},
        conversation_id=convo["id"],
    )
    saved = await db.assistant_conversations.find_one(
        {"tenant_id": ctx["tenant"], "id": convo["id"]}, {"_id": 0}
    )
    rows = saved["metadata"]["tool_diagnostics"]
    assert rows and secret_query not in json.dumps(rows, default=str)
    assert rows[0]["outcome"] == "clarification_required"
    assert len(rows[0]["selector_fingerprints"]["record_id"]) == 64
    with pytest.raises(assistant_tools.ToolError):
        await assistant_tools.execute_call(
            ctx["user"],
            {"name": "invoices", "arguments": "not valid json"},
            conversation_id=convo["id"],
        )
    saved = await db.assistant_conversations.find_one(
        {"tenant_id": ctx["tenant"], "id": convo["id"]}
    )
    assert (
        saved["metadata"]["tool_diagnostics"][-1]["outcome"] == "invalid_json_arguments"
    )


@pytest.mark.asyncio
async def test_unknown_usage_price_stops_without_retry_and_retains_reservation(
    ctx, monkeypatch
):
    response = text("An answer with unpriced tier.")
    response.update(usage(100, 10, tier="priority"))
    script(monkeypatch, ctx, response)
    with pytest.raises(svc.BusinessAssistantError):
        await ask(ctx)
    assert len(ctx["calls"]) == 1
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"tenant_id": ctx["tenant"]}
    )
    assert cost["estimated_cost_micros"] > 0 and cost["actual_cost_micros"] is None
    assert cost["reconciliation_status"] == "unpriced_usage_reserved_maximum"


@pytest.mark.asyncio
async def test_observed_cost_over_reservation_stops_without_another_request(
    ctx, monkeypatch
):
    response = tool("invoices")
    response.update(usage(10000000, 10))
    script(monkeypatch, ctx, response)
    with pytest.raises(svc.BusinessAssistantError) as caught:
        await ask(ctx)
    assert caught.value.code == "assistant_reservation_exceeded"
    assert len(ctx["calls"]) == 1
    row = await db.ai_provider_cost_ledger_entries.find_one(
        {"tenant_id": ctx["tenant"]}
    )
    assert row["estimated_cost_micros"] >= 10000020
    assert row["actual_cost_micros"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,kind,collection",
    [
        ("quote_followups", "quote", "quotes"),
        ("tasks", "task", "tasks"),
        ("work_order_status", "work_order", "work_orders"),
        ("shop_schedule", "calendar_event", "calendar_events"),
    ],
)
async def test_other_canonical_read_tools_resolve_structured_identity(
    ctx, name, kind, collection
):
    from app.core.time_utils import utc_now
    from datetime import timedelta

    now = utc_now()
    ident = uuid.uuid4().hex
    row = {
        "tenant_id": ctx["tenant"],
        "id": ident,
        "number": ident,
        "title": "Fictional record",
        "status": (
            "sent" if kind == "quote" else "queued" if kind == "work_order" else "open"
        ),
        "due_at": now.isoformat(),
    }
    if kind == "calendar_event":
        row.update(
            status="scheduled",
            source_type="manual",
            start_at=now.isoformat(),
            end_at=(now + timedelta(minutes=20)).isoformat(),
        )
    if kind == "work_order":
        row["order_id"] = "order-" + ident
        await db.orders.insert_one(
            {
                "tenant_id": ctx["tenant"],
                "id": row["order_id"],
                "number": "O-" + ident,
                "status": "confirmed",
            }
        )
    await db[collection].insert_one(row)
    convo = await svc.create_conversation(ctx["user"], {})
    refs = [assistant_tools.reference(kind, row)]
    await svc._insert_message(
        ctx["user"],
        conversation_id=convo["id"],
        role="assistant",
        content_text="Previously discussed record",
        mode="owner",
        metadata={
            "sources": refs,
            "record_references": refs,
            "permission_signature": assistant_context.permission_signature(ctx["user"]),
        },
    )
    result = await assistant_tools.execute(
        ctx["user"], name, {"record_id": "discussed"}, conversation_id=convo["id"]
    )
    expected = "calendar_event:" + ident if kind == "calendar_event" else ident
    assert [item["id"] for item in result["items"]] == [expected]
    assert result["sources"][0]["source_id"] == ident


def test_explicit_flex_prices_and_service_tier():
    profile = luna()
    profile["metadata"]["processing_tiers"] = {
        "flex": {
            key: str(Decimal(value) / 2)
            for key, value in profile["metadata"].items()
            if key in ai_text_pricing.RATE_KEYS
        }
    }
    profile["metadata"]["service_tier"] = "flex"
    assert ai_text_pricing.request_options(profile) == {"service_tier": "flex"}
    assert ai_text_pricing.cost(profile, usage(1000, 100, tier="flex"))[0] == 75


@pytest.mark.asyncio
async def test_unchanged_customer_page_preserves_invoice_focus_but_new_page_changes_it(
    ctx, monkeypatch
):
    customer_id, other_id = "customer-" + ctx["tenant"], "other-" + ctx["tenant"]
    await db.customers.insert_many(
        [
            {"id": customer_id, "tenant_id": ctx["tenant"], "name": "First Customer"},
            {"id": other_id, "tenant_id": ctx["tenant"], "name": "Other Customer"},
        ]
    )
    inv = await invoice(ctx, customer_id=customer_id)
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id=inv["id"]),
        text("Current invoice."),
    )
    first = await ask(
        ctx,
        "Show this invoice",
        context={"source_entity_type": "customer", "source_entity_id": customer_id},
    )
    cid = first["conversation"]["id"]
    script(
        monkeypatch,
        ctx,
        tool("invoices", record_id="discussed"),
        text("Current due date."),
    )
    await ask(ctx, "When was that due?", conversation_id=cid)
    assert (
        json.loads(ctx["calls"][-2]["input"][-1]["content"])["record_references"][0][
            "source_id"
        ]
        == inv["id"]
    )
    script(monkeypatch, ctx, text("Other Customer selected."))
    await ask(
        ctx,
        "Use this Customer now",
        conversation_id=cid,
        context={"source_entity_type": "customer", "source_entity_id": other_id},
    )
    assert (
        json.loads(ctx["calls"][-1]["input"][-1]["content"])["record_references"][0][
            "source_id"
        ]
        == other_id
    )
