"""Initial setup orchestration. Owner delivery is the information packet (webstore_information_packet)."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_assignment_access import create_assignment
from .webstore_setup_questionnaires import bind_questionnaire_templates
from .webstore_setup_progress import _refresh_setup_state


async def initialize_store_setup(user: dict, store: dict, owner: dict, fields: dict[str, Any]) -> None:
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {
            "$set": {
                "setup_state": "not_started",
                "setup_profile": fields.get("setup_profile") or {},
                "setup_requirements": fields.get("setup_requirements") or {},
                "store_settings": default_store_settings(store.get("store_type"), fields.get("store_settings") or store.get("store_settings") or {}),
                "target_launch_at": fields.get("target_launch_at"),
                "event_start_at": fields.get("event_start_at"),
                "event_location": fields.get("event_location"),
                "creation_idempotency_key": fields.get("idempotency_key"),
                "updated_at": _now_iso(),
            }
        },
    )
    primary = await create_assignment(
        user,
        store["id"],
        {"role": "owner", "owner_id": owner["id"], "email": owner["email"], "name": owner.get("name"), "is_primary_owner": True},
        primary=True,
        send=bool(fields.get("send_owner_invitation", True)),
    )
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {"$set": {"primary_owner_assignment_id": primary["assignment"]["id"], "updated_at": _now_iso()}},
    )
    for raw in fields.get("additional_owner_emails") or []:
        await create_assignment(user, store["id"], {"role": "owner", "email": raw, "name": raw}, send=True)
    for raw in fields.get("manager_emails") or []:
        await create_assignment(user, store["id"], {"role": "manager", "email": raw, "name": raw}, send=True)
    await bind_questionnaire_templates(user, store["id"])
    await _refresh_setup_state(store["tenant_id"], store["id"])

__all__ = ['initialize_store_setup']
