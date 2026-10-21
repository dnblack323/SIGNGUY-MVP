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


async def memories(user: dict, limit: int = 10) -> list[dict]:
    rows = [
        r
        async for r in db.assistant_memory_entries.find(
            {"tenant_id": user["tenant_id"], "user_id": user["id"], "status": "active"},
            {"_id": 0},
        )
        .sort("updated_at", -1)
        .limit(limit)
    ]
    return [row for row in rows if await memory_visible(user, row)]


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
    return [row for row in reversed(rows) if await visible(user, row)]
