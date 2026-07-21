"""EC19 Help Center and contextual help routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import get_current_user, require_permission
from ..services import help_center as svc
from ..services.help_center import HelpCenterError

router = APIRouter(prefix="/help", tags=["help"])


def _raise(ex: HelpCenterError) -> None:
    raise HTTPException(status_code=ex.status_code, detail=ex.detail)


class HelpArticleIn(BaseModel):
    slug: str
    title: str
    category: str = "general"
    body: str
    status: str = "draft"
    module: Optional[str] = None
    audience: list[str] = Field(default_factory=lambda: ["owner", "admin", "staff"])
    search_keywords: list[str] = Field(default_factory=list)


class HelpStatusIn(BaseModel):
    status: str


class HelpFeedbackIn(BaseModel):
    article_id: Optional[str] = None
    article_slug: Optional[str] = None
    helpful: Optional[bool] = None
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None


class SupportEscalationIn(BaseModel):
    subject: str
    message: str
    source_surface: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.get("/articles")
async def list_articles(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    user: dict = Depends(require_permission(Perm.HELP_READ)),
) -> dict:
    return await svc.search_help(q=q, category=category, module=module, include_archived=include_archived)


@router.get("/articles/{slug}")
async def get_article(slug: str, include_archived: bool = Query(False), user: dict = Depends(require_permission(Perm.HELP_READ))) -> dict:
    try:
        return await svc.get_article(slug, include_archived=include_archived)
    except HelpCenterError as ex:
        _raise(ex)


@router.post("/platform/articles", status_code=201)
async def upsert_article(payload: HelpArticleIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.upsert_article(user, payload.model_dump())
    except HelpCenterError as ex:
        _raise(ex)


@router.post("/platform/articles/{slug}/status")
async def transition_article(slug: str, payload: HelpStatusIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.transition_article(user, slug, payload.status)
    except HelpCenterError as ex:
        _raise(ex)


@router.get("/contextual/{surface_key}")
async def get_contextual(surface_key: str, module: Optional[str] = Query(None), user: dict = Depends(require_permission(Perm.HELP_READ))) -> dict:
    return await svc.contextual_help(surface_key, module=module)


@router.get("/role-guides/{role}")
async def get_role_guides(role: str, user: dict = Depends(require_permission(Perm.HELP_READ))) -> dict:
    return await svc.role_guides(role)


@router.post("/feedback", status_code=201)
async def post_feedback(payload: HelpFeedbackIn, user: dict = Depends(require_permission(Perm.HELP_READ))) -> dict:
    return await svc.feedback(user, payload.model_dump())


@router.post("/support/escalations", status_code=201)
async def create_support_escalation(payload: SupportEscalationIn, user: dict = Depends(require_permission(Perm.SUPPORT_WRITE))) -> dict:
    try:
        return await svc.support_escalation(user, payload.model_dump())
    except HelpCenterError as ex:
        _raise(ex)


@router.get("/billing/failed-subscription")
async def failed_subscription_guidance(user: dict = Depends(require_permission(Perm.SUBSCRIPTION_READ))) -> dict:
    return await svc.failed_subscription_guidance(user)
