"""EC6 — Approvals + Signatures services (thin, dual-parent-safe)."""
from __future__ import annotations
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.approval import Approval
from ..models.signature import Signature, SignatureRequest
from ..services.audit import record_audit
from ..services.sequence import next_number


ALLOWED_APPROVAL_PARENTS = {
    "quote_revision", "proof_version", "contract",
    "order_item", "work_order_summary",
}


async def record_approval(
    *, tenant_id: str, parent_type: str, parent_id: str,
    action: str, actor_type: str, actor_ref: str,
    parent_version: Optional[int] = None,
    reason: Optional[str] = None,
    actor_display: Optional[str] = None,
    ip: Optional[str] = None, user_agent: Optional[str] = None,
) -> dict:
    if parent_type not in ALLOWED_APPROVAL_PARENTS:
        raise ValueError(f"invalid_parent:{parent_type}")
    if action not in {"approve", "request_changes", "decline"}:
        raise ValueError("invalid_action")
    if action in {"request_changes", "decline"} and not reason:
        raise ValueError("reason_required")
    approval = Approval(
        tenant_id=tenant_id,
        parent_type=parent_type,  # type: ignore[arg-type]
        parent_id=parent_id, parent_version=parent_version,
        action=action,  # type: ignore[arg-type]
        reason=reason,
        actor_type=actor_type,  # type: ignore[arg-type]
        actor_ref=actor_ref, actor_display=actor_display,
        ip=ip, user_agent=user_agent,
    ).model_dump()
    await db.approvals.insert_one(approval)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_ref or "system", actor_email=(actor_display or "system@internal"),
        action=f"approval.{action}", entity_type=parent_type, entity_id=parent_id,
        summary=f"{action} on {parent_type} {parent_id}",
        diff={"reason": reason, "actor_type": actor_type, "actor_ref": actor_ref},
    )
    approval.pop("_id", None)
    return serialize_doc(approval)


async def create_signature_request(
    *, tenant_id: str, parent_type: str, parent_id: str,
    title: str, required_signers: list[dict],
    parent_version: Optional[int] = None,
    description: Optional[str] = None, created_by: Optional[str] = None,
    actor_email: Optional[str] = None,
) -> dict:
    if parent_type not in {"proof", "contract", "work_order_summary", "quote", "document"}:
        raise ValueError(f"invalid_parent:{parent_type}")
    num = await next_number(tenant_id=tenant_id, name="signature_request")
    req = SignatureRequest(
        tenant_id=tenant_id, number=num,
        parent_type=parent_type,  # type: ignore[arg-type]
        parent_id=parent_id, parent_version=parent_version,
        title=title, description=description,
        required_signers=[{"name": s["name"], "email": s["email"].lower(),
                           "role": s.get("role"), "signed": False} for s in required_signers],
        status="draft", created_by=created_by,
    ).model_dump()
    await db.signature_requests.insert_one(req)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(created_by or "system"), actor_email=(actor_email or "system@internal"),
        action="signature_request.create", entity_type="signature_request",
        entity_id=req["id"], summary=f"Signature request SR-{num} created",
    )
    req.pop("_id", None)
    return serialize_doc(req)


async def record_signature(
    *, tenant_id: str, request_id: str, signer_email: str,
    signer_name: str, signature_type: str, typed_text: Optional[str] = None,
    signature_data_ref: Optional[str] = None, token_id: Optional[str] = None,
    ip: Optional[str] = None, user_agent: Optional[str] = None,
) -> dict:
    signer_email = (signer_email or "").lower()
    req = await db.signature_requests.find_one({"id": request_id, "tenant_id": tenant_id})
    if not req:
        raise ValueError("signature_request_not_found")
    if req.get("status") in {"completed", "cancelled"}:
        raise ValueError("signature_request_closed")
    # Confirm signer is required
    signers = req.get("required_signers") or []
    idx = next((i for i, s in enumerate(signers) if s["email"].lower() == signer_email and not s.get("signed")), -1)
    if idx < 0:
        raise ValueError("signer_not_required_or_already_signed")
    sig = Signature(
        tenant_id=tenant_id, request_id=request_id,
        signer_name=signer_name, signer_email=signer_email,
        signature_type=signature_type,  # type: ignore[arg-type]
        typed_text=typed_text, signature_data_ref=signature_data_ref,
        token_id=token_id, ip=ip, user_agent=user_agent,
    ).model_dump()
    await db.signatures.insert_one(sig)
    # Mark signer
    signers[idx]["signed"] = True
    signers[idx]["signed_at"] = utc_now().isoformat()
    signers[idx]["signature_id"] = sig["id"]
    all_signed = all(s.get("signed") for s in signers)
    updates: dict = {"required_signers": signers,
                     "status": "completed" if all_signed else "partially_signed",
                     "updated_at": utc_now().isoformat()}
    if all_signed:
        updates["completed_at"] = utc_now().isoformat()
    await db.signature_requests.update_one({"id": request_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=f"signer:{signer_email}", actor_email=signer_email,
        action="signature.record", entity_type="signature_request", entity_id=request_id,
        summary=f"Signed by {signer_email}",
        diff={"all_signed": all_signed},
    )
    sig.pop("_id", None)
    return serialize_doc(sig)
