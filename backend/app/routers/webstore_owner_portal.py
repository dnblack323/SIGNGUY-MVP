"""EC14 - Webstore owner portal routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from ..deps_portal import get_current_portal_identity
from ..services import webstore_setup as setup_svc
from ..services import webstore_branding as branding_svc
from ..services import webstores as svc
from ..services.webstore_branding import WebstoreBrandingError
from ..services.webstore_setup import WebstoreSetupError
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/portal/webstores", tags=["portal-webstores"])


def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_setup(e: WebstoreSetupError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_branding(e: WebstoreBrandingError) -> None:
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


class BrandingDraftIn(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)


class BrandingReviewIn(BaseModel):
    note: str | None = None


class InvitationAcceptIn(BaseModel):
    token: str


class PacketChangeRequestIn(BaseModel):
    category: str = "general"
    affected_item_ref: str | None = None
    comment: str


class PacketDecisionIn(BaseModel):
    comment: str | None = None


class ProductApprovalDecisionIn(BaseModel):
    decision: str
    comment: str | None = None


class TermsAcceptIn(BaseModel):
    terms_version: str | None = None


async def _read_upload_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    max_bytes = setup_svc.MAX_SETUP_FILE_BYTES
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise WebstoreSetupError("file_too_large", "Setup files must be 50 MB or smaller", 413)
        chunks.append(chunk)
    return b"".join(chunks)


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


@router.get("/{webstore_id}/branding")
async def get_branding(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await branding_svc.get_portal_branding(identity, webstore_id)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.patch("/{webstore_id}/branding/draft")
async def save_branding_draft(webstore_id: str, payload: BrandingDraftIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await branding_svc.save_portal_draft(identity, webstore_id, payload.content)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.post("/{webstore_id}/branding/request-review")
async def request_branding_review(webstore_id: str, payload: BrandingReviewIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await branding_svc.request_review(identity, webstore_id, portal=True, note=payload.note)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.post("/{webstore_id}/branding/approve")
async def approve_branding(webstore_id: str, payload: BrandingReviewIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await branding_svc.owner_approve(identity, webstore_id, note=payload.note)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.post("/{webstore_id}/branding/request-changes")
async def request_branding_changes(webstore_id: str, payload: BrandingReviewIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await branding_svc.owner_request_changes(identity, webstore_id, note=payload.note or "")
    except WebstoreBrandingError as e:
        _raise_branding(e)


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
        data = await _read_upload_limited(file)
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
async def approve_launch(webstore_id: str, packet_id: str, payload: PacketDecisionIn | None = Body(default=None), identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_approve_launch_packet(identity, webstore_id, packet_id, (payload or PacketDecisionIn()).model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/approval")
async def decide_product_approval(webstore_id: str, product_id: str, payload: ProductApprovalDecisionIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_decide_product_approval(identity, webstore_id, product_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/mockups/{mockup_id}/approval")
async def decide_mockup_approval(webstore_id: str, mockup_id: str, payload: ProductApprovalDecisionIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_decide_mockup_approval(identity, webstore_id, mockup_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/request-changes")
async def request_launch_changes(webstore_id: str, packet_id: str, payload: PacketChangeRequestIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_request_launch_packet_changes(identity, webstore_id, packet_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/reject")
async def reject_launch(webstore_id: str, packet_id: str, payload: PacketDecisionIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_reject_launch_packet(identity, webstore_id, packet_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/terms/accept")
async def accept_terms(webstore_id: str, payload: TermsAcceptIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_accept_terms(identity, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)
