"""Stage E uses mocked decisions and real disposable canonical records."""

import asyncio
from datetime import timedelta
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid

import pytest
import pytest_asyncio

from app.core.db import db
from app.core.time_utils import utc_now
from app.services import (
    assistant_actions as actions,
    assistant_tools,
)
from app.services import business_assistant as svc
from app.services.assistant_memory import save as save_memory
from tests.test_assistant_stage_b import ctx, script, text, tool, ask  # noqa: F401
from tests.test_assistant_stage_d import v, start, utterance, answer  # noqa: F401


@pytest.mark.asyncio
async def test_conversational_memory_is_only_a_preview_until_approved(e, monkeypatch):
    fields = {
        "memory_key": "updates",
        "content_text": "Prefer concise morning updates",
        "source_type": "customer",
        "source_id": e["customer"]["id"],
    }
    script(
        monkeypatch,
        e,
        tool("propose_memory", **fields),
        text("Review and approve the memory suggestion in the interface."),
    )
    result = await ask(
        e,
        "Remember my preferred update format",
        key="memory-preview",
        conversation_id=e["conversation_id"],
    )
    assert result["assistant_message"]["metadata"]["memory_preview"] == fields
    assert (
        await db.assistant_memory_entries.count_documents({"tenant_id": e["tenant"]})
        == 0
    )
    saved = await svc.upsert_memory(e["user"], fields)
    assert saved["approval_source"] == "explicit_user_interface"
    for user in (e["other"], e["foreign"]):
        assert (await svc.list_memory(user))["items"] == []
    for bad in (
        {**fields, "source_id": "deleted"},
        {**fields, "content_text": "my password"},
    ):
        with pytest.raises(assistant_tools.ToolError):
            await assistant_tools.execute(e["user"], "propose_memory", bad)
    await svc.delete_memory(e["user"], saved["id"])
    assert (
        await assistant_tools.execute(e["user"], "recall_memory", {"query": "updates"})
    )["items"] == []


@pytest.mark.asyncio
async def test_voice_memory_suggestion_is_visible_without_saving(v):
    result, runtime, _ = await start(v)
    await utterance(runtime, "Remember that I prefer short updates")
    await answer(
        runtime,
        response="memory-preview",
        output=[
            {
                "type": "function_call",
                "name": "propose_memory",
                "call_id": "memory1",
                "arguments": '{"memory_key":"updates","content_text":"Prefer short updates","source_type":null,"source_id":null}',
            }
        ],
    )
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert any(
        m["metadata"].get("memory_preview", {}).get("memory_key") == "updates"
        for m in history["messages"]
        if m["metadata"].get("memory_preview")
    )
    assert (
        await db.assistant_memory_entries.count_documents({"tenant_id": v["tenant"]})
        == 0
    )


@pytest_asyncio.fixture
async def e(ctx):
    customer = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "name": "Smith Construction",
        "email": "smith@example.test",
        "updated_at": utc_now().isoformat(),
    }
    await db.customers.insert_one(customer)
    quote = {
        "id": uuid.uuid4().hex,
        "tenant_id": ctx["tenant"],
        "customer_id": customer["id"],
        "number": "Q-E-1001",
        "status": "sent",
        "updated_at": utc_now().isoformat(),
    }
    await db.quotes.insert_one(quote)
    convo = await svc.create_conversation(ctx["user"], {})
    return {**ctx, "customer": customer, "quote": quote, "conversation_id": convo["id"]}


async def proposal(e, kind="internal_task", **extra):
    return await svc.propose_action(
        e["user"],
        {
            "conversation_id": e["conversation_id"],
            "action_type": kind,
            "title": "Call Smith about truck lettering",
            "body": "Discuss reflective vinyl",
            "due_at": "tomorrow",
            "target_refs": [{"type": "customer", "id": e["customer"]["id"]}],
            "idempotency_key": uuid.uuid4().hex,
            **extra,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,collection",
    [
        ("internal_task", "tasks"),
        ("internal_note", "internal_notes"),
        ("email_draft", "ai_studio_editable_drafts"),
    ],
)
async def test_real_record_creation_requires_current_interface_confirmation_and_runs_once(
    e, kind, collection
):
    p = await proposal(e, kind)
    assert await db[collection].count_documents({"tenant_id": e["tenant"]}) == 0
    with pytest.raises(svc.BusinessAssistantError):
        await svc.execute_proposal(e["user"], p["id"])
    with pytest.raises(svc.BusinessAssistantError):
        await svc.confirm_proposal(e["user"], p["id"], revision=0)
    await svc.confirm_proposal(e["user"], p["id"], revision=p["revision"])
    results = await asyncio.gather(
        *(
            svc.execute_proposal(e["user"], p["id"], idempotency_key=f"different-{i}")
            for i in range(4)
        ),
        return_exceptions=True,
    )
    assert any(isinstance(r, dict) and r["status"] == "succeeded" for r in results)
    again = await svc.execute_proposal(e["user"], p["id"], idempotency_key="retry")
    assert again["status"] == "succeeded"
    assert await db[collection].count_documents({"tenant_id": e["tenant"]}) == 1
    assert (
        await db.assistant_action_executions.count_documents(
            {"tenant_id": e["tenant"], "proposal_id": p["id"]}
        )
        == 1
    )
    row = await db[collection].find_one({"tenant_id": e["tenant"]})
    if kind == "internal_task":
        assert (
            row["customer_id"] == e["customer"]["id"]
            and row["assigned_user_id"] == e["user"]["id"]
        )
        assert row["due_at"].startswith(
            (utc_now().astimezone(ZoneInfo("America/New_York")) + timedelta(days=1))
            .date()
            .isoformat()
        )
    elif kind == "internal_note":
        assert (
            row["body"] == "Discuss reflective vinyl"
            and row["customer_id"] == e["customer"]["id"]
        )
    else:
        assert again["canonical_result"]["sent"] is False
    assert await db.email_logs.count_documents({"tenant_id": e["tenant"]}) == 0


@pytest.mark.asyncio
async def test_edits_expiry_stale_sources_and_changed_permissions(e):
    p = await proposal(e)
    await svc.confirm_proposal(e["user"], p["id"], p["revision"])
    changed = await svc.edit_proposal(
        e["user"],
        p["id"],
        {
            "revision": 1,
            "editable_payload": {
                **p["editable_payload"],
                "body": "Corrected exact task",
            },
        },
    )
    assert changed["revision"] == 2 and changed["status"] == "edited"
    with pytest.raises(svc.BusinessAssistantError):
        await svc.execute_proposal(e["user"], p["id"])
    with pytest.raises(svc.BusinessAssistantError):
        await svc.confirm_proposal(e["user"], p["id"], 1)
    await svc.confirm_proposal(e["user"], p["id"], 2)
    await db.assistant_action_proposals.update_one(
        {"id": p["id"]},
        {
            "$set": {
                "confirmation_expires_at": (
                    utc_now() - timedelta(seconds=1)
                ).isoformat()
            }
        },
    )
    with pytest.raises(svc.BusinessAssistantError, match="expired"):
        await svc.execute_proposal(e["user"], p["id"])
    p = await proposal(e)
    await db.customers.update_one(
        {"id": e["customer"]["id"]}, {"$set": {"name": "Changed destination"}}
    )
    with pytest.raises(svc.BusinessAssistantError, match="source record changed"):
        await svc.confirm_proposal(e["user"], p["id"], 1)
    p = await proposal(e)
    await db.users.update_one(
        {"id": e["user"]["id"]},
        {
            "$set": {
                "role": "staff",
                "permissions": ["ai_assistant:use", "customer:read", "task:create"],
            }
        },
    )
    with pytest.raises(svc.BusinessAssistantError, match="Permissions changed"):
        await svc.confirm_proposal(e["user"], p["id"], 1)
    assert await db.tasks.count_documents({"tenant_id": e["tenant"]}) == 0


@pytest.mark.asyncio
async def test_private_proposals_and_foreign_targets_are_rejected(e):
    p = await proposal(e)
    for user in (e["other"], e["foreign"]):
        for operation in (actions.get, svc.confirm_proposal, svc.execute_proposal):
            with pytest.raises(svc.BusinessAssistantError):
                await operation(user, p["id"])
    await db.users.update_one(
        {"id": e["other"]["id"]},
        {
            "$set": {
                "role": "staff",
                "permissions": ["ai_assistant:use", "customer:read"],
            }
        },
    )
    with pytest.raises(svc.BusinessAssistantError):
        await svc.propose_action(
            e["other"], {"action_type": "internal_task", "title": "Not allowed"}
        )
    await db.customers.insert_one(
        {"id": "foreign-" + e["tenant"], "tenant_id": e["foreign"]["tenant_id"]}
    )
    with pytest.raises(svc.BusinessAssistantError):
        await proposal(
            e, target_refs=[{"type": "customer", "id": "foreign-" + e["tenant"]}]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "personality",
    [
        "ops_partner",
        "wise_mentor",
        "cheerful_helper",
        "no_bs_direct",
        "sarcastic_funny",
    ],
)
async def test_professional_quote_draft_is_independent_of_personality(e, personality):
    await svc.update_preferences(e["user"], {"personality_key": personality})
    result = await assistant_tools.execute(
        e["user"],
        "propose_action",
        {
            "action_type": "email_draft",
            "title": "Follow up",
            "body": "Ridiculous clown joke from model",
            "target_type": "quote",
            "target_id": e["quote"]["id"],
        },
        conversation_id=e["conversation_id"],
        request_key="same-input",
    )
    assert result["status"] == "awaiting_interface_confirmation"
    assert (
        "Smith Construction" in result["preview"]["body"]
        and "Q-E-1001" in result["preview"]["body"]
    )
    assert "clown" not in result["preview"]["body"]
    assert (
        await db.ai_studio_editable_drafts.count_documents({"tenant_id": e["tenant"]})
        == 0
    )
    await svc.confirm_proposal(e["user"], result["proposal_id"], 1)
    receipt = await svc.execute_proposal(e["user"], result["proposal_id"])
    assert receipt["canonical_result"]["sent"] is False


@pytest.mark.asyncio
async def test_natural_text_clarification_then_proposal_preserves_shared_history(
    e, monkeypatch
):
    script(
        monkeypatch,
        e,
        text("Which Customer should this note be attached to?"),
        tool(
            "propose_action",
            action_type="internal_note",
            title="Reflective vinyl request",
            body="Requested reflective vinyl for the next truck",
            target_type="customer",
            target_id=e["customer"]["id"],
        ),
        text(
            "Review the exact note in the action preview. Nothing has been saved to the Customer yet."
        ),
    )
    first = await ask(
        e,
        "Add a customer note",
        key="clarify-note",
        conversation_id=e["conversation_id"],
    )
    second = await ask(
        e,
        "Smith Construction; reflective vinyl for the next truck",
        key="answer-note",
        conversation_id=e["conversation_id"],
    )
    assert "Which Customer" in first["answer"]
    assert second["proposals"][0]["action_type"] == "internal_note"
    assert "Which Customer" in str(e["calls"][-1]["input"])
    assert await db.internal_notes.count_documents({"tenant_id": e["tenant"]}) == 0


@pytest.mark.asyncio
async def test_memory_correct_delete_duplicate_and_private_recall(e):
    m = await svc.upsert_memory(
        e["user"],
        {
            "memory_key": "updates",
            "content_text": "Prefer concise morning updates",
            "source_type": "customer",
            "source_id": e["customer"]["id"],
        },
    )
    duplicate = await svc.upsert_memory(
        e["user"],
        {
            "memory_key": "another",
            "content_text": "  Prefer concise morning updates ",
            "source_type": "customer",
            "source_id": e["customer"]["id"],
        },
    )
    assert duplicate["id"] == m["id"]
    corrected = await save_memory(
        e["user"],
        {
            "memory_key": "updates",
            "content_text": "Prefer detailed afternoon updates",
            "expected_updated_at": m["updated_at"],
        },
        memory_id=m["id"],
    )
    assert corrected["source_id"] == e["customer"]["id"]
    with pytest.raises(svc.BusinessAssistantError):
        await save_memory(
            e["user"],
            {
                "memory_key": "updates",
                "content_text": "Stale edit",
                "expected_updated_at": m["updated_at"],
            },
            memory_id=m["id"],
        )
    recalled = await assistant_tools.execute(
        e["user"], "recall_memory", {"query": "afternoon updates"}
    )
    assert "detailed afternoon" in str(recalled)
    assert await assistant_tools.reference_allowed(e["user"], recalled["sources"][0])
    for user in (e["other"], e["foreign"]):
        assert (
            await assistant_tools.execute(user, "recall_memory", {"query": "updates"})
        )["items"] == []
        with pytest.raises(svc.BusinessAssistantError):
            await save_memory(
                user,
                {"memory_key": "updates", "content_text": "Private change"},
                memory_id=m["id"],
            )
    await svc.delete_memory(e["user"], m["id"])
    assert not await assistant_tools.reference_allowed(
        e["user"], recalled["sources"][0]
    )
    assert (await svc.list_memory(e["user"]))["items"] == []


@pytest.mark.asyncio
async def test_voice_and_text_use_same_proposal_tool_and_no_model_execution(v):
    result, runtime, _ = await start(v)
    await utterance(runtime, "Create an internal task for tomorrow")
    await answer(
        runtime,
        response="propose-task",
        output=[
            {
                "type": "function_call",
                "name": "propose_action",
                "call_id": "task1",
                "arguments": '{"action_type":"internal_task","title":"Review production","body":"Check open work","due_when":"tomorrow"}',
            }
        ],
    )
    await answer(
        runtime,
        response="explain-preview",
        text="Please confirm the task in the interface.",
    )
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert len(history["proposals"]) == 1
    assert await db.tasks.count_documents({"tenant_id": v["tenant"]}) == 0
    with pytest.raises(assistant_tools.ToolError):
        await assistant_tools.execute(v["user"], "execute_assistant_action", {})
    p = history["proposals"][0]
    await svc.confirm_proposal(v["user"], p["id"], 1)
    await svc.execute_proposal(v["user"], p["id"])
    assert await db.tasks.count_documents({"tenant_id": v["tenant"]}) == 1


@pytest.mark.asyncio
async def test_saved_record_is_real_and_private_and_studio_list_respects_sources(e):
    from app.services import ai_studio

    p = await proposal(e, "email_draft")
    await svc.confirm_proposal(e["user"], p["id"], 1)
    receipt = await svc.execute_proposal(e["user"], p["id"])
    record = await actions.saved_record(e["user"], p["id"])
    assert record["id"] == receipt["canonical_result"]["draft_id"]
    assert record["content"] == "Discuss reflective vinyl"
    assert (await ai_studio.list_editable_drafts(e["other"]))["items"] == []
    assert (await ai_studio.list_activity(e["other"], tool_key="business_assistant"))[
        "items"
    ] == []
    assert (
        len(
            (await ai_studio.list_activity(e["user"], tool_key="business_assistant"))[
                "items"
            ]
        )
        == 1
    )
    for user in (e["other"], e["foreign"]):
        with pytest.raises(svc.BusinessAssistantError):
            await actions.saved_record(user, p["id"])
    await db.customers.delete_one({"tenant_id": e["tenant"], "id": e["customer"]["id"]})
    assert (await ai_studio.list_editable_drafts(e["user"]))["items"] == []
    assert (await ai_studio.list_activity(e["user"], tool_key="business_assistant"))[
        "items"
    ] == []
    with pytest.raises(svc.BusinessAssistantError):
        await actions.saved_record(e["user"], p["id"])


@pytest.mark.asyncio
async def test_failure_after_canonical_write_is_recovered_by_read_without_duplicate(
    e, monkeypatch
):
    from app.services import task_service

    original = task_service.create_task
    calls = []

    async def interrupted(**kwargs):
        calls.append(kwargs)
        await original(**kwargs)
        raise RuntimeError("Simulated receipt loss after actual task insertion")

    monkeypatch.setattr(task_service, "create_task", interrupted)
    p = await proposal(e)
    await svc.confirm_proposal(e["user"], p["id"], 1)
    with pytest.raises(svc.BusinessAssistantError):
        await svc.execute_proposal(e["user"], p["id"])
    recovered = await svc.execute_proposal(e["user"], p["id"])
    assert recovered["status"] == "succeeded"
    assert len(calls) == 1
    assert await db.tasks.count_documents({"tenant_id": e["tenant"]}) == 1


@pytest.mark.asyncio
async def test_duplicate_provider_proposals_and_conflicting_http_keys(e):
    args = {
        "action_type": "internal_task",
        "title": "Call Smith",
        "body": "Discuss the truck",
        "target_type": "customer",
        "target_id": e["customer"]["id"],
    }
    first = await assistant_tools.execute(
        e["user"],
        "propose_action",
        args,
        conversation_id=e["conversation_id"],
        request_key="turn1:call1",
    )
    second = await assistant_tools.execute(
        e["user"],
        "propose_action",
        args,
        conversation_id=e["conversation_id"],
        request_key="turn1:call2",
    )
    assert first["proposal_id"] == second["proposal_id"]
    await proposal(e, idempotency_key="same-key")
    with pytest.raises(svc.BusinessAssistantError, match="different content"):
        await proposal(e, idempotency_key="same-key", body="A different note")


@pytest.mark.asyncio
async def test_dates_use_canonical_shop_timezone_and_dst_not_personality_preferences(
    e, monkeypatch
):
    await db.settings.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": e["tenant"],
            "namespace": "company_profile",
            "key": "timezone",
            "value": "America/Los_Angeles",
        }
    )
    await svc.update_preferences(e["user"], {"timezone": "Asia/Tokyo"})
    monkeypatch.setattr(
        actions, "utc_now", lambda: datetime(2026, 3, 8, 6, tzinfo=timezone.utc)
    )
    p = await proposal(e)
    assert p["preview"]["due_at"] == "2026-03-08T09:00:00-07:00"
    assert p["preview"]["timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_memory_correction_invalidates_active_voice_context(v):
    m = await svc.upsert_memory(
        v["user"], {"memory_key": "format", "content_text": "Prefer very short updates"}
    )
    _, runtime, _ = await start(v)
    assert "very short" in str(runtime.ws.sent)
    await save_memory(
        v["user"],
        {"memory_key": "format", "content_text": "Prefer detailed updates"},
        memory_id=m["id"],
    )
    with pytest.raises(assistant_tools.ToolError, match="Source access"):
        await runtime.check()


@pytest.mark.asyncio
async def test_order_note_is_attached_only_to_chosen_order(e):
    order_id = uuid.uuid4().hex
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": e["tenant"],
            "number": "O-E-1",
            "customer_id": e["customer"]["id"],
        }
    )
    p = await proposal(
        e, "internal_note", target_refs=[{"type": "order", "id": order_id}]
    )
    await svc.confirm_proposal(e["user"], p["id"], 1)
    receipt = await svc.execute_proposal(e["user"], p["id"])
    note = await db.internal_notes.find_one(
        {"tenant_id": e["tenant"], "id": receipt["canonical_result"]["note_id"]}
    )
    assert note["order_id"] == order_id and note["customer_id"] is None
    record = await actions.saved_record(e["user"], p["id"])
    assert record["content"] == "Discuss reflective vinyl"


@pytest.mark.asyncio
async def test_memory_topic_can_be_renamed_and_original_topic_reused(e):
    first = await svc.upsert_memory(
        e["user"], {"memory_key": "format", "content_text": "Short updates"}
    )
    renamed = await save_memory(
        e["user"],
        {"memory_key": "morning format", "content_text": "Short updates"},
        memory_id=first["id"],
    )
    second = await svc.upsert_memory(
        e["user"], {"memory_key": "format", "content_text": "Detailed updates"}
    )
    assert renamed["id"] != second["id"]
    assert len((await svc.list_memory(e["user"]))["items"]) == 2
