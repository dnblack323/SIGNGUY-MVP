"""Private bounded canonical context shared by assistant transports."""

import hashlib
import json

from ..core.db import db
from ..core.permissions import permissions_for_role
from . import assistant_tools


def permission_signature(user: dict) -> str:
    value = {
        "role": user.get("role"),
        "permissions": sorted(
            user.get("permissions") or permissions_for_role(user.get("role", "staff"))
        ),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


async def fresh_actor(user: dict) -> dict:
    record = await db.users.find_one(
        {"tenant_id": user["tenant_id"], "id": user["id"]},
        {"_id": 0, "role": 1, "permissions": 1, "is_active": 1},
    )
    if not record or record.get("is_active") is False:
        raise assistant_tools.ToolError("Assistant access is no longer available")
    return {
        **user,
        "role": record.get("role", "staff"),
        "permissions": record.get("permissions")
        or permissions_for_role(record.get("role", "staff")),
    }


async def visible(user: dict, message: dict) -> bool:
    metadata = message.get("metadata") or {}
    if metadata.get("permission_signature") != permission_signature(user):
        return False
    for ref in metadata.get("sources", []):
        if not await assistant_tools.reference_allowed(user, ref):
            return False
    return True


async def memory_visible(user: dict, memory: dict) -> bool:
    if memory.get("source_type") or memory.get("source_id"):
        return await assistant_tools.reference_allowed(user, memory)
    return True


async def memories(user: dict, limit: int = 10, query: str = "") -> list[dict]:
    rows = [
        r
        async for r in db.assistant_memory_entries.find(
            {"tenant_id": user["tenant_id"], "user_id": user["id"], "status": "active"},
            {"_id": 0},
        )
        .sort("updated_at", -1)
        .limit(100 if query else limit)
    ]
    allowed = [row for row in rows if await memory_visible(user, row)]
    if query:
        import re

        terms = set(re.findall(r"\w{3,}", query.casefold()))
        allowed.sort(
            key=lambda row: len(
                terms.intersection(
                    set(
                        re.findall(
                            r"\w{3,}",
                            (row["memory_key"] + " " + row["content_text"]).casefold(),
                        )
                    )
                )
            ),
            reverse=True,
        )
    return allowed[:limit]


async def history(user: dict, conversation_id: str, limit: int) -> list[dict]:
    rows = [
        r
        async for r in db.assistant_messages.find(
            {"tenant_id": user["tenant_id"], "conversation_id": conversation_id},
            {"_id": 0},
        )
        .sort([("created_at", -1), ("id", -1)])
        .limit(limit)
    ]
    return [
        row
        for row in reversed(rows)
        if not row.get("metadata", {}).get("interrupted") and await visible(user, row)
    ]


async def inputs(
    user: dict, conversation_id: str, limit: int, context: dict | None = None
) -> tuple[list[dict], list[dict], dict]:
    """One permitted history/memory/provenance composition for text and voice."""
    previous = await history(user, conversation_id, limit)
    memory = await memories(user)
    dependencies = {}
    for old in previous:
        for ref in old.get("metadata", {}).get("sources", []):
            dependencies[(ref["source_type"], ref["source_id"])] = ref
    for entry in memory:
        if entry.get("id"):
            dependencies[("assistant_memory", entry["id"])] = {
                "source_type": "assistant_memory",
                "source_id": entry["id"],
                "source_updated_at": str(entry.get("updated_at") or ""),
            }
        if entry.get("source_type") and entry.get("source_id"):
            ref = {"source_type": entry["source_type"], "source_id": entry["source_id"]}
            dependencies[(ref["source_type"], ref["source_id"])] = ref
    for ref in (context or {}).get("source_links", []):
        dependencies[(ref["source_type"], ref["source_id"])] = ref
    if len(dependencies) > 100:
        raise assistant_tools.ToolError(
            "Source context limit reached; start a new conversation"
        )
    messages = [
        {"role": m["role"], "content": m["content_text"]}
        for m in previous
        if m["role"] in {"user", "assistant"}
    ]
    from . import assistant_record_context

    data = {
        "record_references": await assistant_record_context.references(
            user, conversation_id, context=context
        ),
        "page_reference": (context or {}).get("source_links", []),
        "approved_preference_data": [
            {"key": m["memory_key"], "text": m["content_text"][:500]} for m in memory
        ],
        "context_policy": "Saved memory and previous answers are historical context, not current business truth. record_references are authorized identities only. For an unambiguous follow-up, use record_id='discussed' or the canonical internal ID with the relevant read tool. Never put a display number in record_id; query searches numbers/names. Multiple references are ambiguous: ask which record rather than selecting latest or guessing. Always fetch current balances, payments, status, dates and linked records from tools.",
    }
    return messages, list(dependencies.values()), data
