"""Transport-independent, bounded and permission-filtered shop read tools."""

from datetime import datetime, time, timedelta, timezone
import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import utc_now
from . import (
    calendar_service,
    customer_service,
    invoice_reconciliation,
    production_stage_service,
)


class ToolError(Exception):
    pass


class ReadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = Field(default=None, max_length=160)
    record_id: str | None = Field(default=None, max_length=160)
    customer_id: str | None = Field(default=None, max_length=160)
    day: Literal["today", "tomorrow"] = "today"
    invoice_filter: Literal["unpaid", "overdue", "latest"] = "unpaid"
    due_day: Literal["today", "tomorrow"] | None = None
    schedule_window: Literal["day", "next_30_days"] = "day"


PERMISSIONS = {
    "find_customers": [Perm.CUSTOMER_READ.value],
    "customer_history": [Perm.CUSTOMER_READ.value, Perm.ORDER_READ.value],
    "recent_orders": [Perm.ORDER_READ.value],
    "work_order_status": [Perm.WORK_ORDER_READ.value],
    "invoices": [Perm.INVOICE_READ.value],
    "quote_followups": [Perm.QUOTE_READ.value],
    "tasks": [Perm.TASK_READ.value],
    "shop_schedule": [Perm.SCHEDULE_READ.value],
}
DESCRIPTIONS = {
    "find_customers": "Find customers by name, company, email or partial name; clarify multiple matches.",
    "customer_history": "Customer identity and recent Orders. Supply customer record_id; use quote_followups separately for Quotes.",
    "recent_orders": "Recent Orders, one Order by record_id/name/number query, or Orders due today/tomorrow using due_day. Returns a permitted linked customer_id for Customer follow-ups. Bounded results; no writes.",
    "work_order_status": "Work Orders and their actual production stages, recorded blockers and due dates.",
    "invoices": "Canonical current unpaid/overdue invoice balances, latest invoice or a specific invoice. Supply exact customer_id to restrict to a permitted Customer; never assume shop-wide invoices belong to that Customer. Overdue is before today in the selected timezone.",
    "quote_followups": "Open sent/viewed Quotes that can be reviewed for follow-up; no assumed last-contact date or sending.",
    "tasks": "Permitted open tasks due today or tomorrow in the selected timezone.",
    "shop_schedule": "Shop Schedule and permitted projected work for today/tomorrow, or upcoming 30 days using schedule_window=next_30_days. Query matches event titles, e.g. installation. Bounded results, not proof nothing exists later.",
}
TARGETS = {
    "customer": ("customers", Perm.CUSTOMER_READ.value, "/customers/"),
    "order": ("orders", Perm.ORDER_READ.value, "/orders/"),
    "work_order": ("work_orders", Perm.WORK_ORDER_READ.value, "/work-orders/"),
    "invoice": ("invoices", Perm.INVOICE_READ.value, "/invoices/"),
    "quote": ("quotes", Perm.QUOTE_READ.value, "/quotes/"),
    "task": ("tasks", Perm.TASK_READ.value, "/team/tasks"),
    "calendar_event": ("calendar_events", Perm.SCHEDULE_READ.value, "/shop-schedule"),
}


def has_perm(user: dict, permission: str) -> bool:
    return user.get("role") in {"owner", "admin"} or permission in set(
        user.get("permissions") or permissions_for_role(user.get("role", "staff"))
    )


def tool_definitions(user: dict) -> list[dict]:
    schema = ReadArgs.model_json_schema()

    # Presentation-only Pydantic titles repeat in every tool and consume the
    # bounded voice instructions. Preserve all validation keywords.
    def compact(value):
        if isinstance(value, dict):
            return {k: compact(v) for k, v in value.items() if k != "title"}
        if isinstance(value, list):
            return [compact(v) for v in value]
        return value

    schema = compact(schema)
    schema["required"] = list(schema["properties"])
    from .assistant_action_tool import definition

    return (
        [
            {
                "type": "function",
                "name": name,
                "description": DESCRIPTIONS[name],
                "parameters": schema,
                "strict": True,
            }
            for name, permissions in PERMISSIONS.items()
            if all(has_perm(user, p) for p in permissions)
        ]
        + definition(user)
        + [
            {
                "type": "function",
                "name": "propose_memory",
                "description": "When explicitly asked to remember or correct private background/preferences, prepare an editable memory suggestion only. Never saves or approves it. Reuse the existing topic for corrections. Link shop-specific information to an exact accessible source. Never propose passwords or current balances/statuses as durable truth. User must approve the exact text in the interface.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_key": {"type": "string", "maxLength": 80},
                        "content_text": {"type": "string", "maxLength": 1000},
                        "source_type": {
                            "type": ["string", "null"],
                            "enum": [
                                "customer",
                                "order",
                                "quote",
                                "invoice",
                                "work_order",
                                "task",
                                None,
                            ],
                        },
                        "source_id": {"type": ["string", "null"], "maxLength": 160},
                    },
                    "required": [
                        "memory_key",
                        "content_text",
                        "source_type",
                        "source_id",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "recall_memory",
                "description": "Read relevant explicitly approved private preferences/background across conversations. Historical memory never replaces live balances, statuses or schedules. Never saves anything.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "maxLength": 160}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]
    )


def reference(kind: str, row: dict) -> dict:
    target = TARGETS[kind]
    return {
        "source_type": kind,
        "source_id": row["id"],
        "source_label": str(
            row.get("number") or row.get("name") or row.get("title") or kind
        ),
        "route": target[2] + (row["id"] if target[2].endswith("/") else ""),
        "source_updated_at": str(row.get("updated_at") or row.get("created_at") or ""),
    }


def project(row: dict, *keys: str) -> dict:
    return {
        key: str(row[key]) if isinstance(row.get(key), datetime) else row.get(key)
        for key in ("id", *keys)
    }


async def reference_allowed(user: dict, ref: dict) -> bool:
    if ref.get("source_type") == "assistant_memory":
        row = await db.assistant_memory_entries.find_one(
            {
                "tenant_id": user["tenant_id"],
                "user_id": user["id"],
                "id": ref.get("source_id"),
                "status": "active",
            },
            {"_id": 0},
        )
        if not row or str(row.get("updated_at") or "") != ref.get("source_updated_at"):
            return False
        if row.get("source_type"):
            return await reference_allowed(
                user,
                {"source_type": row["source_type"], "source_id": row.get("source_id")},
            )
        return True
    target = TARGETS.get(ref.get("source_type"))
    if not target or not has_perm(user, target[1]):
        return False
    row = await db[target[0]].find_one(
        {"tenant_id": user["tenant_id"], "id": ref.get("source_id")}, {"_id": 0}
    )
    if (
        not row
        or row.get("deleted_at")
        or row.get("is_deleted")
        or row.get("status") == "deleted"
    ):
        return False
    if ref.get("source_type") == "calendar_event":
        return _event_visible(user, row)
    return True


def _event_visible(user: dict, row: dict) -> bool:
    if row.get("visibility") == "internal":
        return row.get("created_by_user_id") == user["id"]
    if row.get("visibility") == "employee":
        return row.get("assigned_user_id") == user["id"]
    return True


def _filter(user: dict, args: ReadArgs) -> dict:
    filt = {"tenant_id": user["tenant_id"]}
    if args.record_id:
        filt["id"] = args.record_id
    elif args.query:
        term = {"$regex": re.escape(args.query), "$options": "i"}
        filt["$or"] = [{"name": term}, {"title": term}, {"number": term}]
        if args.query.isdecimal() and len(args.query) <= 15:
            filt["$or"].append({"number": int(args.query)})
    return filt


def _local_date(value, zone: ZoneInfo):
    if not value:
        return None
    try:
        text = str(value)
        if len(text) == 10:
            return datetime.fromisoformat(text).date()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return (
            (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc))
            .astimezone(zone)
            .date()
        )
    except ValueError:
        return None


async def execute_call(user, call, **kwargs):
    import json
    from . import assistant_tool_diagnostics

    try:
        args = json.loads(call.get("arguments") or "{}")
        if not isinstance(args, dict):
            raise ValueError()
    except (ValueError, TypeError):
        await assistant_tool_diagnostics.record(
            user,
            call.get("name"),
            {},
            conversation_id=kwargs.get("conversation_id"),
            outcome="invalid_json_arguments",
        )
        raise ToolError("Invalid tool arguments") from None
    return await execute(user, call.get("name"), args, **kwargs)


async def execute(user, name, raw_args, *, record_references=None, **kwargs):
    from . import (
        assistant_context,
        assistant_record_context,
        assistant_tool_diagnostics,
    )

    if name in PERMISSIONS and not all(has_perm(user, p) for p in PERMISSIONS[name]):
        raise ToolError("This tool is not permitted")
    requested = user
    user = await assistant_context.fresh_actor(user)
    authority_signature = assistant_context.permission_signature(user)
    if requested.get("role") not in {"owner", "admin"}:
        requested_permissions = set(
            requested.get("permissions")
            or permissions_for_role(requested.get("role", "staff"))
        )
        effective = (
            requested_permissions
            if user.get("role") in {"owner", "admin"}
            else requested_permissions.intersection(user["permissions"])
        )
        user = {
            **user,
            "role": requested.get("role", "staff"),
            "permissions": sorted(effective) or ["assistant:no_permissions"],
        }
    conversation_id = kwargs.get("conversation_id")
    if conversation_id:
        # Verify ownership even when the caller supplies in-process voice references.
        current_refs = await assistant_record_context.references(user, conversation_id)
        if record_references is None:
            record_references = current_refs
    question = None
    if conversation_id:
        latest = await db.assistant_messages.find_one(
            {
                "tenant_id": user["tenant_id"],
                "conversation_id": conversation_id,
                "role": "user",
            },
            {"_id": 0, "content_text": 1},
            sort=[("created_at", -1), ("id", -1)],
        )
        question = (latest or {}).get("content_text")
    outcome, result = "invalid_arguments_or_not_permitted", None
    try:
        result = await _execute(
            user,
            name,
            raw_args,
            record_references=record_references or [],
            question=question,
            **kwargs,
        )
        current = await assistant_context.fresh_actor(user)
        if assistant_context.permission_signature(
            current
        ) != authority_signature or any(
            [
                not await reference_allowed(user, ref)
                for ref in result.get("sources", [])
            ]
        ):
            raise ToolError("Record access changed during lookup")
        outcome = (
            "clarification_required"
            if result.get("needs_clarification")
            else (
                "matched"
                if result.get("items") or result.get("sources")
                else "no_match"
            )
        )
        return result
    finally:
        await assistant_tool_diagnostics.record(
            user,
            name,
            raw_args,
            conversation_id=conversation_id,
            outcome=outcome,
            result=result,
        )


async def _execute(
    user: dict,
    name: str,
    raw_args: dict,
    *,
    timezone_name: str = "UTC",
    conversation_id: str | None = None,
    request_key: str | None = None,
    mode: str = "owner",
    record_references=None,
    question=None,
) -> dict:
    if name == "propose_memory":
        from .assistant_memory import suggestion

        return await suggestion(user, raw_args)
    if name == "recall_memory":
        from . import assistant_context

        if (
            set(raw_args) != {"query"}
            or not isinstance(raw_args["query"], str)
            or len(raw_args["query"]) > 160
        ):
            raise ToolError("Use one bounded memory query")
        rows = await assistant_context.memories(user, limit=5, query=raw_args["query"])
        return {
            "items": [
                {
                    "key": r["memory_key"],
                    "text": r["content_text"],
                    "source_type": r.get("source_type"),
                    "source_id": r.get("source_id"),
                }
                for r in rows
            ],
            "sources": [
                {
                    "source_type": "assistant_memory",
                    "source_id": r["id"],
                    "source_label": "Approved private context",
                    "source_updated_at": str(r.get("updated_at") or ""),
                }
                for r in rows
            ],
            "notice": "Approved historical context only. Fetch current business facts from application tools.",
        }
    if name == "propose_action":
        from .assistant_action_tool import execute as propose
        from .business_assistant import BusinessAssistantError

        try:
            return await propose(
                user,
                raw_args,
                conversation_id=conversation_id,
                request_key=request_key,
                mode=mode,
            )
        except BusinessAssistantError as exc:
            raise ToolError(exc.detail) from exc
    if name not in PERMISSIONS or not all(has_perm(user, p) for p in PERMISSIONS[name]):
        raise ToolError("This tool is not permitted")
    args = ReadArgs.model_validate(raw_args)
    from . import assistant_record_context

    try:
        args, related_filter = await assistant_record_context.resolve(
            user, name, args, record_references or [], question=question
        )
    except assistant_record_context.ClarificationRequired as exc:
        return {
            "tool": name,
            "items": [],
            "sources": [],
            "needs_clarification": True,
            "resolution_status": str(exc),
            "notice": "The record reference is ambiguous or unavailable. Ask the user which permitted record they mean; do not guess or use historical financial values.",
        }
    if args.customer_id and name != "invoices":
        raise ToolError("customer_id is supported only for the invoice lookup")
    zone = ZoneInfo(timezone_name)
    today = utc_now().astimezone(zone).date()
    selected = today + timedelta(days=args.day == "tomorrow")
    refs, items = [], []
    missing = []
    complete = True
    tenant = user["tenant_id"]
    if name == "find_customers":
        matches = (
            []
            if args.record_id
            else await customer_service.find_matching_customers(
                tenant_id=tenant, name=args.query, email=args.query
            )
        )
        rows = [match["customer"] for match in matches]
        if args.record_id:
            row = await db.customers.find_one(
                {"tenant_id": tenant, "id": args.record_id}, {"_id": 0}
            )
            rows = [row] if row else []
        if not rows and args.query and not args.record_id:
            term = {"$regex": re.escape(args.query), "$options": "i"}
            rows = [
                r
                async for r in db.customers.find(
                    {
                        "tenant_id": tenant,
                        "merged_into": None,
                        "archived": {"$ne": True},
                        "$or": [{"name": term}, {"company": term}],
                    },
                    {"_id": 0},
                ).limit(26)
            ]
        complete = len(rows) <= 25
        for row in rows[:25]:
            items.append(project(row, "name", "company", "email", "phone"))
            refs.append(reference("customer", row))
    elif name in {"customer_history", "recent_orders"}:
        filt = {**_filter(user, args), **related_filter}
        if name == "recent_orders" and args.due_day:
            selected = today + timedelta(days=args.due_day == "tomorrow")
            filt["due_date"] = {
                "$gte": (selected - timedelta(days=1)).isoformat(),
                "$lt": (selected + timedelta(days=2)).isoformat(),
            }
        if name == "customer_history":
            customer = await db.customers.find_one(
                {"tenant_id": tenant, "id": args.record_id}, {"_id": 0}
            )
            if not customer:
                raise ToolError("Customer not found; choose a permitted customer")
            refs.append(reference("customer", customer))
            filt = {"tenant_id": tenant, "customer_id": customer["id"]}
        bound = 101 if args.due_day else 26
        rows = [
            r
            async for r in db.orders.find(filt, {"_id": 0})
            .sort("created_at", -1)
            .limit(bound)
        ]
        complete = len(rows) < bound
        rows = [
            r
            for r in rows
            if not args.due_day or _local_date(r.get("due_date"), zone) == selected
        ]
        complete = complete and len(rows) <= 25
        for row in rows[:25]:
            item = project(row, "number", "title", "status", "due_date", "created_at")
            if row.get("customer_id") and has_perm(user, Perm.CUSTOMER_READ.value):
                customer = await db.customers.find_one(
                    {"tenant_id": tenant, "id": row["customer_id"]}, {"_id": 0}
                )
                if customer:
                    item["customer_id"] = customer["id"]
                    refs.append(reference("customer", customer))
            items.append(item)
            refs.append(reference("order", row))
    elif name == "work_order_status":
        rows = [
            r
            async for r in db.work_orders.find(_filter(user, args), {"_id": 0})
            .sort("updated_at", -1)
            .limit(26)
        ]
        complete = len(rows) <= 25
        for row in rows[:25]:
            stages = await production_stage_service.list_work_order_stages(
                tenant_id=tenant, work_order_id=row["id"]
            )
            if isinstance(stages, dict):
                stages = stages.get("stages", [])
            items.append(
                {
                    **project(row, "number", "status", "due_date"),
                    "stages": [
                        project(
                            s,
                            "stage_name",
                            "status",
                            "due_at",
                            "waiting_reason",
                            "block_reason",
                        )
                        for s in stages[:30]
                    ],
                }
            )
            refs.append(reference("work_order", row))
        missing.append(
            "Only recorded stage facts are available; absence of a blocker reason does not prove no delay."
        )
    elif name == "invoices":
        filt = {**_filter(user, args), **related_filter, "document_status": "issued"}
        if args.customer_id:
            if not has_perm(user, Perm.CUSTOMER_READ.value):
                raise ToolError("Customer lookup is not permitted")
            customer = await db.customers.find_one(
                {"tenant_id": tenant, "id": args.customer_id}, {"_id": 0}
            )
            if not customer:
                raise ToolError("Customer is missing or inaccessible")
            filt["customer_id"] = customer["id"]
            refs.append(reference("customer", customer))
        if args.invoice_filter == "overdue":
            # Coarse offset-tolerant bound; the local calendar date below is authoritative.
            filt["due_date"] = {
                "$lt": (today + timedelta(days=2)).isoformat(),
                "$nin": [None, ""],
            }
        sort_key, direction = (
            ("created_at", -1) if args.invoice_filter == "latest" else ("due_date", 1)
        )
        rows = [
            r
            async for r in db.invoices.find(filt, {"_id": 0})
            .sort(sort_key, direction)
            .limit(101)
        ]
        complete = len(rows) <= 100
        for row in rows[:100]:
            due = _local_date(row.get("due_date"), zone)
            if args.invoice_filter == "overdue" and (due is None or due >= today):
                continue
            money = await invoice_reconciliation.read_financials(
                tenant_id=tenant, invoice=row
            )
            if money["balance_due_cents"] <= 0 and args.invoice_filter != "latest":
                continue
            if len(items) >= 25:
                complete = False
                break
            items.append(
                {
                    **project(row, "number", "due_date", "total_cents"),
                    **money,
                    "overdue": due < today if due is not None else None,
                }
            )
            refs.append(reference("invoice", row))
            if args.invoice_filter == "latest":
                break
        missing.append(
            "Missing due dates are unknown. Amounts are per invoice, not total shop receivables."
        )
    elif name == "quote_followups":
        rows = [
            r
            async for r in db.quotes.find(
                {**_filter(user, args), "status": {"$in": ["sent", "viewed"]}},
                {"_id": 0},
            )
            .sort("updated_at", 1)
            .limit(26)
        ]
        complete = len(rows) <= 25
        for row in rows[:25]:
            items.append(project(row, "number", "status", "updated_at", "expires_at"))
            refs.append(reference("quote", row))
        missing.append(
            "Candidates are sent/viewed Quotes; last customer contact and conversion probability are not inferred."
        )
    elif name == "tasks":
        rows = [
            r
            async for r in db.tasks.find(
                {
                    "tenant_id": tenant,
                    "archived_at": None,
                    "status": {"$nin": ["completed", "canceled"]},
                    "due_at": {
                        "$gte": (selected - timedelta(days=1)).isoformat(),
                        "$lt": (selected + timedelta(days=2)).isoformat(),
                    },
                },
                {"_id": 0},
            )
            .sort("due_at", 1)
            .limit(101)
        ]
        complete = len(rows) <= 100
        for row in rows[:100]:
            if _local_date(row.get("due_at"), zone) == selected:
                items.append(project(row, "title", "status", "due_at"))
                refs.append(reference("task", row))
    else:
        start = datetime.combine(selected, time.min, zone)
        if args.schedule_window == "next_30_days":
            start = utc_now().astimezone(zone)
        end = (
            start + timedelta(days=30)
            if args.schedule_window == "next_30_days"
            else datetime.combine(selected + timedelta(days=1), time.min, zone)
        )
        result = await calendar_service.list_events(
            tenant_id=tenant,
            start_at=start.isoformat(),
            end_at=end.isoformat(),
            window_first=True,
            exclude_statuses={"canceled"},
            limit=100,
        )
        rows = result.get("items", [])
        complete = len(rows) < 100 and result.get("total", len(rows)) <= len(rows)
        for row in rows:
            if (
                args.query
                and args.query.casefold() not in str(row.get("title", "")).casefold()
            ):
                continue
            source = row.get("source_type")
            if source == "task" and not has_perm(user, Perm.TASK_READ.value):
                continue
            if source in {"production_stage", "work_order"} and not has_perm(
                user, Perm.WORK_ORDER_READ.value
            ):
                continue
            if not _event_visible(user, row):
                continue
            # Projected events link to a canonical source rather than a nonexistent calendar row.
            kind = {"task": "task", "production_stage": "work_order"}.get(
                source, "calendar_event"
            )
            source_id = (
                row.get("work_order_id")
                if kind == "work_order"
                else row.get("source_id")
            )
            ref_row = {**row, "id": source_id or row["id"]}
            if args.record_id and ref_row["id"] != args.record_id:
                continue
            ref = reference(kind, ref_row)
            if await reference_allowed(user, ref):
                items.append(
                    project(row, "title", "start_at", "end_at", "status", "source_type")
                )
                refs.append(ref)
    return {
        "tool": name,
        "resolution_status": (
            "discussed"
            if raw_args.get("record_id") == "discussed"
            else (
                "exact_display_number"
                if raw_args.get("record_id") and raw_args["record_id"] != args.record_id
                else "canonical_or_search"
            )
        ),
        "items": items,
        "sources": refs,
        "complete": complete,
        "timezone": timezone_name,
        "date": selected.isoformat(),
        "missing_data": missing,
        "notice": "Bounded results only; do not infer overall totals or missing facts.",
    }
