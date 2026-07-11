"""EC6 — Public-action + magic-link token minting & consumption.

Raw tokens are generated here and returned to the caller EXACTLY ONCE. Only
SHA-256 hashes are persisted. Consuming a single-use token marks it consumed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.db import db
from ..core.portal_security import generate_raw_token, hash_token
from ..core.time_utils import utc_now
from ..models.public_action_token import PublicActionToken
from ..models.magic_link_token import MagicLinkToken


async def mint_public_action_token(
    *,
    tenant_id: str,
    action: str,
    parent_type: str,
    parent_id: str,
    parent_version: Optional[int] = None,
    audience_email: Optional[str] = None,
    ttl_hours: int = 72,
    single_use: bool = True,
    issued_by: Optional[str] = None,
    ip_issued: Optional[str] = None,
) -> tuple[str, dict]:
    """Return (raw_token, stored_doc). Raw token MUST be delivered exactly once."""
    raw = generate_raw_token()
    doc = PublicActionToken(
        tenant_id=tenant_id,
        token_hash=hash_token(raw),
        action=action,  # type: ignore[arg-type]
        parent_type=parent_type,
        parent_id=parent_id,
        parent_version=parent_version,
        audience_email=(audience_email or "").lower() or None,
        expires_at=utc_now() + timedelta(hours=ttl_hours),
        single_use=single_use,
        issued_by=issued_by,
        ip_issued=ip_issued,
    ).model_dump()
    await db.public_action_tokens.insert_one({**doc, "expires_at": doc["expires_at"].isoformat()})
    return raw, doc


async def consume_public_action_token(token_id: str) -> None:
    await db.public_action_tokens.update_one(
        {"id": token_id, "consumed_at": None},
        {"$set": {"consumed_at": utc_now().isoformat()}},
    )


async def revoke_public_action_token(token_id: str, tenant_id: str) -> bool:
    res = await db.public_action_tokens.update_one(
        {"id": token_id, "tenant_id": tenant_id, "revoked": False},
        {"$set": {"revoked": True}},
    )
    return res.modified_count > 0


async def mint_magic_link_token(
    *,
    tenant_id: str,
    portal_identity_id: str,
    email: str,
    ttl_minutes: int = 30,
    ip_issued: Optional[str] = None,
) -> tuple[str, dict]:
    raw = generate_raw_token()
    doc = MagicLinkToken(
        tenant_id=tenant_id,
        portal_identity_id=portal_identity_id,
        token_hash=hash_token(raw),
        expires_at=utc_now() + timedelta(minutes=ttl_minutes),
        ip_issued=ip_issued,
        email_sent_to=email.lower(),
    ).model_dump()
    await db.magic_link_tokens.insert_one({**doc, "expires_at": doc["expires_at"].isoformat()})
    return raw, doc


async def find_and_consume_magic_link(raw_token: str) -> Optional[dict]:
    """Look up by hash. Reject if expired/consumed. Otherwise mark consumed and
    return the doc. Raw token never persisted."""
    doc = await db.magic_link_tokens.find_one({"token_hash": hash_token(raw_token)})
    if not doc:
        return None
    if doc.get("consumed_at"):
        return None
    exp = doc.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        except Exception:
            exp = None
    if exp and exp < datetime.now(timezone.utc):
        return None
    await db.magic_link_tokens.update_one(
        {"id": doc["id"], "consumed_at": None},
        {"$set": {"consumed_at": utc_now().isoformat()}},
    )
    doc.pop("_id", None)
    return doc
