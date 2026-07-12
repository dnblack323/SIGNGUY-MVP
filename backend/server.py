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
