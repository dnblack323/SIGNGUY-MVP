"""EC7 phase 7b — Vendor + VendorMaterial (shop's supplier list; distinct from
`Customer` records — vendors are sources of purchase, never invoiced parties).

Every vendor row is tenant-scoped. VendorMaterial links a shop's own
`Material` record to a specific `SupplierProduct` for automated fulfillment
suggestions.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc


ConnectorTier = Literal["test_adapter", "api", "edi", "feed_csv", "manual"]


class Vendor(BaseDoc):
    tenant_id: str
    name: str
    display_name: Optional[str] = None
    connector_key: str                     # "test_adapter" | "grimco_manual" | "sanmar_manual" | ...
    connector_tier: ConnectorTier = "manual"
    account_number: Optional[str] = None   # e.g., wholesale account number
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    preferred: bool = False                # tenant-preferred flag (recommendation weight)
    active: bool = True
    notes: Optional[str] = None
    # Secrets/credentials MUST NOT live here; they belong to EC2 integration-secret storage.


class VendorMaterial(BaseDoc):
    """Maps a shop's Material to a vendor's SupplierProduct for automated
    purchasing suggestions. `preferred` selects the default supplier when the
    Material has multiple sources.
    """
    tenant_id: str
    vendor_id: str
    material_id: str
    supplier_product_id: str              # normalized SupplierProduct row id
    supplier_sku: Optional[str] = None
    preferred: bool = False
    last_known_cost_cents: Optional[int] = None
    last_seen_at: Optional[str] = None
    active: bool = True
