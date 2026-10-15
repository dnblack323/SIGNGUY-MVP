"""F2 — Per-user Home dashboard layout preferences.

One document per (tenant_id, user_id). Holds only layout choices (widget
order, hidden widgets, collapsed list widgets); no business data.
"""
from __future__ import annotations

from pydantic import Field

from .base import BaseDoc


class DashboardPreferences(BaseDoc):
    tenant_id: str
    user_id: str
    version: int = 1
    order: list[str] = Field(default_factory=list)
    hidden: list[str] = Field(default_factory=list)
    collapsed: list[str] = Field(default_factory=list)
