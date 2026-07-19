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
    # Migration: the reset-token field was renamed `token` -> `token_hash`
    # (tokens are now stored hashed, never in plaintext). Drop the old
    # unique index if it's still present from before the rename, otherwise
    # every insert after the first collides on the now-unused `token: null`.
    existing_pwd_reset_indexes = await db.password_reset_tokens.index_information()
    if "token_1" in existing_pwd_reset_indexes:
        await db.password_reset_tokens.drop_index("token_1")
    await db.password_reset_tokens.create_index("token_hash", unique=True)
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
    await db.portal_identities.create_index([("tenant_id", 1), ("webstore_owner_id", 1)])
    await db.portal_identities.create_index([("tenant_id", 1), ("webstore_id", 1)])
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

    # ---- EC7 phase 7b — Vendors + Supplier Catalog + Purchase Orders + Receiving ----
    await db.vendors.create_index("id", unique=True)
    await db.vendors.create_index([("tenant_id", 1), ("name", 1)])
    await db.vendors.create_index([("tenant_id", 1), ("active", 1)])

    await db.vendor_materials.create_index("id", unique=True)
    await db.vendor_materials.create_index(
        [("tenant_id", 1), ("vendor_id", 1), ("material_id", 1), ("supplier_product_id", 1)],
        unique=True,
    )
    await db.vendor_materials.create_index([("tenant_id", 1), ("material_id", 1)])

    await db.supplier_warehouses.create_index("id", unique=True)
    await db.supplier_warehouses.create_index([("tenant_id", 1), ("vendor_id", 1), ("code", 1)], unique=True)

    await db.supplier_products.create_index("id", unique=True)
    await db.supplier_products.create_index(
        [("tenant_id", 1), ("vendor_id", 1), ("supplier_sku", 1)], unique=True
    )
    await db.supplier_products.create_index([("tenant_id", 1), ("category", 1), ("active", 1)])
    await db.supplier_products.create_index([("tenant_id", 1), ("family", 1)])
    await db.supplier_products.create_index([("tenant_id", 1), ("compatible_group", 1)])

    await db.supplier_product_stock.create_index("id", unique=True)
    await db.supplier_product_stock.create_index(
        [("tenant_id", 1), ("supplier_product_id", 1), ("warehouse_id", 1)], unique=True
    )

    await db.supplier_order_log.create_index("id", unique=True)
    await db.supplier_order_log.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)], unique=True
    )
    await db.supplier_order_log.create_index([("tenant_id", 1), ("purchase_order_id", 1), ("submitted_at", -1)])
    await db.supplier_order_log.create_index(
        "supplier_order_id", unique=True,
        partialFilterExpression={"supplier_order_id": {"$type": "string"}},
    )

    await db.purchase_orders.create_index("id", unique=True)
    await db.purchase_orders.create_index([("tenant_id", 1), ("number", 1)], unique=True)
    await db.purchase_orders.create_index([("tenant_id", 1), ("vendor_id", 1), ("created_at", -1)])
    await db.purchase_orders.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])

    await db.purchase_order_lines.create_index("id", unique=True)
    await db.purchase_order_lines.create_index(
        [("tenant_id", 1), ("purchase_order_id", 1), ("position", 1)]
    )
    await db.purchase_order_lines.create_index([("tenant_id", 1), ("material_id", 1)])

    await db.receiving_records.create_index("id", unique=True)
    await db.receiving_records.create_index(
        [("tenant_id", 1), ("purchase_order_id", 1), ("idempotency_key", 1)], unique=True
    )
    await db.receiving_records.create_index([("tenant_id", 1), ("purchase_order_id", 1), ("received_at", -1)])

    # ---- EC7 phase 7c — Expenses + Categories + Tax Exemptions ----
    await db.expense_categories.create_index("id", unique=True)
    await db.expense_categories.create_index([("tenant_id", 1), ("key", 1)], unique=True)
    await db.expense_categories.create_index([("tenant_id", 1), ("position", 1)])

    await db.expenses.create_index("id", unique=True)
    await db.expenses.create_index([("tenant_id", 1), ("number", 1)], unique=True)
    await db.expenses.create_index([("tenant_id", 1), ("state", 1), ("expense_date", -1)])
    await db.expenses.create_index([("tenant_id", 1), ("category_key", 1), ("expense_date", -1)])
    await db.expenses.create_index([("tenant_id", 1), ("vendor_id", 1)])
    await db.expenses.create_index([("tenant_id", 1), ("order_id", 1)])
    await db.expenses.create_index([("tenant_id", 1), ("purchase_order_id", 1)])
    await db.expenses.create_index([("tenant_id", 1), ("customer_id", 1)])

    await db.expense_attachments.create_index("id", unique=True)
    await db.expense_attachments.create_index([("tenant_id", 1), ("expense_id", 1), ("archived", 1)])

    await db.tax_exemptions.create_index("id", unique=True)
    await db.tax_exemptions.create_index(
        [("tenant_id", 1), ("customer_id", 1), ("jurisdiction", 1), ("effective_from", -1)]
    )
    await db.tax_exemptions.create_index([("tenant_id", 1), ("jurisdiction", 1), ("archived", 1)])

    # ---- EC8 phase 8a — Employees + Announcements ----
    await db.employees.create_index("id", unique=True)
    await db.employees.create_index([("tenant_id", 1), ("status", 1), ("name", 1)])
    await db.employees.create_index(
        [("tenant_id", 1), ("linked_user_id", 1)],
        unique=True,
        partialFilterExpression={"linked_user_id": {"$type": "string"}},
    )

    await db.announcements.create_index("id", unique=True)
    await db.announcements.create_index([("tenant_id", 1), ("status", 1), ("published_at", -1)])

    # ---- EC8 phase 8b — Time Clock + Timesheets ----
    await db.time_entries.create_index("id", unique=True)
    await db.time_entries.create_index(
        [("tenant_id", 1), ("employee_id", 1)],
        unique=True,
        partialFilterExpression={"status": "open"},
    )
    await db.time_entries.create_index([("tenant_id", 1), ("employee_id", 1), ("clock_in_at", -1)])
    await db.time_entries.create_index([("tenant_id", 1), ("work_date", 1)])
    await db.time_entries.create_index([("tenant_id", 1), ("status", 1)])

    await db.timesheets.create_index("id", unique=True)
    await db.timesheets.create_index([("tenant_id", 1), ("employee_id", 1), ("week_start", 1)], unique=True)
    await db.timesheets.create_index([("tenant_id", 1), ("status", 1), ("week_start", -1)])

    # ---- EC8 phase 8c — Scheduling + Employee Portal ----
    await db.schedules.create_index("id", unique=True)
    await db.schedules.create_index([("tenant_id", 1), ("period_start", 1)], unique=True)
    await db.schedules.create_index([("tenant_id", 1), ("status", 1)])

    await db.shifts.create_index("id", unique=True)
    await db.shifts.create_index([("tenant_id", 1), ("schedule_id", 1)])
    await db.shifts.create_index([("tenant_id", 1), ("employee_id", 1), ("shift_date", 1)])
    await db.shifts.create_index([("tenant_id", 1), ("employee_id", 1), ("start_at", 1), ("end_at", 1)])

    # portal_identities — EC8c employee-typed identities: 1:1 with Employee.
    # (Existing (tenant_id, email) unique index already prevents any duplicate
    # regardless of type.)
    await db.portal_identities.create_index(
        [("tenant_id", 1), ("employee_id", 1)],
        unique=True,
        partialFilterExpression={"portal_type": "employee"},
    )
    await db.portal_identities.create_index([("tenant_id", 1), ("portal_type", 1), ("status", 1)])

    # ---- EC8 phase 8d — Payroll (Pay Periods, Snapshots, Ledger Transactions) ----
    await db.pay_periods.create_index("id", unique=True)
    await db.pay_periods.create_index([("tenant_id", 1), ("start_date", 1)], unique=True)
    await db.pay_periods.create_index([("tenant_id", 1), ("status", 1), ("start_date", -1)])

    await db.payroll_snapshots.create_index("id", unique=True)
    await db.payroll_snapshots.create_index([("tenant_id", 1), ("pay_period_id", 1), ("employee_id", 1)], unique=True)
    await db.payroll_snapshots.create_index([("tenant_id", 1), ("employee_id", 1)])

    await db.payroll_transactions.create_index("id", unique=True)
    await db.payroll_transactions.create_index([("tenant_id", 1), ("employee_id", 1), ("pay_period_id", 1)])
    await db.payroll_transactions.create_index([("tenant_id", 1), ("pay_period_id", 1), ("type", 1), ("voided", 1)])
    await db.payroll_transactions.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    # payroll_carryovers — pending carryover ledger bridge (only exists between
    # a period's close and the creation of its eligible next period).
    await db.payroll_carryovers.create_index("id", unique=True)
    await db.payroll_carryovers.create_index(
        [("tenant_id", 1), ("linked", 1), ("source_period_end_date_plus_one", 1)]
    )
    await db.payroll_carryovers.create_index([("tenant_id", 1), ("employee_id", 1), ("source_period_id", 1)])

    # ---- EC8 phase 8e — Equipment, Training & Certification ----
    await db.equipment.create_index("id", unique=True)
    await db.equipment.create_index([("tenant_id", 1), ("status", 1)])
    await db.equipment.create_index([("tenant_id", 1), ("category", 1)])

    await db.training_definitions.create_index("id", unique=True)
    await db.training_definitions.create_index([("tenant_id", 1), ("active", 1)])
    await db.training_definitions.create_index([("tenant_id", 1), ("equipment_id", 1)])

    await db.training_assignments.create_index("id", unique=True)
    await db.training_assignments.create_index([("tenant_id", 1), ("employee_id", 1), ("status", 1)])
    await db.training_assignments.create_index([("tenant_id", 1), ("due_date", 1)])
    await db.training_assignments.create_index([("tenant_id", 1), ("equipment_id", 1)])
    await db.training_assignments.create_index([("tenant_id", 1), ("training_definition_id", 1)])

    await db.quiz_attempts.create_index("id", unique=True)
    await db.quiz_attempts.create_index([("tenant_id", 1), ("training_assignment_id", 1), ("attempt_number", 1)])

    await db.practical_signoffs.create_index("id", unique=True)
    await db.practical_signoffs.create_index([("tenant_id", 1), ("training_assignment_id", 1)])

    await db.certifications.create_index("id", unique=True)
    await db.certifications.create_index([("tenant_id", 1), ("employee_id", 1), ("status", 1)])
    await db.certifications.create_index([("tenant_id", 1), ("equipment_id", 1), ("status", 1)])
    await db.certifications.create_index([("tenant_id", 1), ("expiration_date", 1)])
    # Prevents two simultaneously-"certified" rows for the same Employee+Equipment (duplicate active certification).
    await db.certifications.create_index(
        [("tenant_id", 1), ("employee_id", 1), ("equipment_id", 1), ("status", 1)],
        unique=True,
        partialFilterExpression={"status": "certified", "equipment_id": {"$type": "string"}},
    )

    # document_links — first actively wired up in EC8 phase 8e (Equipment/Training docs)
    await db.document_links.create_index([("tenant_id", 1), ("entity_type", 1), ("entity_id", 1)])

    # ---- EC9 phase 9A — Material Pricing Profiles, Pricing Components, Saved Items ----
    await db.material_pricing_profiles.create_index("id", unique=True)
    await db.material_pricing_profiles.create_index([("tenant_id", 1), ("material_id", 1)], unique=True)

    await db.pricing_components.create_index("id", unique=True)
    await db.pricing_components.create_index([("tenant_id", 1), ("key", 1)], unique=True)

    await db.pricing_saved_items.create_index("id", unique=True)
    await db.pricing_saved_items.create_index([("tenant_id", 1), ("category", 1)])
    await db.pricing_saved_items.create_index([("tenant_id", 1), ("quick_select", 1)])

    # ---- EC9 phase 9C — Grouped Pricing Setup Quiz submissions ----
    await db.pricing_quiz_submissions.create_index("id", unique=True)
    await db.pricing_quiz_submissions.create_index([("tenant_id", 1), ("status", 1)])
    await db.pricing_quiz_submissions.create_index([("tenant_id", 1), ("created_at", -1)])

    # ---- EC9 phase 9G — Immutable Pricing Snapshot records + Advisory requests ----
    await db.pricing_snapshot_records.create_index("id", unique=True)
    await db.pricing_snapshot_records.create_index(
        [("tenant_id", 1), ("source_type", 1), ("source_id", 1), ("status", 1)]
    )
    await db.pricing_snapshot_records.create_index([("tenant_id", 1), ("created_at", -1)])

    await db.pricing_advisory_requests.create_index("id", unique=True)
    await db.pricing_advisory_requests.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.pricing_advisory_requests.create_index([("tenant_id", 1), ("historical_snapshot_id", 1)])

    # ---- EC10 phase 10A — Intake Submissions ----
    await db.intake_submissions.create_index("id", unique=True)
    await db.intake_submissions.create_index([("tenant_id", 1), ("intake_number", 1)], unique=True)
    await db.intake_submissions.create_index([("tenant_id", 1), ("status", 1)])
    await db.intake_submissions.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.intake_submissions.create_index([("tenant_id", 1), ("quote_id", 1)])
    await db.intake_submissions.create_index([("tenant_id", 1), ("order_id", 1)])
    await db.intake_submissions.create_index([("tenant_id", 1), ("assigned_user_id", 1)])
    await db.intake_submissions.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.intake_submissions.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True, partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    # ---- EC10 phase 10C — Visual Markup ----
    await db.visual_markups.create_index("id", unique=True)
    await db.visual_markups.create_index([("tenant_id", 1), ("status", 1)])
    await db.visual_markups.create_index([("tenant_id", 1), ("intake_id", 1)])
    await db.visual_markups.create_index([("tenant_id", 1), ("intake_item_id", 1)])
    await db.visual_markups.create_index([("tenant_id", 1), ("source_file_id", 1)])
    await db.markup_versions.create_index("id", unique=True)
    await db.markup_versions.create_index([("tenant_id", 1), ("visual_markup_id", 1), ("version_number", 1)], unique=True)

    # ---- EC10 phase 10D — Customer Decision Room (internal authoring only) ----
    await db.decision_rooms.create_index("id", unique=True)
    await db.decision_rooms.create_index([("tenant_id", 1), ("status", 1)])
    await db.decision_rooms.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.decision_rooms.create_index([("tenant_id", 1), ("quote_id", 1)])
    await db.decision_rooms.create_index([("tenant_id", 1), ("order_id", 1)])
    await db.decision_rooms.create_index([("tenant_id", 1), ("intake_id", 1)])
    await db.decision_rooms.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.decision_room_versions.create_index("id", unique=True)
    await db.decision_room_versions.create_index(
        [("tenant_id", 1), ("decision_room_id", 1), ("version_number", 1)], unique=True,
    )

    # ---- EC10 phase 10E-2 — Customer Decisions (append-only) ----
    await db.customer_decisions.create_index("id", unique=True)
    # Idempotency: a duplicate submission with the same client-generated key
    # for the same room must never create a second row. A COMPOUND sparse
    # index is NOT sufficient here — MongoDB only excludes documents from a
    # sparse compound index if they're missing EVERY indexed field, and
    # `tenant_id`/`decision_room_id` are always present, so two key-less
    # rows would still collide. A `partialFilterExpression` restricting the
    # index to documents where `idempotency_key` is an actual string is the
    # correct way to let multiple key-less rows coexist.
    await db.customer_decisions.create_index(
        [("tenant_id", 1), ("decision_room_id", 1), ("idempotency_key", 1)], unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.customer_decisions.create_index([("tenant_id", 1), ("decision_room_id", 1), ("created_at", -1)])
    await db.customer_decisions.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.customer_decisions.create_index([("tenant_id", 1), ("public_token_id", 1)])

    # ---- EC10 phase 10E-3 — Questions, anchored overlays, save-for-later ----
    await db.decision_room_questions.create_index("id", unique=True)
    await db.decision_room_questions.create_index(
        [("tenant_id", 1), ("decision_room_id", 1), ("idempotency_key", 1)], unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.decision_room_questions.create_index([("tenant_id", 1), ("decision_room_id", 1), ("created_at", -1)])
    await db.decision_room_overlays.create_index("id", unique=True)
    await db.decision_room_overlays.create_index(
        [("tenant_id", 1), ("decision_room_id", 1), ("idempotency_key", 1)], unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.decision_room_overlays.create_index([("tenant_id", 1), ("decision_room_id", 1), ("created_at", -1)])
    await db.decision_room_saved_for_later.create_index("id", unique=True)
    await db.decision_room_saved_for_later.create_index(
        [("tenant_id", 1), ("decision_room_id", 1), ("idempotency_key", 1)], unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    # ---- EC10 phase 10E-4 — Internal review queue side metadata ----
    await db.decision_room_review_meta.create_index("id", unique=True)
    await db.decision_room_review_meta.create_index(
        [("tenant_id", 1), ("record_type", 1), ("record_id", 1)], unique=True,
    )
    await db.decision_room_internal_notes.create_index("id", unique=True)
    await db.decision_room_internal_notes.create_index(
        [("tenant_id", 1), ("record_type", 1), ("record_id", 1), ("created_at", -1)],
    )

    # ---- EC10 phase 10G - reusable intake/questionnaire/decision-option templates ----
    await db.template_definitions.create_index("id", unique=True)
    await db.template_definitions.create_index([("tenant_id", 1), ("template_type", 1), ("active", 1)])
    await db.template_definitions.create_index([("tenant_id", 1), ("name", 1), ("template_type", 1)])
    await db.template_definitions.create_index([("owner_scope", 1), ("template_type", 1), ("active", 1), ("source_status", 1)])
    await db.template_definitions.create_index([("tenant_id", 1), ("source_template_id", 1), ("source_template_version", 1)])
    await db.template_definitions.create_index([("tenant_id", 1), ("channels", 1), ("template_type", 1)])
    await db.template_definitions.create_index([("pack_id", 1), ("starter_template", 1), ("premium_reserved", 1)])
    await db.template_packs.create_index("id", unique=True)
    await db.template_packs.create_index([("pack_type", 1), ("active", 1), ("starter_pack", 1), ("premium_reserved", 1)])

    # ---- EC11 phase 11A - Production Workflow Definitions ----
    await db.production_workflows.create_index("id", unique=True)
    await db.production_workflows.create_index([("tenant_id", 1), ("workflow_key", 1)], unique=True)
    await db.production_workflows.create_index([("tenant_id", 1), ("is_tenant_default", 1), ("active", 1)])
    await db.production_workflows.create_index([("tenant_id", 1), ("category_ids", 1), ("active", 1)])
    await db.production_workflows.create_index([("tenant_id", 1), ("scope_type", 1), ("archived_at", 1)])

    # ---- EC11 phase 11C - Live Work Order / Order Item production stages ----
    await db.order_item_workflow_overrides.create_index("id", unique=True)
    await db.order_item_workflow_overrides.create_index(
        [("tenant_id", 1), ("order_item_id", 1)], unique=True,
    )
    await db.order_item_workflow_overrides.create_index([("tenant_id", 1), ("order_id", 1)])

    await db.production_workflow_instances.create_index("id", unique=True)
    await db.production_workflow_instances.create_index(
        [("tenant_id", 1), ("work_order_id", 1), ("order_item_id", 1)], unique=True,
    )
    await db.production_workflow_instances.create_index([("tenant_id", 1), ("order_id", 1)])

    await db.production_stage_instances.create_index("id", unique=True)
    await db.production_stage_instances.create_index(
        [("tenant_id", 1), ("workflow_instance_id", 1), ("stage_key", 1)], unique=True,
    )
    await db.production_stage_instances.create_index([("tenant_id", 1), ("work_order_id", 1), ("sequence", 1)])
    await db.production_stage_instances.create_index([("tenant_id", 1), ("order_item_id", 1), ("sequence", 1)])
    await db.production_stage_instances.create_index([("tenant_id", 1), ("assigned_employee_id", 1), ("status", 1)])

    # EC11 Phase 11F - shared-device production kiosk sessions and one-time supervisor overrides.
    await db.production_kiosk_sessions.create_index("id", unique=True)
    await db.production_kiosk_sessions.create_index("device_token_hash", unique=True)
    await db.production_kiosk_sessions.create_index([("tenant_id", 1), ("status", 1), ("expires_at", 1)])
    await db.production_kiosk_sessions.create_index([("tenant_id", 1), ("activated_by_user_id", 1)])
    await db.production_kiosk_supervisor_overrides.create_index("id", unique=True)
    await db.production_kiosk_supervisor_overrides.create_index("override_token_hash", unique=True)
    await db.production_kiosk_supervisor_overrides.create_index([("tenant_id", 1), ("kiosk_session_id", 1), ("expires_at", 1)])

    # ---- EC12 Phase 12A - shared task foundation ----
    await db.tasks.create_index("id", unique=True)
    await db.tasks.create_index([("tenant_id", 1), ("status", 1), ("archived_at", 1), ("due_at", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("priority", 1), ("status", 1), ("due_at", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("assigned_user_id", 1), ("status", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("assigned_employee_id", 1), ("status", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("created_by_user_id", 1), ("status", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("task_type", 1), ("status", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("quote_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("order_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("order_item_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("work_order_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("invoice_id", 1)])
    await db.tasks.create_index([("tenant_id", 1), ("production_stage_id", 1)])
    await db.tasks.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.task_comments.create_index("id", unique=True)
    await db.task_comments.create_index([("tenant_id", 1), ("task_id", 1), ("created_at", 1)])
    await db.task_reminders.create_index("id", unique=True)
    await db.task_reminders.create_index(
        [("tenant_id", 1), ("task_id", 1), ("reminder_kind", 1), ("policy_key", 1)],
        unique=True,
    )

    # ---- EC12 Phase 12C - employee time-off and absence workflow ----
    await db.time_off_requests.create_index("id", unique=True)
    await db.time_off_requests.create_index([("tenant_id", 1), ("employee_id", 1), ("status", 1), ("start_at", 1)])
    await db.time_off_requests.create_index([("tenant_id", 1), ("status", 1), ("start_at", 1)])

    # ---- EC12 Phase 12D - stored appointments for shared calendar feed ----
    await db.calendar_events.create_index("id", unique=True)
    await db.calendar_events.create_index([("tenant_id", 1), ("start_at", 1), ("end_at", 1), ("status", 1)])
    await db.calendar_events.create_index([("tenant_id", 1), ("employee_id", 1), ("start_at", 1)])
    await db.calendar_events.create_index([("tenant_id", 1), ("customer_id", 1), ("start_at", 1)])
    await db.calendar_events.create_index([("tenant_id", 1), ("work_order_id", 1), ("start_at", 1)])
    await db.calendar_events.create_index([("tenant_id", 1), ("source_type", 1), ("source_id", 1)])

    # ---- EC12 Phases 12E/12F - shared communications, notes, preferences, digest ----
    await db.message_threads.create_index("id", unique=True)
    await db.message_threads.create_index([("tenant_id", 1), ("thread_type", 1), ("last_message_at", -1)])
    await db.message_threads.create_index([("tenant_id", 1), ("participant_user_ids", 1), ("archived_at", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("participant_employee_ids", 1), ("visibility", 1), ("archived_at", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("task_id", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("order_id", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("work_order_id", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("production_stage_id", 1)])
    await db.message_threads.create_index([("tenant_id", 1), ("calendar_event_id", 1)])
    await db.thread_messages.create_index("id", unique=True)
    await db.thread_messages.create_index([("tenant_id", 1), ("thread_id", 1), ("created_at", 1)])
    await db.thread_messages.create_index(
        [("tenant_id", 1), ("thread_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.message_read_states.create_index("id", unique=True)
    await db.message_read_states.create_index(
        [("tenant_id", 1), ("thread_id", 1), ("identity_type", 1), ("identity_id", 1)],
        unique=True,
    )
    await db.internal_notes.create_index("id", unique=True)
    await db.internal_notes.create_index([("tenant_id", 1), ("visibility", 1), ("created_at", -1)])
    await db.internal_notes.create_index([("tenant_id", 1), ("task_id", 1), ("created_at", -1)])
    await db.internal_notes.create_index([("tenant_id", 1), ("order_id", 1), ("created_at", -1)])
    await db.internal_notes.create_index([("tenant_id", 1), ("work_order_id", 1), ("created_at", -1)])
    await db.internal_notes.create_index([("tenant_id", 1), ("employee_id", 1), ("created_at", -1)])
    await db.communication_preferences.create_index("id", unique=True)
    await db.communication_preferences.create_index(
        [("tenant_id", 1), ("identity_type", 1), ("identity_id", 1)],
        unique=True,
    )
    await db.daily_digests.create_index("id", unique=True)
    await db.daily_digests.create_index(
        [("tenant_id", 1), ("recipient_type", 1), ("recipient_id", 1), ("digest_date", 1)],
        unique=True,
    )

    # ---- EC12 Phase 12G - community, founders, feedback, voting, support ----
    await db.community_spaces.create_index("id", unique=True)
    await db.community_spaces.create_index([("scope_type", 1), ("tenant_id", 1), ("active", 1), ("archived_at", 1)])
    await db.community_posts.create_index("id", unique=True)
    await db.community_posts.create_index([("space_id", 1), ("status", 1), ("updated_at", -1)])
    await db.community_posts.create_index([("scope_type", 1), ("tenant_id", 1), ("post_type", 1), ("updated_at", -1)])
    await db.community_posts.create_index(
        [("author_user_id", 1), ("space_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.community_comments.create_index("id", unique=True)
    await db.community_comments.create_index([("post_id", 1), ("parent_comment_id", 1), ("created_at", 1)])
    await db.community_votes.create_index("id", unique=True)
    await db.community_votes.create_index(
        [("record_type", 1), ("record_id", 1), ("identity_type", 1), ("identity_id", 1)],
        unique=True,
    )
    await db.feature_requests.create_index("id", unique=True)
    await db.feature_requests.create_index([("status", 1), ("vote_count", -1), ("created_at", -1)])
    await db.feature_requests.create_index(
        [("tenant_id", 1), ("submitter_user_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.bug_reports.create_index("id", unique=True)
    await db.bug_reports.create_index([("status", 1), ("created_at", -1)])
    await db.bug_reports.create_index([("tenant_id", 1), ("submitter_user_id", 1), ("created_at", -1)])
    await db.bug_reports.create_index(
        [("tenant_id", 1), ("submitter_user_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.founder_access.create_index("id", unique=True)
    await db.founder_access.create_index([("user_id", 1), ("tenant_id", 1), ("revoked_at", 1)])
    await db.support_requests.create_index("id", unique=True)
    await db.support_requests.create_index([("tenant_id", 1), ("destination_type", 1), ("status", 1), ("created_at", -1)])
    await db.support_requests.create_index([("destination_type", 1), ("status", 1), ("created_at", -1)])
    await db.support_requests.create_index(
        [("tenant_id", 1), ("requester_user_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.support_request_notes.create_index("id", unique=True)
    await db.support_request_notes.create_index([("tenant_id", 1), ("support_request_id", 1), ("created_at", 1)])
    await db.community_moderation_reports.create_index([("post_id", 1), ("status", 1), ("created_at", -1)])

    # ---- EC13 Phase 13A - commercial billing catalog and core contracts ----
    await db.commercial_catalog_versions.create_index("id", unique=True)
    await db.commercial_catalog_versions.create_index("version", unique=True)
    await db.commercial_catalog_versions.create_index([("status", 1), ("effective_at", 1)])

    await db.commercial_products.create_index("id", unique=True)
    await db.commercial_products.create_index([("catalog_version_id", 1), ("product_key", 1)], unique=True)
    await db.commercial_products.create_index([("status", 1), ("product_type", 1)])
    await db.commercial_products.create_index([("owner_checkpoint", 1), ("status", 1)])

    await db.commercial_prices.create_index("id", unique=True)
    await db.commercial_prices.create_index([("catalog_version_id", 1), ("price_key", 1)], unique=True)
    await db.commercial_prices.create_index([("product_id", 1), ("billing_interval", 1), ("is_active", 1)])
    await db.commercial_prices.create_index(
        "stripe_price_id",
        unique=True,
        partialFilterExpression={"stripe_price_id": {"$type": "string"}},
    )
    await db.commercial_prices.create_index([("is_public", 1), ("is_active", 1)])

    await db.commercial_entitlement_rules.create_index("id", unique=True)
    await db.commercial_entitlement_rules.create_index([("catalog_version_id", 1), ("product_id", 1)])
    await db.commercial_entitlement_rules.create_index([("feature_key", 1), ("enabled", 1)])
    await db.commercial_entitlement_rules.create_index(
        [("catalog_version_id", 1), ("product_id", 1), ("feature_key", 1), ("entitlement_scope", 1)],
        unique=True,
    )

    await db.founder_tenant_contracts.create_index("id", unique=True)
    await db.founder_tenant_contracts.create_index(
        [("tenant_id", 1)],
        unique=True,
        partialFilterExpression={"founder_status": {"$in": ["pending", "active", "grace"]}},
    )
    await db.founder_tenant_contracts.create_index(
        "founder_slot_number",
        unique=True,
        partialFilterExpression={"founder_slot_number": {"$type": "number"}},
    )
    await db.founder_tenant_contracts.create_index([("tenant_id", 1), ("created_at", -1)])

    await db.platform_fee_schedules.create_index("id", unique=True)
    await db.platform_fee_schedules.create_index([("catalog_version_id", 1), ("fee_key", 1)], unique=True)
    await db.platform_fee_schedules.create_index([("account_status", 1), ("transaction_type", 1), ("is_active", 1)])

    await db.platform_fee_transactions.create_index("id", unique=True)
    await db.platform_fee_transactions.create_index([("tenant_id", 1), ("source_transaction_type", 1), ("source_transaction_id", 1)])
    await db.platform_fee_transactions.create_index(
        [("tenant_id", 1), ("source_transaction_type", 1), ("source_transaction_id", 1), ("reversal_of_fee_transaction_id", 1)],
        unique=True,
        partialFilterExpression={"reversal_of_fee_transaction_id": None},
    )
    await db.platform_fee_transactions.create_index([("reversal_of_fee_transaction_id", 1)])

    # ---- EC13 remaining phases - tenant billing, trials, setup, checkout, dunning ----
    await db.tenant_billing_accounts.create_index("id", unique=True)
    await db.tenant_billing_accounts.create_index("tenant_id", unique=True)
    await db.tenant_billing_accounts.create_index(
        "stripe_customer_id",
        unique=True,
        partialFilterExpression={"stripe_customer_id": {"$type": "string"}},
    )
    await db.tenant_billing_accounts.create_index([("status", 1), ("updated_at", -1)])

    await db.tenant_subscriptions.create_index("id", unique=True)
    await db.tenant_subscriptions.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.tenant_subscriptions.create_index(
        [("tenant_id", 1)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["trialing", "active", "past_due", "cancellation_scheduled", "incomplete", "unpaid"]}},
    )
    await db.tenant_subscriptions.create_index(
        "stripe_subscription_id",
        unique=True,
        partialFilterExpression={"stripe_subscription_id": {"$type": "string"}},
    )
    await db.tenant_subscriptions.create_index([("tenant_id", 1), ("dunning_state", 1), ("first_payment_failed_at", 1)])
    await db.tenant_subscriptions.create_index([("tenant_id", 1), ("current_period_end", 1)])

    await db.trial_records.create_index("id", unique=True)
    await db.trial_records.create_index([("tenant_id", 1), ("trial_kind", 1)], unique=True)
    await db.trial_records.create_index([("tenant_id", 1), ("status", 1), ("ends_at", 1)])
    await db.trial_records.create_index([("checkout_session_id", 1)])

    await db.checkout_session_records.create_index("id", unique=True)
    await db.checkout_session_records.create_index([("tenant_id", 1), ("idempotency_key", 1)], unique=True)

    # ---- EC14 - Webstores ----
    await db.webstore_owners.create_index("id", unique=True)
    await db.webstore_owners.create_index([("tenant_id", 1), ("email", 1)], unique=True)
    await db.webstore_owners.create_index([("tenant_id", 1), ("status", 1)])
    await db.webstore_owners.create_index([("tenant_id", 1), ("portal_identity_id", 1)])

    await db.webstores.create_index("id", unique=True)
    await db.webstores.create_index([("tenant_id", 1), ("slug", 1)], unique=True)
    await db.webstores.create_index([("tenant_id", 1), ("owner_id", 1)])
    await db.webstores.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.webstores.create_index([("tenant_id", 1), ("launched_at", -1)])

    await db.webstore_product_templates.create_index("id", unique=True)
    await db.webstore_product_templates.create_index([("tenant_id", 1), ("active", 1), ("product_category", 1)])
    await db.webstore_product_templates.create_index([("tenant_id", 1), ("template_name", 1)])

    await db.webstore_products.create_index("id", unique=True)
    await db.webstore_products.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])
    await db.webstore_products.create_index([("tenant_id", 1), ("webstore_id", 1), ("public", 1)])

    await db.webstore_questionnaire_submissions.create_index("id", unique=True)
    await db.webstore_questionnaire_submissions.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])

    await db.webstore_artwork_files.create_index("id", unique=True)
    await db.webstore_artwork_files.create_index([("tenant_id", 1), ("webstore_id", 1), ("artwork_status", 1)])

    await db.webstore_mockups.create_index("id", unique=True)
    await db.webstore_mockups.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])
    await db.webstore_mockups.create_index([("tenant_id", 1), ("product_id", 1)])

    await db.webstore_launch_packets.create_index("id", unique=True)
    await db.webstore_launch_packets.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])

    await db.webstore_buyer_orders.create_index("id", unique=True)
    await db.webstore_buyer_orders.create_index([("tenant_id", 1), ("webstore_id", 1), ("created_at", -1)])
    await db.webstore_buyer_orders.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])
    await db.webstore_buyer_orders.create_index(
        [("tenant_id", 1), ("webstore_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    await db.webstore_ledger_entries.create_index("id", unique=True)
    await db.webstore_ledger_entries.create_index([("tenant_id", 1), ("webstore_id", 1), ("created_at", -1)])
    await db.webstore_ledger_entries.create_index([("tenant_id", 1), ("buyer_order_id", 1), ("entry_type", 1)])
    await db.webstore_ledger_entries.create_index([("tenant_id", 1), ("source_type", 1), ("source_id", 1)])
    await db.webstore_ledger_entries.create_index([("tenant_id", 1), ("reversal_of_ledger_entry_id", 1)])

    await db.webstore_activity_events.create_index("id", unique=True)
    await db.webstore_activity_events.create_index([("tenant_id", 1), ("webstore_id", 1), ("created_at", -1)])
    await db.webstore_activity_events.create_index([("tenant_id", 1), ("action", 1), ("created_at", -1)])

    await db.webstore_ai_usage_events.create_index("id", unique=True)
    await db.webstore_ai_usage_events.create_index([("tenant_id", 1), ("webstore_id", 1), ("status", 1)])

    await db.webstore_stripe_connect_records.create_index("id", unique=True)
    await db.webstore_stripe_connect_records.create_index([("tenant_id", 1), ("webstore_id", 1), ("record_type", 1)])
    await db.webstore_stripe_connect_records.create_index(
        [("tenant_id", 1), ("webstore_id", 1), ("record_type", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.checkout_session_records.create_index(
        "stripe_checkout_session_id",
        unique=True,
        partialFilterExpression={"stripe_checkout_session_id": {"$type": "string"}},
    )
    await db.checkout_session_records.create_index([("tenant_id", 1), ("session_type", 1), ("status", 1), ("created_at", -1)])

    await db.billing_portal_session_records.create_index("id", unique=True)
    await db.billing_portal_session_records.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.billing_portal_session_records.create_index(
        "stripe_billing_portal_session_id",
        unique=True,
        partialFilterExpression={"stripe_billing_portal_session_id": {"$type": "string"}},
    )

    await db.setup_package_purchases.create_index("id", unique=True)
    await db.setup_package_purchases.create_index([("tenant_id", 1), ("status", 1), ("created_at", -1)])
    await db.setup_package_purchases.create_index([("tenant_id", 1), ("package_key", 1), ("status", 1)])
    await db.setup_package_purchases.create_index(
        "checkout_session_id",
        unique=True,
        partialFilterExpression={"checkout_session_id": {"$type": "string"}},
    )

    # ---- EC15 - Wrap Lab shared core ----
    await db.wrap_vehicles.create_index("id", unique=True)
    await db.wrap_vehicles.create_index([("tenant_id", 1), ("customer_id", 1)])
    await db.wrap_vehicles.create_index(
        [("tenant_id", 1), ("vin", 1)],
        unique=True,
        partialFilterExpression={"vin": {"$type": "string"}},
    )
    await db.wrap_vehicles.create_index(
        [("tenant_id", 1), ("license_plate", 1)],
        partialFilterExpression={"license_plate": {"$type": "string"}},
    )
    await db.wrap_vehicles.create_index([("tenant_id", 1), ("updated_at", -1)])

    await db.wrap_projects.create_index("id", unique=True)
    await db.wrap_projects.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.wrap_projects.create_index([("tenant_id", 1), ("customer_id", 1), ("updated_at", -1)])
    await db.wrap_projects.create_index([("tenant_id", 1), ("vehicle_id", 1)])
    await db.wrap_projects.create_index([("tenant_id", 1), ("order_id", 1)], partialFilterExpression={"order_id": {"$type": "string"}})
    await db.wrap_projects.create_index([("tenant_id", 1), ("quote_id", 1)], partialFilterExpression={"quote_id": {"$type": "string"}})
    await db.wrap_projects.create_index([("tenant_id", 1), ("work_order_id", 1)], partialFilterExpression={"work_order_id": {"$type": "string"}})

    await db.wrap_coverage_plans.create_index("id", unique=True)
    await db.wrap_coverage_plans.create_index([("tenant_id", 1), ("project_id", 1)])
    await db.wrap_coverage_plans.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])

    await db.wrap_inspections.create_index("id", unique=True)
    await db.wrap_inspections.create_index([("tenant_id", 1), ("project_id", 1), ("inspection_type", 1)])
    await db.wrap_inspections.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])

    await db.wrap_design_scenes.create_index("id", unique=True)
    await db.wrap_design_scenes.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])
    await db.wrap_design_scenes.create_index([("tenant_id", 1), ("project_id", 1), ("revision", 1)], unique=True)

    await db.wrap_panel_plans.create_index("id", unique=True)
    await db.wrap_panel_plans.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])
    await db.wrap_panel_plans.create_index([("tenant_id", 1), ("project_id", 1), ("revision", 1)], unique=True)

    await db.wrap_packets.create_index("id", unique=True)
    await db.wrap_packets.create_index([("tenant_id", 1), ("project_id", 1), ("packet_type", 1), ("revision", 1)], unique=True)
    await db.wrap_packets.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])

    await db.wrap_schedules.create_index("id", unique=True)
    await db.wrap_schedules.create_index([("tenant_id", 1), ("project_id", 1), ("schedule_type", 1)])
    await db.wrap_schedules.create_index([("tenant_id", 1), ("start_at", 1)])
    await db.wrap_schedules.create_index(
        [("tenant_id", 1), ("calendar_event_id", 1)],
        partialFilterExpression={"calendar_event_id": {"$type": "string"}},
    )

    await db.wrap_warranties.create_index("id", unique=True)
    await db.wrap_warranties.create_index([("tenant_id", 1), ("project_id", 1), ("status", 1)])
    await db.wrap_warranties.create_index([("tenant_id", 1), ("expires_at", 1)])

    await db.wrap_activity_events.create_index("id", unique=True)
    await db.wrap_activity_events.create_index([("tenant_id", 1), ("project_id", 1), ("created_at", -1)])
    await db.wrap_activity_events.create_index([("tenant_id", 1), ("action", 1), ("created_at", -1)])

    logger.info("MongoDB indexes ensured")
