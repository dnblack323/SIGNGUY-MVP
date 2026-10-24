"""Bounded user-private conversation diagnostics. No raw selectors or record values."""

import hashlib
import hmac

from ..core.config import get_settings
from ..core.db import db


async def record(user, name, args, *, conversation_id, outcome, result=None):
    from . import assistant_tools

    if not conversation_id:
        return
    raw = args if isinstance(args, dict) else {}
    secret = get_settings().jwt_secret.encode()
    fingerprints = {
        key: hmac.new(
            secret,
            (user["tenant_id"] + ":" + str(raw[key])[:4000]).encode(),
            hashlib.sha256,
        ).hexdigest()
        for key in ("record_id", "customer_id", "query")
        if raw.get(key)
    }
    metadata = {
        "tool": (
            name
            if name in assistant_tools.PERMISSIONS
            or name in {"recall_memory", "propose_memory", "propose_action"}
            else "unknown"
        ),
        "argument_fields": sorted(
            k for k in raw if k in assistant_tools.ReadArgs.model_fields
        ),
        "selector_fingerprints": fingerprints,
        "discussed_reference": raw.get("record_id") == "discussed",
        "outcome": outcome,
        "resolution_status": (result or {}).get("resolution_status"),
        "result_count": len((result or {}).get("items", [])),
        "source_count": len((result or {}).get("sources", [])),
    }
    await db.assistant_conversations.update_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": conversation_id},
        {"$push": {"metadata.tool_diagnostics": {"$each": [metadata], "$slice": -20}}},
    )
