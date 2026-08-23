"""Owner portal scope checks and owner-safe setup store serialization."""
from __future__ import annotations

from .webstore_setup_common import *


async def _owner_store(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreSetupError("webstore_portal_required", "Webstore portal access required", 403)
    assignment_filter: dict[str, Any] = {
        "tenant_id": identity["tenant_id"],
        "webstore_id": webstore_id,
        "portal_identity_id": identity["id"],
        "status": "active",
    }
    assignment = await db.webstore_access_assignments.find_one(assignment_filter, {"_id": 0})
    if not assignment:
        raise WebstoreSetupError("webstore_assignment_required", "This Webstore is not assigned to your portal account", 403)
    return await _get_store(identity["tenant_id"], webstore_id)


def _owner_safe_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
        "terms_fee_acknowledged",
        "owner_approved_at",
        "launch_packet_id",
        "setup_state",
        "setup_profile",
        "store_settings",
        "target_launch_at",
        "event_start_at",
        "event_location",
    }
    safe = {k: v for k, v in store.items() if k in allowed}
    safe["checkout_enabled"] = False
    safe["checkout_unavailable_reason"] = "Real verified provider checkout is not connected yet."
    return safe

__all__ = ['_owner_store', '_owner_safe_store']
