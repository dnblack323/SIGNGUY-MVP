"""Stage F disposable scenario. Real services/records, scripted AI only."""

from datetime import timedelta
import json
import uuid


async def configure(settings, db):
    from app.core.time_utils import utc_now
    from app.services import openai_assistant_provider

    tenant = "assistant-browser"
    tomorrow = (utc_now() + timedelta(days=1)).date().isoformat()
    await db.users.update_one(
        {"tenant_id": tenant, "id": "assistant-browser-owner"},
        {"$set": {"role": "admin"}},
    )
    await db.orders.update_one(
        {"tenant_id": tenant, "id": "browser-order"}, {"$set": {"due_date": tomorrow}}
    )
    await db.invoices.update_one(
        {"tenant_id": tenant, "id": "browser-invoice"},
        {"$set": {"customer_id": "browser-customer"}},
    )
    await db.customers.insert_one(
        {"tenant_id": tenant, "id": "browser-other-customer", "name": "Other Customer"}
    )
    await db.invoices.insert_one(
        {
            "tenant_id": tenant,
            "id": "browser-other-invoice",
            "order_id": "other-order",
            "customer_id": "browser-other-customer",
            "number": "OTHER-1",
            "total_cents": 99999,
            "document_status": "issued",
            "due_date": "2026-01-01",
        }
    )
    await db.work_orders.insert_one(
        {
            "tenant_id": tenant,
            "id": "browser-work-order",
            "order_id": "browser-order",
            "number": "WO-F-1001",
            "status": "queued",
            "due_date": tomorrow,
        }
    )
    await db.calendar_events.insert_one(
        {
            "tenant_id": tenant,
            "id": "browser-schedule",
            "title": "Smith truck lettering installation",
            "start_at": tomorrow + "T14:00:00+00:00",
            "end_at": tomorrow + "T15:00:00+00:00",
            "status": "scheduled",
            "visibility": "staff",
            "source_type": "manual",
        }
    )
    await db.tasks.insert_one(
        {
            "tenant_id": tenant,
            "id": "browser-existing-task",
            "title": "Review Smith artwork",
            "due_at": tomorrow + "T09:00:00+00:00",
            "status": "open",
            "visibility": "staff",
        }
    )

    async def respond(payload):
        last = payload["input"][-1]
        prompt = ""
        for item in reversed(payload["input"]):
            if item.get("role") == "user":
                try:
                    prompt = (
                        json.loads(item.get("content", "{}"))
                        .get("user_message", "")
                        .casefold()
                    )
                except (ValueError, TypeError):
                    pass
                if prompt:
                    break
        if last.get("type") == "function_call_output":
            result = json.loads(last["output"])
            if result.get("proposal_id"):
                answer = "Review and edit the exact action preview, then confirm it in the interface. No application record has been created yet and no email sent."
            elif result.get("memory_preview"):
                answer = "Review this private memory suggestion and explicitly approve it in the memory editor. It is not saved yet."
            elif result.get("tool") == "invoices":
                answer = (
                    "; ".join(
                        f"Invoice {r['number']} has ${r['balance_due_cents']/100:.2f} unpaid"
                        for r in result["items"]
                    )
                    or "No unpaid invoices in this bounded result."
                )
            else:
                answer = "Application record results: " + json.dumps(
                    result.get("items", [])
                )
            content = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": answer}],
                }
            ]
        else:
            name, args = "recent_orders", {"record_id": "browser-order"}
            if "remember" in prompt:
                name, args = "propose_memory", {
                    "memory_key": "updates",
                    "content_text": "Prefer concise morning updates",
                    "source_type": None,
                    "source_id": None,
                }
            elif "task" in prompt and any(x in prompt for x in ("create", "follow-up")):
                name, args = "propose_action", {
                    "action_type": "internal_task",
                    "title": "Call Smith Construction",
                    "body": "Discuss truck lettering follow-up",
                    "due_when": "tomorrow",
                    "target_type": "customer",
                    "target_id": "browser-customer",
                }
            elif "note" in prompt:
                order_note = "order note" in prompt
                name, args = "propose_action", {
                    "action_type": "internal_note",
                    "title": "Reflective vinyl follow-up",
                    "body": "Customer requested reflective vinyl for their truck",
                    "target_type": "order" if order_note else "customer",
                    "target_id": "browser-order" if order_note else "browser-customer",
                }
            elif "draft" in prompt or "email" in prompt:
                name, args = "propose_action", {
                    "action_type": "email_draft",
                    "title": "Quote follow-up",
                    "body": "ignored for neutral customer template",
                    "target_type": "quote",
                    "target_id": "browser-quote",
                }
            elif "invoice" in prompt or "unpaid" in prompt:
                name, args = "invoices", {
                    "customer_id": "browser-customer",
                    "invoice_filter": "overdue" if "overdue" in prompt else "unpaid",
                }
            elif "work order" in prompt:
                name, args = "work_order_status", {"record_id": "browser-work-order"}
            elif "quote" in prompt:
                name, args = "quote_followups", {}
            elif "schedule" in prompt:
                name, args = "shop_schedule", {"day": "tomorrow"}
            elif "task" in prompt:
                name, args = "tasks", {"day": "tomorrow"}
            elif "orders" in prompt and "tomorrow" in prompt:
                name, args = "recent_orders", {"due_day": "tomorrow"}
            elif "find" in prompt and "smith" in prompt:
                name, args = "find_customers", {"query": "Smith"}
            content = [
                {
                    "type": "function_call",
                    "name": name,
                    "arguments": json.dumps(args),
                    "call_id": uuid.uuid4().hex,
                }
            ]
        return {
            "id": uuid.uuid4().hex,
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "output": content,
        }

    openai_assistant_provider.respond = respond
