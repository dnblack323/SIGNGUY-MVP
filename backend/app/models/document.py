"""EC6 — Asset Library Document metadata layer.

Sits over the existing MVP `FileRecord`. A Document tracks logical asset
identity, categorization, review markers, and versioning. The actual bytes
live in the underlying `file_records` collection via `current_file_id`.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

DocumentSourceType = Literal["upload", "generated", "external", "portal_upload"]
DocumentVisibility = Literal["internal", "customer_visible"]
DocumentCategory = Literal[
    "general", "artwork", "proof", "contract", "invoice", "quote",
    "work_order_summary", "customer_intake", "signature_evidence", "ai_generated",
]


class Document(BaseDoc):
    tenant_id: str
    title: str
    category: DocumentCategory = "general"
    source_type: DocumentSourceType = "upload"
    requires_review: bool = False
    current_file_id: Optional[str] = None
    version: int = 1
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    visibility: DocumentVisibility = "internal"
    customer_id: Optional[str] = None      # optional owning customer
    created_by: Optional[str] = None
    archived: bool = False


class DocumentVersion(BaseDoc):
    tenant_id: str
    document_id: str
    version: int
    file_id: str
    notes: Optional[str] = None
    created_by: Optional[str] = None
