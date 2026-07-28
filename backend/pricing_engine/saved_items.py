"""Pure Promotional saved-item helpers for pricing formulas.

This module contains only deterministic starter-item data and exact quantity
tier lookup. Tenant-scoped saved-item CRUD, permissions, persistence, and
auditing remain in ``app.services.pricing_saved_items``.
"""
from __future__ import annotations

from typing import Any


BUSINESS_CARD_STARTER_ITEMS: list[dict[str, Any]] = [
    {
        "name": "Standard Paper Business Cards",
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [
            {"quantity": 100, "price": 25.0},
            {"quantity": 250, "price": 45.0},
            {"quantity": 500, "price": 75.0},
            {"quantity": 1000, "price": 125.0},
            {"quantity": 2000, "price": 175.0},
            {"quantity": 2500, "price": 225.0},
        ],
        "default_notes": "Preloaded starter tier pricing (EC09 Promotional Items appendix).",
        "quick_select": True,
        "active": True,
        "created_from": "new",
    },
    {
        "name": "Magnetic Business Cards",
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [
            {"quantity": 25, "price": 25.0},
            {"quantity": 50, "price": 50.0},
            {"quantity": 100, "price": 75.0},
            {"quantity": 200, "price": 100.0},
            {"quantity": 500, "price": 175.0},
            {"quantity": 1000, "price": 275.0},
        ],
        "default_notes": "Preloaded starter tier pricing (EC09 Promotional Items appendix).",
        "quick_select": True,
        "active": True,
        "created_from": "new",
    },
]


def resolve_quantity_tier_price(item: dict[str, Any], quantity: int) -> float | None:
    """Return an exact configured quantity-tier price, never an invented price."""

    for tier in item.get("quantity_tiers") or []:
        if int(tier.get("quantity", -1)) == int(quantity):
            return float(tier["price"])
    return None
