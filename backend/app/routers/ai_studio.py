"""EC17 Studio AI tools, prompt library, generated assets, and activity routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import get_current_user, require_permission
from ..services import ai_studio as svc
from ..services.ai_studio import AIStudioError

router = APIRouter(prefix="/ai-studio", tags=["ai-studio"])


def _raise(exc: AIStudioError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


class ToolRunIn(BaseModel):
    tool_key: str
    mode_key: str
    title: Optional[str] = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    source_asset_ids: list[str] = Field(default_factory=list)
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


class PromptEntryIn(BaseModel):
    tool_key: str
    mode_key: str
    name: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    required_variables: list[str] = Field(default_factory=list)
    optional_variables: list[str] = Field(default_factory=list)
    template: str


class PromptEntryUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    required_variables: Optional[list[str]] = None
    optional_variables: Optional[list[str]] = None
    template: Optional[str] = None


class BrandContextIn(BaseModel):
    owner_type: str = "tenant"
    owner_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    name: str = "Suggested brand context"
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


class HistoricalImportIn(BaseModel):
    source_file_id: Optional[str] = None
    source_file_name: str
    source_file_type: str
    source_file_size_bytes: int = 0


class PricingSetupProposalIn(BaseModel):
    sections: list[dict[str, Any]] = Field(default_factory=list)
    proposed_defaults: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, Any] = Field(default_factory=dict)


@router.get("/catalog")
async def catalog(user: dict = Depends(require_permission(Perm.AI_TOOL_USE))) -> dict:
    return svc.list_catalog()


@router.get("/catalog/{tool_key}")
async def catalog_tool(tool_key: str, user: dict = Depends(require_permission(Perm.AI_TOOL_USE))) -> dict:
    try:
        return svc.get_tool(tool_key)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/platform/bootstrap", status_code=201)
async def bootstrap_platform_catalog(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bootstrap_platform_catalog(user)
    except (AIStudioError, svc.ai_gateway.AIGatewayError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/runs", status_code=201)
async def run_tool(payload: ToolRunIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.run_tool(user, payload.model_dump(exclude_none=True))
    except (AIStudioError, svc.ai_gateway.AIGatewayError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/generated-assets")
async def generated_assets(
    tool_key: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=250),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_generated_assets(user, tool_key=tool_key, status=status, limit=limit)
    except AIStudioError as exc:
        _raise(exc)


@router.get("/generated-assets/{asset_id}")
async def generated_asset(asset_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.get_generated_asset(user, asset_id)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/generated-assets/{asset_id}/archive")
async def archive_generated_asset(asset_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.archive_generated_asset(user, asset_id)
    except AIStudioError as exc:
        _raise(exc)


@router.get("/drafts")
async def editable_drafts(limit: int = Query(100, ge=1, le=250), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_editable_drafts(user, limit=limit)
    except AIStudioError as exc:
        _raise(exc)


@router.get("/prompts")
async def prompt_entries(
    tool_key: Optional[str] = Query(None),
    mode_key: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_prompt_entries(user, tool_key=tool_key, mode_key=mode_key)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/prompts", status_code=201)
async def create_prompt_entry(payload: PromptEntryIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_prompt_entry(user, payload.model_dump())
    except AIStudioError as exc:
        _raise(exc)


@router.patch("/prompts/{prompt_id}")
async def update_prompt_entry(prompt_id: str, payload: PromptEntryUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_prompt_entry(user, prompt_id, payload.model_dump(exclude_unset=True))
    except AIStudioError as exc:
        _raise(exc)


@router.post("/prompts/{prompt_id}/publish")
async def publish_prompt_entry(prompt_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.publish_prompt_entry(user, prompt_id)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/prompts/{prompt_id}/archive")
async def archive_prompt_entry(prompt_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.archive_prompt_entry(user, prompt_id)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/brand-contexts", status_code=201)
async def create_brand_context(payload: BrandContextIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_brand_context(user, payload.model_dump(exclude_none=True))
    except AIStudioError as exc:
        _raise(exc)


@router.post("/brand-contexts/{context_id}/approve")
async def approve_brand_context(context_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.approve_brand_context(user, context_id)
    except AIStudioError as exc:
        _raise(exc)


@router.post("/pricing/historical-import-analyses", status_code=201)
async def create_historical_import(payload: HistoricalImportIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_historical_import_analysis(user, payload.model_dump(exclude_none=True))
    except AIStudioError as exc:
        _raise(exc)


@router.post("/pricing/setup-proposals", status_code=201)
async def create_pricing_setup_proposal(payload: PricingSetupProposalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_pricing_setup_proposal(user, payload.model_dump())
    except AIStudioError as exc:
        _raise(exc)


@router.get("/activity")
async def activity(
    tool_key: Optional[str] = Query(None),
    mode_key: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=250),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_activity(user, tool_key=tool_key, mode_key=mode_key, limit=limit)
    except AIStudioError as exc:
        _raise(exc)
