"""EC7 phase 7b — Catalog-feed supplier connector stub.

Catalog-feed suppliers publish a static CSV / XML / JSON / SFTP catalog on
a schedule. The full implementation lives in a future phase; the stub keeps
the connector contract stable and registered.
"""
from __future__ import annotations
from typing import Optional

from .base import SupplierConnectorBase, ConnectorCapability


class FeedCsvSupplierAdapter(SupplierConnectorBase):
    connector_key = "feed_csv"
    tier = "feed_csv"
    capabilities: set[ConnectorCapability] = {
        ConnectorCapability.SEARCH,
        ConnectorCapability.PRODUCT,
        ConnectorCapability.INVENTORY,
    }

    async def create_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                    purchase_order: dict, idempotency_key: str,
                                    actor_user_id: Optional[str] = None) -> dict:
        return {
            "status": "feed_only",
            "supplier_order_id": None,
            "message": "Catalog-feed tier supports catalog + inventory only. "
                       "PO submission must be performed on the vendor's site.",
            "idempotency_key": idempotency_key,
        }
