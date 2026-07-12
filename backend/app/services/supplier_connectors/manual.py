"""EC7 phase 7b — Manual supplier connector stub.

The manual tier represents suppliers where we prepare a PO but the user
finishes the purchase on the vendor's website. No electronic submission.
"""
from __future__ import annotations
from typing import Optional

from .base import SupplierConnectorBase, ConnectorCapability


class ManualSupplierAdapter(SupplierConnectorBase):
    connector_key = "manual"
    tier = "manual"
    capabilities: set[ConnectorCapability] = set()      # nothing electronic

    async def create_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                    purchase_order: dict, idempotency_key: str,
                                    actor_user_id: Optional[str] = None) -> dict:
        # Manual suppliers do NOT submit electronically. The Supply Center
        # generates a print/handoff copy of the PO instead.
        return {
            "status": "manual_handoff",
            "supplier_order_id": None,
            "message": "Manual supplier tier — no electronic submission. "
                       "Present the PO to the vendor for entry on their site.",
            "idempotency_key": idempotency_key,
        }
