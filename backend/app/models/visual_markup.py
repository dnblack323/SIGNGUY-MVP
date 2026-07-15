"""EC10 Phase 10C — Visual Markup (staff-only annotation over an existing
uploaded image or PDF page).

`VisualMarkup` is the workspace attached to ONE source asset (an existing
`FileRecord`, never copied/overwritten). `MarkupVersion` is the append-only
history of saved annotation states for that workspace — editing always
creates a NEW version; prior versions are immutable.

`structured_markup_json` stores ONLY Fabric.js annotation objects (shapes/
text/arrows/pins) — it never contains the source image/PDF bytes. The
background (the source asset) is reconstructed client-side from
`source_file_id`/`source_page_number` on every open; only the annotation
layer is persisted here.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

from .base import BaseDoc

MarkupSourceFileType = Literal["image", "pdf"]
MarkupStatus = Literal["active", "archived"]


class VisualMarkup(BaseDoc):
    tenant_id: str
    source_file_id: str
    source_file_type: MarkupSourceFileType
    source_page_number: Optional[int] = None  # required + validated when source_file_type == "pdf"

    intake_id: Optional[str] = None
    intake_item_id: Optional[str] = None
    proof_id: Optional[str] = None  # future-compatible reference — Proofs integration is not built in 10C

    current_version_id: Optional[str] = None
    current_version_number: int = 0
    status: MarkupStatus = "active"

    title: Optional[str] = None
    description: Optional[str] = None

    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None
    archived_at: Optional[str] = None


class MarkupVersion(BaseDoc):
    tenant_id: str
    visual_markup_id: str
    version_number: int

    # Coordinate/resize contract (§7): the canvas resolution this version was
    # saved at, plus the on-screen source dimensions at that same moment —
    # always equal in this implementation (the source fills the canvas), but
    # tracked separately so a future non-1:1 layout doesn't require a schema
    # change. Reopening at a different container width recomputes a uniform
    # scale factor (`display_width / canvas_width`) and applies it via
    # Fabric's `canvas.setZoom()`, never by rewriting stored coordinates.
    canvas_width: int
    canvas_height: int
    source_display_width: int
    source_display_height: int
    coordinate_space: str = "canvas_pixels_v1"

    structured_markup_json: dict[str, Any]  # {"objects": [...]} — annotation objects only, no image bytes
    rendered_preview_file_id: Optional[str] = None  # separate File record — a derivative, never authoritative
    change_summary: Optional[str] = None

    created_by_user_id: Optional[str] = None
    parent_version_id: Optional[str] = None
    status: MarkupStatus = "active"
