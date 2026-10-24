"""Current record identity, never a cache of business facts. Shared by text/voice."""

from ..core.db import db

KINDS = {
    "find_customers": "customer",
    "customer_history": "customer",
    "recent_orders": "order",
    "work_order_status": "work_order",
    "invoices": "invoice",
    "quote_followups": "quote",
    "tasks": "task",
    "shop_schedule": "calendar_event",
}


def focus(result):
    sources = result.get("sources", [])
    primary = [r for r in sources if r["source_type"] == KINDS.get(result.get("tool"))]
    return primary or sources


async def references(user, conversation_id, context=None):
    from . import assistant_context, assistant_tools

    conversation = await db.assistant_conversations.find_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": conversation_id},
        {"_id": 0, "id": 1},
    )
    if not conversation:
        raise assistant_tools.ToolError("Conversation is unavailable")
    selected = (context or {}).get("source_links", [])
    if not selected:
        message = await db.assistant_messages.find_one(
            {
                "tenant_id": user["tenant_id"],
                "conversation_id": conversation_id,
                "role": "assistant",
                "metadata.interrupted": {"$ne": True},
            },
            {"_id": 0},
            sort=[("created_at", -1), ("id", -1)],
        )
        if message and await assistant_context.visible(user, message):
            metadata = message.get("metadata") or {}
            selected = metadata.get("record_references", metadata.get("sources", []))
    result = []
    seen = set()
    for ref in selected[:100]:
        kind, ident = ref.get("source_type"), ref.get("source_id")
        target = assistant_tools.TARGETS.get(kind)
        if not target or (kind, ident) in seen:
            continue
        if not await assistant_tools.reference_allowed(user, ref):
            continue
        row = await db[target[0]].find_one(
            {"tenant_id": user["tenant_id"], "id": ident}, {"_id": 0}
        )
        if row:
            # Label is fresh application data; no balances/statuses in continuity state.
            result.append(assistant_tools.reference(kind, row))
            seen.add((kind, ident))
    return result


class ClarificationRequired(Exception):
    pass


async def resolve(user, name, args, refs, question=None):
    """Resolve 'discussed' or a misplaced exact display number, without guessing."""
    from . import assistant_tools

    kind = KINDS.get(name)
    extra = {}
    if question and kind:
        import re

        candidates = [
            r
            for r in refs
            if r["source_type"] == kind
            and await assistant_tools.reference_allowed(user, r)
        ]
        if len(candidates) > 1:
            named = any(
                re.search(
                    r"(?<!\w)"
                    + re.escape(str(r.get("source_label") or r["source_id"]))
                    + r"(?!\w)",
                    question,
                    re.IGNORECASE,
                )
                for r in candidates
            )
            selects_one = args.record_id or (
                args.query
                and any(
                    args.query.casefold()
                    in {
                        str(r.get("source_label", "")).casefold(),
                        r["source_id"].casefold(),
                    }
                    for r in candidates
                )
            )
            if selects_one and not named:
                raise ClarificationRequired("ambiguous")
    if not kind or not args.record_id:
        return args, extra
    target = assistant_tools.TARGETS[kind]
    tenant = user["tenant_id"]
    if args.record_id == "discussed":
        allowed = [r for r in refs if await assistant_tools.reference_allowed(user, r)]
        direct = [r for r in allowed if r["source_type"] == kind]
        if direct:
            if len(direct) != 1:
                raise ClarificationRequired("ambiguous")
            args = args.model_copy(
                update={"record_id": direct[0]["source_id"], "query": None}
            )
        else:
            anchors = [
                r
                for r in allowed
                if r["source_type"] in {"customer", "order", "invoice"}
            ]
            if len(anchors) != 1:
                raise ClarificationRequired("ambiguous_or_unavailable")
            anchor = anchors[0]
            row = await db[assistant_tools.TARGETS[anchor["source_type"]][0]].find_one(
                {"tenant_id": tenant, "id": anchor["source_id"]}, {"_id": 0}
            )
            if not row:
                raise ClarificationRequired("unavailable")
            if anchor["source_type"] == "customer" and kind in {"order", "invoice"}:
                extra["customer_id"] = row["id"]
                args = args.model_copy(update={"record_id": None, "query": None})
            elif anchor["source_type"] == "order" and kind == "invoice":
                extra["order_id"] = row["id"]
                args = args.model_copy(update={"record_id": None, "query": None})
            elif kind in {"customer", "order"} and row.get(kind + "_id"):
                args = args.model_copy(
                    update={"record_id": row[kind + "_id"], "query": None}
                )
            else:
                raise ClarificationRequired("unsupported_relation")
    if (
        args.customer_id
        and extra.get("customer_id")
        and args.customer_id != extra["customer_id"]
    ):
        raise ClarificationRequired("conflicting_reference")
    if args.record_id:
        exact = await db[target[0]].find_one(
            {"tenant_id": tenant, "id": args.record_id}, {"_id": 0}
        )
        if exact and await assistant_tools.reference_allowed(
            user, {"source_type": kind, "source_id": exact["id"]}
        ):
            return args, extra
        # Exact number/name fallback only. Never fuzzy-select a similar or foreign record.
        field = "name" if kind == "customer" else "number"
        values = [args.record_id]
        if args.record_id.isdecimal() and len(args.record_id) <= 15:
            values.append(int(args.record_id))
        matches = (
            await db[target[0]]
            .find({"tenant_id": tenant, field: {"$in": values}}, {"_id": 0})
            .limit(2)
            .to_list(length=2)
        )
        matches = [
            r
            for r in matches
            if await assistant_tools.reference_allowed(
                user, {"source_type": kind, "source_id": r["id"]}
            )
        ]
        if len(matches) != 1:
            raise ClarificationRequired("ambiguous" if matches else "unavailable")
        args = args.model_copy(update={"record_id": matches[0]["id"], "query": None})
    return args, extra
