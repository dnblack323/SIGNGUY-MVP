"""Central permission catalog + scope separation (EC1 permanent extension).

Design rules (LOCKED — EC0/EC1):
- Backend enforcement is authoritative. Frontend permission checks control
  visibility only.
- Staff permissions (Perm enum) are strictly for internal tenant users.
- Platform scope (PlatformPerm) is a separate scope for cross-tenant platform
  operators. It cannot satisfy a Perm check.
- Portal scope (PortalPerm) is a separate scope for external portal identities
  (Customer, Employee, Webstore Owner, Webstore Manager). It cannot satisfy a
  Perm check.
- New module namespaces are declared here so future checkpoints can introduce
  routes without a scattered enum. Enforcement wiring for future modules is
  intentionally deferred to the checkpoint that owns the module.

Preserves the working MVP StaffPerm values 1:1.

`dashboard:read` is retained today but marked DEPRECATED per Final Scope
Register Part 9.4 — new dashboards inherit read from their underlying modules.
"""
from __future__ import annotations

from enum import Enum


class Perm(str, Enum):
    """Staff permissions (internal tenant users).

    Grouped by module namespace: customer, lead, quote, order, order_item,
    work_order, invoice, payment, document, email, audit, user, dashboard,
    pricing, inventory, vendor, purchasing, employee, task, schedule,
    timeclock, timesheet, payroll, equipment, training, certification,
    report, webstore, wrap_lab, ai, settings, integration, subscription,
    community, ai_credit, intake, markup, production_workflow.
    """
    # Customers / Leads
    CUSTOMER_READ = "customer:read"
    CUSTOMER_WRITE = "customer:write"
    LEAD_READ = "lead:read"
    LEAD_WRITE = "lead:write"
    # Quotes
    QUOTE_READ = "quote:read"
    QUOTE_WRITE = "quote:write"
    QUOTE_CONVERT = "quote:convert"
    QUOTE_APPROVE = "quote:approve"
    QUOTE_DECLINE = "quote:decline"
    # Orders + Order Items
    ORDER_READ = "order:read"
    ORDER_WRITE = "order:write"
    ORDER_CANCEL = "order:cancel"
    ORDER_ITEM_WRITE = "order_item:write"
    # Work Orders
    WORK_ORDER_READ = "work_order:read"
    WORK_ORDER_WRITE = "work_order:write"
    WORK_ORDER_STATUS = "work_order:status"
    # Invoices + Payments
    INVOICE_READ = "invoice:read"
    INVOICE_WRITE = "invoice:write"
    INVOICE_SEND = "invoice:send"
    INVOICE_VOID = "invoice:void"
    PAYMENT_READ = "payment:read"
    PAYMENT_WRITE = "payment:write"
    PAYMENT_VOID = "payment:void"
    PAYMENT_REFUND = "payment:refund"
    # Documents
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_SHARE = "document:share"
    # Emails
    EMAIL_READ = "email:read"
    EMAIL_SEND = "email:send"
    # Audit
    AUDIT_READ = "audit:read"
    # Users / admin
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    ROLE_READ = "role:read"
    ROLE_WRITE = "role:write"
    # Dashboard (DEPRECATED — retained for MVP compat; new dashboards inherit module read).
    DASHBOARD_READ = "dashboard:read"
    # Pricing
    PRICING_READ = "pricing:read"
    PRICING_WRITE = "pricing:write"
    PRICING_CALCULATE = "pricing:calculate"
    # Settings / Integrations
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"
    # Inventory / Purchasing (Shop Ops → Inventory & Purchasing)
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    VENDOR_READ = "vendor:read"
    VENDOR_WRITE = "vendor:write"
    PURCHASING_READ = "purchasing:read"
    PURCHASING_WRITE = "purchasing:write"
    # Expenses (EC7 phase 7c — operational expense system, distinct from customer payments)
    EXPENSE_READ = "expense:read"
    EXPENSE_WRITE = "expense:write"
    EXPENSE_ARCHIVE = "expense:archive"
    # Finance dashboard + tax reports (EC7 phase 7c — canonical labeled-basis metrics)
    FINANCE_READ = "finance:read"
    TAX_REPORT_READ = "tax_report:read"
    # Team & Workflow (EC8 — canonical set, approved 2026-07 EC8 preflight gate.
    # Superseded values EMPLOYEE_WRITE/EMPLOYEE_ADMIN/TIME_CLOCK_READ/
    # TIME_CLOCK_WRITE/TIMESHEET_APPROVE/PAYROLL_WRITE/PAYROLL_ADMIN were
    # declared in EC1 but never consumed by any route — safe, non-breaking
    # rename performed before EC8 implementation depends on them.)
    EMPLOYEE_READ = "employee:read"
    EMPLOYEE_MANAGE = "employee:manage"
    TASK_READ = "task:read"
    TASK_WRITE = "task:write"
    TASK_CREATE = "task:create"
    TASK_UPDATE = "task:update"
    TASK_ASSIGN = "task:assign"
    TASK_COMPLETE = "task:complete"
    TASK_ARCHIVE = "task:archive"
    TASK_MANAGE = "task:manage"
    MESSAGE_READ = "message:read"
    MESSAGE_CREATE = "message:create"
    MESSAGE_MANAGE = "message:manage"
    NOTE_READ = "note:read"
    NOTE_CREATE = "note:create"
    NOTE_MANAGE = "note:manage"
    ANNOUNCEMENT_READ = "announcement:read"
    ANNOUNCEMENT_MANAGE = "announcement:manage"
    DIGEST_READ = "digest:read"
    DIGEST_MANAGE = "digest:manage"
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_MANAGE = "schedule:manage"
    TIMECLOCK_SELF = "timeclock:self"
    TIMECLOCK_MANAGE = "timeclock:manage"
    TIMESHEET_SELF = "timesheet:self"
    TIMESHEET_READ = "timesheet:read"
    TIMESHEET_MANAGE = "timesheet:manage"
    PAYROLL_SELF = "payroll:self"
    PAYROLL_READ = "payroll:read"
    PAYROLL_MANAGE = "payroll:manage"
    PAYROLL_EXPORT = "payroll:export"
    EQUIPMENT_READ = "equipment:read"
    EQUIPMENT_MANAGE = "equipment:manage"
    TRAINING_SELF = "training:self"
    TRAINING_MANAGE = "training:manage"
    CERTIFICATION_READ = "certification:read"
    CERTIFICATION_MANAGE = "certification:manage"
    # Reports / Analytics
    REPORT_READ = "report:read"
    REPORT_WRITE = "report:write"
    ANALYTICS_READ = "analytics:read"
    # Add-ons
    WEBSTORE_READ = "webstore:read"
    WEBSTORE_WRITE = "webstore:write"
    WEBSTORE_MANAGE = "webstore:manage"
    WRAP_LAB_READ = "wrap_lab:read"
    WRAP_LAB_WRITE = "wrap_lab:write"
    WRAP_LAB_ADVANCE = "wrap_lab:advance_stage"
    # Creative Studio / AI
    AI_TOOL_USE = "ai_tool:use"
    AI_ASSISTANT_USE = "ai_assistant:use"
    AI_PROMPT_READ = "ai_prompt:read"
    AI_PROMPT_WRITE = "ai_prompt:write"
    AI_HISTORY_READ = "ai_history:read"
    # Commercial / Community
    SUBSCRIPTION_READ = "subscription:read"
    SUBSCRIPTION_MANAGE = "subscription:manage"
    AI_CREDIT_READ = "ai_credit:read"
    AI_CREDIT_ADMIN = "ai_credit:admin"
    COMMUNITY_READ = "community:read"
    COMMUNITY_POST = "community:post"
    COMMUNITY_MODERATE = "community:moderate"
    SUPPORT_READ = "support:read"
    SUPPORT_WRITE = "support:write"
    # EC10 Phase 10A — Order Intake (canonical intake capture, pre-Quote/Order).
    # Distinct from `document:*` (files) and `quote:*`/`order:*` (the
    # authoritative records an accepted intake may later be converted into).
    INTAKE_READ = "intake:read"
    INTAKE_WRITE = "intake:write"
    # EC10 Phase 10C — Visual Markup (staff annotation workspace over an
    # existing uploaded image/PDF page). Distinct from `document:*` (raw
    # files) — markup is the structured annotation layer on top of a file.
    MARKUP_READ = "markup:read"
    MARKUP_WRITE = "markup:write"
    # EC10 Phase 10D — Customer Decision Room (internal authoring only; no
    # customer/public access exists yet). `publish`/`archive` are kept
    # separate from ordinary `write` — every staff login may author/edit a
    # room, but freezing a published version (customer-exposure-adjacent,
    # even though 10E's actual customer access is not built) and archiving
    # a room out of normal internal views are reserved for owner/admin.
    DECISION_ROOM_READ = "decision_room:read"
    DECISION_ROOM_WRITE = "decision_room:write"
    DECISION_ROOM_PUBLISH = "decision_room:publish"
    DECISION_ROOM_ARCHIVE = "decision_room:archive"
    TEMPLATE_READ = "template:read"
    TEMPLATE_WRITE = "template:write"
    # EC11 Phase 11A - Production Workflow Definitions. Read is staff-visible;
    # manage is owner/admin-only in the current role model.
    PRODUCTION_WORKFLOW_READ = "production_workflow:read"
    PRODUCTION_WORKFLOW_MANAGE = "production_workflow:manage"


class PlatformPerm(str, Enum):
    """Platform-scope permissions (cross-tenant). Never satisfies a Perm check."""
    PLATFORM_ADMIN = "platform:admin"
    PLATFORM_TENANT_READ = "platform:tenant_read"
    PLATFORM_TENANT_WRITE = "platform:tenant_write"
    PLATFORM_TENANT_STATUS = "platform:tenant_status"
    PLATFORM_AUDIT_READ = "platform:audit_read"
    PLATFORM_BROADCAST_WRITE = "platform:broadcast_write"
    PLATFORM_SUBSCRIPTION_ADMIN = "platform:subscription_admin"
    PLATFORM_AI_CREDIT_ADMIN = "platform:ai_credit_admin"


class PortalPerm(str, Enum):
    """Portal-scope permissions (external portal identities). Never satisfies a Perm check."""
    PORTAL_CUSTOMER_VIEW = "portal:customer_view"
    PORTAL_CUSTOMER_APPROVE = "portal:customer_approve"
    PORTAL_CUSTOMER_SIGN = "portal:customer_sign"
    PORTAL_CUSTOMER_PAY = "portal:customer_pay"
    PORTAL_CUSTOMER_MESSAGE = "portal:customer_message"
    PORTAL_EMPLOYEE_VIEW = "portal:employee_view"
    PORTAL_EMPLOYEE_TIME_CLOCK = "portal:employee_time_clock"
    PORTAL_EMPLOYEE_TIMESHEET_VIEW = "portal:employee_timesheet_view"
    PORTAL_EMPLOYEE_PAY_VIEW = "portal:employee_pay_view"
    PORTAL_EMPLOYEE_SCHEDULE_VIEW = "portal:employee_schedule_view"
    PORTAL_EMPLOYEE_TRAINING_VIEW = "portal:employee_training_view"
    PORTAL_EMPLOYEE_CERTIFICATION_VIEW = "portal:employee_certification_view"
    PORTAL_EMPLOYEE_TASKS = "portal:employee_tasks"
    PORTAL_EMPLOYEE_MESSAGES = "portal:employee_messages"
    PORTAL_EMPLOYEE_PROFILE = "portal:employee_profile"
    PORTAL_WEBSTORE_OWNER_ADMIN = "portal:webstore_owner_admin"
    PORTAL_WEBSTORE_MANAGER_OPS = "portal:webstore_manager_ops"


# ---- Working MVP role maps (preserved verbatim; extended with additional staff perms) ----

OWNER_ADMIN_PERMS: list[str] = [p.value for p in Perm]

STAFF_PERMS: list[str] = [
    Perm.CUSTOMER_READ.value, Perm.CUSTOMER_WRITE.value,
    Perm.QUOTE_READ.value, Perm.QUOTE_WRITE.value, Perm.QUOTE_CONVERT.value,
    Perm.ORDER_READ.value, Perm.ORDER_WRITE.value,
    Perm.WORK_ORDER_READ.value, Perm.WORK_ORDER_WRITE.value,
    Perm.INVOICE_READ.value, Perm.INVOICE_WRITE.value, Perm.PAYMENT_WRITE.value,
    Perm.DOCUMENT_READ.value, Perm.DOCUMENT_WRITE.value,
    Perm.EMAIL_READ.value, Perm.EMAIL_SEND.value,
    Perm.AUDIT_READ.value,
    Perm.DASHBOARD_READ.value,
    Perm.PRICING_READ.value, Perm.PRICING_CALCULATE.value,
    # EC8 phase 8b — every staff login may clock themselves in/out and view
    # their own timesheet (if linked to an Employee record). Viewing/managing
    # OTHER employees' time remains owner/admin only (timeclock:manage etc.
    # are granted only via OWNER_ADMIN_PERMS).
    Perm.TIMECLOCK_SELF.value, Perm.TIMESHEET_SELF.value,
    # EC12 Phase 12A - staff may read shared tenant tasks. Mutations stay
    # owner/admin-only under the finer task:* action permissions.
    Perm.TASK_READ.value,
    # EC12 Phase 12E - staff may participate in communication threads and
    # create ordinary notes; manage/delete-style operations stay owner/admin.
    Perm.MESSAGE_READ.value, Perm.MESSAGE_CREATE.value,
    Perm.NOTE_READ.value, Perm.NOTE_CREATE.value,
    Perm.ANNOUNCEMENT_READ.value, Perm.DIGEST_READ.value,
    # EC8 phase 8e — every staff login may view/complete their OWN assigned
    # Training (if linked to an Employee record), mirroring the
    # TIMECLOCK_SELF/TIMESHEET_SELF self-service convention above.
    Perm.TRAINING_SELF.value,
    # EC10 Phase 10A — every staff login may capture/view intake submissions
    # (pre-Quote/Order requests); it is not a privileged/admin-only action.
    Perm.INTAKE_READ.value, Perm.INTAKE_WRITE.value,
    # EC10 Phase 10C — every staff login may create/edit Visual Markup on an
    # intake asset, mirroring the intake self-service convention above.
    Perm.MARKUP_READ.value, Perm.MARKUP_WRITE.value,
    # EC10 Phase 10D — every staff login may author/edit Decision Rooms;
    # publish/archive remain owner/admin-only (see Perm docstring above).
    Perm.DECISION_ROOM_READ.value, Perm.DECISION_ROOM_WRITE.value,
    Perm.TEMPLATE_READ.value, Perm.TEMPLATE_WRITE.value,
    Perm.PRODUCTION_WORKFLOW_READ.value,
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": OWNER_ADMIN_PERMS,
    "admin": OWNER_ADMIN_PERMS,
    "staff": STAFF_PERMS,
}


def permissions_for_role(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, [])


def is_staff_perm(value: str) -> bool:
    """Return True if the value is a staff Perm (not platform/portal)."""
    return value in {p.value for p in Perm}


def is_platform_perm(value: str) -> bool:
    return value in {p.value for p in PlatformPerm}


def is_portal_perm(value: str) -> bool:
    return value in {p.value for p in PortalPerm}
