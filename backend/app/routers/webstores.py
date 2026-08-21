"""EC14 - staff Webstores manager route composition."""
from __future__ import annotations

from fastapi import APIRouter

from .webstores_collection import router as webstores_collection_router
from .webstores_setup_templates import router as webstores_setup_templates_router
from .webstores_lifecycle import router as webstores_lifecycle_router
from .webstores_orders_payments import router as webstores_orders_payments_router
from .webstores_setup_routes import router as webstores_setup_routes_router
from .webstores_branding_routes import router as webstores_branding_routes_router
from .webstores_setup_file_removal import router as webstores_setup_file_removal_router
from .webstores_catalog import router as webstores_catalog_router
from .webstores_launch_operations import router as webstores_launch_operations_router
from .webstores_reference import router as webstores_reference_router

router = APIRouter()

for subrouter in (
    webstores_collection_router,
    webstores_setup_templates_router,
    webstores_lifecycle_router,
    webstores_orders_payments_router,
    webstores_setup_routes_router,
    webstores_branding_routes_router,
    webstores_setup_file_removal_router,
    webstores_catalog_router,
    webstores_launch_operations_router,
    webstores_reference_router,
):
    router.include_router(subrouter)
