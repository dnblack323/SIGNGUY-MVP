"""Webstore detail, status, lifecycle, and readiness routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("/{webstore_id}")
async def get_webstore(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.get_webstore(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.patch("/{webstore_id}")
async def update_webstore(webstore_id: str, payload: WebstorePatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_webstore(user, webstore_id, payload.model_dump(exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/status")
async def set_status(webstore_id: str, payload: StatusIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_webstore_status(user, webstore_id, payload.status, reason=payload.reason)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/lifecycle")
async def transition_lifecycle(webstore_id: str, payload: LifecycleTransitionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.transition_webstore_lifecycle(user, webstore_id, payload.state, reason=payload.reason)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/relaunch")
async def relaunch(webstore_id: str, payload: RelaunchIn, user: dict = Depends(require_permission(Perm.WEBSTORE_MANAGE))) -> dict:
    try:
        return await svc.relaunch_webstore(user, webstore_id, reason=payload.reason)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/lifecycle-events")
async def lifecycle_events(webstore_id: str, limit: int = Query(30, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_lifecycle_events(user, webstore_id, limit=limit)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/launch-readiness")
async def launch_readiness(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.launch_readiness(user, webstore_id)
    except WebstoreError as e:
        _raise(e)
