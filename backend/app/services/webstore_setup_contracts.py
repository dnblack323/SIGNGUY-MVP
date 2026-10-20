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
    LEGACY_WEBSTORE_TYPES,
    WEBSTORE_TYPES,
    WebstoreAccessAssignment,
    WebstoreAnswerApplication,
    WebstoreInvitation,
    WebstoreQuestionnaireSubmission,
    WebstoreSetupFile,
)
from ..models.forms import FormTemplate
from . import storage
from .activity import record_activity_with_audit
from .email import record_processed_activity, send_email
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
SAFE_ANSWER_MAPPING = {
    "store_name": {"target": "name", "label": "Store name"},
    "description": {"target": "description", "label": "Description"},
    "target_launch_at": {"target": "target_launch_at", "label": "Target launch"},
    "deadline_at": {"target": "deadline_at", "label": "Order deadline"},
    "event_name": {"target": "setup_profile.event_name", "label": "Event name"},
    "event_start_at": {"target": "event_start_at", "label": "Event date"},
    "event_location": {"target": "event_location", "label": "Event location"},
    "event_description": {"target": "setup_profile.event_description", "label": "Event description"},
    "event_type": {"target": "setup_profile.event_type", "label": "Event type"},
    "audience": {"target": "setup_profile.audience", "label": "Audience"},
    "goals": {"target": "setup_profile.goals", "label": "Goals"},
    "notes": {"target": "setup_profile.owner_notes", "label": "Owner notes"},
    "pickup_instructions": {"target": "setup_profile.pickup_instructions", "label": "Pickup instructions"},
    "customer_name": {"target": "setup_profile.customer_name", "label": "Customer name"},
    "organization_name": {"target": "setup_profile.organization_name", "label": "Organization"},
    "phone_number": {"target": "setup_profile.phone_number", "label": "Phone number"},
    "email_address": {"target": "setup_profile.email_address", "label": "Email address"},
    "decision_maker": {"target": "setup_profile.decision_maker", "label": "Decision maker"},
    "products_wanted": {"target": "setup_profile.products_wanted", "label": "Products wanted"},
    "design_count": {"target": "setup_profile.design_count", "label": "Design count"},
    "personalization_needed": {"target": "setup_profile.personalization_needed", "label": "Personalization needed"},
    "personalization_details": {"target": "setup_profile.personalization_details", "label": "Personalization details"},
    "apparel_colors": {"target": "setup_profile.apparel_colors", "label": "Apparel colors"},
    "open_to_suggestions": {"target": "setup_profile.open_to_suggestions", "label": "Open to suggestions"},
    "finished_artwork_status": {"target": "setup_profile.finished_artwork_status", "label": "Finished artwork status"},
    "design_notes": {"target": "setup_profile.design_notes", "label": "Design notes"},
    "brand_colors": {"target": "setup_profile.brand_colors", "label": "Brand colors"},
    "colors_to_avoid": {"target": "setup_profile.colors_to_avoid", "label": "Colors to avoid"},
    "fulfillment_method": {"target": "setup_profile.fulfillment_method", "label": "Fulfillment method"},
    "bag_label_orders": {"target": "setup_profile.bag_label_orders", "label": "Bag and label orders"},
    "approval_contact": {"target": "setup_profile.approval_contact", "label": "Approval contact"},
    "approval_required": {"target": "setup_profile.approval_required", "label": "Approval required"},
    "store_purpose": {"target": "setup_profile.store_purpose", "label": "Store purpose"},
    "access_policy_preference": {"target": "setup_profile.access_policy_preference", "label": "Access policy preference"},
    "catalog_change_frequency": {"target": "setup_profile.catalog_change_frequency", "label": "Catalog change frequency"},
    "billing_po_requirements": {"target": "setup_profile.billing_po_requirements", "label": "Billing or PO requirements"},
    "fundraiser_name": {"target": "setup_profile.fundraiser_name", "label": "Fundraiser name"},
    "fundraiser_goal_amount": {"target": "setup_profile.fundraiser_goal_amount", "label": "Fundraiser goal"},
    "fundraiser_start_at": {"target": "setup_profile.fundraiser_start_at", "label": "Fundraiser start"},
    "show_progress_bar": {"target": "setup_profile.show_progress_bar", "label": "Show progress bar"},
    "show_total_raised_publicly": {"target": "setup_profile.show_total_raised_publicly", "label": "Show total raised publicly"},
    "profit_allocation_type": {"target": "setup_profile.profit_allocation_type", "label": "Profit allocation type"},
    "profit_allocation_percentage": {"target": "setup_profile.profit_allocation_percentage", "label": "Profit allocation percent"},
    "fixed_amount_per_item": {"target": "setup_profile.fixed_amount_per_item", "label": "Fixed amount per item"},
    "allow_checkout_donations": {"target": "setup_profile.allow_checkout_donations", "label": "Checkout donations"},
    "donation_amount_options": {"target": "setup_profile.donation_amount_options", "label": "Donation options"},
    "allow_late_orders": {"target": "setup_profile.allow_late_orders", "label": "Allow late orders"},
    "event_fundraiser_enabled": {"target": "setup_profile.event_fundraiser_enabled", "label": "Event fundraiser enabled"},
    "brand_identity_name": {"target": "setup_profile.brand_identity_name", "label": "Brand identity"},
    "promotion_goal": {"target": "setup_profile.promotion_goal", "label": "Promotion goal"},
    "campaign_duration": {"target": "setup_profile.campaign_duration", "label": "Campaign duration"},
    "promo_channels": {"target": "setup_profile.promo_channels", "label": "Promotion channels"},
    "promo_copy_notes": {"target": "setup_profile.promo_copy_notes", "label": "Promo copy notes"},
    "employee_audience": {"target": "setup_profile.employee_audience", "label": "Employee audience"},
    "department_categories": {"target": "setup_profile.department_categories", "label": "Department categories"},
    "allowance_notes": {"target": "setup_profile.allowance_notes", "label": "Allowance notes"},
    "questionnaire_followup_needed": {"target": "setup_profile.questionnaire_followup_needed", "label": "Follow-up needed"},
}

WEBSTORE_FORM_ADAPTER = "webstore_questionnaire"


__all__ = [name for name in globals() if not name.startswith("__")]
