"""EC2 — Tenant Settings model.

Namespaced key/value store scoped per tenant. Values are typed JSON.
Namespaces group related settings (e.g. "company_profile", "invoicing_defaults",
"branding", "portal", "sales_tax", "notifications"). Each (tenant, namespace, key)
tuple is unique.

Values are stored as JSON to keep the shape flexible. Callers are expected to
validate values against a per-namespace schema at the service layer.

Secrets (API keys, webhook secrets) must NEVER be written into `settings`.
Secrets live only in environment variables and are surfaced via the
`integration_status` service, which reports availability without exposing
the value.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import BaseDoc


class Setting(BaseDoc):
    tenant_id: str
    namespace: str  # e.g. "company_profile"
    key: str        # e.g. "phone"
    value: Any      # typed JSON (bool, int, float, string, dict, list)
    value_type: str = "string"  # informational hint: "string" | "int" | "bool" | "json"
    updated_by: Optional[str] = None  # user_id of last writer
