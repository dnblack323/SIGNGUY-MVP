"""EC11 Phase 11F - production kiosk session records."""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from .base import BaseDoc


class ProductionKioskDeviceSession(BaseDoc):
    tenant_id: str
    device_token_hash: str
    status: str = "active"
    device_label: Optional[str] = None
    activated_by_user_id: str
    activated_by_email: str
    activated_at: str
    expires_at: str
    last_activity_at: str
    revoked_at: Optional[str] = None
    revoked_by_user_id: Optional[str] = None
    revoke_reason: Optional[str] = None
    employee_id: Optional[str] = None
    employee_identity_id: Optional[str] = None
    employee_session_token_hash: Optional[str] = None
    employee_session_started_at: Optional[str] = None
    employee_session_expires_at: Optional[str] = None
    employee_last_activity_at: Optional[str] = None
    failed_identification_count: int = 0
    failed_identification_window_started_at: Optional[str] = None
    identification_locked_until: Optional[str] = None


class ProductionKioskSupervisorOverride(BaseDoc):
    tenant_id: str
    kiosk_session_id: str
    employee_id: str
    supervisor_user_id: str
    supervisor_email: str
    supervisor_role: str
    action: str
    stage_id: str
    reason: str
    override_token_hash: str
    expires_at: str
    consumed_at: Optional[str] = None
    consumed_by_employee_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
