"""Setup progress aggregation and setup-state derivation."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_portal_scope import _owner_store


async def setup_progress_for_staff(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    return await _setup_progress(store, staff=True)


async def setup_progress_for_portal(identity: dict, webstore_id: str) -> dict:
    store = await _owner_store(identity, webstore_id)
    return await _setup_progress(store, staff=False)


async def _setup_progress(store: dict, *, staff: bool) -> dict:
    tenant_id = store["tenant_id"]
    webstore_id = store["id"]
    invited_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "invited"}
    )
    active_owner_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "role": "owner", "status": "active"}
    )
    draft_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "draft"}
    )
    submitted_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "submitted"}
    )
    reviewed_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "reviewed"}
    )
    from .webstore_setup_files import count_active_setup_files

    file_count = await count_active_setup_files(tenant_id, webstore_id)
    state = await _derive_setup_state(store, invited_count, active_owner_count, draft_count, submitted_count, reviewed_count, file_count)
    type_requirements = evaluate_type_requirements(store)
    steps = [
        {"key": "primary_owner", "label": "Primary Store Owner assigned", "status": "complete" if active_owner_count else "blocked"},
        {"key": "invitations", "label": "Owner and manager invitations", "status": "waiting" if invited_count else "complete"},
        {"key": "questionnaire", "label": "Owner intake questionnaire", "status": "review" if submitted_count else "complete" if reviewed_count else "in_progress" if draft_count else "not_started"},
        {"key": "files", "label": "Setup files", "status": "complete" if file_count else "not_started"},
        {"key": "type_requirements", "label": f"{type_requirements['label']} requirements", "status": "complete" if type_requirements["complete"] else "blocked"},
        {"key": "staff_review", "label": "Staff setup review", "status": "complete" if reviewed_count else "not_started"},
        {"key": "branding", "label": "Branding editor", "status": "deferred"},
        {"key": "products", "label": "Product catalog buildout", "status": "deferred"},
        {"key": "stripe", "label": "Verified Stripe checkout", "status": "deferred"},
    ]
    response = {"webstore_id": webstore_id, "setup_state": state, "steps": steps, "type_requirements": type_requirements, "read_only": True}
    if staff:
        response["counts"] = {
            "invited_assignments": invited_count,
            "active_owners": active_owner_count,
            "draft_questionnaires": draft_count,
            "submitted_questionnaires": submitted_count,
            "reviewed_questionnaires": reviewed_count,
            "setup_files": file_count,
        }
    return response


async def _derive_setup_state(store: dict, invited: int, owners: int, drafts: int, submitted: int, reviewed: int, files: int) -> str:
    if owners <= 0:
        state = "blocked"
    elif invited:
        state = "invitation_pending"
    elif submitted:
        state = "staff_review"
    elif reviewed and files:
        state = "setup_complete"
    elif reviewed or files:
        state = "setup_in_progress"
    elif drafts:
        state = "questionnaire_in_progress"
    else:
        state = "not_started"
    return state


async def compute_setup_state(store: dict) -> str:
    """Setup state is derived on read and never stored (D3-2)."""
    return (await _setup_progress(store, staff=False))["setup_state"]


async def _refresh_next_action(tenant_id: str, webstore_id: str) -> None:
    """Called after setup changes (never on reads): keeps the next-action task in step."""
    from .webstore_next_action import sync_next_action_side_effects

    await sync_next_action_side_effects(tenant_id, webstore_id)

__all__ = ['setup_progress_for_staff', 'setup_progress_for_portal', '_setup_progress', '_derive_setup_state', 'compute_setup_state', '_refresh_next_action']
