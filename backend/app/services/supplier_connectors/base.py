"""EC7 phase 7b — Supplier connector abstract base.

The interface intentionally mirrors master plan §12A operations:
`search_catalog`, `get_product`, `get_variants`, `get_account_price`,
`get_inventory`, `get_shipping_quote`, `create_supplier_order`,
`retrieve_supplier_order`, `retrieve_tracking`, `cancel_order`.

Each connector reports its supported `capabilities` so the shortage service /
recommendation engine / Supply Center UI can degrade gracefully when a
supplier can't (for example) submit orders electronically.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional


RATE_ESTIMATED = "estimated"          # tag applied when live freight is unavailable
RATE_LIVE = "live"


class ConnectorCapability(str, Enum):
    SEARCH = "search_catalog"
    PRODUCT = "get_product"
    VARIANTS = "get_variants"
    ACCOUNT_PRICE = "get_account_price"
    INVENTORY = "get_inventory"
    SHIPPING_QUOTE = "get_shipping_quote"
    SUBMIT_ORDER = "create_supplier_order"
    RETRIEVE_ORDER = "retrieve_supplier_order"
    TRACKING = "retrieve_tracking"
    CANCEL = "cancel_order"


class SupplierConnectorBase(ABC):
    """Abstract supplier connector. Sub-classes advertise `capabilities`
    and implement only the methods they support. Every unsupported operation
    should raise `NotImplementedError` (default behaviour).
    """

    #: Human-readable connector name (also the registry key).
    connector_key: str = "base"

    #: Which of the ConnectorCapability values this connector supports.
    capabilities: set[ConnectorCapability] = set()

    #: Free-form connection tier label (test_adapter | api | edi | feed_csv | manual).
    tier: str = "manual"

    def supports(self, cap: ConnectorCapability) -> bool:
        return cap in self.capabilities

    # ----- Catalog operations -----
    async def search_catalog(self, *, tenant_id: str, vendor_id: str, query: str,
                             category: Optional[str] = None, limit: int = 50) -> list[dict]:
        raise NotImplementedError

    async def get_product(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str) -> dict:
        raise NotImplementedError

    async def get_variants(self, *, tenant_id: str, vendor_id: str, family_key: str) -> list[dict]:
        raise NotImplementedError

    async def get_account_price(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str,
                                quantity: int) -> dict:
        raise NotImplementedError

    async def get_inventory(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str) -> list[dict]:
        raise NotImplementedError

    async def get_shipping_quote(self, *, tenant_id: str, vendor_id: str, warehouse_id: str,
                                 line_count: int, weight_lbs: float = 0.0) -> dict:
        raise NotImplementedError

    # ----- Ordering operations -----
    @abstractmethod
    async def create_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                    purchase_order: dict, idempotency_key: str,
                                    actor_user_id: Optional[str] = None) -> dict:
        ...

    async def retrieve_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                      supplier_order_id: str) -> dict:
        raise NotImplementedError

    async def retrieve_tracking(self, *, tenant_id: str, vendor_id: str,
                                supplier_order_id: str) -> dict:
        raise NotImplementedError

    async def cancel_order(self, *, tenant_id: str, vendor_id: str,
                           supplier_order_id: str, reason: Optional[str] = None) -> dict:
        raise NotImplementedError
