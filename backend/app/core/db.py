"""Motor client + collection accessors + one-time index setup."""
from __future__ import annotations

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
_client: AsyncIOMotorClient = AsyncIOMotorClient(_settings.mongo_url)
db: AsyncIOMotorDatabase = _client[_settings.db_name]


def get_client() -> AsyncIOMotorClient:
    return _client


async def ensure_indexes() -> None:
    """Create indexes idempotently. Called at FastAPI startup."""
    # Tenants + Users
    await db.tenants.create_index("id", unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index([("tenant_id", 1), ("email", 1)], unique=True)
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("expires_at")

    # Sequence counters
    await db.counters.create_index([("tenant_id", 1), ("name", 1)], unique=True)

    # Domain entities — all tenant-scoped
    for coll in ("customers", "quotes", "orders", "work_orders", "invoices", "payments",
                 "files", "attachments", "email_logs", "audit_events"):
        await db[coll].create_index("id", unique=True)
        await db[coll].create_index("tenant_id")

    # Sequential numbers (unique per tenant)
    await db.quotes.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.orders.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.work_orders.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.invoices.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)

    # One invoice per order (enforced) — user preference
    await db.invoices.create_index([("tenant_id", 1), ("order_id", 1)], unique=True, sparse=True)

    # Attachments polymorphic index
    await db.attachments.create_index([("tenant_id", 1), ("parent_type", 1), ("parent_id", 1)])

    # Audit event lookups
    await db.audit_events.create_index([("tenant_id", 1), ("entity_type", 1), ("entity_id", 1), ("created_at", -1)])
    await db.audit_events.create_index([("tenant_id", 1), ("created_at", -1)])

    # Email logs
    await db.email_logs.create_index([("tenant_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.email_logs.create_index([("tenant_id", 1), ("related_type", 1), ("related_id", 1)])

    # Pricing settings \u2014 one doc per tenant
    await db.pricing_settings.create_index("tenant_id", unique=True)

    # ---- EC2 — Shared Platform Services indexes ----
    # settings
    await db.settings.create_index([("tenant_id", 1), ("namespace", 1), ("key", 1)], unique=True)
    await db.settings.create_index([("tenant_id", 1), ("namespace", 1)])

    # activity_events
    await db.activity_events.create_index("id", unique=True)
    await db.activity_events.create_index([("tenant_id", 1), ("module", 1), ("created_at", -1)])
    await db.activity_events.create_index([("tenant_id", 1), ("entity_type", 1), ("entity_id", 1)])
    await db.activity_events.create_index([("tenant_id", 1), ("severity", 1), ("created_at", -1)])

    # notifications
    await db.notifications.create_index("id", unique=True)
    await db.notifications.create_index(
        [("tenant_id", 1), ("recipient_user_id", 1), ("status", 1), ("created_at", -1)]
    )
    await db.notifications.create_index(
        [("tenant_id", 1), ("recipient_user_id", 1), ("read_at", 1)]
    )

    # email_activity
    await db.email_activity.create_index("id", unique=True)
    await db.email_activity.create_index([("tenant_id", 1), ("email_log_id", 1), ("event_timestamp", -1)])
    await db.email_activity.create_index([("provider", 1), ("provider_event_id", 1)], unique=True)
    await db.email_activity.create_index(
        [("tenant_id", 1), ("related_entity_type", 1), ("related_entity_id", 1)]
    )

    # webhook_events
    await db.webhook_events.create_index("id", unique=True)
    await db.webhook_events.create_index([("provider", 1), ("provider_event_id", 1)], unique=True)
    await db.webhook_events.create_index([("provider", 1), ("processing_status", 1), ("received_at", -1)])

    # file_links / document_links / document_shares
    await db.file_links.create_index("id", unique=True)
    await db.file_links.create_index([("tenant_id", 1), ("parent_type", 1), ("parent_id", 1)])
    await db.file_links.create_index([("tenant_id", 1), ("file_id", 1)])
    await db.document_links.create_index("id", unique=True)
    await db.document_links.create_index(
        [("tenant_id", 1), ("document_id", 1), ("entity_type", 1), ("entity_id", 1)]
    )
    await db.document_shares.create_index("id", unique=True)
    await db.document_shares.create_index([("tenant_id", 1), ("document_id", 1)])
    await db.document_shares.create_index([("tenant_id", 1), ("recipient_key", 1), ("revoked", 1)])

    # feature_entitlements
    await db.feature_entitlements.create_index("id", unique=True)
    await db.feature_entitlements.create_index([("tenant_id", 1), ("feature_key", 1)], unique=True)

    # ---- EC3 — Quotes / Orders / Pricing Snapshots indexes ----
    # quote_line_items
    await db.quote_line_items.create_index("id", unique=True)
    await db.quote_line_items.create_index(
        [("tenant_id", 1), ("quote_id", 1), ("revision_number", 1), ("position", 1)]
    )
    # quote_revisions — one row per (quote, revision_number)
    await db.quote_revisions.create_index("id", unique=True)
    await db.quote_revisions.create_index(
        [("tenant_id", 1), ("quote_id", 1), ("revision_number", 1)], unique=True
    )
    # quotes — supplementary lookups
    await db.quotes.create_index([("tenant_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.quotes.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.quotes.create_index([("tenant_id", 1), ("expires_at", 1)])
    await db.quotes.create_index([("tenant_id", 1), ("converted_order_id", 1)])
    # orders — supplementary lookups
    await db.orders.create_index([("tenant_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.orders.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.orders.create_index([("tenant_id", 1), ("source_quote_id", 1)])
    # order_items
    await db.order_items.create_index("id", unique=True)
    await db.order_items.create_index([("tenant_id", 1), ("order_id", 1), ("position", 1)])
    await db.order_items.create_index([("tenant_id", 1), ("production_required", 1)])

    # ---- EC4 — Payments indexes ----
    await db.payments.create_index("id", unique=True)
    await db.payments.create_index([("tenant_id", 1), ("invoice_id", 1), ("received_at", -1)])
    await db.payments.create_index([("tenant_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.payments.create_index(
        [("tenant_id", 1), ("invoice_id", 1), ("idempotency_key", 1)],
        unique=True, partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.payments.create_index(
        "stripe_payment_intent_id", unique=True,
        partialFilterExpression={"stripe_payment_intent_id": {"$type": "string"}},
    )
    await db.payments.create_index(
        "stripe_charge_id", unique=True,
        partialFilterExpression={"stripe_charge_id": {"$type": "string"}},
    )
    await db.payments.create_index(
        "stripe_refund_id", unique=True,
        partialFilterExpression={"stripe_refund_id": {"$type": "string"}},
    )
    await db.invoices.create_index([("tenant_id", 1), ("document_status", 1), ("updated_at", -1)])
    await db.invoices.create_index([("tenant_id", 1), ("financial_status", 1), ("due_date", 1)])

    # ---- EC6 — Documents, Portal, Proofs, Signatures, Approvals, Public Tokens ----
    await db.documents.create_index("id", unique=True)
    await db.documents.create_index([("tenant_id", 1), ("category", 1), ("created_at", -1)])
    await db.documents.create_index([("tenant_id", 1), ("customer_id", 1), ("archived", 1)])
    await db.document_versions.create_index("id", unique=True)
    await db.document_versions.create_index([("tenant_id", 1), ("document_id", 1), ("version", -1)])

    await db.proofs.create_index("id", unique=True)
    await db.proofs.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.proofs.create_index([("tenant_id", 1), ("parent_type", 1), ("parent_id", 1)])
    await db.proofs.create_index([("tenant_id", 1), ("customer_id", 1), ("status", 1)])
    await db.proof_versions.create_index("id", unique=True)
    await db.proof_versions.create_index([("tenant_id", 1), ("proof_id", 1), ("version", -1)], unique=True)

    await db.approvals.create_index("id", unique=True)
    await db.approvals.create_index([("tenant_id", 1), ("parent_type", 1), ("parent_id", 1), ("created_at", -1)])

    await db.signature_requests.create_index("id", unique=True)
    await db.signature_requests.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.signature_requests.create_index([("tenant_id", 1), ("parent_type", 1), ("parent_id", 1)])
    await db.signatures.create_index("id", unique=True)
    await db.signatures.create_index([("tenant_id", 1), ("request_id", 1)])

    await db.portal_identities.create_index("id", unique=True)
    await db.portal_identities.create_index([("tenant_id", 1), ("email", 1)], unique=True)
    await db.portal_identities.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.portal_identities.create_index([("tenant_id", 1), ("status", 1)])

    await db.magic_link_tokens.create_index("id", unique=True)
    await db.magic_link_tokens.create_index("token_hash", unique=True)
    await db.magic_link_tokens.create_index([("tenant_id", 1), ("portal_identity_id", 1), ("expires_at", 1)])

    await db.public_action_tokens.create_index("id", unique=True)
    await db.public_action_tokens.create_index("token_hash", unique=True)
    await db.public_action_tokens.create_index([("tenant_id", 1), ("action", 1), ("parent_type", 1), ("parent_id", 1)])
    await db.public_action_tokens.create_index([("tenant_id", 1), ("expires_at", 1)])

    await db.quote_requests.create_index("id", unique=True)
    await db.quote_requests.create_index([("tenant_id", 1), ("number", 1)], unique=True, sparse=True)
    await db.quote_requests.create_index([("tenant_id", 1), ("status", 1), ("created_at", -1)])

    await db.customer_intakes.create_index("id", unique=True)
    await db.customer_intakes.create_index([("tenant_id", 1), ("customer_id", 1), ("status", 1)])

    # ---- EC7 phase 7a — Materials + Inventory ----
    await db.materials.create_index("id", unique=True)
    await db.materials.create_index([("tenant_id", 1), ("sku", 1)], unique=True, sparse=True)
    await db.materials.create_index([("tenant_id", 1), ("category", 1), ("active", 1)])
    await db.materials.create_index([("tenant_id", 1), ("name", 1)])
    await db.material_cost_history.create_index("id", unique=True)
    await db.material_cost_history.create_index([("tenant_id", 1), ("material_id", 1), ("effective_at", -1)])
    await db.inventory_locations.create_index("id", unique=True)
    await db.inventory_locations.create_index([("tenant_id", 1), ("name", 1)])
    await db.inventory_items.create_index("id", unique=True)
    await db.inventory_items.create_index(
        [("tenant_id", 1), ("material_id", 1), ("location_id", 1)], unique=True
    )
    await db.inventory_movements.create_index("id", unique=True)
    await db.inventory_movements.create_index([("tenant_id", 1), ("material_id", 1), ("created_at", -1)])
    await db.inventory_movements.create_index([("tenant_id", 1), ("location_id", 1), ("created_at", -1)])
    await db.inventory_movements.create_index([("tenant_id", 1), ("source_entity_type", 1), ("source_entity_id", 1)])
    await db.inventory_movements.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.inventory_reservations.create_index("id", unique=True)
    await db.inventory_reservations.create_index([("tenant_id", 1), ("material_id", 1), ("location_id", 1), ("active", 1)])
    await db.inventory_reservations.create_index([("tenant_id", 1), ("source_entity_type", 1), ("source_entity_id", 1)])

    logger.info("MongoDB indexes ensured")
