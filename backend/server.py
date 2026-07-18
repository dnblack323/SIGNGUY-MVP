from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import get_settings
from app.core.db import ensure_indexes
from app.core.security_guards import enforce_startup_guards
from app.services.storage import initialize as init_storage
from app.routers import (
    auth as auth_router,
    users as users_router,
    customers as customers_router,
    quotes as quotes_router,
    orders as orders_router,
    work_orders as work_orders_router,
    invoices as invoices_router,
    documents as documents_router,
    emails as emails_router,
    audit as audit_router,
    dashboard as dashboard_router,
    pricing as pricing_router,
    # EC2 — Shared Platform Services
    settings as settings_router,
    notifications as notifications_router,
    webhooks as webhooks_router,
    entitlements as entitlements_router,
    integration_status as integration_status_router,
    activity as activity_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("signguy")

_settings = get_settings()

# EC1 — Production Startup Guards: refuse to start under an unsafe configuration.
enforce_startup_guards(_settings)

app = FastAPI(title="SignGuy AI", version="0.1.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


api_router.include_router(auth_router.router)
api_router.include_router(users_router.router)
api_router.include_router(customers_router.router)
api_router.include_router(quotes_router.router)
api_router.include_router(orders_router.router)
api_router.include_router(work_orders_router.router)
api_router.include_router(work_orders_router.prod_router)
api_router.include_router(invoices_router.router)
from app.routers import payments as payments_router  # noqa: E402
from app.routers import webhooks_stripe as webhooks_stripe_router  # noqa: E402
api_router.include_router(payments_router.router)
api_router.include_router(webhooks_stripe_router.router)
api_router.include_router(documents_router.router)
api_router.include_router(emails_router.router)
api_router.include_router(audit_router.router)
api_router.include_router(dashboard_router.router)
api_router.include_router(pricing_router.router)

# EC2 — Shared Platform Services
api_router.include_router(settings_router.router)
api_router.include_router(notifications_router.router)
api_router.include_router(webhooks_router.router)
api_router.include_router(entitlements_router.router)
api_router.include_router(integration_status_router.router)
api_router.include_router(activity_router.router)

    # EC6 — Portal auth
from app.routers import portal_auth as portal_auth_router
from app.routers import portal_customer as portal_customer_router
from app.routers import portal_identities as portal_identities_router
from app.routers import public_actions as public_actions_router
from app.routers import documents_meta as documents_meta_router
from app.routers import proofs as proofs_router
from app.routers import signatures as signatures_router
api_router.include_router(portal_auth_router.router)
api_router.include_router(portal_customer_router.router)
api_router.include_router(portal_identities_router.router)
api_router.include_router(public_actions_router.router)
api_router.include_router(documents_meta_router.router)
api_router.include_router(proofs_router.router)
api_router.include_router(signatures_router.router)
api_router.include_router(signatures_router.approvals_router)

# EC7 — Phase 7a Inventory foundation
from app.routers import inventory as inventory_router_module
api_router.include_router(inventory_router_module.materials_router)
api_router.include_router(inventory_router_module.inventory_router)

# EC7 — Phase 7b Vendors + Supplier Catalog + Purchase Orders + Receiving
from app.routers import vendors as vendors_router_module
from app.routers import supply_center as supply_center_router_module
from app.routers import purchase_orders as purchase_orders_router_module
api_router.include_router(vendors_router_module.router)
api_router.include_router(supply_center_router_module.router)
api_router.include_router(purchase_orders_router_module.router)

# EC7 — Phase 7c Expenses + Finance Dashboard + Tax Reports
from app.routers import expenses as expenses_router_module
from app.routers import finance as finance_router_module
from app.routers import tax_reports as tax_reports_router_module
api_router.include_router(expenses_router_module.categories_router)
api_router.include_router(expenses_router_module.expenses_router)
api_router.include_router(finance_router_module.router)
api_router.include_router(tax_reports_router_module.router)

# EC7 — Phase 7d Curated Reports + CSV export + Custom Report Builder
from app.routers import reports as reports_router_module
api_router.include_router(reports_router_module.router)

# EC8 — Phase 8a Employees + Team Dashboard + Announcements
from app.routers import employees as employees_router_module
from app.routers import team_dashboard as team_dashboard_router_module
from app.routers import announcements as announcements_router_module
api_router.include_router(employees_router_module.router)
api_router.include_router(team_dashboard_router_module.router)
api_router.include_router(announcements_router_module.router)

# EC8 — Phase 8b Time Clock + Timesheets
from app.routers import time_clock as time_clock_router_module
from app.routers import timesheets as timesheets_router_module
api_router.include_router(time_clock_router_module.router)
api_router.include_router(timesheets_router_module.router)

# EC8 — Phase 8b dev-only fixture: links dev-login Owner to an Employee record
# (idempotent, refuses outside development — see routers/dev_tools.py)
from app.routers import dev_tools as dev_tools_router_module
api_router.include_router(dev_tools_router_module.router)

# EC8 — Phase 8c Scheduling + Employee Portal (additive on EC6 Portal Identity)
from app.routers import schedule as schedule_router_module
from app.routers import employee_portal_admin as employee_portal_admin_router_module
from app.routers import portal_employee as portal_employee_router_module
api_router.include_router(schedule_router_module.router)
api_router.include_router(schedule_router_module.shifts_router)
api_router.include_router(employee_portal_admin_router_module.router)
api_router.include_router(portal_employee_router_module.router)

# EC8 — Phase 8d Payroll (Pay Periods, ledger transactions, My Pay, reports)
from app.routers import payroll as payroll_router_module
api_router.include_router(payroll_router_module.router)

# EC8 — Phase 8e Equipment, Training & Certification + Work Order enforcement
from app.routers import equipment as equipment_router_module
from app.routers import training as training_router_module
from app.routers import certification as certification_router_module
api_router.include_router(equipment_router_module.router)
api_router.include_router(training_router_module.router)
api_router.include_router(certification_router_module.router)

# EC9 — Phase 9A Pricing architecture: Material Pricing Profiles (linked to
# canonical EC7 Material), Pricing Components (non-inventory charges/fees),
# and reusable Saved Items (reference canonical Materials, never copy them)
from app.routers import pricing_materials as pricing_materials_router_module
from app.routers import pricing_components as pricing_components_router_module
from app.routers import pricing_saved_items as pricing_saved_items_router_module
api_router.include_router(pricing_materials_router_module.router)
api_router.include_router(pricing_components_router_module.router)
api_router.include_router(pricing_saved_items_router_module.router)

# EC9 — Phase 9C Grouped Pricing Setup Quiz (additive to the detailed wizard)
from app.routers import pricing_quiz as pricing_quiz_router_module
api_router.include_router(pricing_quiz_router_module.router)

# EC9 — Phase 9G Immutable Pricing Snapshots + provider-neutral Advisory
# contracts (no live AI/web/market provider call anywhere behind these).
from app.routers import pricing_snapshots as pricing_snapshots_router_module
from app.routers import pricing_advisory as pricing_advisory_router_module
api_router.include_router(pricing_snapshots_router_module.router)
api_router.include_router(pricing_advisory_router_module.router)

# EC10 — Phase 10A Intake architecture and canonical data contracts (staff-only;
# customer-facing/public intake submission deferred to a later phase).
from app.routers import intake as intake_router_module
api_router.include_router(intake_router_module.router)

# EC10 — Phase 10C Visual Markup (staff-only annotation workspace over an
# existing uploaded image/PDF page; customer annotation deferred).
from app.routers import visual_markup as visual_markup_router_module
api_router.include_router(visual_markup_router_module.router)

# EC10 — Phase 10D Customer Decision Room models + internal authoring only
# (staff-only; no customer/public access, no decision-to-order integration).
from app.routers import decision_room as decision_room_router_module
api_router.include_router(decision_room_router_module.router)

from app.routers import decision_room_apply as decision_room_apply_router_module
api_router.include_router(decision_room_apply_router_module.router)

# EC10 — Phase 10E-1 Customer Portal Decision Room access (read-only,
# published-version-only; no selection/rejection/comment actions yet).
from app.routers import decision_room_portal as decision_room_portal_router_module
api_router.include_router(decision_room_portal_router_module.router)

# EC10 — Phase 10E-4 Internal Decision Room review queue. Triage-only:
# list/filter customer activity, assign reviewers, mark supported items as
# reviewed/acknowledged, and add staff-only notes. No commercial apply path.
from app.routers import decision_room_review_queue as decision_room_review_queue_router_module
api_router.include_router(decision_room_review_queue_router_module.router)

from app.routers import templates as templates_router_module
api_router.include_router(templates_router_module.router)

# EC11 - Phase 11A Production Workflow Definitions and canonical stage contracts.
from app.routers import production_workflows as production_workflows_router_module
api_router.include_router(production_workflows_router_module.router)

# EC11 - Phase 11B Production Timeline and Event History Foundation. Staff-only,
# read-only projection over existing source records; no live stage mutations.
from app.routers import production_timeline as production_timeline_router_module
api_router.include_router(production_timeline_router_module.router)

# EC11 - Phase 11C Live Work Order / Order Item production stage instances.
from app.routers import production_stages as production_stages_router_module
api_router.include_router(production_stages_router_module.router)

# EC11 - Phase 11F Shop-Floor Production Kiosk Mode. Restricted kiosk-device
# sessions delegate stage actions to Phase 11C and Time Clock actions to EC8.
from app.routers import production_kiosk as production_kiosk_router_module
api_router.include_router(production_kiosk_router_module.router)

# EC12 Phase 12A - shared task foundation. Staff-only task management lives
# here; Employee Portal self-scoped task access stays in portal_employee.py.
from app.routers import tasks as tasks_router_module
api_router.include_router(tasks_router_module.router)

# EC12 Phases 12C/12D - employee time-off workflow and shared calendar.
from app.routers import time_off as time_off_router_module
from app.routers import calendar as calendar_router_module
api_router.include_router(time_off_router_module.router)
api_router.include_router(calendar_router_module.router)

# EC12 Phases 12E/12F - shared communications and Employee Portal account experience.
from app.routers import communications as communications_router_module
api_router.include_router(communications_router_module.router)

# EC12 Phase 12G - community, founders, feedback, voting, and support routing.
from app.routers import community as community_router_module
api_router.include_router(community_router_module.router)

# EC13 Phase 13A - commercial billing catalog and core contracts only.
from app.routers import commercial_catalog as commercial_catalog_router_module
api_router.include_router(commercial_catalog_router_module.router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    await ensure_indexes()
    init_storage()
    logger.info("SignGuy AI backend started")
