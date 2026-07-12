"""EC6 — Portal authentication routes (public).

Contract:
- `POST /api/portal/auth/login` — password path (only if identity is not magic_link_only).
- `POST /api/portal/auth/magic-link` — request a magic link (does NOT reveal existence).
- `POST /api/portal/auth/magic-link/verify` — consume the raw token, issue portal JWT.
- `GET  /api/portal/auth/me` — returns the resolved portal identity + permissions.

Tenant discovery: the caller supplies `tenant_slug` in the body/header to
scope the lookup. In dev bypass we accept the first tenant if only one exists.
"""
from __future__ import annotations
import time
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from ..core.db import db
from ..deps_portal import get_current_portal_identity
from ..services.portal_identity import authenticate_password, find_active_identity_by_email, issue_portal_jwt
from ..services.portal_tokens import mint_magic_link_token, find_and_consume_magic_link
from ..services.email import send_email
from ..services.audit import record_audit

router = APIRouter(prefix="/portal/auth", tags=["portal_auth"])

# Simple in-process rate limiter (per (ip, route)). Coarse; hardening later.
_RATE_BUCKETS: dict[tuple, list[float]] = {}
_WINDOW_SECONDS = 60
_MAX_PER_WINDOW = 10


def _rate_limit(request: Request, key: str) -> None:
    ip = (request.client.host if request.client else "?") or "?"
    bucket_key = (ip, key)
    now = time.time()
    bucket = [t for t in _RATE_BUCKETS.get(bucket_key, []) if now - t < _WINDOW_SECONDS]
    if len(bucket) >= _MAX_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again shortly.")
    bucket.append(now)
    _RATE_BUCKETS[bucket_key] = bucket


async def _resolve_tenant_id(tenant_slug: Optional[str]) -> Optional[str]:
    if tenant_slug:
        t = await db.tenants.find_one({"slug": tenant_slug}, {"_id": 0, "id": 1})
        return t["id"] if t else None
    # In dev-bypass single-tenant, allow implicit resolution
    count = await db.tenants.count_documents({})
    if count == 1:
        t = await db.tenants.find_one({}, {"_id": 0, "id": 1})
        return t["id"] if t else None
    return None


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: Optional[str] = None


class MagicLinkRequestIn(BaseModel):
    email: EmailStr
    tenant_slug: Optional[str] = None


class MagicLinkVerifyIn(BaseModel):
    token: str


@router.post("/login")
async def login(payload: LoginIn, request: Request) -> dict:
    _rate_limit(request, "login")
    tid = await _resolve_tenant_id(payload.tenant_slug)
    if not tid:
        raise HTTPException(status_code=404, detail="Tenant not found")
    identity = await authenticate_password(tenant_id=tid, email=str(payload.email), password=payload.password)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid credentials or magic-link-only identity")
    was_first_login = identity.get("portal_type") == "employee" and not identity.get("last_login_at")
    token = issue_portal_jwt(identity)
    identity.pop("password_hash", None)
    action = "employee_portal_login" if identity.get("portal_type") == "employee" else "portal.login"
    await record_audit(
        tenant_id=tid, actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        action=action, entity_type="portal_identity", entity_id=identity["id"],
        summary="Portal password login",
    )
    if was_first_login:
        await record_audit(
            tenant_id=tid, actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
            action="employee_portal_activated", entity_type="portal_identity", entity_id=identity["id"],
            summary="Employee Portal identity activated (first login)",
        )
    return {"token": token, "identity": identity}


@router.post("/magic-link")
async def request_magic_link(payload: MagicLinkRequestIn, request: Request) -> dict:
    _rate_limit(request, "magic-link")
    tid = await _resolve_tenant_id(payload.tenant_slug)
    # Do NOT reveal identity existence — always return "sent" to prevent enumeration
    if tid:
        identity = await find_active_identity_by_email(tenant_id=tid, email=str(payload.email))
        if identity:
            raw, _tok = await mint_magic_link_token(
                tenant_id=tid, portal_identity_id=identity["id"], email=identity["email"],
                ip_issued=(request.client.host if request.client else None),
            )
            send_email(
                to_email=identity["email"],
                subject="Sign in to your portal",
                body_text=f"Sign-in link: /portal/verify?t={raw}\nSingle-use. Expires in 30 minutes.",
                body_html=(f"<p>Use this single-use link to sign in: "
                           f"<a href='/portal/verify?t={raw}'>Open portal</a></p>"),
            )
    return {"status": "sent"}


@router.post("/magic-link/verify")
async def verify_magic_link(payload: MagicLinkVerifyIn, request: Request) -> dict:
    _rate_limit(request, "magic-link-verify")
    doc = await find_and_consume_magic_link(payload.token)
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    identity = await db.portal_identities.find_one(
        {"id": doc["portal_identity_id"], "tenant_id": doc["tenant_id"], "status": "active"},
        {"_id": 0, "password_hash": 0},
    )
    if not identity:
        raise HTTPException(status_code=401, detail="Portal identity inactive")
    was_first_login = identity.get("portal_type") == "employee" and not identity.get("last_login_at")
    from ..core.time_utils import utc_now
    await db.portal_identities.update_one(
        {"id": identity["id"]}, {"$set": {"last_login_at": utc_now().isoformat()}},
    )
    token = issue_portal_jwt(identity)
    action = "employee_portal_login" if identity.get("portal_type") == "employee" else "portal.magic_link_login"
    await record_audit(
        tenant_id=identity["tenant_id"], actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        action=action, entity_type="portal_identity",
        entity_id=identity["id"], summary="Portal magic-link login",
    )
    if was_first_login:
        await record_audit(
            tenant_id=identity["tenant_id"], actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
            action="employee_portal_activated", entity_type="portal_identity", entity_id=identity["id"],
            summary="Employee Portal identity activated (first login)",
        )
    return {"token": token, "identity": identity}


@router.get("/me")
async def me(identity: dict = Depends(get_current_portal_identity)) -> dict:
    identity.pop("password_hash", None)
    return {"identity": identity, "permissions": identity.get("permissions") or []}
