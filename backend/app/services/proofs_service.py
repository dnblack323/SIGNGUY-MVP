"""EC6 — Proofs service.

Creates / versions / transitions proofs. Snapshot-style version rows are
immutable. Transitions call this service, which writes audit + activity and
notifies staff assigned to the parent order/work_order where applicable.
"""
from __future__ import annotations
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.proof import Proof, ProofVersion
from ..services.audit import record_audit
from ..services.sequence import next_number

ALLOWED_TRANSITIONS = {
    "draft": {"sent", "cancelled"},
    "sent": {"viewed", "approved", "changes_requested", "cancelled", "superseded"},
    "viewed": {"approved", "changes_requested", "cancelled", "superseded"},
    "approved": {"superseded", "cancelled"},
    "changes_requested": {"superseded", "cancelled", "sent"},
    "cancelled": set(),
    "superseded": set(),
}


async def create_proof(
    *, tenant_id: str, parent_type: str, parent_id: str, title: str,
    file_id: Optional[str], document_id: Optional[str] = None,
    customer_id: Optional[str] = None, description: Optional[str] = None,
    created_by: Optional[str] = None, actor_email: Optional[str] = None,
) -> dict:
    num = await next_number(tenant_id=tenant_id, name="proof")
    proof = Proof(
        tenant_id=tenant_id, number=num,
        parent_type=parent_type,  # type: ignore[arg-type]
        parent_id=parent_id, customer_id=customer_id,
        title=title, description=description,
        current_version=1, current_file_id=file_id, current_document_id=document_id,
        status="draft", created_by=created_by,
    ).model_dump()
    await db.proofs.insert_one(proof)
    if file_id:
        ver = ProofVersion(
            tenant_id=tenant_id, proof_id=proof["id"], version=1, file_id=file_id,
            document_id=document_id, created_by=created_by,
        ).model_dump()
        await db.proof_versions.insert_one(ver)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(created_by or "system"), actor_email=(actor_email or "system@internal"),
        action="proof.create", entity_type="proof", entity_id=proof["id"],
        summary=f"Proof P-{num} created", diff={"title": title, "parent_type": parent_type, "parent_id": parent_id},
    )
    proof.pop("_id", None)
    return serialize_doc(proof)


async def add_proof_version(
    *, tenant_id: str, proof_id: str, file_id: str,
    document_id: Optional[str] = None, notes: Optional[str] = None,
    created_by: Optional[str] = None, actor_email: Optional[str] = None,
) -> dict:
    proof = await db.proofs.find_one({"id": proof_id, "tenant_id": tenant_id})
    if not proof:
        raise ValueError("proof_not_found")
    new_v = int(proof.get("current_version", 1)) + 1
    ver = ProofVersion(
        tenant_id=tenant_id, proof_id=proof_id, version=new_v, file_id=file_id,
        document_id=document_id, notes=notes, created_by=created_by,
    ).model_dump()
    await db.proof_versions.insert_one(ver)
    await db.proofs.update_one(
        {"id": proof_id, "tenant_id": tenant_id},
        {"$set": {"current_version": new_v, "current_file_id": file_id,
                  "current_document_id": document_id, "updated_at": utc_now().isoformat(),
                  "status": "draft"}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(created_by or "system"), actor_email=(actor_email or "system@internal"),
        action="proof.add_version", entity_type="proof", entity_id=proof_id,
        summary=f"Proof version v{new_v} added",
    )
    doc = await db.proofs.find_one({"id": proof_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def transition_proof(
    *, tenant_id: str, proof_id: str, target: str,
    reason: Optional[str] = None, actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None, actor_kind: str = "staff",
) -> dict:
    proof = await db.proofs.find_one({"id": proof_id, "tenant_id": tenant_id})
    if not proof:
        raise ValueError("proof_not_found")
    current = proof.get("status", "draft")
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid_transition:{current}->{target}")
    if target in {"changes_requested", "cancelled"} and not reason:
        raise ValueError("reason_required")
    now = utc_now().isoformat()
    updates: dict = {"status": target, "updated_at": now}
    if target == "sent":
        updates["last_sent_at"] = now
    elif target == "viewed":
        updates["last_viewed_at"] = now
    elif target == "approved":
        updates["approved_at"] = now
    elif target == "changes_requested":
        updates["changes_requested_at"] = now
        updates["changes_requested_reason"] = reason
    elif target == "cancelled":
        updates["cancelled_at"] = now
        updates["cancelled_reason"] = reason
    await db.proofs.update_one({"id": proof_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(actor_user_id or f"portal:{actor_kind}"), actor_email=(actor_email or "system@internal"),
        action=f"proof.{target}", entity_type="proof", entity_id=proof_id,
        summary=f"Proof → {target}", diff={"from": current, "to": target, "reason": reason, "actor_kind": actor_kind},
    )
    doc = await db.proofs.find_one({"id": proof_id}, {"_id": 0})
    return serialize_doc(doc or {})
