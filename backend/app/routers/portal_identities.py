"""EC6 — Portal Identity management (staff).

Staff endpoints to create, list, update, disable portal identities per Customer.
Also mint a magic-link email invite for a portal identity (raw token emailed
once via `services/email.py`).
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.portal_identity import create_portal_identity, update_portal_identity
from ..services.portal_tokens import mint_magic_link_token
from ..services.email import send_email
from ..services.audit import record_audit
from ..models.portal_identity import PRESET_BUNDLES

router = APIRouter(prefix="/portal-identities", tags=["portal_identities"])


class PortalIdentityCreateIn(BaseModel):
    customer_id: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None
    permissions_preset: str = "viewer_only"
    custom_permissions: list[str] = Field(default_factory=list)
    magic_link_only: bool = True
    send_invite_email: bool = True


class PortalIdentityUpdateIn(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None
    status: Optional[str] = None
    permissions_preset: Optional[str] = None
    permissions: Optional[list[str]] = None
    magic_link_only: Optional[bool] = None


@router.get("/presets")
async def presets(user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    return {"presets": PRESET_BUNDLES}


@router.get("")
async def list_identities(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.CUSTOMER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if customer_id: q["customer_id"] = customer_id
    if status: q["status"] = status
    total = await db.portal_identities.count_documents(q)
    cur = db.portal_identities.find(q, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(500)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


@router.post("", status_code=201)
async def create(payload: PortalIdentityCreateIn, request: Request,
                 user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    # Confirm customer belongs to this tenant
    cust = await db.customers.find_one({"id": payload.customer_id, "tenant_id": user["tenant_id"]})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        identity = await create_portal_identity(
            tenant_id=user["tenant_id"], customer_id=payload.customer_id,
            email=str(payload.email), full_name=payload.full_name, phone=payload.phone,
            role_label=payload.role_label,
            permissions_preset=payload.permissions_preset,
            custom_permissions=payload.custom_permissions,
            magic_link_only=payload.magic_link_only,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    identity.pop("password_hash", None)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="portal_identity.create", entity_type="portal_identity",
        entity_id=identity["id"], summary=f"Portal identity created for {identity['email']}",
    )
    if payload.send_invite_email:
        raw, _tok = await mint_magic_link_token(
            tenant_id=user["tenant_id"], portal_identity_id=identity["id"],
            email=identity["email"],
            ip_issued=(request.client.host if request.client else None),
        )
        # Email the raw token exactly once. Fails soft in dev (SendGrid may be disabled).
        send_email(
            to_email=identity["email"],
            subject="Your portal access invitation",
            body_text=f"Open your portal: /portal/verify?t={raw}\nThis single-use link expires in 30 minutes.",
            body_html=(f"<p>You have been granted portal access.</p>"
                       f"<p>Click to sign in: <a href='/portal/verify?t={raw}'>Open portal</a></p>"
                       f"<p>This link is single-use and expires in 30 minutes.</p>"),
        )
    return identity


@router.patch("/{iid}")
async def update(iid: str, payload: PortalIdentityUpdateIn,
                 user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    try:
        updated = await update_portal_identity(
            identity_id=iid, tenant_id=user["tenant_id"], updates=updates,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    updated.pop("password_hash", None)
    return updated


@router.post("/{iid}/resend-magic-link")
async def resend_magic_link(iid: str, request: Request,
                            user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    identity = await db.portal_identities.find_one(
        {"id": iid, "tenant_id": user["tenant_id"], "status": "active"}, {"_id": 0}
    )
    if not identity:
        raise HTTPException(status_code=404, detail="Portal identity not found")
    raw, _tok = await mint_magic_link_token(
        tenant_id=user["tenant_id"], portal_identity_id=iid,
        email=identity["email"], ip_issued=(request.client.host if request.client else None),
    )
    send_email(
        to_email=identity["email"],
        subject="Sign in to your portal",
        body_text=f"Use this single-use link to sign in: /portal/verify?t={raw}\nExpires in 30 minutes.",
        body_html=(f"<p>Use this single-use link to sign in: "
                   f"<a href='/portal/verify?t={raw}'>Open portal</a></p>"
                   f"<p>Expires in 30 minutes.</p>"),
    )
    return {"status": "sent"}
