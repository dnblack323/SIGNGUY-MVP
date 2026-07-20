"""EC18 Business Assistant, structured action, BI, and voice routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from ..deps import get_current_user
from ..services import business_assistant as svc
from ..services.business_assistant import BusinessAssistantError

router = APIRouter(prefix="/assistant", tags=["business-assistant"])


def _raise(exc: BusinessAssistantError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


class ConversationIn(BaseModel):
    title: Optional[str] = None
    mode: str = "owner"


class AssistantAskIn(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    mode: str = "owner"
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class ActionProposalIn(BaseModel):
    conversation_id: Optional[str] = None
    mode: str = "owner"
    action_type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    instructions: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    route: Optional[str] = None
    target_refs: list[dict[str, Any]] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
    editable_payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    metering_idempotency_key: Optional[str] = None


class ProposalEditIn(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    editable_payload: dict[str, Any] = Field(default_factory=dict)


class MemoryIn(BaseModel):
    memory_key: str
    content_text: str


class RoutineIn(BaseModel):
    name: str
    prompt: str
    mode: str = "owner"
    schedule: dict[str, Any] = Field(default_factory=dict)
    next_run_at: Optional[str] = None


class StudioDelegationIn(BaseModel):
    tool_key: str = "social_post_builder"
    mode_key: str = "completed_work_showcase"
    mode: str = "operations"
    conversation_id: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class VoiceSessionIn(BaseModel):
    conversation_id: Optional[str] = None
    mode: str = "owner"


class VoiceUsageIn(BaseModel):
    provider_event_id: str
    input_audio_seconds: StrictInt = Field(default=0, ge=0)
    output_audio_seconds: StrictInt = Field(default=0, ge=0)


@router.get("/catalog")
async def catalog(user: dict = Depends(get_current_user)) -> dict:
    try:
        await svc.assert_assistant_access(user)
    except BusinessAssistantError as exc:
        _raise(exc)
    return svc.list_catalog()


@router.post("/platform/bootstrap", status_code=201)
async def bootstrap_platform_catalog(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bootstrap_platform_catalog(user)
    except (BusinessAssistantError, svc.ai_gateway.AIGatewayError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/conversations", status_code=201)
async def create_conversation(payload: ConversationIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_conversation(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/conversations")
async def list_conversations(limit: int = Query(50, ge=1, le=200), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_conversations(user, limit=limit)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.get_conversation(user, conversation_id)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/messages", status_code=201)
async def ask_assistant(payload: AssistantAskIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.ask_assistant(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/actions/proposals", status_code=201)
async def propose_action(payload: ActionProposalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.propose_action(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.patch("/actions/proposals/{proposal_id}")
async def edit_proposal(proposal_id: str, payload: ProposalEditIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.edit_proposal(user, proposal_id, payload.model_dump(exclude_unset=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/actions/proposals/{proposal_id}/confirm")
async def confirm_proposal(proposal_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.confirm_proposal(user, proposal_id)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/actions/proposals/{proposal_id}/cancel")
async def cancel_proposal(proposal_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.cancel_proposal(user, proposal_id)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/actions/proposals/{proposal_id}/execute")
async def execute_proposal(
    proposal_id: str,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.execute_proposal(user, proposal_id, idempotency_key=idempotency_key)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/memory")
async def list_memory(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_memory(user)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/memory", status_code=201)
async def upsert_memory(payload: MemoryIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.upsert_memory(user, payload.model_dump())
    except BusinessAssistantError as exc:
        _raise(exc)


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.delete_memory(user, memory_id)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/routines", status_code=201)
async def create_routine(payload: RoutineIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_routine(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/routines")
async def list_routines(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_routines(user)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/quick-actions")
async def quick_actions(mode: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_quick_actions(user, mode=mode)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/delegations/studio", status_code=201)
async def create_studio_delegation(payload: StudioDelegationIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_studio_delegation(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/insights")
async def list_insights(generate: bool = Query(False), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_insights(user, generate=generate)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.dismiss_insight(user, insight_id)
    except BusinessAssistantError as exc:
        _raise(exc)


@router.get("/voice/config")
async def get_voice_config(user: dict = Depends(get_current_user)) -> dict:
    try:
        await svc.assert_assistant_access(user)
    except BusinessAssistantError as exc:
        _raise(exc)
    return svc.voice_config()


@router.post("/voice/sessions", status_code=201)
async def create_voice_session(payload: VoiceSessionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_realtime_session(user, payload.model_dump(exclude_none=True))
    except BusinessAssistantError as exc:
        _raise(exc)


@router.post("/voice/sessions/{voice_session_id}/usage", status_code=201)
async def record_voice_usage(voice_session_id: str, payload: VoiceUsageIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.record_voice_usage(user, voice_session_id, payload.model_dump())
    except BusinessAssistantError as exc:
        _raise(exc)
