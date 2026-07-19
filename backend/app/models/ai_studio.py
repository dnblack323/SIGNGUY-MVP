"""EC17 - Studio AI tools, prompt library, generated assets, and activity."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

StudioCatalogStatus = Literal["active", "inactive", "removed", "ec18_only", "meta_only"]
PromptOwnerScope = Literal["platform_starter", "tenant"]
PromptLifecycle = Literal["draft", "published", "archived"]
GeneratedAssetStatus = Literal["draft", "saved", "archived"]
StudioResultStorage = Literal["generated_asset", "editable_draft", "history_only"]
ProposalStatus = Literal["draft", "reviewed", "approved", "rejected", "deferred"]


class AIStudioPromptEntry(BaseDoc):
    tenant_id: Optional[str] = None
    owner_scope: PromptOwnerScope = "tenant"
    source_prompt_entry_id: Optional[str] = None
    tool_key: str
    mode_key: str
    capability_key: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    required_variables: list[str] = Field(default_factory=list)
    optional_variables: list[str] = Field(default_factory=list)
    template: str
    version: int = 1
    status: PromptLifecycle = "draft"
    published_at: Optional[str] = None
    published_by_user_id: Optional[str] = None
    archived_at: Optional[str] = None
    archived_by_user_id: Optional[str] = None
    ec16_prompt_version_id: Optional[str] = None


class AIGeneratedAsset(BaseDoc):
    tenant_id: str
    creator_user_id: str
    tool_key: str
    mode_key: str
    family_key: str
    capability_key: str
    usage_band: str
    credit_display: str = "AI credits apply"
    result_storage: StudioResultStorage = "generated_asset"
    status: GeneratedAssetStatus = "saved"
    title: str
    asset_type: str
    content_text: Optional[str] = None
    content_json: dict[str, Any] = Field(default_factory=dict)
    file_metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    action_request_id: Optional[str] = None
    prompt_entry_id: Optional[str] = None
    ec16_prompt_version_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    source_asset_ids: list[str] = Field(default_factory=list)
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    parent_asset_id: Optional[str] = None
    revision_of_asset_id: Optional[str] = None
    parent_record_type: Optional[str] = None
    parent_record_id: Optional[str] = None
    context_summary: dict[str, Any] = Field(default_factory=dict)
    accepted_as_type: Optional[str] = None
    accepted_record_id: Optional[str] = None
    archived_at: Optional[str] = None
    archived_by_user_id: Optional[str] = None


class AIStudioEditableDraft(BaseDoc):
    tenant_id: str
    creator_user_id: str
    tool_key: str
    mode_key: str
    family_key: str
    capability_key: str
    usage_band: str
    credit_display: str = "AI credits apply"
    draft_type: str
    title: str
    content_text: str
    content_json: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    action_request_id: Optional[str] = None
    prompt_entry_id: Optional[str] = None
    ec16_prompt_version_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    parent_record_type: Optional[str] = None
    parent_record_id: Optional[str] = None
    saved_asset_id: Optional[str] = None
    saved_document_id: Optional[str] = None
    saved_template_id: Optional[str] = None
    archived_at: Optional[str] = None
    archived_by_user_id: Optional[str] = None


class AIStudioBrandContext(BaseDoc):
    tenant_id: str
    owner_type: str = "tenant"
    owner_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    name: str
    status: Literal["suggested", "approved", "archived"] = "suggested"
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[str] = None
    logo_file_ids: list[str] = Field(default_factory=list)
    brand_colors: list[str] = Field(default_factory=list)
    typography_guidance: Optional[str] = None
    brand_voice: Optional[str] = None
    audience: Optional[str] = None
    business_description: Optional[str] = None
    values: list[str] = Field(default_factory=list)
    approved_taglines: list[str] = Field(default_factory=list)
    preferred_wording: list[str] = Field(default_factory=list)
    prohibited_wording: list[str] = Field(default_factory=list)
    archived_at: Optional[str] = None


class AIStudioPricingImportAnalysis(BaseDoc):
    tenant_id: str
    created_by_user_id: str
    source_file_id: Optional[str] = None
    source_file_name: Optional[str] = None
    source_file_type: str
    source_file_size_bytes: int = 0
    status: ProposalStatus = "draft"
    extracted_values: list[dict[str, Any]] = Field(default_factory=list)
    proposed_mappings: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_signals: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: str = "mock"
    action_request_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    approval_boundary: str = "application_deferred_to_canonical_pricing_checkpoint"
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[str] = None


class AIStudioPricingSetupProposal(BaseDoc):
    tenant_id: str
    created_by_user_id: str
    status: ProposalStatus = "draft"
    sections: list[dict[str, Any]] = Field(default_factory=list)
    proposed_defaults: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    comparison: dict[str, Any] = Field(default_factory=dict)
    action_request_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    application_boundary: str = "requires_explicit_canonical_pricing_service_application"
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[str] = None
