"""Disposable real-auth fixtures for the Webstores browser acceptance matrix.

This module is intentionally executable only from a test environment. It starts
the normal FastAPI application with random credentials and an isolated database;
it does not add routes, dependency branches, or production authentication code.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any


def _require_harness_environment() -> None:
    if os.environ.get("WEBSTORES_BROWSER_HARNESS") != "1":
        raise RuntimeError("WEBSTORES_BROWSER_HARNESS=1 is required")
    if os.environ.get("ENV", "development").strip().lower() == "production":
        raise RuntimeError("The browser harness cannot run in production")
    if os.environ.get("AUTH_DEV_BYPASS", "false").strip().lower() == "true":
        raise RuntimeError("The browser harness requires AUTH_DEV_BYPASS=false")
    db_name = os.environ.get("DB_NAME", "")
    if not db_name.startswith("webstores_browser_harness_"):
        raise RuntimeError("The browser harness requires an isolated webstores_browser_harness_* DB_NAME")
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "dev-secret-do-not-use-in-prod":
        raise RuntimeError("The browser harness requires random JWT_SECRET material")


_require_harness_environment()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.db import db, ensure_indexes  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.core.time_utils import prepare_for_mongo  # noqa: E402
from app.services.storage import initialize as init_storage  # noqa: E402
from server import app  # noqa: E402


def _load_existing_builder() -> Any:
    path = Path(__file__).with_name("test_ec14_webstores.py")
    spec = importlib.util.spec_from_file_location("webstores_acceptance_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the existing Webstores fixture builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._build_launchable_store


def _user(*, tenant_id: str, email: str, name: str, role: str, password: str) -> dict[str, Any]:
    return {
        "id": secrets.token_hex(16),
        "tenant_id": tenant_id,
        "email": email,
        "full_name": name,
        "role": role,
        "password_hash": hash_password(password),
        "is_active": True,
    }


async def _seed() -> dict[str, Any]:
    run_id = secrets.token_hex(8)
    tenant_a_id = f"browser-tenant-a-{run_id}"
    tenant_b_id = f"browser-tenant-b-{run_id}"
    tenant_a_slug = f"browser-a-{run_id}"
    tenant_b_slug = f"browser-b-{run_id}"
    staff_password = secrets.token_urlsafe(18)
    tenant_b_password = secrets.token_urlsafe(18)
    owner_a_password = secrets.token_urlsafe(18)
    owner_b_password = secrets.token_urlsafe(18)

    tenant_a = {"id": tenant_a_id, "slug": tenant_a_slug, "name": "Browser Matrix Tenant A"}
    tenant_b = {"id": tenant_b_id, "slug": tenant_b_slug, "name": "Browser Matrix Tenant B"}
    staff_a = _user(
        tenant_id=tenant_a_id,
        email=f"staff-a-{run_id}@example.com",
        name="Tenant A Staff",
        role="admin",
        password=staff_password,
    )
    staff_b = _user(
        tenant_id=tenant_b_id,
        email=f"staff-b-{run_id}@example.com",
        name="Tenant B Staff",
        role="admin",
        password=tenant_b_password,
    )
    await db.tenants.insert_many([tenant_a, tenant_b])
    await db.users.insert_many([prepare_for_mongo(staff_a), prepare_for_mongo(staff_b)])

    build_launchable_store = _load_existing_builder()
    staff_token = create_access_token(subject=staff_a["id"], tenant_id=tenant_a_id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://browser-harness",
        headers={"Authorization": f"Bearer {staff_token}"},
    ) as staff_client:
        store_a = await build_launchable_store(staff_client, f"a-{run_id}")
        store_b = await build_launchable_store(staff_client, f"b-{run_id}")
        template_response = await staff_client.post(
            "/api/webstores/setup/questionnaire-templates",
            json={
                "store_type": "fundraiser",
                "title": "Fundraiser intake",
                "version": 1,
                "webstore_id": store_a["store"]["id"],
                "sections": [{"key": "purpose", "title": "Store purpose", "questions": [{"key": "purpose", "label": "Purpose"}]}],
            },
        )
        if template_response.status_code not in {200, 201}:
            raise RuntimeError(f"Questionnaire fixture failed: {template_response.status_code} {template_response.text}")

    owner_a_identity_id = store_a["webstore_owner"]["portal_identity_id"]
    owner_b_identity_id = store_b["webstore_owner"]["portal_identity_id"]
    await db.portal_identities.update_many(
        {"id": {"$in": [owner_a_identity_id, owner_b_identity_id]}, "tenant_id": tenant_a_id},
        {"$set": {"password_hash": hash_password(owner_a_password), "magic_link_only": False}},
    )
    # Store B receives a distinct owner credential so Store A's owner has no
    # alternate portal identity that could reach it.
    await db.portal_identities.update_one(
        {"id": owner_b_identity_id, "tenant_id": tenant_a_id},
        {"$set": {"password_hash": hash_password(owner_b_password), "magic_link_only": False}},
    )

    # Deliberately conflicting stored readiness values exercise the fail-closed
    # provider boundary. No provider authority, payment, or order is created.
    await db.webstores.update_one(
        {"tenant_id": tenant_a_id, "id": store_a["store"]["id"]},
        {
            "$set": {
                "status": "live",
                "checkout_enabled": True,
                "stripe_payment_ready": True,
                "payment_readiness_status": "live_ready",
                "provider_onboarding_state": "complete",
                "provider_charges_enabled": True,
                "provider_payouts_enabled": True,
                "provider_readiness_source": "stored_fixture_only",
                "provider_account_reference": "fixture-account-must-not-authorize",
            }
        },
    )

    return {
        "run_id": run_id,
        "api_base": f"http://127.0.0.1:{os.environ.get('WEBSTORES_BROWSER_BACKEND_PORT', '8102')}/api",
        "tenant_a": {"id": tenant_a_id, "slug": tenant_a_slug},
        "tenant_b": {"id": tenant_b_id, "slug": tenant_b_slug},
        "staff_a": {"email": staff_a["email"], "password": staff_password},
        "staff_b": {"email": staff_b["email"], "password": tenant_b_password},
        "owner_a": {
            "email": f"chair-a-{run_id}@example.com",
            "password": owner_a_password,
            "portal_identity_id": owner_a_identity_id,
        },
        "owner_b": {
            "email": f"chair-b-{run_id}@example.com",
            "password": owner_b_password,
            "portal_identity_id": owner_b_identity_id,
        },
        "store_a": {
            "id": store_a["store"]["id"],
            "slug": store_a["store"]["slug"],
            "public_slug": store_a["store"].get("public_slug") or store_a["store"]["slug"],
            "product_id": store_a["product"]["id"],
            "packet_id": store_a["packet"]["id"],
        },
        "store_b": {
            "id": store_b["store"]["id"],
            "slug": store_b["store"]["slug"],
            "public_slug": store_b["store"].get("public_slug") or store_b["store"]["slug"],
            "product_id": store_b["product"]["id"],
        },
        "expected_collections": {"payments": 0, "orders": 0, "webstore_payment_events": 0},
    }


async def _main() -> None:
    await ensure_indexes()
    init_storage()
    fixture_path = Path(os.environ["WEBSTORES_BROWSER_FIXTURE_PATH"])
    fixture = await _seed()
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    import uvicorn

    config = uvicorn.Config(
        app,
        host=os.environ.get("WEBSTORES_BROWSER_BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("WEBSTORES_BROWSER_BACKEND_PORT", "8102")),
        log_level="warning",
    )
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    asyncio.run(_main())
