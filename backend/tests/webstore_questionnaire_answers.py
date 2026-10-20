"""Complete Webstore Starter questionnaire answers for tests (pack content v2)."""
from __future__ import annotations

from typing import Any

BASE = {
    "organization_name": "Lincoln Boosters",
    "contact_name": "Pat Organizer",
    "contact_email": "pat@example.com",
    "contact_phone": "555-0100",
    "store_name": "Lincoln Spirit Store",
    "target_launch_at": "2099-03-01",
    "deadline_at": "2099-03-20",
    "products_wanted": ["tshirts", "hoodies"],
    "personalization_needed": "no",
    "artwork_status": "ready",
    "fulfillment_methods": ["organizer_pickup"],
    "pickup_location": "Lincoln High gym",
    "earns_proceeds": "no",
    "intake_acknowledgement": ["confirmed"],
}
TYPE = {
    "fundraiser": {"fundraiser_purpose": "New band uniforms", "profit_allocation_type": "decide_with_shop"},
    "event": {"event_name": "Spring Fair", "event_start_at": "2099-03-28", "event_location": "Town Park"},
    "team_school": {"group_name": "Lincoln Lions"},
    "b2b": {"b2b_preset": "customer_merch", "access_policy_preference": "public"},
    "promotional": {"brand_identity_name": "Coach Kim"},
    "general": {"store_purpose": "Spirit wear"},
}


def complete_answers(store_type: str = "event", **overrides: Any) -> dict[str, Any]:
    return {**BASE, **TYPE.get(store_type, {}), **overrides}
