"""EC18 - Paid Business Assistant, action safety, BI, and voice contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

ConversationStatus = Literal["active", "archived", "deleted"]
AssistantMode = Literal["owner", "operations", "finance", "production", "workforce"]
MessageRole = Literal["user", "assistant", "system", "tool"]
ActionStatus = Literal["proposed", "edited", "confirmed", "canceled", "expired", "executing", "succeeded", "failed", "stale", "unsupported"]
MemoryStatus = Literal["active", "archived", "deleted"]
RoutineStatus = Literal["active", "paused", "archived"]
InsightStatus = Literal["new", "dismissed", "archived"]
VoiceSessionStatus = Literal["created", "connecting", "active", "ended", "failed", "unavailable"]


class AssistantSourceCitation(BaseDoc):
    tenant_id: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    source_type: str
    source_id: str
    source_label: Optional[str] = None
    route: Optional[str] = None
    date_range: Optional[dict[str, Any]] = None
    source_updated_at: Optional[str] = None
    calculation: Optional[dict[str, Any]] = None
    missing_data: list[str] = Field(default_factory=list)


class AssistantConversation(BaseDoc):
    tenant_id: str
    user_id: str
    title: str = "Business Assistant"
    mode: AssistantMode = "owner"
    status: ConversationStatus = "active"
    context_snapshot_ids: list[str] = Field(default_factory=list)
    active_context: dict[str, Any] = Field(default_factory=dict)
    last_message_at: Optional[str] = None
    archived_at: Optional[str] = None
    deleted_at: Optional[str] = None


class AssistantMessage(BaseDoc):
    tenant_id: str
    conversation_id: str
    user_id: Optional[str] = None
    role: MessageRole
    content_text: str = ""
    parts: list[dict[str, Any]] = Field(default_factory=list)
    mode: AssistantMode = "owner"
    context_snapshot_id: Optional[str] = None
    action_request_id: Optional[str] = None
    source_citation_ids: list[str] = Field(default_factory=list)
    action_proposal_ids: list[str] = Field(default_factory=list)
    voice_session_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssistantContextSnapshot(BaseDoc):
    tenant_id: str
    user_id: str
    conversation_id: Optional[str] = None
    mode: AssistantMode = "owner"
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[str] = None
    source_route: Optional[str] = None
    source_updated_at: Optional[str] = None
    validated: bool = True
    status: Literal["created", "used", "expired", "discarded"] = "created"
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    expires_at: Optional[str] = None


class AssistantActionProposal(BaseDoc):
    tenant_id: str
    conversation_id: str
    user_id: str
    capability_key: str
    action_type: str
    title: str
    summary: str
    status: ActionStatus = "proposed"
    mode: AssistantMode = "owner"
    target_refs: list[dict[str, Any]] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
    editable_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    skipped_refs: list[dict[str, Any]] = Field(default_factory=list)
    context_snapshot_id: Optional[str] = None
    source_citation_ids: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
    expires_at: Optional[str] = None
    confirmed_by_user_id: Optional[str] = None
    confirmed_at: Optional[str] = None
    canceled_by_user_id: Optional[str] = None
    canceled_at: Optional[str] = None
    stale_reason: Optional[str] = None


class AssistantActionExecution(BaseDoc):
    tenant_id: str
    proposal_id: str
    conversation_id: str
    user_id: str
    status: ActionStatus = "executing"
    idempotency_key: Optional[str] = None
    canonical_service: Optional[str] = None
    canonical_result: dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    action_request_id: Optional[str] = None
    executed_at: Optional[str] = None


class AssistantMemoryEntry(BaseDoc):
    tenant_id: str
    user_id: str
    memory_key: str
    content_text: str
    status: MemoryStatus = "active"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    visibility: Literal["user", "tenant"] = "user"
    archived_at: Optional[str] = None
    deleted_at: Optional[str] = None


class AssistantRoutine(BaseDoc):
    tenant_id: str
    user_id: str
    name: str
    prompt: str
    mode: AssistantMode = "owner"
    status: RoutineStatus = "active"
    schedule: dict[str, Any] = Field(default_factory=dict)
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    generated_proposal_only: bool = True


class AssistantInsight(BaseDoc):
    tenant_id: str
    user_id: Optional[str] = None
    insight_key: str
    title: str
    summary: str
    status: InsightStatus = "new"
    severity: Literal["info", "warning", "critical"] = "info"
    source_citations: list[dict[str, Any]] = Field(default_factory=list)
    dedupe_key: Optional[str] = None
    window: dict[str, Any] = Field(default_factory=dict)
    dismissed_by_user_id: Optional[str] = None
    dismissed_at: Optional[str] = None


class AssistantVoiceSession(BaseDoc):
    tenant_id: str
    user_id: str
    conversation_id: Optional[str] = None
    status: VoiceSessionStatus = "created"
    provider_key: str = "openai"
    model_key: str
    voice: Optional[str] = None
    provider_session_id: Optional[str] = None
    transcript_retention: str = "conversation_policy"
    raw_audio_stored: bool = False
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    unavailable_reason: Optional[str] = None
    input_audio_seconds: StrictInt = Field(default=0, ge=0)
    output_audio_seconds: StrictInt = Field(default=0, ge=0)
    usage_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
