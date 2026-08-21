"""Webstore branding routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("/{webstore_id}/branding")
async def get_branding(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await branding_svc.get_staff_branding(user, webstore_id)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.patch("/{webstore_id}/branding/draft")
async def save_branding_draft(webstore_id: str, payload: BrandingDraftIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await branding_svc.save_staff_draft(user, webstore_id, payload.content)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.post("/{webstore_id}/branding/request-review")
async def request_branding_review(webstore_id: str, payload: BrandingReviewIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await branding_svc.request_review(user, webstore_id, note=payload.note)
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.post("/{webstore_id}/branding/publish")
async def publish_branding(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await branding_svc.publish(user, webstore_id)
    except WebstoreBrandingError as e:
        _raise_branding(e)
