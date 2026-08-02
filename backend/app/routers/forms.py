"""Shared form maker routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import forms_service
from ..services.forms_service import FormsError

router = APIRouter(prefix="/forms", tags=["forms"])
public_router = APIRouter(prefix="/public/forms", tags=["public-forms"])


def _raise(error: FormsError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail)


class FormTemplateIn(BaseModel):
    name: str
    module: str = "general"
    context_type: str = "general"
    description: Optional[str] = None
    status: str = "draft"
    sections: list[dict[str, Any]] = Field(default_factory=list)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    mapping_config: dict[str, Any] = Field(default_factory=dict)
    private_config: dict[str, Any] = Field(default_factory=dict)
    source_template_id: Optional[str] = None


class FormTemplatePatchIn(BaseModel):
    name: Optional[str] = None
    module: Optional[str] = None
    context_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    sections: Optional[list[dict[str, Any]]] = None
    questions: Optional[list[dict[str, Any]]] = None
    mapping_config: Optional[dict[str, Any]] = None
    private_config: Optional[dict[str, Any]] = None


class FormRequestIn(BaseModel):
    template_id: str
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    status: str = "pending"
    expires_at: Optional[str] = None
    consent_metadata: dict[str, Any] = Field(default_factory=dict)


class FormResponseIn(BaseModel):
    respondent_email: Optional[str] = None
    respondent_name: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    consent_metadata: dict[str, Any] = Field(default_factory=dict)


class FormResponseReviewIn(BaseModel):
    mapping_results: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/templates")
async def list_templates(
    module: Optional[str] = Query(None),
    context_type: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    user: dict = Depends(require_permission(Perm.TEMPLATE_READ)),
) -> dict:
    try:
        return await forms_service.list_templates(
            tenant_id=user["tenant_id"],
            module=module,
            context_type=context_type,
            include_archived=include_archived,
        )
    except FormsError as error:
        _raise(error)


@router.post("/templates", status_code=201)
async def create_template(payload: FormTemplateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.create_template(tenant_id=user["tenant_id"], user=user, payload=payload.model_dump())
    except FormsError as error:
        _raise(error)


@router.get("/templates/{template_id}")
async def get_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    try:
        return await forms_service.get_template(tenant_id=user["tenant_id"], template_id=template_id)
    except FormsError as error:
        _raise(error)


@router.patch("/templates/{template_id}")
async def update_template(template_id: str, payload: FormTemplatePatchIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.update_template(
            tenant_id=user["tenant_id"],
            template_id=template_id,
            user=user,
            payload=payload.model_dump(exclude_unset=True),
        )
    except FormsError as error:
        _raise(error)


@router.post("/templates/{template_id}/publish")
async def publish_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.update_template(tenant_id=user["tenant_id"], template_id=template_id, user=user, payload={"status": "published"})
    except FormsError as error:
        _raise(error)


@router.post("/templates/{template_id}/archive")
async def archive_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.update_template(tenant_id=user["tenant_id"], template_id=template_id, user=user, payload={"status": "archived"})
    except FormsError as error:
        _raise(error)


@router.post("/templates/{template_id}/duplicate", status_code=201)
async def duplicate_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.duplicate_template(tenant_id=user["tenant_id"], template_id=template_id, user=user)
    except FormsError as error:
        _raise(error)


@router.get("/requests")
async def list_requests(
    context_type: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.TEMPLATE_READ)),
) -> dict:
    try:
        return await forms_service.list_requests(tenant_id=user["tenant_id"], context_type=context_type, context_id=context_id)
    except FormsError as error:
        _raise(error)


@router.post("/requests", status_code=201)
async def create_request(payload: FormRequestIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.create_request(tenant_id=user["tenant_id"], user=user, payload=payload.model_dump())
    except FormsError as error:
        _raise(error)


@router.get("/responses")
async def list_responses(
    template_id: Optional[str] = Query(None),
    context_type: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.TEMPLATE_READ)),
) -> dict:
    try:
        return await forms_service.list_responses(
            tenant_id=user["tenant_id"],
            template_id=template_id,
            context_type=context_type,
            context_id=context_id,
        )
    except FormsError as error:
        _raise(error)


@router.post("/responses/{response_id}/review")
async def review_response(response_id: str, payload: FormResponseReviewIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await forms_service.review_response(
            tenant_id=user["tenant_id"],
            response_id=response_id,
            user=user,
            mapping_results=payload.mapping_results,
        )
    except FormsError as error:
        _raise(error)


@public_router.get("/requests/{token}")
async def get_public_request(token: str) -> dict:
    try:
        return await forms_service.get_request_by_token(raw_token=token)
    except FormsError as error:
        _raise(error)


@public_router.post("/requests/{token}/responses", status_code=201)
async def submit_public_response(token: str, payload: FormResponseIn) -> dict:
    try:
        return await forms_service.submit_response_by_token(raw_token=token, payload=payload.model_dump())
    except FormsError as error:
        _raise(error)
