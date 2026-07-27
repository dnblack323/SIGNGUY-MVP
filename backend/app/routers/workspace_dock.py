"""Authenticated Workspace Dock API."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_user
from ..services.workspace_dock import (
    WorkspaceDockError,
    activate_workspace,
    close_workspace,
    list_workspace_state,
    open_workspace,
    remove_recent_workspace,
    reopen_recent_workspace,
    reorder_workspaces,
    set_pinned,
    update_workspace,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceOpenIn(BaseModel):
    workspace_type: str
    record_id: Optional[str] = None
    label: Optional[str] = None
    pathname: str
    query_params: dict[str, str] = Field(default_factory=dict)
    view_state: dict[str, Any] = Field(default_factory=dict)
    scroll_position: int = 0
    pinned: bool = False


class WorkspacePatchIn(BaseModel):
    label: Optional[str] = None
    pathname: Optional[str] = None
    query_params: Optional[dict[str, str]] = None
    view_state: Optional[dict[str, Any]] = None
    scroll_position: Optional[int] = None
    dirty: Optional[bool] = None


class WorkspaceReorderIn(BaseModel):
    workspace_ids: list[str]


def _raise(exc: WorkspaceDockError) -> None:
    detail: str | dict[str, Any]
    if exc.extra:
        detail = {"message": str(exc), **exc.extra}
    else:
        detail = str(exc)
    raise HTTPException(status_code=exc.status_code, detail=detail)


@router.get("")
async def list_workspaces(user: dict = Depends(get_current_user)) -> dict:
    return await list_workspace_state(user["tenant_id"], user["id"])


@router.get("/recent")
async def list_recent_workspaces(user: dict = Depends(get_current_user)) -> dict:
    state = await list_workspace_state(user["tenant_id"], user["id"])
    return {"recent_workspaces": state["recent_workspaces"], "limits": state["limits"]}


@router.post("/open", status_code=201)
async def open_workspace_route(payload: WorkspaceOpenIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await open_workspace(user["tenant_id"], user, payload.model_dump())
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/{workspace_id}/activate")
async def activate_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await activate_workspace(user["tenant_id"], user, workspace_id)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.patch("/{workspace_id}")
async def patch_workspace_route(workspace_id: str, payload: WorkspacePatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await update_workspace(user["tenant_id"], user["id"], workspace_id, payload.model_dump(exclude_unset=True))
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/{workspace_id}/pin")
async def pin_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await set_pinned(user["tenant_id"], user["id"], workspace_id, True)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/{workspace_id}/unpin")
async def unpin_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await set_pinned(user["tenant_id"], user["id"], workspace_id, False)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/reorder")
async def reorder_workspace_route(payload: WorkspaceReorderIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await reorder_workspaces(user["tenant_id"], user["id"], payload.workspace_ids)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/{workspace_id}/close")
async def close_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await close_workspace(user["tenant_id"], user["id"], workspace_id)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.post("/recent/{workspace_id}/reopen")
async def reopen_recent_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await reopen_recent_workspace(user["tenant_id"], user, workspace_id)
    except WorkspaceDockError as exc:
        _raise(exc)


@router.delete("/recent/{workspace_id}")
async def remove_recent_workspace_route(workspace_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await remove_recent_workspace(user["tenant_id"], user["id"], workspace_id)
    except WorkspaceDockError as exc:
        _raise(exc)
