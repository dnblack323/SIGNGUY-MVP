"""EC2 — Cross-entity document link.

Some documents (quotes, invoices, work orders) can be linked to multiple
business entities (a customer + an order + a project). DocumentLink
records those many-to-many associations without duplicating the file.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from .base import BaseDoc


class DocumentLink(BaseDoc):
    tenant_id: str
    document_id: str        # references the underlying document (file_id)
    entity_type: str
    entity_id: str
    # EC8 phase 8e — when an entity_type is portal-visible (e.g. "equipment",
    # "training_definition"), a link is only shown to the Employee/Customer
    # Portal if this is explicitly True. Defaults to False (private/internal)
    # so linking a document never silently exposes it.
    portal_visible: bool = False
    created_by: Optional[str] = None
