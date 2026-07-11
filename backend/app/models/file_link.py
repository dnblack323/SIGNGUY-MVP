"""EC2 — Polymorphic File Link.

Distinct from the existing MVP `Attachment` (which anchors uploaded files to
business records). A FileLink models a lightweight cross-reference between
a stored file and an *arbitrary* parent (including future portal, webstore,
or wrap-lab contexts) with an optional role tag.

MVP `Attachment` remains authoritative for order/quote/invoice/customer
attachments; this table backs future portal + document-share flows.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from .base import BaseDoc


class FileLink(BaseDoc):
    tenant_id: str
    file_id: str
    parent_type: str       # e.g. "webstore_product", "wrap_lab_project", "portal_message"
    parent_id: str
    role: Optional[str] = None    # e.g. "primary", "reference", "signed_pdf"
    created_by: Optional[str] = None
    archived: bool = False
