"""Shared Webstore service constants."""
from __future__ import annotations

import re

from ..models.webstore import WEBSTORE_LIFECYCLE_STATES, WEBSTORE_TYPES

WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
PRODUCT_PURCHASABLE_STATUSES = {"active"}
PLATFORM_TEMPLATE_TENANT_ID = "__platform__"
TEMPLATE_SCOPES = {"tenant", "platform"}
TEMPLATE_STATUSES = {"draft", "active", "archived"}
PRODUCT_STATUSES = {"draft", "planned", "incomplete", "ready", "active", "inactive", "archived"}
CATALOG_PRODUCT_STATUSES = {"planned", "incomplete", "ready", "active", "archived"}
CATEGORY_STATUSES = {"active", "archived"}
CUSTOMER_IMAGE_SLOTS = {"primary", "secondary"}
PRODUCT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "svg"}
FULFILLMENT_METHODS = {"pickup", "shipping"}
STAGE4A_PUBLICATION_FIELDS = {"public", "featured"}
PRODUCT_APPROVAL_DECISIONS = {"approve", "request_changes", "reject"}
PRODUCT_APPROVAL_STATUSES = {"not_submitted", "pending_owner_approval", "approved", "rejected", "changes_requested", "superseded"}
STAGE4A_FINANCIAL_VARIANT_FIELDS = {
    "production_cost_cents",
    "selling_price_cents",
    "store_owner_share_cents",
    "platform_fee_basis_points",
    "margin_cents",
    "margin_percent",
    "revenue_cents",
    "fundraiser_share_cents",
    "owner_share_cents",
    "variants",
    "variant_pricing",
    "variant_skus",
    "sku",
    "personalization_enabled",
    "image_file_ids",
}
SLUG_RE = re.compile(r"[^a-z0-9]+")
PUBLIC_CHECKOUT_ENABLED = True
VALID_WEBSTORE_TYPES = set(WEBSTORE_TYPES)
VALID_WEBSTORE_STATUSES = set(WEBSTORE_LIFECYCLE_STATES)
PHASE6_LIFECYCLE_STATES = (
    "draft",
    "intake_pending",
    "setup_in_progress",
    "owner_review",
    "payment_setup_pending",
    "ready_to_launch",
    "live",
    "paused",
    "closed",
    "archived",
)
CURRENT_WEBSTORE_TERMS_VERSION = "webstore_terms_2026_07"
PAYMENT_READINESS_STATES = {"not_configured", "pending", "restricted", "ready", "unavailable", "not_applicable"}
CHANGE_REQUEST_CATEGORIES = {
    "branding",
    "product",
    "price",
    "description",
    "artwork",
    "mockup",
    "variant",
    "personalization",
    "fulfillment",
    "availability",
    "policy",
    "general",
}
CHANGE_REQUEST_STATUSES = {"open", "answered", "resolved", "declined", "superseded"}
MATERIAL_STORE_FIELDS = {
    "name",
    "description",
    "branding",
    "store_type",
    "deadline_at",
    "target_launch_at",
    "event_start_at",
    "event_location",
    "intended_launch_at",
    "intended_close_at",
    "launch_timezone",
    "required_terms_version",
    "store_settings",
    "direct_owner_payout_required",
    "stripe_onboarding_required",
}
MATERIAL_PRODUCT_FIELDS = {
    "name",
    "short_description",
    "full_description",
    "description",
    "category_id",
    "category_name",
    "category",
    "product_type",
    "fulfillment_notes",
    "fulfillment_methods",
    "default_fulfillment_method",
    "pickup_instructions",
    "shipping_cost_cents",
    "sku",
    "selling_price_cents",
    "store_owner_share_cents",
    "fundraiser_share_cents",
    "platform_fee_basis_points",
    "variants",
    "personalization_enabled",
    "personalization_fields",
    "bundle_items",
    "inventory_policy",
    "inventory_quantity",
    "launch_packet_include",
    "customer_images",
    "artwork_associations",
    "mockup_associations",
    "public",
    "featured",
    "status",
}

STARTER_PRODUCT_TEMPLATE_MARKER = "starter_common_webstore_template_2026_08"
STARTER_PRODUCT_TEMPLATES = [
    {
        "template_name": "T-shirt",
        "product_category": "apparel",
        "product_type": "tshirt",
        "default_title": "T-shirt",
        "default_short_description": "Comfortable custom printed T-shirt.",
        "default_description": "A classic short-sleeve T-shirt customized with your store artwork. Available in common adult sizes and selected colors.",
        "suggested_category_name": "Apparel",
        "production_method": "screen_print_or_dtf",
        "default_variants": [{"size": size, "color": "", "selling_price_cents": 2500} for size in ["S", "M", "L", "XL", "2XL"]],
        "suggested_selling_price_cents": 2500,
    },
    {
        "template_name": "Hoodie",
        "product_category": "apparel",
        "product_type": "hoodie",
        "default_title": "Hoodie",
        "default_short_description": "Warm pullover hoodie with custom artwork.",
        "default_description": "A soft pullover hoodie decorated with your store artwork. Good for fundraisers, teams, events, and company stores.",
        "suggested_category_name": "Apparel",
        "production_method": "screen_print_or_dtf",
        "default_variants": [{"size": size, "color": "", "selling_price_cents": 4500} for size in ["S", "M", "L", "XL", "2XL"]],
        "suggested_selling_price_cents": 4500,
    },
    {
        "template_name": "Hat",
        "product_category": "apparel",
        "product_type": "hat",
        "default_title": "Hat",
        "default_short_description": "Adjustable hat with logo or store artwork.",
        "default_description": "An adjustable cap decorated with a logo, patch, or printed design for everyday wear.",
        "suggested_category_name": "Accessories",
        "production_method": "embroidery_or_patch",
        "default_variants": [{"size": "One size", "color": "", "selling_price_cents": 2800}],
        "suggested_selling_price_cents": 2800,
    },
    {
        "template_name": "Decal / Sticker",
        "product_category": "decals",
        "product_type": "decal",
        "default_title": "Decal / Sticker",
        "default_short_description": "Custom decal or sticker using store artwork.",
        "default_description": "A durable decal or sticker printed from your approved artwork. Great as an add-on item for events and fundraisers.",
        "suggested_category_name": "Decals",
        "production_method": "print_cut",
        "default_variants": [{"size": "Small", "color": "Full color", "selling_price_cents": 600}, {"size": "Large", "color": "Full color", "selling_price_cents": 1000}],
        "suggested_selling_price_cents": 600,
    },
    {
        "template_name": "Banner",
        "product_category": "signs",
        "product_type": "banner",
        "default_title": "Banner",
        "default_short_description": "Custom event or sponsor banner.",
        "default_description": "A printed banner customized with your store artwork, event information, sponsor logos, or promotional message.",
        "suggested_category_name": "Signs",
        "production_method": "digital_print",
        "default_variants": [{"size": "2x4", "color": "Full color", "selling_price_cents": 6500}, {"size": "3x6", "color": "Full color", "selling_price_cents": 11000}],
        "suggested_selling_price_cents": 6500,
    },
    {
        "template_name": "Tumbler",
        "product_category": "promotional",
        "product_type": "tumbler",
        "default_title": "Tumbler",
        "default_short_description": "Drinkware with custom logo or campaign artwork.",
        "default_description": "A branded tumbler or cup using your approved store artwork. Useful for company stores, fundraisers, and promotional campaigns.",
        "suggested_category_name": "Drinkware",
        "production_method": "sublimation_or_vendor",
        "default_variants": [{"size": "20 oz", "color": "", "selling_price_cents": 3000}],
        "suggested_selling_price_cents": 3000,
    },
]
WEBSTORE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"questionnaire_sent", "waiting_on_store_owner", "questionnaire_submitted", "products_selected", "store_packet_generated", "archived"},
    "questionnaire_sent": {"waiting_on_store_owner", "questionnaire_submitted", "changes_requested", "archived"},
    "waiting_on_store_owner": {"questionnaire_submitted", "changes_requested", "archived"},
    "questionnaire_submitted": {"ai_setup_ready", "artwork_needs_review", "products_selected", "store_packet_generated", "archived"},
    "ai_setup_ready": {"ai_product_suggestions_ready", "artwork_needs_review", "products_selected", "archived"},
    "ai_product_suggestions_ready": {"artwork_needs_review", "products_selected", "archived"},
    "artwork_needs_review": {"mockups_generated", "products_selected", "archived"},
    "mockups_generated": {"mockups_approved", "changes_requested", "products_selected", "archived"},
    "mockups_approved": {"products_selected", "store_packet_generated", "archived"},
    "products_selected": {"store_packet_generated", "sent_for_approval", "archived"},
    "store_packet_generated": {"sent_for_approval", "changes_requested", "archived"},
    "sent_for_approval": {"approved", "changes_requested", "archived"},
    "changes_requested": {"questionnaire_submitted", "store_packet_generated", "sent_for_approval", "archived"},
    "approved": {"launch_ready", "scheduled", "live", "archived"},
    "launch_ready": {"scheduled", "paused", "live", "archived"},
    "scheduled": {"launch_ready", "paused", "live", "closed", "archived"},
    "paused": {"launch_ready", "scheduled", "live", "closed", "archived"},
    "live": {"closing_soon", "paused", "closed", "in_production", "completed", "archived"},
    "closing_soon": {"paused", "closed", "archived"},
    "closed": {"relaunch_ready", "archived"},
    "in_production": {"completed", "closed", "archived"},
    "completed": {"relaunch_ready", "archived"},
    "relaunch_ready": {"approved", "launch_ready", "scheduled", "live", "archived"},
    "archived": set(),
}
PHASE6_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"intake_pending", "archived"},
    "intake_pending": {"setup_in_progress", "archived"},
    "setup_in_progress": {"owner_review", "archived"},
    "owner_review": {"setup_in_progress", "payment_setup_pending", "archived"},
    "payment_setup_pending": {"owner_review", "ready_to_launch", "archived"},
    "ready_to_launch": {"payment_setup_pending", "live", "paused", "closed", "archived"},
    "live": {"paused", "closed", "archived"},
    "paused": {"ready_to_launch", "live", "closed", "archived"},
    "closed": {"archived"},
    "archived": set(),
}
PHASE6_TO_INTERNAL_STATUS = {
    "draft": "draft",
    "intake_pending": "waiting_on_store_owner",
    "setup_in_progress": "questionnaire_submitted",
    "owner_review": "store_packet_generated",
    "payment_setup_pending": "approved",
    "ready_to_launch": "launch_ready",
    "live": "live",
    "paused": "paused",
    "closed": "closed",
    "archived": "archived",
}
INTERNAL_STATUS_TO_PHASE6 = {
    "draft": "draft",
    "questionnaire_sent": "intake_pending",
    "waiting_on_store_owner": "intake_pending",
    "questionnaire_submitted": "setup_in_progress",
    "ai_setup_ready": "setup_in_progress",
    "ai_product_suggestions_ready": "setup_in_progress",
    "artwork_needs_review": "setup_in_progress",
    "mockups_generated": "setup_in_progress",
    "mockups_approved": "setup_in_progress",
    "products_selected": "setup_in_progress",
    "store_packet_generated": "owner_review",
    "sent_for_approval": "owner_review",
    "changes_requested": "owner_review",
    "approved": "payment_setup_pending",
    "launch_ready": "ready_to_launch",
    "scheduled": "ready_to_launch",
    "paused": "paused",
    "live": "live",
    "closing_soon": "live",
    "in_production": "live",
    "completed": "closed",
    "closed": "closed",
    "relaunch_ready": "closed",
    "archived": "archived",
}
