"""Auth: register-tenant (bootstrap), login, logout, me, password reset, Google sign-in."""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Literal, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from ..core.config import get_settings
from ..core.db import db
from ..core.permissions import permissions_for_role
from ..core.security import (
    create_access_token,
    decode_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import get_current_user
from ..models.user import PasswordResetToken, Tenant, User
from ..services.audit import record_audit
from ..services.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()

# Emergent-managed Google Auth session exchange endpoint. Fixed platform URL,
# not tenant/environment-specific — not sourced from .env.
EMERGENT_AUTH_SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


class RegisterTenantIn(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=200)
    tenant_slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    owner_email: EmailStr
    owner_full_name: str = Field(min_length=1, max_length=200)
    owner_password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: dict
    tenant: dict
    permissions: list[str]


class RequestPasswordResetIn(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/register-tenant", response_model=TokenOut, status_code=201)
async def register_tenant(payload: RegisterTenantIn) -> TokenOut:
    """Bootstrap a new tenant with its Owner user. Public endpoint."""
    existing = await db.tenants.find_one({"slug": payload.tenant_slug})
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug already taken")

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    user = User(
        tenant_id=tenant.id,
        email=payload.owner_email,
        full_name=payload.owner_full_name,
        role="owner",
        password_hash=hash_password(payload.owner_password),
    )
    await db.tenants.insert_one(prepare_for_mongo(tenant.model_dump()))
    await db.users.insert_one(prepare_for_mongo(user.model_dump()))

    await record_audit(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        actor_email=user.email,
        action="tenant.create",
        entity_type="tenant",
        entity_id=tenant.id,
        summary=f"Tenant '{tenant.name}' created",
    )

    token = create_access_token(subject=user.id, tenant_id=tenant.id)
    user_out = serialize_doc(user.model_dump())
    user_out.pop("password_hash", None)
    return TokenOut(
        access_token=token,
        user=user_out,
        tenant=serialize_doc(tenant.model_dump()),
        permissions=permissions_for_role(user.role),
    )


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn) -> TokenOut:
    tenant = await db.tenants.find_one({"slug": payload.tenant_slug})
    generic_error = HTTPException(status_code=401, detail="Invalid shop, email, or password")
    if not tenant:
        raise generic_error
    doc = await db.users.find_one({"tenant_id": tenant["id"], "email": str(payload.email).lower()})
    if not doc:
        # try case-preserved too (older records may not be lowercased)
        doc = await db.users.find_one({"tenant_id": tenant["id"], "email": payload.email})
    if not doc or not verify_password(payload.password, doc["password_hash"]) or not doc.get("is_active", True):
        raise generic_error
    await db.users.update_one({"id": doc["id"]}, {"$set": {"last_login_at": utc_now().isoformat()}})
    token = create_access_token(subject=doc["id"], tenant_id=doc["tenant_id"])
    u = serialize_doc(doc)
    u.pop("password_hash", None)
    return TokenOut(
        access_token=token,
        user=u,
        tenant=serialize_doc(tenant),
        permissions=permissions_for_role(doc.get("role", "staff")),
    )


class GoogleSessionIn(BaseModel):
    session_id: str = Field(min_length=1)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "shop"


async def _unique_tenant_slug(base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    for _ in range(5):
        if not await db.tenants.find_one({"slug": candidate}):
            return candidate
        candidate = f"{slug}-{uuid4().hex[:6]}"
    return f"{slug}-{uuid4().hex[:6]}"


@router.post("/google/session", response_model=TokenOut)
async def google_session(payload: GoogleSessionIn) -> TokenOut:
    """Exchange an Emergent-managed Google Auth `session_id` for our own JWT.

    This bridges Google Sign-In into the existing tenant/user/JWT system
    (same TokenOut shape as /login and /register-tenant) instead of adding
    a second, cookie-based session mechanism — Google is only used here to
    verify identity (email/name), the app's own JWT remains the single
    source of truth for authenticated requests.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                EMERGENT_AUTH_SESSION_DATA_URL,
                headers={"X-Session-ID": payload.session_id},
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Could not reach Google sign-in service")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired Google sign-in session")
    profile = resp.json()
    google_id = profile.get("id")
    email = (profile.get("email") or "").lower()
    name = profile.get("name") or email.split("@")[0]
    if not google_id or not email:
        raise HTTPException(status_code=502, detail="Google sign-in did not return a profile")

    doc = await db.users.find_one({"google_id": google_id})
    if not doc:
        # Link to an existing password-based account with the same email —
        # but only when the email is unambiguous. Email is unique per-tenant,
        # not globally, so if more than one tenant has this email we must
        # not silently guess which shop to link (would risk logging the
        # user into the wrong shop). Ask them to use email+password+shop
        # sign-in instead, where the shop is explicit.
        matches = await db.users.find({"email": email}).to_list(length=2)
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail="This email exists in more than one shop. Please sign in with your shop, email, and password instead.",
            )
        if matches:
            doc = matches[0]
            await db.users.update_one({"id": doc["id"]}, {"$set": {"google_id": google_id}})
            doc["google_id"] = google_id

    if doc:
        if not doc.get("is_active", True):
            raise HTTPException(status_code=401, detail="This account is disabled")
        tenant = await db.tenants.find_one({"id": doc["tenant_id"]})
        if not tenant:
            raise HTTPException(status_code=401, detail="Tenant not found")
        await db.users.update_one({"id": doc["id"]}, {"$set": {"last_login_at": utc_now().isoformat()}})
        u = serialize_doc(doc)
        u.pop("password_hash", None)
        return TokenOut(
            access_token=create_access_token(subject=doc["id"], tenant_id=doc["tenant_id"]),
            user=u,
            tenant=serialize_doc(tenant),
            permissions=permissions_for_role(doc.get("role", "staff")),
        )

    # First-ever sign-in for this Google identity — auto-create a new tenant + owner.
    tenant = Tenant(name=f"{name}'s Shop", slug=await _unique_tenant_slug(name or email))
    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=name,
        role="owner",
        password_hash=hash_password(uuid4().hex),
        google_id=google_id,
    )
    await db.tenants.insert_one(prepare_for_mongo(tenant.model_dump()))
    await db.users.insert_one(prepare_for_mongo(user.model_dump()))
    await record_audit(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        actor_email=user.email,
        action="tenant.create",
        entity_type="tenant",
        entity_id=tenant.id,
        summary=f"Tenant '{tenant.name}' created via Google sign-in",
    )
    user_out = serialize_doc(user.model_dump())
    user_out.pop("password_hash", None)
    return TokenOut(
        access_token=create_access_token(subject=user.id, tenant_id=tenant.id),
        user=user_out,
        tenant=serialize_doc(tenant.model_dump()),
        permissions=permissions_for_role(user.role),
    )


@router.post("/logout", status_code=204, response_class=Response)
async def logout(user: dict = Depends(get_current_user)) -> Response:
    # JWT stateless: client discards token. Log the event.
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="user.logout",
        entity_type="user",
        entity_id=user["id"],
        summary=f"{user['email']} logged out",
    )
    return Response(status_code=204)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    tenant = await db.tenants.find_one({"id": user["tenant_id"]})
    perms = permissions_for_role(user.get("role", "staff"))
    u = dict(user)
    u.pop("password_hash", None)
    return {"user": u, "tenant": serialize_doc(tenant), "permissions": perms}


@router.post("/request-password-reset", status_code=202)
async def request_password_reset(payload: RequestPasswordResetIn) -> dict:
    """Always returns the identical `{"ok": true}` shape regardless of
    whether the shop/email combination exists, whether the account is
    rate-limited, or whether the email actually sent — this prevents an
    attacker from using response differences to enumerate valid accounts."""
    response: dict = {"ok": True}
    tenant = await db.tenants.find_one({"slug": payload.tenant_slug})
    doc = await db.users.find_one({"tenant_id": tenant["id"], "email": str(payload.email).lower()}) if tenant else None
    if not doc:
        return response

    # Basic rate limit: at most 5 reset requests per user per 15 minutes.
    window_start = utc_now() - timedelta(minutes=15)
    recent_count = await db.password_reset_tokens.count_documents({
        "user_id": doc["id"], "created_at": {"$gte": window_start.isoformat()},
    })
    if recent_count >= 5:
        return response

    raw_token = generate_reset_token()
    expires_at = utc_now() + timedelta(minutes=_settings.password_reset_ttl_minutes)
    reset = PasswordResetToken(
        user_id=doc["id"],
        tenant_id=doc["tenant_id"],
        token_hash=hash_reset_token(raw_token),
        expires_at=expires_at,
    )
    await db.password_reset_tokens.insert_one(prepare_for_mongo(reset.model_dump()))

    reset_link = f"/reset-password?token={raw_token}"
    body = (
        f"Hi {doc.get('full_name','')},\n\n"
        f"You (or someone) requested a password reset for your SignGuy AI account.\n"
        f"Use this token within {_settings.password_reset_ttl_minutes} minutes:\n\n"
        f"Token: {raw_token}\n"
        f"Link: {reset_link}\n\n"
        f"If you didn't request this, ignore this message."
    )
    send_email(to_email=doc["email"], subject="Reset your SignGuy AI password", body_text=body)
    # DEV-ONLY convenience so local/dev testing can proceed without SendGrid.
    # Never included outside a development environment.
    if _settings.env == "development":
        response["dev_reset_token"] = raw_token
    return response


@router.post("/reset-password", status_code=204, response_class=Response)
async def reset_password(payload: ResetPasswordIn) -> Response:
    tok = await db.password_reset_tokens.find_one({"token_hash": hash_reset_token(payload.token)})
    if not tok:
        raise HTTPException(status_code=400, detail="Invalid or unknown token")
    if tok.get("used_at"):
        raise HTTPException(status_code=400, detail="Token already used")
    exp = tok["expires_at"]
    if isinstance(exp, str):
        from datetime import datetime
        try:
            exp_dt = datetime.fromisoformat(exp)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed expiry")
    else:
        exp_dt = exp
    if exp_dt < utc_now():
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one({"id": tok["user_id"]}, {"$set": {"password_hash": hash_password(payload.new_password)}})
    await db.password_reset_tokens.update_one({"id": tok["id"]}, {"$set": {"used_at": utc_now().isoformat()}})
    user = await db.users.find_one({"id": tok["user_id"]})
    if user:
        await record_audit(
            tenant_id=user["tenant_id"],
            actor_user_id=user["id"],
            actor_email=user["email"],
            action="user.password_reset",
            entity_type="user",
            entity_id=user["id"],
            summary=f"Password reset for {user['email']}",
        )
    return Response(status_code=204)


@router.get("/dev-config")
async def dev_config() -> dict:
    """Tells the frontend whether the dev auth bypass is enabled.

    Refuses to run outside a development environment (EC1 guard).
    """
    if _settings.env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    return {"dev_bypass": _settings.auth_dev_bypass}


DEV_TENANT_SLUG = "dev-shop"
DEV_OWNER_EMAIL = "dev@signguy-dev.example.com"


@router.post("/dev-login", response_model=TokenOut)
async def dev_login() -> TokenOut:
    """DEV-ONLY: auto-provision a Dev Shop + owner and return a JWT.

    Requires ENV=development AND AUTH_DEV_BYPASS=true. In production, refuses
    even if AUTH_DEV_BYPASS were somehow set (defense in depth alongside the
    startup guard in app.core.security_guards).
    """
    if _settings.env != "development" or not _settings.auth_dev_bypass:
        raise HTTPException(status_code=404, detail="Dev bypass disabled")

    tenant = await db.tenants.find_one({"slug": DEV_TENANT_SLUG})
    if not tenant:
        t = Tenant(name="Dev Shop", slug=DEV_TENANT_SLUG)
        await db.tenants.insert_one(prepare_for_mongo(t.model_dump()))
        tenant = await db.tenants.find_one({"id": t.id})

    user = await db.users.find_one({"tenant_id": tenant["id"], "email": DEV_OWNER_EMAIL})
    if not user:
        u = User(
            tenant_id=tenant["id"],
            email=DEV_OWNER_EMAIL,
            full_name="Dev Owner",
            role="owner",
            password_hash=hash_password("dev-bypass-not-a-real-password"),
        )
        await db.users.insert_one(prepare_for_mongo(u.model_dump()))
        user = await db.users.find_one({"id": u.id})

    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": utc_now().isoformat()}})
    token = create_access_token(subject=user["id"], tenant_id=tenant["id"])
    u_out = serialize_doc(user)
    u_out.pop("password_hash", None)
    return TokenOut(
        access_token=token,
        user=u_out,
        tenant=serialize_doc(tenant),
        permissions=permissions_for_role(user.get("role", "owner")),
    )
