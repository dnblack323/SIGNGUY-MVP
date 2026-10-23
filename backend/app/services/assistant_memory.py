"""Explicitly approved private memory in the existing canonical collection."""

import re
import uuid

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.business_assistant import AssistantMemoryEntry
from .assistant_actions import actor, error, scope
from . import assistant_context, assistant_tools


async def suggestion(user, fields):
    """Validate a conversational suggestion without writing approved memory."""
    from pydantic import BaseModel, ConfigDict, Field
    from typing import Literal

    class Preview(BaseModel):
        model_config = ConfigDict(extra="forbid")
        memory_key: str = Field(min_length=1, max_length=80, pattern=r"^[\w .:-]+$")
        content_text: str = Field(min_length=1, max_length=1000)
        source_type: (
            Literal["customer", "order", "quote", "invoice", "work_order", "task"]
            | None
        ) = None
        source_id: str | None = Field(default=None, max_length=160)

    user = await actor(user)
    preview = Preview.model_validate(fields).model_dump()
    refs = []
    if preview["source_type"] or preview["source_id"]:
        ref = {"source_type": preview["source_type"], "source_id": preview["source_id"]}
        if not await assistant_tools.reference_allowed(user, ref):
            raise assistant_tools.ToolError("Choose an accessible memory source")
        refs.append({**ref, "source_label": f"Memory source: {preview['source_type']}"})
    if any(
        word in preview["content_text"].casefold()
        for word in ("api key", "password", "secret")
    ):
        raise assistant_tools.ToolError("Secrets cannot be proposed as memory")
    return {
        "memory_preview": preview,
        "sources": refs,
        "notice": "Suggestion only, not saved. Review and explicitly approve in the memory editor.",
    }


async def save(user, fields, memory_id=None):
    from .business_assistant import _audit

    user = await actor(user)
    key = str(fields.get("memory_key") or "").strip().casefold()
    content = str(fields.get("content_text") or "").strip()
    if not re.fullmatch(r"[\w .:-]{1,80}", key) or not 1 <= len(content) <= 1000:
        raise error(
            "invalid_memory",
            "Use a stable memory topic (1–80 characters) and 1–1000 characters of approved context",
            422,
        )
    if any(word in content.casefold() for word in ("api key", "password", "secret")):
        raise error(
            "secret_memory_rejected",
            "Secrets and credentials cannot be saved as assistant memory",
            400,
        )
    existing = await db.assistant_memory_entries.find_one(
        {
            **scope(user),
            **(
                {"id": memory_id, "status": "active"}
                if memory_id
                else {"memory_key": key, "status": "active"}
            ),
        },
        {"_id": 0},
    )
    if memory_id and (
        not existing or not await assistant_context.memory_visible(user, existing)
    ):
        raise error("memory_not_found", "Saved memory not found", 404)
    if existing and await db.assistant_memory_entries.find_one(
        {
            **scope(user),
            "memory_key": key,
            "status": "active",
            "id": {"$ne": existing["id"]},
        }
    ):
        raise error(
            "memory_topic_exists",
            "This topic already has a saved entry; edit that entry instead",
        )
    source_type = fields.get("source_type", (existing or {}).get("source_type"))
    source_id = fields.get("source_id", (existing or {}).get("source_id"))
    if source_type or source_id:
        if (
            source_type
            not in {"customer", "order", "quote", "invoice", "work_order", "task"}
            or not source_id
            or not await assistant_tools.reference_allowed(
                user, {"source_type": source_type, "source_id": source_id}
            )
        ):
            raise error(
                "memory_source_denied", "Choose an accessible source record", 403
            )
    normalized = " ".join(content.casefold().split())
    duplicate = await db.assistant_memory_entries.find_one(
        {
            **scope(user),
            "status": "active",
            "normalized_content": normalized,
            "source_type": source_type,
            "source_id": source_id,
        },
        {"_id": 0},
    )
    if duplicate and (not existing or duplicate["id"] != existing["id"]):
        return serialize_doc(duplicate)
    updates = {
        "memory_key": key,
        "content_text": content,
        "normalized_content": normalized,
        "source_type": source_type,
        "source_id": source_id,
        "visibility": "user",
        "status": "active",
        "updated_at": utc_now().isoformat(),
        "approval_source": "explicit_user_interface",
    }
    if existing:
        expected = fields.get("expected_updated_at") or existing.get("updated_at")
        changed = await db.assistant_memory_entries.update_one(
            {
                **scope(user),
                "id": existing["id"],
                "status": "active",
                "updated_at": expected,
            },
            {"$set": updates},
        )
        if not changed.matched_count:
            raise error(
                "memory_changed",
                "This memory changed; reload it before saving your correction",
            )
        result_id = existing["id"]
    else:
        result_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, f"memory:{user['tenant_id']}:{user['id']}:{key}"
            )
        )
        occupied = await db.assistant_memory_entries.find_one(
            {**scope(user), "id": result_id, "status": "active"}, {"_id": 0}
        )
        if occupied and occupied.get("memory_key") != key:
            # Renaming a topic must not prevent deliberate reuse of its old name.
            result_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memory:{user['tenant_id']}:{user['id']}:{key}:{occupied['memory_key']}",
                )
            )
        doc = AssistantMemoryEntry(
            id=result_id, **scope(user), memory_key=key, content_text=content
        ).model_dump()
        try:
            await db.assistant_memory_entries.update_one(
                {**scope(user), "id": result_id, "status": {"$ne": "active"}},
                {
                    "$set": updates,
                    "$setOnInsert": {
                        k: v
                        for k, v in prepare_for_mongo(doc).items()
                        if k not in updates
                    },
                },
                upsert=True,
            )
        except DuplicateKeyError as exc:
            raise error(
                "memory_changed",
                "A memory for this topic was saved concurrently; reload it",
            ) from exc
    await _audit(
        user,
        "assistant.memory_saved",
        "assistant_memory_entry",
        result_id,
        "Private memory explicitly saved or corrected",
    )
    return serialize_doc(
        await db.assistant_memory_entries.find_one(
            {**scope(user), "id": result_id}, {"_id": 0}
        )
    )
