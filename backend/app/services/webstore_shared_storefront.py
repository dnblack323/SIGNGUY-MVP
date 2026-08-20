"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *
from .webstore_shared_catalog import _approval_history
from .webstore_shared_contracts import _public_cart_config

def _public_store(
    store: dict,
    published_branding: Optional[dict[str, Any]] = None,
    fundraiser_progress: Optional[dict[str, Any]] = None,
    provider_authority: Optional[bool] = None,
) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "deadline_at",
        "public_url",
        "checkout_enabled",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    result["branding"] = published_branding or {}
    provider_status = provider_configuration_status(get_settings())
    provider_ready = provider_status["provider_authority"] if provider_authority is None else provider_authority
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_ready
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    result["cart_config"] = _public_cart_config(store)
    if store.get("store_type") == "fundraiser":
        result["fundraiser_progress"] = fundraiser_progress or {
            "goal_cents": result["cart_config"]["fundraiser_goal_cents"],
            "completed_sales_cents": 0,
            "percent": 0,
            "over_goal": False,
            "paid_only": True,
        }
    return result


def _portal_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
        "terms_fee_acknowledged",
        "owner_approved_at",
        "launch_packet_id",
        "launch_packet_version",
        "owner_approved_packet_id",
        "owner_approved_packet_version",
        "owner_approval_invalidated_at",
        "owner_approval_invalidated_reason",
        "required_terms_version",
        "terms_acceptance_id",
        "terms_accepted_version",
        "terms_accepted_at",
        "setup_state",
        "setup_profile",
        "store_settings",
        "target_launch_at",
        "intended_launch_at",
        "intended_close_at",
        "launch_timezone",
        "event_start_at",
        "event_location",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    provider_status = provider_configuration_status(get_settings())
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_status["provider_authority"]
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    return result


def _portal_launch_packet(packet: Optional[dict]) -> Optional[dict]:
    if not packet:
        return None
    allowed = {
        "id",
        "webstore_id",
        "status",
        "version",
        "snapshot",
        "snapshot_hash",
        "pricing_summary",
        "promotion_copy",
        "qr_code_url",
        "share_url",
        "delivery_status",
        "delivery_recipient_email",
        "delivery_portal_path",
        "sent_at",
        "delivered_at",
        "owner_decision_at",
        "change_request_reason",
        "superseded_at",
        "invalidated_at",
        "invalidated_reason",
    }
    return {k: v for k, v in packet.items() if k in allowed}


async def _portal_launch_packet_with_history(tenant_id: str, packet: Optional[dict]) -> Optional[dict]:
    safe = _portal_launch_packet(packet)
    if not safe:
        return None
    safe["approval_history"] = await _approval_history(tenant_id, "webstore_launch_packet", safe["id"])
    return safe


def _portal_change_request(item: dict) -> dict:
    allowed = {
        "id",
        "packet_id",
        "packet_version",
        "category",
        "affected_item_ref",
        "owner_comment",
        "status",
        "owner_visible_history",
        "resolved_at",
        "created_at",
        "updated_at",
    }
    return {k: v for k, v in item.items() if k in allowed}


def _portal_terms_acceptance(item: Optional[dict]) -> Optional[dict]:
    if not item:
        return None
    allowed = {
        "id",
        "terms_version",
        "accepted_at",
        "packet_id",
        "packet_version",
        "terms_snapshot",
        "fee_summary_snapshot",
        "status",
    }
    return {k: v for k, v in item.items() if k in allowed}

__all__ = [name for name in globals() if not name.startswith("__")]
