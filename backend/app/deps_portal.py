"""EC6 — Portal auth dependencies. Fully separate from staff `deps.py`.

Staff routes MUST NOT accept a portal token. Portal routes MUST NOT accept a
staff token. Two dependency graphs, zero crossover.
"""
from __future__ import annotations

from typing import Callable, Optional
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .core.db import db
from .core.portal_security import decode_portal_token, hash_token
from .core.time_utils import serialize_doc

_portal_bearer = HTTPBearer(auto_error=False)


async def get_current_portal_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_portal_bearer),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing portal token")
    try:
        payload = decode_portal_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid portal token")
    if payload.get("sub_scope") != "portal" or payload.get("typ") != "portal_access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a portal token")
    pid = payload.get("sub")
    tid = payload.get("tenant_id")
    token_portal_type = payload.get("portal_type") or "customer"
    cid = payload.get("customer_id")
    eid = payload.get("employee_id")
    if not (pid and tid):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad portal payload")
    identity = await db.portal_identities.find_one({"id": pid, "tenant_id": tid, "status": "active"})
    if not identity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Portal identity inactive")
    # Legacy (pre-EC8c) customer identities have no `portal_type` field on the
    # stored doc — default them to "customer" rather than requiring a migration.
    doc_portal_type = identity.get("portal_type") or "customer"
    if doc_portal_type != token_portal_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Portal type mismatch")
    if token_portal_type == "customer":
        if not cid or identity.get("customer_id") != cid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad portal payload")
    elif token_portal_type == "employee":
        if not eid or identity.get("employee_id") != eid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad portal payload")
    return serialize_doc(identity)  # type: ignore[return-value]


def require_portal_permission(*required: str) -> Callable:
    async def _dep(identity: dict = Depends(get_current_portal_identity)) -> dict:
        perms = set(identity.get("permissions") or [])
        missing = [p for p in required if p not in perms]
        if missing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing portal permission: {missing[0]}")
        return identity
    return _dep


def require_employee_portal_permission(*required: str) -> Callable:
    """EC8 phase 8c — Employee Portal guard.

    Defense in depth beyond the disjoint permission-string namespaces: even
    if a customer identity somehow held an `employee:*` permission string, a
    customer-typed token/identity is still hard-rejected here. Also enforces
    that the linked Employee record is still `active` on every request — an
    Employee suspended/terminated after the portal identity was created loses
    portal access immediately, without needing to separately disable the
    PortalIdentity.
    """
    async def _dep(identity: dict = Depends(get_current_portal_identity)) -> dict:
        if identity.get("portal_type") != "employee" or not identity.get("employee_id"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee portal access required")
        perms = set(identity.get("permissions") or [])
        missing = [p for p in required if p not in perms]
        if missing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing portal permission: {missing[0]}")
        emp = await db.employees.find_one(
            {"id": identity["employee_id"], "tenant_id": identity["tenant_id"]}, {"_id": 0, "status": 1}
        )
        if not emp or emp.get("status") != "active":
            from .services.audit import record_audit
            await record_audit(
                tenant_id=identity["tenant_id"], actor_user_id=f"portal:{identity['id']}",
                actor_email=identity.get("email", ""), action="employee_portal_access_denied",
                entity_type="portal_identity", entity_id=identity["id"],
                summary="Employee Portal access denied — linked Employee is not active",
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account is not active")
        return identity
    return _dep


async def resolve_public_token(
    request: Request,
    raw_token: Optional[str] = None,
    *,
    expected_action: Optional[str] = None,
    expected_parent_type: Optional[str] = None,
    expected_parent_id: Optional[str] = None,
) -> dict:
    """Look up a public-action token by SHA-256 hash. Enforce expiry / consumption /
    audience / action / parent binding. Returns the stored token doc (never
    echoes the raw value)."""
    if not raw_token:
        raw_token = request.query_params.get("t") or request.headers.get("X-Public-Token") or ""
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing token")
    doc = await db.public_action_tokens.find_one({"token_hash": hash_token(raw_token)})
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid token")
    if doc.get("revoked"):
        raise HTTPException(status_code=410, detail="Token revoked")
    if doc.get("consumed_at") and doc.get("single_use", True):
        raise HTTPException(status_code=410, detail="Token already used")
    exp = doc.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        except Exception:
            exp = None
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Token expired")
    if expected_action and doc.get("action") != expected_action:
        raise HTTPException(status_code=403, detail="Token action mismatch")
    if expected_parent_type and doc.get("parent_type") != expected_parent_type:
        raise HTTPException(status_code=403, detail="Token parent mismatch")
    if expected_parent_id and doc.get("parent_id") != expected_parent_id:
        raise HTTPException(status_code=403, detail="Token parent mismatch")
    doc.pop("_id", None)
    return doc
