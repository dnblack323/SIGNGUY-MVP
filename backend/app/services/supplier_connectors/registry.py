"""EC7 phase 7b — Connector registry.

Maps `connector_key` (stored on the Vendor record) to a concrete connector
instance. Additional connectors (manual, feed_csv, real APIs) can be
registered here without touching Supply Center, purchasing, or receiving
code.
"""
from __future__ import annotations
from typing import Dict

from .base import SupplierConnectorBase
from .test_adapter import TestSupplierAdapter
from .manual import ManualSupplierAdapter
from .feed_csv import FeedCsvSupplierAdapter


_registry: Dict[str, SupplierConnectorBase] = {
    "test_adapter": TestSupplierAdapter(),
    "manual": ManualSupplierAdapter(),
    "feed_csv": FeedCsvSupplierAdapter(),
}


def register_connector(key: str, connector: SupplierConnectorBase) -> None:
    _registry[key] = connector


def get_connector(key: str) -> SupplierConnectorBase:
    if key not in _registry:
        raise KeyError(f"unknown connector: {key}")
    return _registry[key]


def list_connectors() -> list[dict]:
    return [
        {"key": k, "tier": c.tier, "capabilities": sorted(cap.value for cap in c.capabilities)}
        for k, c in _registry.items()
    ]
