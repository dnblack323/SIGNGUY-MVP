"""Webstore setup constants, questionnaire defaults, and data contracts."""
from __future__ import annotations

import mimetypes
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.portal_security import create_portal_token, generate_raw_token, hash_token
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.portal_identity import WEBSTORE_MANAGER_PORTAL_PERMS, WEBSTORE_OWNER_PORTAL_PERMS
from ..models.webstore import (
    WEBSTORE_TYPES,
    WebstoreAccessAssignment,
    WebstoreAnswerApplication,
    WebstoreInvitation,
    WebstoreQuestionnaireSubmission,
)
from ..models.forms import FormTemplate
from . import storage
from .activity import record_activity_with_audit
from .email import public_url, send_logged_email
from .notifications import notify_tenant_owners
from .webstore_type_requirements import default_store_settings, evaluate_type_requirements

WEBSTORE_SETUP_STATES = (
    "not_started",
    "invitation_pending",
    "questionnaire_in_progress",
    "questionnaire_submitted",
    "staff_review",
    "changes_requested",
    "setup_in_progress",
    "blocked",
    "setup_complete",
)
ACTIVE_ASSIGNMENT_STATUSES = {"invited", "active"}
ACCEPTABLE_INVITATION_STATUSES = {"pending", "sent", "send_failed"}
MAX_SETUP_FILE_BYTES = 50 * 1024 * 1024
SAFE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "svg", "ai", "eps", "csv", "xlsx", "docx"}
DOWNLOAD_ONLY_EXTENSIONS = {"ai", "eps", "csv", "xlsx", "docx"}
BLOCKED_EXTENSIONS = {
    "exe",
    "bat",
    "cmd",
    "com",
    "msi",
    "ps1",
    "sh",
    "js",
    "jar",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "html",
    "htm",
}
LOCKED_ANSWER_FIELDS = {
    "production_cost_cents",
    "selling_price_cents",
    "store_owner_share_cents",
    "platform_fee_basis_points",
    "fees",
    "shipping_cents",
    "tax_cents",
    "stripe_payment_ready",
    "stripe_onboarding_required",
    "direct_owner_payout_required",
    "launch_ready",
    "launch_readiness",
}
# Questionnaire answer -> draft Webstore field. ``transform`` converts the answer
# (see webstore_setup_answer_applications._transform); ``material`` marks answers
# whose change matters for review (highlighted in revision comparison).
SAFE_ANSWER_MAPPING: dict[str, dict[str, Any]] = {
    # Store basics and dates
    "store_name": {"target": "name", "label": "Store name", "material": True},
    "description": {"target": "description", "label": "Description"},
    "target_launch_at": {"target": "target_launch_at", "label": "Opening date", "material": True},
    "deadline_at": {"target": "deadline_at", "label": "Ordering closes", "material": True},
    "late_orders_allowed": {"target": "store_settings.deadlines.late_orders_allowed", "label": "Late orders allowed", "transform": "yes_bool"},
    "repeat_campaign": {"target": "store_settings.campaign.repeat", "label": "Repeat campaign"},
    # Organization and contacts (the Customer record owns the organization itself)
    "organization_name": {"target": "setup_profile.organization_name", "label": "Organization"},
    "contact_name": {"target": "setup_profile.contact_name", "label": "Main contact"},
    "contact_email": {"target": "setup_profile.contact_email", "label": "Contact email"},
    "contact_phone": {"target": "setup_profile.contact_phone", "label": "Contact phone"},
    "decision_maker": {"target": "setup_profile.decision_maker", "label": "Decision maker"},
    # Products, personalization and artwork
    "products_wanted": {"target": "setup_profile.products_wanted", "label": "Products wanted", "material": True},
    "product_notes": {"target": "setup_profile.product_notes", "label": "Product notes"},
    "open_to_suggestions": {"target": "setup_profile.open_to_suggestions", "label": "Wants recommendations"},
    "personalization_needed": {"target": "store_settings.production.personalization_enabled", "label": "Personalization", "transform": "yes_bool", "material": True},
    "personalization_details": {"target": "store_settings.production.personalization_details", "label": "Personalization details"},
    "artwork_status": {"target": "store_settings.production.artwork_status", "label": "Artwork status", "material": True},
    "design_notes": {"target": "setup_profile.design_notes", "label": "Design notes"},
    "brand_colors": {"target": "setup_profile.brand_colors", "label": "Colors to use"},
    "colors_to_avoid": {"target": "setup_profile.colors_to_avoid", "label": "Colors to avoid"},
    "sponsors_included": {"target": "setup_profile.sponsors_included", "label": "Includes sponsors", "transform": "yes_bool"},
    "sponsor_names": {"target": "setup_profile.sponsor_names", "label": "Sponsor names"},
    # Fulfillment (pickup_window_* answers are grouped into store_settings.fulfillment.pickup_windows)
    "fulfillment_methods": {"target": "store_settings.fulfillment.methods", "label": "Fulfillment methods", "transform": "list", "material": True},
    "shipping_notes": {"target": "store_settings.fulfillment.shipping_copy", "label": "Shipping notes"},
    "delivery_address": {"target": "store_settings.fulfillment.delivery_address", "label": "Delivery address", "material": True},
    "pickup_location": {"target": "store_settings.fulfillment.pickup_location", "label": "Pickup location", "material": True},
    "pickup_instructions": {"target": "store_settings.fulfillment.pickup_instructions", "label": "Pickup instructions"},
    "bag_label_orders": {"target": "store_settings.fulfillment.bag_and_label", "label": "Bag and label orders", "transform": "yes_bool"},
    # Proceeds and payouts (no banking details are ever collected)
    "earns_proceeds": {"target": "setup_profile.earns_proceeds", "label": "Earns proceeds"},
    "payout_recipient_name": {"target": "setup_profile.payout_recipient_name", "label": "Payout recipient", "material": True},
    "payout_method_preference": {"target": "setup_profile.payout_method_preference", "label": "Payout method"},
    "payout_mailing_address": {"target": "setup_profile.payout_mailing_address", "label": "Check mailing address"},
    "payout_contact": {"target": "setup_profile.payout_contact", "label": "Payout contact"},
    "notes": {"target": "setup_profile.owner_notes", "label": "Owner notes"},
    # Fundraiser
    "fundraiser_name": {"target": "store_settings.fundraiser.name", "label": "Fundraiser name"},
    "fundraiser_purpose": {"target": "store_settings.fundraiser.purpose", "label": "Fundraiser purpose", "material": True},
    "fundraiser_goal_amount": {"target": "store_settings.fundraiser.goal_amount_cents", "label": "Fundraising goal", "transform": "dollars_to_cents"},
    "show_progress_bar": {"target": "store_settings.donation.public_progress", "label": "Show progress", "transform": "yes_bool"},
    "profit_allocation_type": {"target": "store_settings.fundraiser.allocation_type", "label": "Proceeds calculation", "material": True},
    "profit_allocation_percentage": {"target": "store_settings.fundraiser.allocation_percentage", "label": "Proceeds percentage", "transform": "number", "material": True},
    "fixed_amount_per_item": {"target": "store_settings.fundraiser.allocation_fixed_cents", "label": "Proceeds per item", "transform": "dollars_to_cents", "material": True},
    "allow_checkout_donations": {"target": "store_settings.donation.enabled", "label": "Checkout donations", "transform": "yes_bool", "material": True},
    "donation_amount_options": {"target": "store_settings.donation.suggested_amounts", "label": "Suggested donations"},
    # Event
    "event_name": {"target": "setup_profile.event_name", "label": "Event name"},
    "event_start_at": {"target": "event_start_at", "label": "Event date", "material": True},
    "event_location": {"target": "event_location", "label": "Event location", "material": True},
    "event_description": {"target": "setup_profile.event_description", "label": "Event description"},
    "event_fundraiser_enabled": {"target": "setup_profile.event_fundraiser_enabled", "label": "Event raises money", "transform": "yes_bool"},
    "event_fundraiser_purpose": {"target": "store_settings.fundraiser.purpose", "label": "Fundraiser purpose", "material": True},
    "event_checkout_donations": {"target": "store_settings.donation.enabled", "label": "Checkout donations", "transform": "yes_bool", "material": True},
    # Team / School
    "group_name": {"target": "setup_profile.group_name", "label": "Team or school"},
    "group_type": {"target": "setup_profile.group_type", "label": "Group type"},
    "season": {"target": "setup_profile.season", "label": "Season"},
    "player_names_numbers": {"target": "setup_profile.player_names_numbers", "label": "Player names or numbers", "transform": "yes_bool"},
    "approval_contact": {"target": "setup_profile.approval_contact", "label": "Design approver"},
    "team_fundraising": {"target": "setup_profile.team_fundraising", "label": "Group raises money", "transform": "yes_bool"},
    "team_fundraiser_purpose": {"target": "store_settings.fundraiser.purpose", "label": "Fundraiser purpose", "material": True},
    # Business / B2B (Employee/Company is the b2b_preset "employee_company")
    "b2b_preset": {"target": "setup_profile.b2b_preset", "label": "Business store preset"},
    "access_policy_preference": {"target": "store_settings.access_policy.mode", "label": "Store access", "transform": "access_mode", "material": True},
    "employee_access_method": {"target": "setup_profile.employee_access_method", "label": "Employee access"},
    "employee_audience": {"target": "setup_profile.employee_audience", "label": "Employee audience"},
    "department_categories": {"target": "setup_profile.department_categories", "label": "Departments"},
    "allowance_notes": {"target": "setup_profile.allowance_notes", "label": "Allowance notes"},
    "catalog_change_frequency": {"target": "setup_profile.catalog_change_frequency", "label": "Catalog changes"},
    "billing_po_requirements": {"target": "setup_profile.billing_po_requirements", "label": "Billing / PO requirements"},
    # Promotional
    "brand_identity_name": {"target": "setup_profile.brand_identity_name", "label": "Brand identity"},
    "promotion_goal": {"target": "setup_profile.promotion_goal", "label": "Promotion goal"},
    "campaign_duration": {"target": "setup_profile.campaign_duration", "label": "Campaign duration"},
    "promo_channels": {"target": "store_settings.promo.channels", "label": "Promotion channels", "transform": "list"},
    "promo_copy_notes": {"target": "store_settings.promo.copy_notes", "label": "Promo copy notes"},
    # General
    "store_purpose": {"target": "setup_profile.store_purpose", "label": "Store purpose"},
    "audience": {"target": "setup_profile.audience", "label": "Audience"},
}
PICKUP_WINDOWS_TARGET = "store_settings.fulfillment.pickup_windows"
PICKUP_WINDOW_FIELDS = ("date", "start", "end", "location", "instructions")

WEBSTORE_FORM_ADAPTER = "webstore_questionnaire"


__all__ = [name for name in globals() if not name.startswith("__")]
