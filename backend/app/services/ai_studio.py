"""EC17 AI Studio service.

This layer owns tenant-facing Studio tools, prompts, generated results, and
activity views. Execution still goes through EC16; no external provider calls
are made here.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.ai_gateway import AICapability, AIContextPacket, AIModelProfile, AIPromptVersion, AIProviderConfig
from ..models.ai_studio import (
    AIGeneratedAsset,
    AIStudioBrandContext,
    AIStudioEditableDraft,
    AIStudioPricingImportAnalysis,
    AIStudioPricingSetupProposal,
    AIStudioPromptEntry,
)
from . import ai_gateway
from .activity import record_activity_with_audit
from .entitlements import has_entitlement


AI_STUDIO_ENTITLEMENT_FEATURE_KEY = "ai_studio"
LOCAL_PROVIDER_KEY = "ec17_local_mock"
LOCAL_MODEL_KEY = "ec17_local_contract_model"
LOCAL_PROMPT_VERSION = "ec17-local-1"
CREDIT_DISPLAY = "AI credits apply"

USAGE_BANDS = {
    "light": "Short rewrite, small text transformation, brief reply, or simple idea list.",
    "standard": "Normal text generation such as an email, product description, review reply, or social caption.",
    "heavy": "Long-form, context-heavy, document, campaign, multi-platform, historical analysis, or multiple-output generation.",
    "premium": "Image generation, image editing, vision/OCR, file analysis, or other provider-expensive work.",
}

INACTIVE_CAPABILITY_IDENTIFIERS = {
    "ec18_only": [
        "assistant.email_draft",
        "assistant.chat",
        "assistant.action_parse",
        "assistant.voice_transcription",
        "assistant.voice_reply",
        "assistant.intent_classify",
        "assistant.navigation_classify",
        "assistant.memory_compress",
    ],
    "removed": ["order.service_prefill", "studio.text.bulk_followup"],
    "meta_only": ["integration.facebook.message_classify", "integration.facebook.order_extract"],
}


class AIStudioError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _mode(key: str, name: str, *, usage_band: str, result_storage: str, capability_key: str, fields: list[dict[str, Any]], warnings: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "mode_key": key,
        "name": name,
        "capability_key": capability_key,
        "usage_band": usage_band,
        "credit_display": CREDIT_DISPLAY,
        "result_storage": result_storage,
        "fields": fields,
        "warnings": warnings or [],
    }


TEXT_FIELD = {"name": "prompt", "label": "Prompt", "type": "textarea", "required": True}
IMAGE_FIELD = {"name": "source_image_id", "label": "Source image", "type": "file_ref", "required": False}
CONTEXT_NOTE_FIELD = {"name": "context_notes", "label": "Context notes", "type": "textarea", "required": False}


TOOL_FAMILIES: list[dict[str, Any]] = [
    {"family_key": "design_image", "name": "Design & Image Studio", "module": "Design Studio"},
    {"family_key": "marketing_brand", "name": "Marketing & Brand Studio", "module": "Marketing"},
    {"family_key": "writing_documents", "name": "Business Writing & Documents", "module": "Documents"},
    {"family_key": "pricing_profitability", "name": "Pricing & Profitability", "module": "Pricing"},
]

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "tool_key": "ai_image_generator",
        "name": "AI Image Generator",
        "family_key": "design_image",
        "featured": True,
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("general_text_to_image", "General Text-to-Image", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.custom_concept", fields=[TEXT_FIELD]),
            _mode("custom_image_concept", "Custom Image Concept", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.custom_concept", fields=[TEXT_FIELD, CONTEXT_NOTE_FIELD]),
        ],
    },
    {
        "tool_key": "mockup_generator",
        "name": "Mockup Generator",
        "family_key": "design_image",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("sign_mockup", "Sign Mockup", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.sign_mockup", fields=[TEXT_FIELD, CONTEXT_NOTE_FIELD]),
            _mode("banner_mockup", "Banner Mockup", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.banner_concept", fields=[TEXT_FIELD, CONTEXT_NOTE_FIELD]),
            _mode("product_mockup", "Product Mockup", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.mockup", fields=[TEXT_FIELD, CONTEXT_NOTE_FIELD], warnings=["Webstore context is preloaded only when authorized and never auto-published."]),
        ],
    },
    {
        "tool_key": "logo_lab",
        "name": "Logo Lab",
        "family_key": "design_image",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("new_logo_concepts", "New Logo Concepts", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.logo_concepts", fields=[TEXT_FIELD], warnings=["Concept only. No trademark or production-ready claim."]),
            _mode("refresh_existing_logo", "Refresh Existing Logo", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.logo_refresh", fields=[TEXT_FIELD, IMAGE_FIELD], warnings=["Original logos are preserved. Refreshes save as separate concepts."]),
        ],
    },
    {
        "tool_key": "vehicle_graphics_studio",
        "name": "Vehicle Graphics Studio",
        "family_key": "design_image",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("vehicle_wrap_concept", "Vehicle Wrap Concept", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.wrap_mockup", fields=[TEXT_FIELD, CONTEXT_NOTE_FIELD], warnings=["Concept / Mockup - Not Production-Ready."]),
            _mode("race_number_design", "Race Number Design", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.motorsports_graphics", fields=[TEXT_FIELD]),
            _mode("driver_name_plate", "Driver Name Plate", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.motorsports_graphics", fields=[TEXT_FIELD]),
            _mode("team_branding", "Team Branding", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.motorsports_graphics", fields=[TEXT_FIELD]),
        ],
    },
    {
        "tool_key": "photo_editor",
        "name": "Photo Editor",
        "family_key": "design_image",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.DOCUMENT_READ.value],
        "modes": [
            _mode("enhance_photo", "Enhance Photo", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.photo_cleanup", fields=[TEXT_FIELD, IMAGE_FIELD], warnings=["Local mock/test output only while H7 remains active. Original image is preserved."]),
            _mode("edit_replace_area", "Edit/Replace Area", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.edit_fill", fields=[TEXT_FIELD, IMAGE_FIELD, {"name": "mask_description", "label": "Selected region or mask", "type": "textarea", "required": True}, {"name": "preserve_area_instructions", "label": "Preserve-area instructions", "type": "textarea", "required": False}, {"name": "reference_image_id", "label": "Reference image", "type": "file_ref", "required": False}, {"name": "output_dimensions", "label": "Output aspect/dimensions", "type": "text", "required": False}], warnings=["No claim that a real image edit occurred under local mock execution. Original image is preserved."]),
            _mode("add_remove_object", "Add or Remove Object", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.edit_fill", fields=[TEXT_FIELD, IMAGE_FIELD]),
            _mode("background_change", "Background Change", usage_band="premium", result_storage="generated_asset", capability_key="studio.image.edit_fill", fields=[TEXT_FIELD, IMAGE_FIELD]),
        ],
    },
    {
        "tool_key": "artwork_assistant",
        "name": "Artwork Assistant",
        "family_key": "design_image",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.DOCUMENT_READ.value],
        "modes": [
            _mode("artwork_check", "Artwork Check", usage_band="premium", result_storage="generated_asset", capability_key="studio.artwork.vector_guidance", fields=[TEXT_FIELD, IMAGE_FIELD], warnings=["Advisory only. No production approval."]),
            _mode("vector_preparation_guidance", "Vector Preparation Guidance", usage_band="premium", result_storage="generated_asset", capability_key="studio.artwork.vector_guidance", fields=[TEXT_FIELD, IMAGE_FIELD], warnings=["No production vector guarantee."]),
            _mode("font_finder", "Font Finder", usage_band="premium", result_storage="generated_asset", capability_key="studio.artwork.font_finder", fields=[TEXT_FIELD, IMAGE_FIELD], warnings=["Font matches may be uncertain and require verification."]),
        ],
    },
    {
        "tool_key": "social_post_builder",
        "name": "Social Post Builder",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("quick_job_post", "Quick Job Post", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.completed_job_post", fields=[TEXT_FIELD, {"name": "publicity_permission_state", "label": "Customer/publicity permission", "type": "select", "required": True, "options": ["confirmed", "unknown", "missing"]}], warnings=["Draft only. No direct publishing."]),
            _mode("completed_work_showcase", "Completed-Work Showcase", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.completed_job_post", fields=[TEXT_FIELD, {"name": "publicity_permission_state", "label": "Customer/publicity permission", "type": "select", "required": True, "options": ["confirmed", "unknown", "missing"]}], warnings=["Draft only. No direct publishing."]),
            _mode("multi_platform_post_pack", "Multi-Platform Post Pack", usage_band="heavy", result_storage="editable_draft", capability_key="studio.text.social_pack", fields=[TEXT_FIELD, {"name": "platforms", "label": "Platforms", "type": "text", "required": False}, {"name": "publicity_permission_state", "label": "Customer/publicity permission", "type": "select", "required": True, "options": ["confirmed", "unknown", "missing"]}], warnings=["Draft only. No direct publishing or scheduling."]),
        ],
    },
    {
        "tool_key": "content_writer",
        "name": "Content Writer",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("business_copy", "Business Copy", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.copy_writer", fields=[TEXT_FIELD]),
            _mode("website_advertising_copy", "Website or Advertising Copy", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.marketing_content", fields=[TEXT_FIELD]),
            _mode("blog_seo_content", "Blog and SEO Content", usage_band="heavy", result_storage="editable_draft", capability_key="studio.text.marketing_content", fields=[TEXT_FIELD]),
        ],
    },
    {
        "tool_key": "campaign_planner",
        "name": "Campaign Planner",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("campaign_ideas", "Campaign Ideas", usage_band="light", result_storage="editable_draft", capability_key="studio.text.idea_brainstorm", fields=[TEXT_FIELD]),
            _mode("campaign_plan", "Campaign Plan", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.campaign_plan", fields=[TEXT_FIELD], warnings=["Proposed plan only. No external campaign creation."]),
            _mode("content_calendar", "Content Calendar", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.content_calendar", fields=[TEXT_FIELD], warnings=["Proposed calendar only. No scheduling."]),
        ],
    },
    {
        "tool_key": "brand_kit_builder",
        "name": "Brand Kit Builder",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("brand_ideas", "Brand Ideas", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.brand_kit", fields=[TEXT_FIELD], warnings=["Suggestions only until approved as brand context."]),
            _mode("tagline_generator", "Tagline Generator", usage_band="light", result_storage="editable_draft", capability_key="studio.text.idea_brainstorm", fields=[TEXT_FIELD]),
            _mode("color_palette", "Color Palette", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.brand_kit", fields=[TEXT_FIELD]),
            _mode("brand_voice", "Brand Voice", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.brand_kit", fields=[TEXT_FIELD]),
        ],
    },
    {
        "tool_key": "product_content_builder",
        "name": "Product Content Builder",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("product_name_suggestions", "Product Name Suggestions", usage_band="light", result_storage="editable_draft", capability_key="studio.text.idea_brainstorm", fields=[TEXT_FIELD]),
            _mode("product_description_draft", "Product Description Draft", usage_band="standard", result_storage="editable_draft", capability_key="webstore.product_description", fields=[TEXT_FIELD], warnings=["Editable draft. Never changes price, availability, order, or payment."]),
            _mode("webstore_product_content", "Webstore Product Content", usage_band="standard", result_storage="editable_draft", capability_key="webstore.product_description", fields=[TEXT_FIELD], warnings=["Requires confirmation before applying text; never auto-publishes."]),
        ],
    },
    {
        "tool_key": "review_reply_assistant",
        "name": "Review Reply Assistant",
        "family_key": "marketing_brand",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("positive_review_reply", "Positive Review Reply", usage_band="light", result_storage="editable_draft", capability_key="studio.text.review_reply", fields=[TEXT_FIELD], warnings=["Draft only. Human review required."]),
            _mode("negative_review_reply", "Negative Review Reply", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.review_reply", fields=[TEXT_FIELD], warnings=["Draft only. No invented promises, refunds, admissions, or legal statements."]),
            _mode("neutral_custom_reply", "Neutral or Custom Reply", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.review_reply", fields=[TEXT_FIELD]),
        ],
    },
    {
        "tool_key": "email_draft_assistant",
        "name": "Email Draft Assistant",
        "family_key": "writing_documents",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.EMAIL_SEND.value],
        "modes": [
            _mode("quote_follow_up", "Quote Follow-up", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD], warnings=["Editable draft only. Never sent automatically."]),
            _mode("payment_reminder", "Payment Reminder", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD], warnings=["Never changes payment status."]),
            _mode("thank_you_email", "Thank-you Email", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
            _mode("overdue_invoice_email", "Overdue Invoice Email", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
            _mode("job_update", "Job Update", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
            _mode("job_complete_email", "Job-Complete Email", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
            _mode("proof_approval_request", "Proof/Approval Request", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
            _mode("custom_email", "Custom Email", usage_band="standard", result_storage="editable_draft", capability_key="studio.text.email_draft", fields=[TEXT_FIELD]),
        ],
    },
    {
        "tool_key": "proposal_builder",
        "name": "Proposal Builder",
        "family_key": "writing_documents",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.TEMPLATE_READ.value],
        "modes": [_mode("proposal", "Proposal", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.proposal_draft", fields=[TEXT_FIELD], warnings=["Editable draft. Preview before reuse."])],
    },
    {
        "tool_key": "document_writer",
        "name": "Document Writer",
        "family_key": "writing_documents",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.TEMPLATE_READ.value],
        "modes": [
            _mode("general_business_document", "General Business Document", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("proposal", "Proposal", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.proposal_draft", fields=[TEXT_FIELD]),
            _mode("scope_of_work", "Scope of Work", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("standard_operating_procedure", "Standard Operating Procedure", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("job_description", "Job Description", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("policy_or_instructions", "Policy or Instructions", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("customer_letter", "Customer Letter", usage_band="standard", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("customer_order_document", "Customer or Order Document", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD]),
            _mode("contract_draft", "Contract Draft", usage_band="heavy", result_storage="generated_asset", capability_key="studio.text.document_draft", fields=[TEXT_FIELD], warnings=["Editable draft only. Legal review required. No claim of legal sufficiency."]),
        ],
    },
    {
        "tool_key": "permit_guidance",
        "name": "Permit Guidance",
        "family_key": "writing_documents",
        "required_permissions": [Perm.AI_TOOL_USE.value],
        "modes": [
            _mode("permit_checklist", "Permit Checklist", usage_band="heavy", result_storage="generated_asset", capability_key="studio.research.permit_guidance", fields=[{"name": "jurisdiction", "label": "Jurisdiction", "type": "text", "required": True}, {"name": "state", "label": "State", "type": "text", "required": False}, {"name": "city", "label": "City or municipality", "type": "text", "required": False}, {"name": "project_address", "label": "Project address", "type": "text", "required": False}, {"name": "sign_type", "label": "Sign type", "type": "text", "required": False}, {"name": "sign_dimensions", "label": "Sign dimensions", "type": "text", "required": False}, {"name": "illumination", "label": "Illumination", "type": "text", "required": False}, {"name": "mounting_method", "label": "Mounting method", "type": "text", "required": False}, TEXT_FIELD], warnings=["Informational only. Verify requirements with the proper local authority. No legal advice or approval guarantee."]),
        ],
    },
    {
        "tool_key": "pricing_profitability",
        "name": "Pricing & Profitability",
        "family_key": "pricing_profitability",
        "required_permissions": [Perm.AI_TOOL_USE.value, Perm.PRICING_READ.value],
        "modes": [
            _mode("pricing_advisor", "Pricing Advisor", usage_band="standard", result_storage="editable_draft", capability_key="pricing.advisory", fields=[TEXT_FIELD], warnings=["Advisory only. Does not modify Quote, Order, Invoice, catalog price, or Pricing Foundation."]),
            _mode("pricing_insights", "Pricing Insights", usage_band="heavy", result_storage="editable_draft", capability_key="pricing.insights", fields=[TEXT_FIELD], warnings=["Does not invent conclusions without adequate data."]),
            _mode("historical_pricing_import_analysis", "Historical Pricing Import Analysis", usage_band="premium", result_storage="editable_draft", capability_key="pricing.historical_invoice_analysis", fields=[{"name": "source_file_name", "label": "Source file name", "type": "text", "required": True}, {"name": "source_file_type", "label": "File type", "type": "select", "required": True, "options": ["pdf", "csv", "xlsx", "xls"]}, {"name": "source_file_size_bytes", "label": "File size", "type": "number", "required": False}], warnings=["Local mock extraction only while H7 remains active. No current pricing values are changed."]),
            _mode("wrap_cost_guidance", "Wrap Cost Guidance", usage_band="heavy", result_storage="editable_draft", capability_key="wrap_lab.cost_guidance", fields=[TEXT_FIELD], warnings=["Advisory only. Does not mutate Wrap Lab, Quotes, Orders, Invoices, or Pricing Foundation."]),
            _mode("shop_pricing_setup_assistant", "Shop Pricing Setup Assistant", usage_band="heavy", result_storage="editable_draft", capability_key="pricing.setup_suggestions", fields=[TEXT_FIELD], warnings=["Proposals require explicit owner/admin confirmation and canonical Pricing Foundation service application."]),
        ],
    },
]


def _catalog_map() -> dict[str, dict[str, Any]]:
    return {tool["tool_key"]: tool for tool in TOOL_CATALOG}


def _mode_map(tool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {mode["mode_key"]: mode for mode in tool["modes"]}


def _has_perm(user: dict[str, Any], perm: str) -> bool:
    if user.get("role") in {"owner", "admin"}:
        return True
    return perm in set(user.get("permissions") or permissions_for_role(user.get("role", "staff")))


def _require_perm(user: dict[str, Any], perm: str) -> None:
    if not _has_perm(user, perm):
        raise AIStudioError("permission_required", f"Missing permission: {perm}", 403)


def _tool_and_mode(tool_key: str, mode_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    tool = _catalog_map().get(tool_key)
    if not tool:
        raise AIStudioError("tool_not_found", "AI Studio tool not found", 404)
    mode = _mode_map(tool).get(mode_key)
    if not mode:
        raise AIStudioError("mode_not_found", "AI Studio mode not found", 404)
    return tool, mode


def _active_capability_keys() -> set[str]:
    keys: set[str] = set()
    for tool in TOOL_CATALOG:
        for mode in tool["modes"]:
            keys.add(mode["capability_key"])
    return keys


def list_catalog() -> dict[str, Any]:
    tools = []
    for tool in TOOL_CATALOG:
        cloned = deepcopy(tool)
        cloned["status"] = "active"
        cloned["entitlement_feature_key"] = AI_STUDIO_ENTITLEMENT_FEATURE_KEY
        tools.append(cloned)
    return {
        "families": TOOL_FAMILIES,
        "usage_bands": USAGE_BANDS,
        "credit_display": CREDIT_DISPLAY,
        "tools": tools,
        "inactive_capability_identifiers": INACTIVE_CAPABILITY_IDENTIFIERS,
    }


def get_tool(tool_key: str) -> dict[str, Any]:
    tool = _catalog_map().get(tool_key)
    if not tool:
        raise AIStudioError("tool_not_found", "AI Studio tool not found", 404)
    cloned = deepcopy(tool)
    cloned["status"] = "active"
    cloned["entitlement_feature_key"] = AI_STUDIO_ENTITLEMENT_FEATURE_KEY
    return cloned


async def bootstrap_platform_catalog(user: dict[str, Any]) -> dict[str, Any]:
    ai_gateway.require_platform_ai_admin(user)
    provider = await _ensure_local_provider()
    model = await _ensure_local_model(provider)
    created_capabilities = []
    created_prompts = []
    for capability_key in sorted(_active_capability_keys()):
        cap = await _ensure_local_capability(capability_key, model["id"])
        prompt = await _ensure_local_prompt(capability_key)
        created_capabilities.append(cap["capability_key"])
        created_prompts.append(prompt["id"])
    await _audit(user, "ai_studio.catalog_bootstrapped", "ai_studio_catalog", "ec17", "EC17 local mock catalog bootstrapped")
    return {
        "provider_key": provider["provider_key"],
        "model_key": model["model_key"],
        "capability_keys": created_capabilities,
        "prompt_version_ids": created_prompts,
        "external_provider_calls": 0,
    }


async def _ensure_local_provider() -> dict[str, Any]:
    query = {"provider_key": LOCAL_PROVIDER_KEY}
    existing = await db.ai_provider_configs.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIProviderConfig(
        provider_key=LOCAL_PROVIDER_KEY,
        display_name="EC17 Local Mock Provider",
        status="active",
        credential_mode="none",
        supported_modalities=["text", "image", "document", "analysis"],
        metadata={"ec17_local_mock": True, "external_provider_calls": 0},
    ).model_dump()
    try:
        await db.ai_provider_configs.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_provider_configs.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def _ensure_local_model(provider: dict[str, Any]) -> dict[str, Any]:
    query = {"provider_config_id": provider["id"], "model_key": LOCAL_MODEL_KEY}
    existing = await db.ai_model_profiles.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIModelProfile(
        provider_config_id=provider["id"],
        provider_key=provider["provider_key"],
        model_key=LOCAL_MODEL_KEY,
        display_name="EC17 Local Contract Model",
        task_category="studio",
        intensity="local_mock",
        status="active",
        metadata={"ec17_local_mock": True, "external_provider_calls": 0},
    ).model_dump()
    try:
        await db.ai_model_profiles.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_model_profiles.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def _ensure_local_capability(capability_key: str, model_profile_id: str) -> dict[str, Any]:
    query = {"capability_key": capability_key}
    existing = await db.ai_capabilities.find_one(query, {"_id": 0})
    if existing:
        if model_profile_id not in (existing.get("allowed_model_profile_ids") or []):
            ids = list(existing.get("allowed_model_profile_ids") or []) + [model_profile_id]
            await db.ai_capabilities.update_one({"id": existing["id"]}, {"$set": {"allowed_model_profile_ids": ids, "updated_at": _now_iso()}})
            existing["allowed_model_profile_ids"] = ids
        return serialize_doc(existing)
    action_key = capability_key.split(".")[-1]
    doc = AICapability(
        capability_key=capability_key,
        display_name=capability_key.replace(".", " ").replace("_", " ").title(),
        feature_key="ai_studio",
        action_key=action_key,
        entitlement_feature_key=AI_STUDIO_ENTITLEMENT_FEATURE_KEY,
        status="active",
        billable=True,
        default_credit_charge=1,
        allowed_model_profile_ids=[model_profile_id],
        metadata={"ec17_local_mock": True, "credit_display": CREDIT_DISPLAY, "no_final_numeric_credit_price": True},
    ).model_dump()
    try:
        await db.ai_capabilities.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_capabilities.find_one(query, {"_id": 0})
        if existing:
            return await _ensure_local_capability(capability_key, model_profile_id)
        raise
    return serialize_doc(doc)


async def _ensure_local_prompt(capability_key: str) -> dict[str, Any]:
    prompt_key = f"{capability_key}.ec17_local"
    query = {"prompt_key": prompt_key, "version": LOCAL_PROMPT_VERSION}
    existing = await db.ai_prompt_versions.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIPromptVersion(
        capability_key=capability_key,
        prompt_key=prompt_key,
        version=LOCAL_PROMPT_VERSION,
        status="published",
        template="EC17 deterministic local contract prompt. No external provider call.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        published_by_user_id="system",
        published_at=_now_iso(),
    ).model_dump()
    try:
        await db.ai_prompt_versions.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_prompt_versions.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def run_tool(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_TOOL_USE.value)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=AI_STUDIO_ENTITLEMENT_FEATURE_KEY):
        raise AIStudioError("feature_not_entitled", f"Feature not entitled: {AI_STUDIO_ENTITLEMENT_FEATURE_KEY}", 402)
    tool, mode = _tool_and_mode(fields.get("tool_key"), fields.get("mode_key"))
    for perm in tool.get("required_permissions") or []:
        _require_perm(user, perm)
    await _validate_context_and_permissions(user, fields.get("context") or {}, tool, mode)

    idempotency_key = fields.get("idempotency_key")
    if idempotency_key:
        existing = await _find_existing_result(user["tenant_id"], idempotency_key)
        if existing:
            return existing

    capability = await db.ai_capabilities.find_one({"capability_key": mode["capability_key"], "status": "active"}, {"_id": 0})
    if not capability:
        raise AIStudioError("studio_capability_not_bootstrapped", "Platform AI admin must bootstrap the EC17 local mock catalog before execution", 409)
    prompt = await db.ai_prompt_versions.find_one({"capability_key": mode["capability_key"], "status": "published"}, {"_id": 0}, sort=[("published_at", -1)])
    context_packet = await _create_context_packet(user, fields, tool, mode)
    action = await ai_gateway.create_gateway_request(
        user,
        {
            "capability_key": mode["capability_key"],
            "prompt_version_id": prompt.get("id") if prompt else None,
            "context_packet_id": context_packet["id"],
            "idempotency_key": idempotency_key,
            "input_units": 0,
            "output_units": 0,
            "estimated_cost_micros": 0,
            "duration_ms": 0,
            "source_links": fields.get("source_links") or [],
            "simulate_result": "success",
        },
    )
    result = _build_local_result(tool, mode, fields)
    if mode["result_storage"] == "generated_asset":
        saved = await _save_generated_asset(user, tool, mode, fields, result, action, context_packet, prompt, idempotency_key)
    else:
        saved = await _save_editable_draft(user, tool, mode, fields, result, action, context_packet, prompt, idempotency_key)
    await _audit(user, "ai_studio.tool_run", saved["record_type"], saved["id"], f"AI Studio tool run: {tool['name']} - {mode['name']}")
    return saved


async def _find_existing_result(tenant_id: str, idempotency_key: str) -> Optional[dict[str, Any]]:
    filt = {"tenant_id": tenant_id, "provenance.idempotency_key": idempotency_key}
    existing = await db.ai_generated_assets.find_one(filt, {"_id": 0})
    if existing:
        result = serialize_doc(existing)
        result["record_type"] = "generated_asset"
        return result
    existing_draft = await db.ai_studio_editable_drafts.find_one(filt, {"_id": 0})
    if existing_draft:
        result = serialize_doc(existing_draft)
        result["record_type"] = "editable_draft"
        return result
    return None


async def _validate_context_and_permissions(user: dict[str, Any], context: dict[str, Any], tool: dict[str, Any], mode: dict[str, Any]) -> None:
    ctx_type = context.get("context_type") or context.get("source_entity_type")
    ctx_id = context.get("context_id") or context.get("source_entity_id")
    if not ctx_type or not ctx_id:
        return
    mapping = {
        "customer": ("customers", Perm.CUSTOMER_READ.value),
        "quote": ("quotes", Perm.QUOTE_READ.value),
        "order": ("orders", Perm.ORDER_READ.value),
        "invoice": ("invoices", Perm.INVOICE_READ.value),
        "webstore": ("webstores", Perm.WEBSTORE_MANAGE.value),
        "wrap_project": ("wrap_projects", Perm.WRAP_LAB_WRITE.value),
        "document": ("documents", Perm.DOCUMENT_READ.value),
        "file": ("files", Perm.DOCUMENT_READ.value),
    }
    if ctx_type not in mapping:
        raise AIStudioError("unsupported_context_type", "Unsupported AI Studio context type", 400)
    collection, perm = mapping[ctx_type]
    _require_perm(user, perm)
    doc = await getattr(db, collection).find_one({"tenant_id": user["tenant_id"], "id": ctx_id}, {"_id": 0})
    if not doc:
        raise AIStudioError("context_not_found", "Linked context was not found for this tenant", 404)
    if tool["tool_key"] == "social_post_builder":
        state = (context.get("publicity_permission_state") or "").lower()
        if not state:
            context["publicity_permission_state"] = "unknown"


async def _create_context_packet(user: dict[str, Any], fields: dict[str, Any], tool: dict[str, Any], mode: dict[str, Any]) -> dict[str, Any]:
    context = fields.get("context") or {}
    packet = AIContextPacket(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        source_entity_type=context.get("context_type") or context.get("source_entity_type"),
        source_entity_id=context.get("context_id") or context.get("source_entity_id"),
        source_links=fields.get("source_links") or [],
        consent_flags={"customer_publicity_confirmed": context.get("publicity_permission_state") == "confirmed"},
        payload_summary={
            "tool_key": tool["tool_key"],
            "mode_key": mode["mode_key"],
            "visible_context": context,
            "h7_local_mock": True,
        },
    ).model_dump()
    await db.ai_context_packets.insert_one(prepare_for_mongo(packet))
    return serialize_doc(packet)


def _build_local_result(tool: dict[str, Any], mode: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    inputs = fields.get("inputs") or {}
    prompt = inputs.get("prompt") or inputs.get("context_notes") or "No prompt supplied"
    warnings = list(mode.get("warnings") or [])
    if tool["tool_key"] == "social_post_builder":
        publicity_state = (inputs.get("publicity_permission_state") or (fields.get("context") or {}).get("publicity_permission_state") or "unknown").lower()
        if publicity_state != "confirmed":
            warnings.append("Customer/publicity permission is unknown or missing. Do not publish until durable authorization is confirmed.")
        content_json = {
            "primary_caption": f"Draft caption for: {prompt}",
            "alternate_caption": f"Alternate caption for: {prompt}",
            "image_alt_text": f"Alt text describing the completed sign project: {prompt}",
            "hashtags": ["#SignShop", "#CustomSigns"],
            "call_to_action": "Contact the shop to discuss a similar project.",
            "posting_suggestions": ["Review customer/photo-use permission before public posting."],
            "platform_versions": [{"platform": "Facebook", "text": f"Facebook-ready draft: {prompt}"}, {"platform": "Instagram", "text": f"Instagram-ready draft: {prompt}"}],
            "publicity_permission_state": publicity_state,
        }
    elif mode["capability_key"] == "studio.research.permit_guidance":
        content_json = {
            "information_checklist": ["Jurisdiction", "Project address", "Sign dimensions", "Illumination", "Mounting method"],
            "questions_for_local_authority": ["What permit type is required?", "Are illumination or zoning limits applicable?", "Which drawings or site plans are needed?"],
            "draft_project_description": f"Draft project description based on user-supplied information: {prompt}",
            "missing_information_warnings": ["Verify current requirements with the proper local authority."],
            "source_boundary": {"external_research_performed": False, "source_url": None, "access_date": None},
        }
    elif mode["mode_key"] == "historical_pricing_import_analysis":
        content_json = _mock_historical_import(fields)
    elif mode["mode_key"] == "contract_draft":
        warnings.append("Legal review required before use. This draft is not legal advice and is not a signature request.")
        content_json = {"document_sections": ["Parties", "Scope", "Pricing", "Terms", "Review notes"], "legal_review_required": True}
    elif mode["capability_key"].startswith("studio.image") or mode["capability_key"].startswith("studio.artwork"):
        content_json = {
            "concept_summary": f"Local mock concept for {mode['name']}: {prompt}",
            "production_ready": False,
            "label": "Concept / Mockup - Not Production-Ready",
            "source_image_preserved": bool(inputs.get("source_image_id")),
            "source_image_id": inputs.get("source_image_id"),
            "selected_region_or_mask": inputs.get("mask_description"),
            "preserve_area_instructions": inputs.get("preserve_area_instructions"),
            "reference_image_id": inputs.get("reference_image_id"),
            "output_dimensions": inputs.get("output_dimensions"),
            "external_provider_calls": 0,
        }
    else:
        content_json = {"draft": f"Local mock draft for {mode['name']}: {prompt}", "editable": True}
    return {
        "title": fields.get("title") or f"{mode['name']} Result",
        "content_text": content_json.get("draft") or content_json.get("concept_summary") or content_json.get("draft_project_description") or str(content_json),
        "content_json": content_json,
        "warnings": warnings,
    }


def _mock_historical_import(fields: dict[str, Any]) -> dict[str, Any]:
    inputs = fields.get("inputs") or {}
    file_type = str(inputs.get("source_file_type") or "").lower()
    return {
        "supported_file_types": ["pdf", "csv", "xlsx", "xls"],
        "source_file_type": file_type,
        "file_type_valid": file_type in {"pdf", "csv", "xlsx", "xls"},
        "source_preserved": True,
        "extracted_values": [
            {"field": "historical_job_or_product_type", "value": "mock sign job", "confidence": "mock"},
            {"field": "unit_price", "value_cents": 12500, "confidence": "mock"},
            {"field": "total_price", "value_cents": 25000, "confidence": "mock"},
        ],
        "proposed_pricing_foundation_mapping": [{"source_field": "unit_price", "target": "pricing_reference_only", "requires_approval": True}],
        "duplicate_signals": [{"signal": "same customer/date/total", "confidence": "mock"}],
        "warnings": ["Local mock extraction only. No OCR, file analysis provider, or current pricing mutation occurred."],
        "application_boundary": "Import application is deferred to an authorized canonical pricing workflow.",
    }


async def _save_generated_asset(user: dict[str, Any], tool: dict[str, Any], mode: dict[str, Any], fields: dict[str, Any], result: dict[str, Any], action: dict[str, Any], context_packet: dict[str, Any], prompt: Optional[dict[str, Any]], idempotency_key: Optional[str]) -> dict[str, Any]:
    context = fields.get("context") or {}
    doc = AIGeneratedAsset(
        tenant_id=user["tenant_id"],
        creator_user_id=user["id"],
        tool_key=tool["tool_key"],
        mode_key=mode["mode_key"],
        family_key=tool["family_key"],
        capability_key=mode["capability_key"],
        usage_band=mode["usage_band"],
        title=result["title"],
        asset_type=_asset_type_for(mode),
        content_text=result["content_text"],
        content_json=result["content_json"],
        provenance={"h7_local_mock": True, "external_provider_calls": 0, "idempotency_key": idempotency_key},
        warnings=result["warnings"],
        action_request_id=action["id"],
        ec16_prompt_version_id=prompt.get("id") if prompt else None,
        context_packet_id=context_packet["id"],
        source_asset_ids=fields.get("source_asset_ids") or [],
        source_links=fields.get("source_links") or [],
        parent_record_type=context.get("context_type"),
        parent_record_id=context.get("context_id"),
        context_summary=context,
    ).model_dump()
    await db.ai_generated_assets.insert_one(prepare_for_mongo(doc))
    saved = serialize_doc(doc)
    saved["record_type"] = "generated_asset"
    return saved


async def _save_editable_draft(user: dict[str, Any], tool: dict[str, Any], mode: dict[str, Any], fields: dict[str, Any], result: dict[str, Any], action: dict[str, Any], context_packet: dict[str, Any], prompt: Optional[dict[str, Any]], idempotency_key: Optional[str]) -> dict[str, Any]:
    context = fields.get("context") or {}
    doc = AIStudioEditableDraft(
        tenant_id=user["tenant_id"],
        creator_user_id=user["id"],
        tool_key=tool["tool_key"],
        mode_key=mode["mode_key"],
        family_key=tool["family_key"],
        capability_key=mode["capability_key"],
        usage_band=mode["usage_band"],
        draft_type=_draft_type_for(mode),
        title=result["title"],
        content_text=result["content_text"],
        content_json=result["content_json"],
        warnings=result["warnings"],
        action_request_id=action["id"],
        ec16_prompt_version_id=prompt.get("id") if prompt else None,
        context_packet_id=context_packet["id"],
        parent_record_type=context.get("context_type"),
        parent_record_id=context.get("context_id"),
    ).model_dump()
    doc["provenance"] = {"h7_local_mock": True, "external_provider_calls": 0, "idempotency_key": idempotency_key}
    await db.ai_studio_editable_drafts.insert_one(prepare_for_mongo(doc))
    saved = serialize_doc(doc)
    saved["record_type"] = "editable_draft"
    return saved


def _asset_type_for(mode: dict[str, Any]) -> str:
    if mode["capability_key"].startswith("studio.image"):
        return "image_concept"
    if mode["capability_key"].startswith("studio.artwork"):
        return "artwork_guidance"
    if mode["capability_key"] == "studio.text.campaign_plan":
        return "campaign_plan"
    if mode["capability_key"] == "studio.text.content_calendar":
        return "content_calendar"
    if mode["capability_key"] == "studio.text.proposal_draft":
        return "proposal_draft"
    return "document_draft"


def _draft_type_for(mode: dict[str, Any]) -> str:
    if mode["capability_key"] == "studio.text.email_draft":
        return "communication_draft"
    if mode["capability_key"] == "studio.text.review_reply":
        return "review_reply_draft"
    if mode["capability_key"] == "webstore.product_description":
        return "product_content_draft"
    if mode["capability_key"].startswith("pricing.") or mode["capability_key"].startswith("wrap_lab."):
        return "pricing_recommendation"
    return "content_draft"


async def list_generated_assets(user: dict[str, Any], *, tool_key: Optional[str] = None, status: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
    _require_perm(user, Perm.DOCUMENT_READ.value)
    filt: dict[str, Any] = {"tenant_id": user["tenant_id"]}
    if tool_key:
        filt["tool_key"] = tool_key
    if status:
        filt["status"] = status
    items = [serialize_doc(d) async for d in db.ai_generated_assets.find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)]
    return {"items": items, "total": len(items)}


async def get_generated_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any]:
    _require_perm(user, Perm.DOCUMENT_READ.value)
    doc = await db.ai_generated_assets.find_one({"tenant_id": user["tenant_id"], "id": asset_id}, {"_id": 0})
    if not doc:
        raise AIStudioError("generated_asset_not_found", "Generated asset not found", 404)
    return serialize_doc(doc)


async def archive_generated_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any]:
    _require_perm(user, Perm.DOCUMENT_WRITE.value)
    doc = await get_generated_asset(user, asset_id)
    now = _now_iso()
    await db.ai_generated_assets.update_one({"tenant_id": user["tenant_id"], "id": asset_id}, {"$set": {"status": "archived", "archived_at": now, "archived_by_user_id": user["id"], "updated_at": now}})
    await _audit(user, "ai_studio.asset_archived", "ai_generated_asset", asset_id, "Generated asset archived")
    return await get_generated_asset(user, asset_id)


async def list_editable_drafts(user: dict[str, Any], *, limit: int = 100) -> dict[str, Any]:
    _require_perm(user, Perm.AI_HISTORY_READ.value)
    items = [serialize_doc(d) async for d in db.ai_studio_editable_drafts.find({"tenant_id": user["tenant_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)]
    return {"items": items, "total": len(items)}


async def create_prompt_entry(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_PROMPT_WRITE.value)
    tool, mode = _tool_and_mode(fields.get("tool_key"), fields.get("mode_key"))
    doc = AIStudioPromptEntry(
        tenant_id=user["tenant_id"],
        owner_scope="tenant",
        tool_key=tool["tool_key"],
        mode_key=mode["mode_key"],
        capability_key=mode["capability_key"],
        name=str(fields.get("name") or "").strip(),
        description=fields.get("description"),
        category=tool["family_key"],
        tags=fields.get("tags") or [],
        required_variables=fields.get("required_variables") or [],
        optional_variables=fields.get("optional_variables") or [],
        template=str(fields.get("template") or "").strip(),
    ).model_dump()
    if not doc["name"] or not doc["template"]:
        raise AIStudioError("invalid_prompt", "Prompt name and template are required", 400)
    await db.ai_studio_prompt_entries.insert_one(prepare_for_mongo(doc))
    await _audit(user, "ai_studio.prompt_created", "ai_studio_prompt_entry", doc["id"], "AI Studio prompt created")
    return serialize_doc(doc)


async def update_prompt_entry(user: dict[str, Any], prompt_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_PROMPT_WRITE.value)
    doc = await db.ai_studio_prompt_entries.find_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"_id": 0})
    if not doc:
        raise AIStudioError("prompt_not_found", "Prompt not found", 404)
    locked = {"template", "tool_key", "mode_key", "required_variables", "optional_variables"}
    if doc.get("status") == "published" and locked.intersection(fields):
        raise AIStudioError("published_prompt_immutable", "Published prompt entries are immutable; copy or create a new version", 409)
    allowed = {k: v for k, v in fields.items() if k in {"name", "description", "tags", "template", "required_variables", "optional_variables"}}
    if not allowed:
        raise AIStudioError("no_updates", "No supported prompt updates provided", 400)
    allowed["updated_at"] = _now_iso()
    await db.ai_studio_prompt_entries.update_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"$set": prepare_for_mongo(allowed)})
    await _audit(user, "ai_studio.prompt_updated", "ai_studio_prompt_entry", prompt_id, "AI Studio prompt updated")
    return serialize_doc(await db.ai_studio_prompt_entries.find_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"_id": 0}))


async def publish_prompt_entry(user: dict[str, Any], prompt_id: str) -> dict[str, Any]:
    _require_perm(user, Perm.AI_PROMPT_WRITE.value)
    doc = await db.ai_studio_prompt_entries.find_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"_id": 0})
    if not doc:
        raise AIStudioError("prompt_not_found", "Prompt not found", 404)
    if doc.get("status") == "published":
        return serialize_doc(doc)
    now = _now_iso()
    await db.ai_studio_prompt_entries.update_one({"id": prompt_id}, {"$set": {"status": "published", "published_at": now, "published_by_user_id": user["id"], "updated_at": now}})
    await _audit(user, "ai_studio.prompt_published", "ai_studio_prompt_entry", prompt_id, "AI Studio prompt published")
    return serialize_doc(await db.ai_studio_prompt_entries.find_one({"id": prompt_id}, {"_id": 0}))


async def archive_prompt_entry(user: dict[str, Any], prompt_id: str) -> dict[str, Any]:
    _require_perm(user, Perm.AI_PROMPT_WRITE.value)
    now = _now_iso()
    result = await db.ai_studio_prompt_entries.update_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"$set": {"status": "archived", "archived_at": now, "archived_by_user_id": user["id"], "updated_at": now}})
    if result.matched_count == 0:
        raise AIStudioError("prompt_not_found", "Prompt not found", 404)
    await _audit(user, "ai_studio.prompt_archived", "ai_studio_prompt_entry", prompt_id, "AI Studio prompt archived")
    return serialize_doc(await db.ai_studio_prompt_entries.find_one({"tenant_id": user["tenant_id"], "id": prompt_id}, {"_id": 0}))


async def list_prompt_entries(user: dict[str, Any], *, tool_key: Optional[str] = None, mode_key: Optional[str] = None) -> dict[str, Any]:
    _require_perm(user, Perm.AI_PROMPT_READ.value)
    filt: dict[str, Any] = {"$or": [{"tenant_id": user["tenant_id"]}, {"owner_scope": "platform_starter"}], "status": {"$ne": "archived"}}
    if tool_key:
        filt["tool_key"] = tool_key
    if mode_key:
        filt["mode_key"] = mode_key
    items = [serialize_doc(d) async for d in db.ai_studio_prompt_entries.find(filt, {"_id": 0, "template": 0}).sort([("owner_scope", 1), ("name", 1)])]
    return {"items": items, "total": len(items)}


async def create_brand_context(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_TOOL_USE.value)
    doc = AIStudioBrandContext(
        tenant_id=user["tenant_id"],
        owner_type=fields.get("owner_type") or "tenant",
        owner_id=fields.get("owner_id"),
        source_asset_id=fields.get("source_asset_id"),
        name=str(fields.get("name") or "Suggested brand context"),
        status="suggested",
        logo_file_ids=fields.get("logo_file_ids") or [],
        brand_colors=fields.get("brand_colors") or [],
        typography_guidance=fields.get("typography_guidance"),
        brand_voice=fields.get("brand_voice"),
        audience=fields.get("audience"),
        business_description=fields.get("business_description"),
        values=fields.get("values") or [],
        approved_taglines=fields.get("approved_taglines") or [],
        preferred_wording=fields.get("preferred_wording") or [],
        prohibited_wording=fields.get("prohibited_wording") or [],
    ).model_dump()
    await db.ai_studio_brand_contexts.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def approve_brand_context(user: dict[str, Any], context_id: str) -> dict[str, Any]:
    _require_perm(user, Perm.AI_TOOL_USE.value)
    now = _now_iso()
    result = await db.ai_studio_brand_contexts.update_one({"tenant_id": user["tenant_id"], "id": context_id}, {"$set": {"status": "approved", "approved_by_user_id": user["id"], "approved_at": now, "updated_at": now}})
    if result.matched_count == 0:
        raise AIStudioError("brand_context_not_found", "Brand context not found", 404)
    await _audit(user, "ai_studio.brand_context_approved", "ai_studio_brand_context", context_id, "AI brand context approved")
    return serialize_doc(await db.ai_studio_brand_contexts.find_one({"tenant_id": user["tenant_id"], "id": context_id}, {"_id": 0}))


async def create_historical_import_analysis(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_TOOL_USE.value)
    _require_perm(user, Perm.PRICING_READ.value)
    file_type = str(fields.get("source_file_type") or "").lower()
    if file_type not in {"pdf", "csv", "xlsx", "xls"}:
        raise AIStudioError("unsupported_import_file_type", "Supported import file types are PDF, CSV, XLSX, and XLS", 400)
    if int(fields.get("source_file_size_bytes") or 0) > 20_000_000:
        raise AIStudioError("import_file_too_large", "Historical pricing import source file is too large", 413)
    doc = AIStudioPricingImportAnalysis(
        tenant_id=user["tenant_id"],
        created_by_user_id=user["id"],
        source_file_id=fields.get("source_file_id"),
        source_file_name=fields.get("source_file_name"),
        source_file_type=file_type,
        source_file_size_bytes=int(fields.get("source_file_size_bytes") or 0),
        extracted_values=_mock_historical_import({"inputs": fields})["extracted_values"],
        proposed_mappings=_mock_historical_import({"inputs": fields})["proposed_pricing_foundation_mapping"],
        duplicate_signals=_mock_historical_import({"inputs": fields})["duplicate_signals"],
        warnings=_mock_historical_import({"inputs": fields})["warnings"],
    ).model_dump()
    await db.ai_studio_pricing_import_analyses.insert_one(prepare_for_mongo(doc))
    await _audit(user, "ai_studio.pricing_import_analysis_created", "ai_studio_pricing_import_analysis", doc["id"], "Historical pricing import analysis created")
    return serialize_doc(doc)


async def create_pricing_setup_proposal(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    _require_perm(user, Perm.AI_TOOL_USE.value)
    _require_perm(user, Perm.PRICING_WRITE.value)
    sections = fields.get("sections") or [
        {"section": "Shop Profile", "status": "proposed"},
        {"section": "Employees and Labor", "status": "proposed"},
        {"section": "Monthly Overhead", "status": "proposed"},
        {"section": "Billable Hours and Utilization", "status": "proposed"},
        {"section": "Materials and Waste", "status": "proposed"},
        {"section": "Margin and Profit Goals", "status": "proposed"},
    ]
    doc = AIStudioPricingSetupProposal(
        tenant_id=user["tenant_id"],
        created_by_user_id=user["id"],
        sections=sections,
        proposed_defaults=fields.get("proposed_defaults") or [],
        warnings=["Proposal boundary only. No Pricing Foundation values changed."],
        comparison=fields.get("comparison") or {},
    ).model_dump()
    await db.ai_studio_pricing_setup_proposals.insert_one(prepare_for_mongo(doc))
    await _audit(user, "ai_studio.pricing_setup_proposal_created", "ai_studio_pricing_setup_proposal", doc["id"], "Pricing setup proposal created")
    return serialize_doc(doc)


async def list_activity(user: dict[str, Any], *, tool_key: Optional[str] = None, mode_key: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
    _require_perm(user, Perm.AI_HISTORY_READ.value)
    filt: dict[str, Any] = {"tenant_id": user["tenant_id"]}
    if tool_key:
        filt["tool_key"] = tool_key
    if mode_key:
        filt["mode_key"] = mode_key
    assets = [serialize_doc(d) | {"record_type": "generated_asset"} async for d in db.ai_generated_assets.find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)]
    drafts = [serialize_doc(d) | {"record_type": "editable_draft"} async for d in db.ai_studio_editable_drafts.find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)]
    items = sorted(assets + drafts, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]
    return {"items": items, "total": len(items), "hidden_internal_fields": ["provider_payload", "hidden_prompt", "raw_exception", "other_tenant_data"]}


async def _audit(user: dict[str, Any], action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "ai-studio"),
        module="ai_studio",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )
