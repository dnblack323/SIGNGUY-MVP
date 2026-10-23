"""Existing Assistant proposals: shared validation and explicit-interface execution."""

from datetime import datetime, time, timedelta
import hashlib
import json
import re
import uuid
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from . import assistant_context, assistant_tools
from .time_period_utils import get_tenant_timezone

CONTROLLED = {"internal_task", "internal_note", "email_draft"}


def error(code, detail, status=409):
    from .business_assistant import BusinessAssistantError

    return BusinessAssistantError(code, detail, status)


async def actor(user):
    from .business_assistant import assert_assistant_access

    try:
        current = await assistant_context.fresh_actor(user)
    except assistant_tools.ToolError as exc:
        raise error("assistant_access_changed", str(exc), 403) from exc
    await assert_assistant_access(current)
    return current


def scope(user):
    return {"tenant_id": user["tenant_id"], "user_id": user["id"]}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=8000)
    subject: str = Field(default="", max_length=160)
    priority: str = Field(default="normal", pattern="^(low|normal|high|rush)$")
    due_at: str | None = Field(default=None, max_length=80)
    timezone: str = ""


def due_date(value, timezone_name):
    if not value:
        return None
    zone = ZoneInfo(timezone_name)
    if value.casefold() in {"today", "tomorrow"}:
        day = utc_now().astimezone(zone).date() + timedelta(
            days=value.casefold() == "tomorrow"
        )
        return datetime.combine(day, time(9), zone).isoformat()
    try:
        if len(value) == 10:
            return datetime.combine(
                datetime.fromisoformat(value).date(), time(9), zone
            ).isoformat()
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)).isoformat()
    except ValueError as exc:
        raise error(
            "invalid_task_date",
            "Clarify the task date/time; use today, tomorrow or an ISO date",
            422,
        ) from exc


def payload_for(kind, fields, timezone_name):
    raw = fields.get("editable_payload") or fields.get("preview") or fields
    data = {k: raw[k] for k in Payload.model_fields if k in raw}
    data["title"] = data.get("title") or fields.get("title") or "Assistant follow-up"
    data["title"] = data["title"].strip()
    data["body"] = (
        data.get("body") or raw.get("description") or fields.get("summary") or ""
    )
    data["timezone"] = timezone_name
    if kind == "email_draft":
        data["subject"] = data.get("subject") or data["title"]
    try:
        result = Payload.model_validate(data).model_dump()
    except ValueError as exc:
        raise error(
            "invalid_action_payload",
            "Use a valid title, bounded content and supported task priority",
            422,
        ) from exc
    result["due_at"] = due_date(result["due_at"], timezone_name)
    if kind in {"internal_note", "email_draft"} and not result["body"].strip():
        raise error(
            "action_content_required",
            "Clarify the exact note or email body before proposing it",
            422,
        )
    return result


async def targets(user, refs, kind, *, previous=False):
    from . import business_assistant as svc

    if len(refs) > 3:
        raise error(
            "action_target_limit",
            "Choose one Customer/Order and, for a follow-up, its Quote",
            422,
        )
    if kind == "internal_note" and (
        len(refs) != 1 or refs[0].get("type") not in {"customer", "order"}
    ):
        raise error(
            "note_target_required",
            "Choose the exact Customer or Order for this permanent note",
            422,
        )
    if kind == "email_draft" and not refs:
        raise error(
            "draft_target_required",
            "Choose the Customer or Quote for this follow-up draft",
            422,
        )
    results = []
    for ref in refs:
        target = svc.CONTEXT_TARGETS.get(ref.get("type"))
        if not target or not ref.get("id"):
            raise error(
                "invalid_action_target",
                "Choose a supported, accessible application record",
                422,
            )
        if kind in CONTROLLED and ref["type"] not in {"customer", "order", "quote"}:
            raise error(
                "action_target_not_supported",
                "This V1 action supports Customer, Order and Quote references",
                422,
            )
        svc._require_perm(user, target["read_perm"])
        row = await db[target["collection"]].find_one(
            {"tenant_id": user["tenant_id"], "id": ref["id"]}, {"_id": 0}
        )
        if not row:
            raise error(
                "action_source_missing", "The action source is missing or inaccessible"
            )
        fingerprint = digest(row)
        if (
            previous
            and ref.get("source_fingerprint")
            and fingerprint != ref["source_fingerprint"]
        ):
            raise error(
                "proposal_stale", "The source record changed; review a new proposal"
            )
        results.append(
            {
                "type": ref["type"],
                "id": ref["id"],
                "source_updated_at": str(row.get("updated_at") or ""),
                "source_fingerprint": fingerprint,
                "label": str(
                    row.get("name")
                    or row.get("title")
                    or row.get("number")
                    or ref["type"]
                ),
                "route": target["route"].format(id=ref["id"]),
            }
        )
    return results


async def propose(user, fields):
    from . import business_assistant as svc

    user = await actor(user)
    kind = fields.get("action_type")
    if kind not in svc.ACTION_PERMISSIONS:
        convo = await svc._conversation(user, fields.get("conversation_id"))
        return await svc._save_proposal(
            user,
            convo["id"],
            "owner",
            fields,
            status="unsupported",
            warnings=["Unsupported action. No data changed."],
            required_permissions=[],
        )
    for perm in svc.ACTION_PERMISSIONS[kind]:
        svc._require_perm(user, perm)
    convo = await svc._conversation(
        user, fields.get("conversation_id"), mode=fields.get("mode")
    )
    shop_timezone = await get_tenant_timezone(user["tenant_id"])
    refs = await targets(user, fields.get("target_refs") or [], kind)
    payload = (
        payload_for(kind, fields, shop_timezone)
        if kind in CONTROLLED
        else fields.get("editable_payload")
        or fields.get("preview")
        or svc._default_preview(kind, fields)
    )
    key = str(fields.get("idempotency_key") or uuid.uuid4().hex)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", key):
        raise error("invalid_proposal_key", "Use a bounded stable proposal key", 422)
    fingerprint = digest(
        {"kind": kind, "payload": payload, "refs": refs, "conversation": convo["id"]}
    )
    ledger_key = digest({**scope(user), "key": key})
    existing = await db.assistant_action_proposals.find_one(
        {**scope(user), "idempotency_key": ledger_key}, {"_id": 0}
    )
    if existing:
        if existing.get("input_fingerprint") != fingerprint:
            raise error(
                "proposal_key_conflict",
                "This proposal key belongs to different content",
            )
        return await get(user, existing["id"])
    proposal = await svc._save_proposal(
        user,
        convo["id"],
        svc._mode_key(fields.get("mode")),
        {
            **fields,
            "idempotency_key": ledger_key,
            "input_fingerprint": fingerprint,
            "permission_signature": assistant_context.permission_signature(user),
            "target_refs": refs,
            "preview": payload,
            "editable_payload": payload,
            "expires_at": (utc_now() + timedelta(minutes=30)).isoformat(),
        },
        status="proposed",
        warnings=[
            "Review the exact content and destination. Nothing is created until interface confirmation."
        ]
        + (["Draft only; never sent automatically."] if kind == "email_draft" else []),
        required_permissions=svc.ACTION_PERMISSIONS[kind],
    )
    await svc._audit(
        user,
        "assistant.action_proposed",
        "assistant_action_proposal",
        proposal["id"],
        "Assistant proposal ready for interface review",
    )
    return await get(user, proposal["id"])


async def get(user, proposal_id):
    from . import business_assistant as svc

    user = await actor(user)
    proposal = await svc._proposal(user, proposal_id)
    await svc._conversation(user, proposal["conversation_id"])
    for perm in svc.ACTION_PERMISSIONS.get(proposal["action_type"], []):
        svc._require_perm(user, perm)
    await targets(user, proposal.get("target_refs") or [], proposal["action_type"])
    if proposal.get("permission_signature") and proposal[
        "permission_signature"
    ] != assistant_context.permission_signature(user):
        raise error(
            "proposal_permissions_changed",
            "Permissions changed; request a fresh proposal",
            403,
        )
    return proposal


async def validate(user, proposal):
    if proposal.get("expires_at") and proposal["expires_at"] <= utc_now().isoformat():
        raise error(
            "proposal_expired", "The preview expired; request and review a new proposal"
        )
    await targets(
        user, proposal.get("target_refs") or [], proposal["action_type"], previous=True
    )


async def edit(user, proposal_id, fields):
    user = await actor(user)
    proposal = await get(user, proposal_id)
    await validate(user, proposal)
    if proposal["status"] not in {"proposed", "edited", "confirmed"}:
        raise error("proposal_not_editable", "Only pending proposals can be edited")
    expected = fields.get("revision")
    if expected is not None and expected != proposal.get("revision", 1):
        raise error(
            "proposal_revision_conflict",
            "The preview changed; reload it before editing",
        )
    shop_timezone = await get_tenant_timezone(user["tenant_id"])
    payload = (
        payload_for(proposal["action_type"], {**proposal, **fields}, shop_timezone)
        if proposal["action_type"] in CONTROLLED
        else fields.get("editable_payload") or proposal["editable_payload"]
    )
    changed = await db.assistant_action_proposals.update_one(
        {
            **scope(user),
            "id": proposal_id,
            "status": proposal["status"],
            "revision": proposal.get("revision", 1),
        },
        {
            "$set": {
                "editable_payload": payload,
                "preview": payload,
                "status": "edited",
                "updated_at": utc_now().isoformat(),
                "confirmed_at": None,
                "confirmed_by_user_id": None,
            },
            "$inc": {"revision": 1},
        },
    )
    if not changed.matched_count:
        raise error("proposal_changed", "The proposal changed; reload it")
    return await get(user, proposal_id)


async def confirm(user, proposal_id, revision=None):
    user = await actor(user)
    proposal = await get(user, proposal_id)
    await validate(user, proposal)
    if proposal["status"] == "confirmed" and revision == proposal.get("revision"):
        return proposal
    if proposal["status"] not in {"proposed", "edited"}:
        raise error(
            "proposal_not_confirmable", "Only a pending preview can be confirmed"
        )
    if proposal["action_type"] in CONTROLLED and revision != proposal.get(
        "revision", 1
    ):
        raise error(
            "confirmation_revision_required",
            "Review and confirm the current preview version",
        )
    changed = await db.assistant_action_proposals.update_one(
        {
            **scope(user),
            "id": proposal_id,
            "status": proposal["status"],
            "revision": proposal.get("revision", 1),
        },
        {
            "$set": {
                "status": "confirmed",
                "confirmed_by_user_id": user["id"],
                "confirmed_at": utc_now().isoformat(),
                "confirmation_expires_at": (
                    utc_now() + timedelta(minutes=5)
                ).isoformat(),
                "confirmed_payload_hash": digest(proposal["editable_payload"]),
            }
        },
    )
    if not changed.matched_count:
        raise error("proposal_changed", "The preview changed; review it again")
    return await get(user, proposal_id)


async def cancel(user, proposal_id):
    proposal = await get(user, proposal_id)
    if proposal["status"] in {"executing", "succeeded", "failed", "canceled"}:
        return proposal
    await db.assistant_action_proposals.update_one(
        {**scope(user), "id": proposal_id, "status": proposal["status"]},
        {"$set": {"status": "canceled", "updated_at": utc_now().isoformat()}},
    )
    return await get(user, proposal_id)


async def execute(user, proposal_id, idempotency_key=None):
    from . import business_assistant as svc
    from ..models.business_assistant import AssistantActionExecution

    user = await actor(user)
    proposal = await get(user, proposal_id)
    receipt = await db.assistant_action_executions.find_one(
        {**scope(user), "proposal_id": proposal_id}, {"_id": 0}
    )
    if receipt:
        if receipt["status"] in {"executing", "failed"}:
            observed = await observed_result(user, proposal)
            if observed:
                receipt.update(
                    status="succeeded",
                    canonical_service=observed["canonical_service"],
                    canonical_result=observed,
                    failure_reason=None,
                )
                await db.assistant_action_executions.update_one(
                    {**scope(user), "id": receipt["id"]}, {"$set": receipt}
                )
                await db.assistant_action_proposals.update_one(
                    {**scope(user), "id": proposal_id},
                    {"$set": {"status": "succeeded", "result": observed}},
                )
        if receipt["status"] == "executing":
            raise error(
                "execution_pending",
                "Execution outcome is pending. Do not create another proposal; verify the linked records first",
            )
        return serialize_doc(receipt)
    await validate(user, proposal)
    if (
        proposal["status"] != "confirmed"
        or proposal.get("confirmed_by_user_id") != user["id"]
    ):
        raise error(
            "proposal_confirmation_required",
            "Confirm the exact preview in the interface first",
        )
    if proposal.get(
        "confirmation_expires_at", ""
    ) <= utc_now().isoformat() or proposal.get("confirmed_payload_hash") != digest(
        proposal["editable_payload"]
    ):
        raise error(
            "confirmation_expired",
            "Confirmation expired or content changed; review a new proposal",
        )
    claim = await db.assistant_action_proposals.find_one_and_update(
        {
            **scope(user),
            "id": proposal_id,
            "status": "confirmed",
            "revision": proposal.get("revision", 1),
        },
        {"$set": {"status": "executing", "updated_at": utc_now().isoformat()}},
        return_document=ReturnDocument.AFTER,
    )
    if not claim:
        raise error(
            "execution_pending", "This proposal is already executing; reload its result"
        )
    execution = AssistantActionExecution(
        **scope(user),
        proposal_id=proposal_id,
        conversation_id=proposal["conversation_id"],
        idempotency_key=f"proposal:{proposal_id}",
    ).model_dump()
    await db.assistant_action_executions.insert_one(prepare_for_mongo(execution))
    try:
        # Recheck after the claim immediately before touching a canonical service.
        current = await actor(user)
        await get(current, proposal_id)
        await validate(current, proposal)
        result = await svc._execute_safe_canonical_action(current, proposal)
    except Exception:
        await db.assistant_action_executions.update_one(
            {**scope(user), "id": execution["id"]},
            {
                "$set": {
                    "status": "failed",
                    "failure_reason": "Execution outcome requires review; no automatic retry",
                }
            },
        )
        await db.assistant_action_proposals.update_one(
            {**scope(user), "id": proposal_id}, {"$set": {"status": "failed"}}
        )
        raise error(
            "action_failed",
            "The action could not be confirmed complete. Check the destination before creating another proposal",
            502,
        )
    execution.update(
        status=result["status"],
        canonical_service=result["canonical_service"],
        canonical_result=result,
        executed_at=utc_now().isoformat(),
    )
    if proposal["action_type"] in CONTROLLED:
        result["route"] = f"/studio/assistant?record_proposal={proposal_id}"
    await db.assistant_action_executions.update_one(
        {**scope(user), "id": execution["id"]}, {"$set": execution}
    )
    await db.assistant_action_proposals.update_one(
        {**scope(user), "id": proposal_id},
        {"$set": {"status": result["status"], "result": result}},
    )
    refs = [
        assistant_tools.reference(r["type"], {"id": r["id"], "name": r["label"]})
        for r in proposal["target_refs"]
        if r["type"] in assistant_tools.TARGETS
    ]
    await svc._insert_message(
        user,
        conversation_id=proposal["conversation_id"],
        role="assistant",
        content_text=result["assistant_summary"],
        mode=proposal.get("mode", "owner"),
        proposal_ids=[proposal_id],
        metadata={
            "permission_signature": assistant_context.permission_signature(user),
            "sources": refs,
        },
    )
    await svc._audit(
        user,
        "assistant.action_completed",
        "assistant_action_proposal",
        proposal_id,
        result["assistant_summary"],
    )
    return serialize_doc(execution)


async def observed_result(user, proposal):
    """Recover by reading deterministic canonical identity, never repeat a write."""
    kind = proposal["action_type"]
    if kind not in CONTROLLED:
        return None
    if kind == "internal_task":
        coll, key, query = (
            "tasks",
            "task_id",
            {"idempotency_key": f"assistant-task:{proposal['id']}"},
        )
    elif kind == "internal_note":
        coll, key = "internal_notes", "note_id"
        query = {
            "id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"assistant-note:{user['tenant_id']}:{proposal['id']}",
                )
            ),
            "author_user_id": user["id"],
        }
    else:
        coll, key = "ai_studio_editable_drafts", "draft_id"
        query = {
            "id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"assistant-draft:{user['tenant_id']}:{proposal['id']}",
                )
            ),
            "creator_user_id": user["id"],
        }
    row = await db[coll].find_one({"tenant_id": user["tenant_id"], **query}, {"_id": 0})
    if not row:
        return None
    return {
        "status": "succeeded",
        "canonical_service": coll,
        key: row["id"],
        "sent": False,
        "route": f"/studio/assistant?record_proposal={proposal['id']}",
        "assistant_summary": "The actual saved record was found. No additional record was created or email sent.",
    }


async def saved_record(user, proposal_id):
    from . import business_assistant as svc
    from ..core.permissions import Perm

    user = await actor(user)
    proposal = await get(user, proposal_id)
    receipt = await db.assistant_action_executions.find_one(
        {**scope(user), "proposal_id": proposal_id, "status": "succeeded"}, {"_id": 0}
    )
    if not receipt:
        raise error(
            "saved_record_missing", "No completed application record is available", 404
        )
    result = receipt["canonical_result"]
    kind = proposal["action_type"]
    collection, key, permission = {
        "internal_task": ("tasks", "task_id", Perm.TASK_READ.value),
        "internal_note": ("internal_notes", "note_id", Perm.NOTE_READ.value),
        "email_draft": (
            "ai_studio_editable_drafts",
            "draft_id",
            Perm.AI_HISTORY_READ.value,
        ),
    }[kind]
    svc._require_perm(user, permission)
    row = await db[collection].find_one(
        {"tenant_id": user["tenant_id"], "id": result[key]}, {"_id": 0}
    )
    if not row:
        raise error(
            "saved_record_missing",
            "The created record was deleted or is unavailable",
            404,
        )
    return {
        "id": row["id"],
        "kind": kind,
        "title": row.get("title"),
        "content": row.get("description")
        or row.get("body")
        or row.get("content_text")
        or "",
        "due_at": row.get("due_at"),
        "subject": row.get("content_json", {}).get("subject"),
        "destinations": proposal["target_refs"],
        "sent": False if kind == "email_draft" else None,
    }


async def list_for_conversation(user, conversation_id):
    user = await actor(user)
    rows = []
    async for row in (
        db.assistant_action_proposals.find(
            {**scope(user), "conversation_id": conversation_id}, {"_id": 0}
        )
        .sort("created_at", -1)
        .limit(30)
    ):
        try:
            rows.append(await get(user, row["id"]))
        except Exception as exc:
            from .business_assistant import BusinessAssistantError

            if not isinstance(exc, BusinessAssistantError):
                raise
    return rows
