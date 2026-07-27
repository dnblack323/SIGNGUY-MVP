"""Authenticated Workspace Dock persistence models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseDoc

WorkspaceStatus = Literal["open", "recent"]


class WorkspaceDockItem(BaseModel):
    id: str
    workspace_type: str
    workspace_key: str
    record_id: Optional[str] = None
    record_number: Optional[str] = None
    label: str
    pathname: str
    query_params: dict[str, str] = Field(default_factory=dict)
    view_state: dict[str, Any] = Field(default_factory=dict)
    active: bool = False
    pinned: bool = False
    position: Optional[int] = None
    scroll_position: int = 0
    dirty: bool = False
    status: WorkspaceStatus = "open"
    last_opened_at: datetime
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkspaceDockState(BaseDoc):
    tenant_id: str
    user_id: str
    open_workspaces: list[WorkspaceDockItem] = Field(default_factory=list)
    recent_workspaces: list[WorkspaceDockItem] = Field(default_factory=list)
