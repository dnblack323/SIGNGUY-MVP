"""EC12 Phase 12E - staff communication, notes, preferences, and digest routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import communication_service
from ..services.communication_service import CommunicationError

router = APIRouter(prefix="/communications", tags=["communications"])


def _raise(e: CommunicationError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class ThreadCreateIn(BaseModel):
    thread_type: str
    title: str
    participant_user_ids: list[str] = Field(default_factory=list)
    participant_employee_ids: list[str] = Field(default_factory=list)
    team_or_group_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    task_id: Optional[str] = None
    calendar_event_id: Optional[str] = None
    announcement_id: Optional[str] = None
    visibility: str = "internal"


class ParticipantIn(BaseModel):
    participant_user_ids: list[str] = Field(default_factory=list)
    participant_employee_ids: list[str] = Field(default_factory=list)


class MessageIn(BaseModel):
    body: str
    idempotency_key: Optional[str] = None


class NoteIn(BaseModel):
    title: Optional[str] = None
    body: str
    visibility: str = "internal"
    pinned: bool = False
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    task_id: Optional[str] = None
    calendar_event_id: Optional[str] = None
    employee_id: Optional[str] = None


class NoteUpdateIn(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    visibility: Optional[str] = None
    pinned: Optional[bool] = None


class PreferenceIn(BaseModel):
    in_app_messages: Optional[bool] = None
    task_notifications: Optional[bool] = None
    schedule_changes: Optional[bool] = None
    time_off_decisions: Optional[bool] = None
    appointment_reminders: Optional[bool] = None
    announcements: Optional[bool] = None
    daily_digest: Optional[bool] = None
    email_delivery: Optional[bool] = None
    digest_time: Optional[str] = None
    digest_frequency: Optional[str] = None
    quiet_hours: Optional[dict[str, Any]] = None


@router.get("/threads")
async def list_threads(
    thread_type: Optional[str] = None,
    q: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.MESSAGE_READ)),
) -> dict:
    try:
        return await communication_service.list_threads(
            tenant_id=user["tenant_id"], identity_type="user", identity_id=user["id"],
            thread_type=thread_type, q=q, include_archived=include_archived, limit=limit, skip=skip,
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/threads", status_code=201)
async def create_thread(payload: ThreadCreateIn, user: dict = Depends(require_permission(Perm.MESSAGE_CREATE))) -> dict:
    try:
        return await communication_service.create_thread(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(require_permission(Perm.MESSAGE_READ))) -> dict:
    try:
        return await communication_service.get_thread(
            tenant_id=user["tenant_id"], thread_id=thread_id, identity_type="user", identity_id=user["id"],
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/threads/{thread_id}/participants")
async def add_participants(thread_id: str, payload: ParticipantIn, user: dict = Depends(require_permission(Perm.MESSAGE_MANAGE))) -> dict:
    try:
        return await communication_service.add_participants(
            tenant_id=user["tenant_id"], thread_id=thread_id, actor_user_id=user["id"], actor_email=user["email"],
            participant_user_ids=payload.participant_user_ids, participant_employee_ids=payload.participant_employee_ids,
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.MESSAGE_READ)),
) -> dict:
    try:
        return await communication_service.list_messages(
            tenant_id=user["tenant_id"], thread_id=thread_id, identity_type="user", identity_id=user["id"],
            limit=limit, skip=skip,
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/threads/{thread_id}/messages", status_code=201)
async def send_message(thread_id: str, payload: MessageIn, user: dict = Depends(require_permission(Perm.MESSAGE_CREATE))) -> dict:
    try:
        return await communication_service.send_message(
            tenant_id=user["tenant_id"], thread_id=thread_id, body=payload.body,
            actor_user_id=user["id"], actor_email=user["email"], idempotency_key=payload.idempotency_key,
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/threads/{thread_id}/read")
async def mark_read(thread_id: str, user: dict = Depends(require_permission(Perm.MESSAGE_READ))) -> dict:
    try:
        return await communication_service.mark_thread_read(
            tenant_id=user["tenant_id"], thread_id=thread_id, identity_type="user", identity_id=user["id"],
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/threads/{thread_id}/archive")
async def archive_thread(thread_id: str, user: dict = Depends(require_permission(Perm.MESSAGE_MANAGE))) -> dict:
    try:
        return await communication_service.archive_thread(
            tenant_id=user["tenant_id"], thread_id=thread_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/notes")
async def list_notes(
    customer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    production_stage_id: Optional[str] = None,
    task_id: Optional[str] = None,
    calendar_event_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.NOTE_READ)),
) -> dict:
    try:
        linked = {k: v for k, v in {
            "customer_id": customer_id, "order_id": order_id, "order_item_id": order_item_id,
            "work_order_id": work_order_id, "production_stage_id": production_stage_id,
            "task_id": task_id, "calendar_event_id": calendar_event_id, "employee_id": employee_id,
        }.items() if v}
        return await communication_service.list_notes(
            tenant_id=user["tenant_id"], identity_type="user", identity_id=user["id"], linked=linked,
            include_archived=include_archived, limit=limit, skip=skip,
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/notes", status_code=201)
async def create_note(payload: NoteIn, user: dict = Depends(require_permission(Perm.NOTE_CREATE))) -> dict:
    try:
        return await communication_service.create_note(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CommunicationError as e:
        _raise(e)


@router.patch("/notes/{note_id}")
async def edit_note(note_id: str, payload: NoteUpdateIn, user: dict = Depends(require_permission(Perm.NOTE_MANAGE))) -> dict:
    try:
        return await communication_service.edit_note(
            tenant_id=user["tenant_id"], note_id=note_id, actor_user_id=user["id"], actor_email=user["email"],
            updates=payload.model_dump(exclude_none=True),
        )
    except CommunicationError as e:
        _raise(e)


@router.post("/notes/{note_id}/archive")
async def archive_note(note_id: str, user: dict = Depends(require_permission(Perm.NOTE_MANAGE))) -> dict:
    try:
        return await communication_service.archive_note(
            tenant_id=user["tenant_id"], note_id=note_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/preferences/me")
async def get_my_preferences(user: dict = Depends(require_permission(Perm.MESSAGE_READ))) -> dict:
    return await communication_service.get_preferences(tenant_id=user["tenant_id"], identity_type="user", identity_id=user["id"])


@router.patch("/preferences/me")
async def update_my_preferences(payload: PreferenceIn, user: dict = Depends(require_permission(Perm.MESSAGE_READ))) -> dict:
    return await communication_service.update_preferences(
        tenant_id=user["tenant_id"], identity_type="user", identity_id=user["id"],
        actor_user_id=user["id"], actor_email=user["email"], updates=payload.model_dump(exclude_none=True),
    )


@router.get("/digest/preview")
async def preview_digest(
    digest_date: Optional[str] = None,
    user: dict = Depends(require_permission(Perm.DIGEST_READ)),
) -> dict:
    return await communication_service.preview_digest(
        tenant_id=user["tenant_id"], recipient_type="user", recipient_id=user["id"], digest_date=digest_date,
    )


@router.post("/digest/generate")
async def generate_digest(
    digest_date: Optional[str] = None,
    user: dict = Depends(require_permission(Perm.DIGEST_READ)),
) -> dict:
    return await communication_service.generate_digest(
        tenant_id=user["tenant_id"], recipient_type="user", recipient_id=user["id"], digest_date=digest_date,
    )


@router.post("/digest/{digest_id}/delivered")
async def mark_digest_delivered(digest_id: str, user: dict = Depends(require_permission(Perm.DIGEST_READ))) -> dict:
    try:
        return await communication_service.mark_digest_delivered(
            tenant_id=user["tenant_id"], digest_id=digest_id, recipient_type="user", recipient_id=user["id"],
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/badge")
async def unread_badge(user: dict = Depends(require_permission(Perm.MESSAGE_READ))) -> dict:
    return await communication_service.unread_badge(tenant_id=user["tenant_id"], identity_type="user", identity_id=user["id"])
