"""EC7 phase 7b — Supplier connector package.

Every connector implements `SupplierConnectorBase`. Connectors report their
`capabilities` explicitly — foundation MUST work even when a supplier supports
only part of the interface (per master plan Appendix A.3).
"""
from .base import SupplierConnectorBase, ConnectorCapability, RATE_ESTIMATED
from .registry import get_connector, register_connector, list_connectors
from .test_adapter import TestSupplierAdapter

__all__ = [
    "SupplierConnectorBase",
    "ConnectorCapability",
    "TestSupplierAdapter",
    "get_connector",
    "register_connector",
    "list_connectors",
    "RATE_ESTIMATED",
]
