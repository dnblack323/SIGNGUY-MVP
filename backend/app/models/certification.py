"""EC8 phase 8e — Certification.

Status is backend-derived where practical: `expired` is computed from
`expiration_date` on read (see `services/certification_service.py`
`effective_status`), not relied on solely as a stored/stale value — though
the stored `status` field is also actively transitioned to `"expired"` by
the same helper so list/report queries can filter on it directly without
recomputing per row.

Never hard-deleted. Revocation sets `revoked_at`/`revoked_by`/
`revocation_reason` and flips `status="revoked"` — the record itself is
permanent history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from .base import BaseDoc

CertificationStatus = Literal[
    "not_started", "in_progress", "pending_signoff", "certified", "expired", "revoked", "failed",
]


class Certification(BaseDoc):
    tenant_id: str
    employee_id: str
    equipment_id: Optional[str] = None
    certification_type: Optional[str] = None  # free-text label when not tied to a specific Equipment
    source_training_assignment_id: Optional[str] = None
    status: CertificationStatus = "not_started"
    issued_date: Optional[str] = None
    expiration_date: Optional[str] = None
    trainer_user_id: Optional[str] = None
    required_score: Optional[int] = None
    actual_score: Optional[int] = None
    practical_signoff_result: Optional[str] = None
    restrictions: Optional[str] = None
    renewal_of: Optional[str] = None   # prior Certification.id
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revocation_reason: Optional[str] = None
    override_eligible: bool = True   # informational only — Equipment.access_policy is authoritative for gating
    created_by: str
    updated_by: str
