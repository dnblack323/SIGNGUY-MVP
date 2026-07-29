"""Tenant reporting contracts for the shared Report Builder.

These documents are metadata and execution history only. They never store a
current transferable price, invoice total, payroll total, or other source-of-
truth business amount. Every run/export/schedule re-reads the authorized
tenant source records through the reporting service.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc


ReportDefinitionVisibility = Literal["private", "shared_users", "shared_roles"]
ReportDefinitionStatus = Literal["active", "archived"]
ReportExportFormat = Literal[
    "csv",
    "xlsx",
    "pdf",
    "print",
    "accounting_csv",
    "payroll_csv",
    "tax_csv",
]
ReportExportStatus = Literal["queued", "running", "completed", "failed"]
ReportScheduleCadence = Literal["daily", "weekly", "monthly", "pay_period", "event_triggered"]
ReportScheduleStatus = Literal["enabled", "disabled", "archived"]
ReportScheduleRunStatus = Literal["running", "succeeded", "failed", "skipped"]


class ReportDefinition(BaseDoc):
    tenant_id: str
    name: str
    description: Optional[str] = None
    owner_user_id: str
    owner_email: str
    source_kind: Literal["standard", "custom"] = "standard"
    standard_report_key: Optional[str] = None
    custom_dataset: Optional[str] = None
    fields: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    group_by: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    calculated_fields: list[dict[str, Any]] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    export_defaults: dict[str, Any] = Field(default_factory=dict)
    dashboard_widget: Optional[dict[str, Any]] = None
    visibility: ReportDefinitionVisibility = "private"
    shared_user_ids: list[str] = Field(default_factory=list)
    shared_role_keys: list[str] = Field(default_factory=list)
    version: int = 1
    parent_definition_id: Optional[str] = None
    status: ReportDefinitionStatus = "active"
    archived_at: Optional[str] = None


class ReportExport(BaseDoc):
    tenant_id: str
    report_definition_id: Optional[str] = None
    standard_report_key: Optional[str] = None
    custom_dataset: Optional[str] = None
    requested_by_user_id: str
    requested_by_email: str
    export_format: ReportExportFormat
    status: ReportExportStatus = "queued"
    row_count: int = 0
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    filters: dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    completed_at: Optional[str] = None


class ReportSchedule(BaseDoc):
    tenant_id: str
    report_definition_id: str
    owner_user_id: str
    owner_email: str
    cadence: ReportScheduleCadence
    timezone: str = "UTC"
    delivery_time: Optional[str] = None
    delivery_formats: list[ReportExportFormat] = Field(default_factory=lambda: ["csv"])
    recipient_user_ids: list[str] = Field(default_factory=list)
    recipient_emails: list[str] = Field(default_factory=list)
    status: ReportScheduleStatus = "enabled"
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    retry_count: int = 0


class ReportScheduleRun(BaseDoc):
    tenant_id: str
    schedule_id: str
    report_definition_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: ReportScheduleRunStatus = "running"
    export_ids: list[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    permissions_revalidated: bool = False
    delivery_mode: str = "test_no_email"
