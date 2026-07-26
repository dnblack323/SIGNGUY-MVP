"""Safe external user serialization helpers."""
from __future__ import annotations

from typing import Any

from .time_utils import serialize_doc


EXTERNAL_USER_EXCLUDE_FIELDS = {
    "password_hash",
    "platform_creator_pending_audit",
}

EXTERNAL_USER_PROJECTION = {
    "_id": 0,
    **{field: 0 for field in EXTERNAL_USER_EXCLUDE_FIELDS},
}


def serialize_external_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if user is None:
        return None
    out = serialize_doc(dict(user))
    for field in EXTERNAL_USER_EXCLUDE_FIELDS:
        out.pop(field, None)
    return out
