"""EC6 — Portal Identity + Portal Auth services.

Locked contracts:
- One portal identity → one tenant + one customer.
- Email lowercased at write; unique (tenant_id, email).
- Permissions are backend-authoritative. Presets can be applied; custom lists
  are the caller's explicit responsibility.
- Coarse brute-force lockout on password login.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.db import db
from ..core.security import hash_password, verify_password
from ..core.portal_security import create_portal_token
from ..core.time_utils import serialize_doc, utc_now
from ..models.portal_identity import PortalIdentity, PRESET_BUNDLES, PORTAL_PERMS, EMPLOYEE_PORTAL_PERMS

MAX_FAILED = 5
LOCK_MINUTES = 15


async def create_portal_identity(
    *,
    tenant_id: str,
    customer_id: Optional[str] = None,
    portal_type: str = "customer",
    employee_id: Optional[str] = None,
    email: str,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    role_label: Optional[str] = None,
    permissions_preset: str = "viewer_only",
    custom_permissions: Optional[list[str]] = None,
    magic_link_only: bool = True,
    initial_password: Optional[str] = None,
) -> dict:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email_required")
    existing = await db.portal_identities.find_one({"tenant_id": tenant_id, "email": email})
    if existing:
        raise ValueError("email_already_exists")
    if portal_type == "employee":
        # Employee Portal identities always get the full self-scope grant —
        # there is no per-identity preset like the customer role_label bundles.
        perms = list(EMPLOYEE_PORTAL_PERMS)
        permissions_preset = "custom"
    else:
        perms = list(PRESET_BUNDLES.get(permissions_preset, []))
        if permissions_preset == "custom":
            # Whitelist against PORTAL_PERMS
            perms = [p for p in (custom_permissions or []) if p in PORTAL_PERMS]
    pw_hash = hash_password(initial_password) if (initial_password and not magic_link_only) else None
    identity = PortalIdentity(
        tenant_id=tenant_id,
        portal_type=portal_type,  # type: ignore[arg-type]
        customer_id=customer_id,
        employee_id=employee_id,
        email=email,
        full_name=full_name,
        phone=phone,
        role_label=role_label,
        permissions_preset=permissions_preset,  # type: ignore[arg-type]
        permissions=perms,
        magic_link_only=magic_link_only,
        password_hash=pw_hash,
    ).model_dump()
    await db.portal_identities.insert_one(identity)
    identity.pop("_id", None)
    return serialize_doc(identity)


async def update_portal_identity(
    *,
    identity_id: str,
    tenant_id: str,
    updates: dict,
) -> dict:
    allowed_keys = {"full_name", "phone", "role_label", "status", "permissions_preset",
                    "permissions", "magic_link_only"}
    clean: dict = {}
    for k, v in updates.items():
        if k not in allowed_keys:
            continue
        clean[k] = v
    if "permissions_preset" in clean and clean["permissions_preset"] != "custom":
        clean["permissions"] = list(PRESET_BUNDLES.get(clean["permissions_preset"], []))
    if "permissions" in clean and clean.get("permissions_preset") == "custom":
        clean["permissions"] = [p for p in clean["permissions"] if p in PORTAL_PERMS]
    clean["updated_at"] = utc_now().isoformat()
    res = await db.portal_identities.update_one(
        {"id": identity_id, "tenant_id": tenant_id}, {"$set": clean}
    )
    if res.matched_count == 0:
        raise ValueError("portal_identity_not_found")
    doc = await db.portal_identities.find_one({"id": identity_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def _is_locked(identity: dict) -> bool:
    lu = identity.get("locked_until")
    if not lu:
        return False
    if isinstance(lu, str):
        try:
            lu = datetime.fromisoformat(lu.replace("Z", "+00:00"))
        except Exception:
            lu = None
    return bool(lu and lu > datetime.now(timezone.utc))


async def authenticate_password(*, tenant_id: str, email: str, password: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    doc = await db.portal_identities.find_one({"tenant_id": tenant_id, "email": email, "status": "active"})
    if not doc:
        return None
    if doc.get("magic_link_only") or not doc.get("password_hash"):
        return None
    if await _is_locked(doc):
        return None
    if not verify_password(password, doc["password_hash"]):
        await db.portal_identities.update_one(
            {"id": doc["id"]},
            {"$inc": {"failed_login_count": 1},
             "$set": {"locked_until": (utc_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
                      if (doc.get("failed_login_count", 0) + 1) >= MAX_FAILED else None}},
        )
        return None
    # Success — reset counters and record login
    await db.portal_identities.update_one(
        {"id": doc["id"]},
        {"$set": {"failed_login_count": 0, "locked_until": None,
                  "last_login_at": utc_now().isoformat()}},
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def find_active_identity_by_email(*, tenant_id: str, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    doc = await db.portal_identities.find_one({"tenant_id": tenant_id, "email": email, "status": "active"})
    if not doc:
        return None
    doc.pop("_id", None)
    return serialize_doc(doc)


def issue_portal_jwt(identity: dict) -> str:
    return create_portal_token(
        portal_identity_id=identity["id"],
        tenant_id=identity["tenant_id"],
        customer_id=identity.get("customer_id"),
        portal_type=identity.get("portal_type") or "customer",
        employee_id=identity.get("employee_id"),
    )
