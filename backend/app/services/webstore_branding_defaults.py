"""Default Webstore branding content."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .webstore_branding_contracts import WHOLE_SECTION_PATHS

def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _store_type_defaults(store_type: str) -> dict[str, Any]:
    if store_type == "b2b":
        return {
            "business_welcome": "",
            "ordering_instructions": "",
            "access_notice": "",
            "fulfillment_summary": "",
        }
    if store_type == "fundraiser":
        return {
            "organization_name": "",
            "campaign_heading": "",
            "campaign_message": "",
            "proceeds_explanation": "",
            "show_goal_progress": False,
            "show_campaign_end_date": True,
        }
    if store_type == "event":
        return {
            "event_display_name": "",
            "event_heading": "",
            "event_message": "",
            "show_event_datetime": True,
            "show_location": True,
            "show_ordering_deadline": True,
            "pickup_instructions": "",
        }
    if store_type == "promotional":
        return {
            "campaign_heading": "",
            "campaign_message": "",
            "offer_wording": "",
            "show_deadline": True,
            "promotion_badge": "",
        }
    if store_type == "employee":
        return {
            "company_welcome": "",
            "employee_ordering_instructions": "",
            "access_notice": "",
            "fulfillment_message": "",
        }
    return {
        "general_welcome": "",
        "about_store": "",
        "shopping_instructions": "",
    }


def default_branding(store: dict) -> dict[str, Any]:
    display_name = store.get("name") or "Webstore"
    return {
        "brand_basics": {
            "display_name": display_name,
            "tagline": store.get("description") or "",
            "primary_logo": {},
            "alternate_logo": {},
            "favicon": {},
            "social_image": {},
            "logo_alt_text": "",
        },
        "colors_fonts": {
            "primary_color": "#0f172a",
            "secondary_color": "#1e293b",
            "accent_color": "#2563eb",
            "page_background_color": "#f8fafc",
            "main_text_color": "#111827",
            "button_background_color": "#2563eb",
            "button_text_color": "#ffffff",
            "heading_font": "inter",
            "body_font": "inter",
            "button_corner_style": "slightly_rounded",
        },
        "header": {
            "show_header": True,
            "display_mode": "name",
            "logo_size": "medium",
            "background_color": "#ffffff",
            "announcement_enabled": False,
            "announcement_text": "",
            "announcement_background_color": "#fef3c7",
            "announcement_text_color": "#92400e",
            "announcement_link_destination": "none",
        },
        "hero": {
            "show_hero": True,
            "image": {},
            "image_focal_position": "center",
            "overlay_color": "#000000",
            "headline": display_name,
            "supporting_text": store.get("description") or "",
            "primary_button_enabled": True,
            "primary_button_label": "Shop products",
            "primary_button_destination": "catalog",
        },
        "store_information": {
            "show_section": True,
            "welcome_heading": f"Welcome to {display_name}",
            "welcome_text": store.get("description") or "",
            "supporting_image": {},
            "store_instructions": "",
            "contact_display": "store",
        },
        "store_type_content": _store_type_defaults(store.get("store_type") or "general"),
        "catalog_introduction": {
            "show_catalog_area": True,
            "heading": "Featured products",
            "introduction": "Product catalog content is managed in a later Webstores stage.",
            "background_color": "#ffffff",
        },
        "footer": {
            "show_footer": True,
            "background_color": "#0f172a",
            "text_color": "#ffffff",
            "display_mode": "store_name",
            "message": "",
            "show_contact": True,
            "show_social_links": False,
            "show_policy_links": False,
            "show_powered_by": True,
        },
    }
