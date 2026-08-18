"""EC14 - Webstores service layer."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
import secrets
from typing import Any, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db as _real_db
from ..core.config import get_settings as _real_get_settings
from ..core.permissions import PlatformPerm, Perm, has_platform_admin_access, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.webstore import (
    Webstore,
    WebstoreAIUsageEvent,
    WebstoreActivity,
    WebstoreArtworkFile,
    WebstoreBuyerOrder,
    WebstoreChangeRequest,
    WebstoreLaunchPacket,
    WebstoreLedgerEntry,
    WebstoreLifecycleEvent,
    WebstoreMockup,
    WebstoreOwner,
    WebstorePacketApproval,
    WebstoreProduct,
    WebstoreProductCategory,
    WebstoreProductTemplate,
    WebstorePurchaseIntent,
    WebstoreQuestionnaireSubmission,
    WebstoreStripeConnectRecord,
    WebstoreTermsAcceptance,
)
from ..repositories.webstores import WebstoreRepository
from .activity import record_activity_with_audit
from .approvals_signatures_service import record_approval
from . import ai_gateway
from . import ai_studio
from . import webstore_branding as branding_svc
from .entitlements import has_entitlement
from .email import record_processed_activity, send_email
from .portal_identity import create_portal_identity
from .sequence import next_number, next_record_number
from . import storage
from .webstore_payment_provider import ProviderAuthority, get_webstore_payment_provider as _real_get_webstore_payment_provider, provider_configuration_status as _real_provider_configuration_status
from .webstore_type_requirements import default_store_settings, evaluate_type_requirements
from .webstore_constants import (
    CATALOG_PRODUCT_STATUSES,
    CATEGORY_STATUSES,
    CHANGE_REQUEST_CATEGORIES,
    CHANGE_REQUEST_STATUSES,
    CURRENT_WEBSTORE_TERMS_VERSION,
    CUSTOMER_IMAGE_SLOTS,
    FULFILLMENT_METHODS,
    INTERNAL_STATUS_TO_PHASE6,
    LIVE_BLOCKING_STATUSES,
    MATERIAL_PRODUCT_FIELDS,
    MATERIAL_STORE_FIELDS,
    PAYMENT_READINESS_STATES,
    PHASE6_LIFECYCLE_STATES,
    PHASE6_LIFECYCLE_TRANSITIONS,
    PHASE6_TO_INTERNAL_STATUS,
    PLATFORM_TEMPLATE_TENANT_ID,
    PRODUCT_APPROVAL_DECISIONS,
    PRODUCT_APPROVAL_STATUSES,
    PRODUCT_IMAGE_EXTENSIONS,
    PRODUCT_PURCHASABLE_STATUSES,
    PRODUCT_STATUSES,
    PUBLIC_CHECKOUT_ENABLED,
    SLUG_RE,
    STAGE4A_FINANCIAL_VARIANT_FIELDS,
    STAGE4A_PUBLICATION_FIELDS,
    STARTER_PRODUCT_TEMPLATE_MARKER,
    STARTER_PRODUCT_TEMPLATES,
    TEMPLATE_SCOPES,
    TEMPLATE_STATUSES,
    VALID_WEBSTORE_STATUSES,
    VALID_WEBSTORE_TYPES,
    WEBSTORE_TRANSITIONS,
    WEBSTORES_FEATURE_KEY,
)

owners_repo = WebstoreRepository("webstore_owners")
stores_repo = WebstoreRepository("webstores")
templates_repo = WebstoreRepository("webstore_product_templates")
products_repo = WebstoreRepository("webstore_products")
categories_repo = WebstoreRepository("webstore_product_categories")
submissions_repo = WebstoreRepository("webstore_questionnaire_submissions")
artwork_repo = WebstoreRepository("webstore_artwork_files")
mockups_repo = WebstoreRepository("webstore_mockups")
packets_repo = WebstoreRepository("webstore_launch_packets")
packet_approvals_repo = WebstoreRepository("webstore_packet_approvals")
terms_acceptances_repo = WebstoreRepository("webstore_terms_acceptances")
change_requests_repo = WebstoreRepository("webstore_change_requests")
buyer_orders_repo = WebstoreRepository("webstore_buyer_orders")
ledger_repo = WebstoreRepository("webstore_ledger_entries")
activity_repo = WebstoreRepository("webstore_activity_events")
lifecycle_events_repo = WebstoreRepository("webstore_lifecycle_events")
ai_repo = WebstoreRepository("webstore_ai_usage_events")

WEBSTORE_PRODUCT_AI_ACTIONS: dict[str, dict[str, Any]] = {
    "product_description": {
        "label": "Product description draft",
        "tool_key": "product_content_builder",
        "mode_key": "webstore_product_content",
        "capability_key": "webstore.product_description",
        "result_record_type": "editable_draft",
        "output_kind": "product_content_draft",
        "usage_note": "Saves an editable AI Studio draft. It never changes product text, pricing, availability, or published storefront content.",
    },
    "product_mockup": {
        "label": "Product mockup concept",
        "tool_key": "mockup_generator",
        "mode_key": "product_mockup",
        "capability_key": "studio.image.mockup",
        "result_record_type": "generated_asset",
        "output_kind": "image_concept",
        "usage_note": "Saves an AI Studio generated asset for review. It never creates, replaces, approves, or publishes a Webstore mockup.",
    },
}


class WebstoreError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class _CompatDbProxy:
    def __getattr__(self, name: str) -> Any:
        override = _facade_override("db", self)
        if override is not self:
            return getattr(override, name)
        return getattr(_real_db, name)

    def __getitem__(self, name: str) -> Any:
        override = _facade_override("db", self)
        if override is not self:
            return override[name]
        return _real_db[name]


db = _CompatDbProxy()


def _facade_override(name: str, fallback: Any) -> Any:
    import sys

    facade = sys.modules.get(__package__ + ".webstores")
    override = getattr(facade, name, None) if facade is not None else None
    if override is not None and override is not fallback:
        return override
    return fallback


def get_settings() -> Any:
    return _facade_override("get_settings", get_settings)() if _facade_override("get_settings", get_settings) is not get_settings else _real_get_settings()


def get_webstore_payment_provider(settings: Any) -> Any:
    override = _facade_override("get_webstore_payment_provider", get_webstore_payment_provider)
    if override is not get_webstore_payment_provider:
        return override(settings)
    return _real_get_webstore_payment_provider(settings)


def provider_configuration_status(*args: Any, **kwargs: Any) -> dict[str, Any]:
    override = _facade_override("provider_configuration_status", provider_configuration_status)
    if override is not provider_configuration_status:
        return override(*args, **kwargs)
    return _real_provider_configuration_status(*args, **kwargs)


__all__ = [name for name in globals() if not name.startswith("__")]
