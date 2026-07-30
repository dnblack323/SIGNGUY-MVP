"""EC14 - Webstore owner portal routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from ..deps_portal import get_current_portal_identity
from ..services import webstore_setup as setup_svc
from ..services import webstores as svc
from ..services.webstore_setup import WebstoreSetupError
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/portal/webstores", tags=["portal-webstores"])


def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_setup(e: WebstoreSetupError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _webstore_identity(identity: dict = Depends(get_current_portal_identity)) -> dict:
    perms = set(identity.get("permissions") or [])
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise HTTPException(status_code=403, detail="Webstore portal access required")
    if not ({"portal:webstore_owner_admin", "portal:webstore_manager_ops"} & perms):
        raise HTTPException(status_code=403, detail="Missing portal permission: portal:webstore_owner_admin")
    return identity


class QuestionnaireIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    known_products: list[dict[str, Any]] = Field(default_factory=list)
    open_to_suggestions: bool = True
    missing_info_flags: list[str] = Field(default_factory=list)


class InvitationAcceptIn(BaseModel):
    token: str


@router.get("")
async def list_owned(identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_portal_list(identity)
    except WebstoreError as e:
        _raise(e)


@router.post("/invitations/accept")
async def accept_invitation(payload: InvitationAcceptIn) -> dict:
    try:
        return await setup_svc.accept_invitation(payload.token)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}")
async def detail(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_portal_detail(identity, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/questionnaire")
async def questionnaire(webstore_id: str, payload: QuestionnaireIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await setup_svc.submit_questionnaire(identity, webstore_id, payload.model_dump())
    except WebstoreError as e:
        _raise(e)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/questionnaire")
async def get_questionnaire(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await setup_svc.owner_questionnaire(identity, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/draft")
async def questionnaire_draft(webstore_id: str, payload: QuestionnaireIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await setup_svc.save_questionnaire_draft(identity, webstore_id, payload.model_dump())
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-progress")
async def setup_progress(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await setup_svc.setup_progress_for_portal(identity, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-files")
async def setup_files(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await setup_svc.portal_list_setup_files(identity, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/setup-files", status_code=201)
async def upload_setup_file(
    webstore_id: str,
    category: str = Form(...),
    notes: str | None = Form(None),
    replaces_file_id: str | None = Form(None),
    file: UploadFile = File(...),
    identity: dict = Depends(_webstore_identity),
) -> dict:
    try:
        data = await file.read()
        return await setup_svc.portal_upload_setup_file(
            identity,
            webstore_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            category=category,
            notes=notes,
            replaces_file_id=replaces_file_id,
        )
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-files/{file_id}/download")
async def download_setup_file(webstore_id: str, file_id: str, identity: dict = Depends(_webstore_identity)) -> Response:
    try:
        await setup_svc.setup_progress_for_portal(identity, webstore_id)
        doc, data, content_type = await setup_svc.download_setup_file(identity["tenant_id"], webstore_id, file_id)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{doc.get("file_name", "setup-file")}"'},
        )
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/approve")
async def approve_launch(webstore_id: str, packet_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_approve_launch_packet(identity, webstore_id, packet_id)
    except WebstoreError as e:
        _raise(e)
