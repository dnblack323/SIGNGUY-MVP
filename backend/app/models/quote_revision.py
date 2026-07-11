"""EC3 — Quote Revision (immutable snapshot).

A revision captures the full customer-visible commercial state of a Quote at
a specific point in time. Once written, revisions are read-only. The Quote
document tracks the latest revision number; conversion + approval reference
the exact revision applied.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import BaseDoc


class QuoteRevision(BaseDoc):
    tenant_id: str
    quote_id: str
    revision_number: int

    # Header snapshot
    job_name: str
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None
    expires_at: Optional[str] = None

    # Line items snapshot (denormalized copy at revision time)
    line_items: list[dict[str, Any]] = Field(default_factory=list)

    # Totals snapshot
    subtotal_cents: int = 0
    discount_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0

    # Provenance
    actor_user_id: str
    actor_email: str
    reason: Optional[str] = None
