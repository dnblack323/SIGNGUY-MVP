"""EC8 phase 8e — Training service.

Owns TrainingDefinition CRUD, TrainingAssignment lifecycle (assign / start /
complete / fail / cancel), Quiz attempt scoring (backend-only — answer keys
never leave this module), and Practical Signoff. Bounded on purpose — this
is NOT a generic workflow engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.practical_signoff import PracticalSignoff
from ..models.quiz_attempt import QuizAttempt
from ..models.training_assignment import TrainingAssignment
from ..models.training_definition import TrainingDefinition
from . import documents_service
from .activity import record_activity_with_audit
from .certification_service import notify_employee_event

ENTITY_TYPE = "training_definition"


class TrainingError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def public_definition_view(defn: dict) -> dict:
    """Strips the answer key (`correct_index`) — used for every Employee
    Portal response. Manager-facing responses use the raw document."""
    out = {**defn}
    out["quiz_questions"] = [
        {"id": q.get("id"), "prompt": q.get("prompt"), "choices": q.get("choices", [])}
        for q in defn.get("quiz_questions", [])
    ]
    return out


# ---------------------------------------------------------------------------
# Training Definitions
# ---------------------------------------------------------------------------

async def create_training_definition(*, tenant_id: str, actor_user_id: str, actor_email: str, **fields: Any) -> dict:
    doc = TrainingDefinition(tenant_id=tenant_id, created_by=actor_user_id, updated_by=actor_user_id, **fields).model_dump()
    await db.training_definitions.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="training_created", entity_type="training_definition", entity_id=doc["id"],
        summary=f"Training created: {doc['title']}",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def get_training_definition(*, tenant_id: str, training_definition_id: str) -> dict:
    doc = await db.training_definitions.find_one({"id": training_definition_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise TrainingError(404, "Training not found")
    return serialize_doc(doc)


async def list_training_definitions(*, tenant_id: str, equipment_id: Optional[str] = None, active_only: bool = False) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if equipment_id:
        q["equipment_id"] = equipment_id
    if active_only:
        q["active"] = True
    cur = db.training_definitions.find(q, {"_id": 0}).sort("title", 1)
    return [serialize_doc(d) async for d in cur]


async def update_training_definition(*, tenant_id: str, training_definition_id: str, actor_user_id: str, actor_email: str, **fields: Any) -> dict:
    existing = await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)
    fields["updated_by"] = actor_user_id
    fields["updated_at"] = utc_now().isoformat()
    if any(k in fields for k in ("quiz_questions", "required_steps", "passing_score", "practical_signoff_required")):
        fields["version"] = existing.get("version", 1) + 1
    await db.training_definitions.update_one({"id": training_definition_id, "tenant_id": tenant_id}, {"$set": fields})
    return await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)


async def archive_training_definition(*, tenant_id: str, training_definition_id: str, actor_user_id: str, actor_email: str) -> dict:
    existing = await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)
    await db.training_definitions.update_one(
        {"id": training_definition_id, "tenant_id": tenant_id},
        {"$set": {"active": False, "updated_by": actor_user_id, "updated_at": utc_now().isoformat()}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="training_updated", entity_type="training_definition", entity_id=training_definition_id,
        summary=f"Training archived: {existing['title']}",
    )
    return await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)


async def link_document(*, tenant_id: str, training_definition_id: str, document_id: str, portal_visible: bool, actor_user_id: str) -> dict:
    await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)
    try:
        return await documents_service.link_document(
            tenant_id=tenant_id, document_id=document_id, entity_type=ENTITY_TYPE, entity_id=training_definition_id,
            portal_visible=portal_visible, created_by=actor_user_id,
        )
    except ValueError:
        raise TrainingError(404, "Document not found")


async def list_documents(*, tenant_id: str, training_definition_id: str, portal_visible_only: bool = False) -> list[dict]:
    return await documents_service.list_linked_documents(
        tenant_id=tenant_id, entity_type=ENTITY_TYPE, entity_id=training_definition_id, portal_visible_only=portal_visible_only,
    )


# ---------------------------------------------------------------------------
# Training Assignments
# ---------------------------------------------------------------------------

async def assign_training(
    *, tenant_id: str, employee_id: str, training_definition_id: str, actor_user_id: str, actor_email: str,
    due_date: Optional[str] = None, manager_notes: Optional[str] = None, renewal_of: Optional[str] = None,
) -> dict:
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1, "name": 1})
    if not emp:
        raise TrainingError(404, "Employee not found")
    defn = await get_training_definition(tenant_id=tenant_id, training_definition_id=training_definition_id)
    doc = TrainingAssignment(
        tenant_id=tenant_id, employee_id=employee_id, training_definition_id=training_definition_id,
        equipment_id=defn.get("equipment_id"), assigned_by=actor_user_id, due_date=due_date,
        required_score=defn.get("passing_score"), practical_signoff_required=defn.get("practical_signoff_required", False),
        manager_notes=manager_notes, renewal_of=renewal_of, created_by=actor_user_id, updated_by=actor_user_id,
    ).model_dump()
    await db.training_assignments.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="training_assigned", entity_type="training_assignment", entity_id=doc["id"],
        summary=f"Training '{defn['title']}' assigned to {emp['name']}",
    )
    await notify_employee_event(tenant_id, employee_id, "training_assigned", f"You've been assigned training: {defn['title']}")
    doc.pop("_id", None)
    return serialize_doc(doc)


async def get_assignment(*, tenant_id: str, assignment_id: str) -> dict:
    doc = await db.training_assignments.find_one({"id": assignment_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise TrainingError(404, "Training assignment not found")
    return serialize_doc(doc)


async def list_assignments(
    *, tenant_id: str, employee_id: Optional[str] = None, training_definition_id: Optional[str] = None,
    equipment_id: Optional[str] = None, status_in: Optional[list[str]] = None,
) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        q["employee_id"] = employee_id
    if training_definition_id:
        q["training_definition_id"] = training_definition_id
    if equipment_id:
        q["equipment_id"] = equipment_id
    if status_in:
        q["status"] = {"$in": status_in}
    docs = [d async for d in db.training_assignments.find(q, {"_id": 0}).sort("due_date", 1)]
    defn_ids = list({d["training_definition_id"] for d in docs})
    defns: dict[str, dict] = {}
    if defn_ids:
        defns = {
            d["id"]: d async for d in
            db.training_definitions.find({"tenant_id": tenant_id, "id": {"$in": defn_ids}}, {"_id": 0, "id": 1, "title": 1, "training_type": 1})
        }
    out = []
    for d in docs:
        d = serialize_doc(d)
        d["overdue"] = bool(d.get("due_date") and d["due_date"] < _today() and d["status"] not in ("completed", "cancelled", "failed"))
        defn = defns.get(d["training_definition_id"])
        d["training_title"] = defn.get("title") if defn else None
        d["training_type"] = defn.get("training_type") if defn else None
        out.append(d)
    return out


async def start_assignment(*, tenant_id: str, assignment_id: str, employee_id: str) -> dict:
    """Employee-initiated (self-scoped — caller must already have verified employee_id ownership)."""
    a = await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)
    if a["employee_id"] != employee_id:
        raise TrainingError(403, "This Training Assignment belongs to a different Employee")
    if a["status"] != "not_started":
        return a
    now_iso = utc_now().isoformat()
    await db.training_assignments.update_one(
        {"id": assignment_id, "tenant_id": tenant_id},
        {"$set": {"status": "in_progress", "started_at": now_iso, "updated_at": now_iso}},
    )
    return await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


async def complete_assignment(*, tenant_id: str, assignment_id: str, employee_id: str, actor_user_id: str, actor_email: str) -> dict:
    """Marks the non-quiz/non-signoff steps done. If a practical signoff is
    required, moves to pending_signoff instead of completed. Called by the
    Employee themself (self-scoped)."""
    a = await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)
    if a["employee_id"] != employee_id:
        raise TrainingError(403, "This Training Assignment belongs to a different Employee")
    if a["status"] in ("completed", "failed", "cancelled"):
        raise TrainingError(409, f"Training assignment is already {a['status']}")
    now_iso = utc_now().isoformat()
    if a.get("practical_signoff_required"):
        new_status, practical_status = "pending_signoff", "pending"
    else:
        new_status, practical_status = "completed", a.get("practical_signoff_status", "not_required")
    fields: dict[str, Any] = {"status": new_status, "progress_percent": 100, "updated_at": now_iso, "practical_signoff_status": practical_status}
    if new_status == "completed":
        fields["completed_at"] = now_iso
    await db.training_assignments.update_one({"id": assignment_id, "tenant_id": tenant_id}, {"$set": fields})
    if new_status == "completed":
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="team", action="training_completed", entity_type="training_assignment", entity_id=assignment_id,
            summary=f"Training completed by employee {employee_id}",
        )
    return await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


async def fail_assignment(*, tenant_id: str, assignment_id: str, actor_user_id: str, actor_email: str, reason: Optional[str] = None) -> dict:
    a = await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)
    now_iso = utc_now().isoformat()
    await db.training_assignments.update_one(
        {"id": assignment_id, "tenant_id": tenant_id},
        {"$set": {"status": "failed", "updated_at": now_iso, "manager_notes": reason or a.get("manager_notes")}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="training_failed", entity_type="training_assignment", entity_id=assignment_id,
        summary=f"Training assignment failed for employee {a['employee_id']}", severity="warning",
    )
    return await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


async def cancel_assignment(*, tenant_id: str, assignment_id: str, actor_user_id: str, actor_email: str) -> dict:
    await db.training_assignments.update_one(
        {"id": assignment_id, "tenant_id": tenant_id},
        {"$set": {"status": "cancelled", "updated_at": utc_now().isoformat()}},
    )
    return await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


# ---------------------------------------------------------------------------
# Quiz attempts — backend-only scoring, full history retained
# ---------------------------------------------------------------------------

async def submit_quiz_attempt(
    *, tenant_id: str, assignment_id: str, employee_id: str, answers: list[dict],
    started_at: str, actor_user_id: str, actor_email: str,
) -> dict:
    a = await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)
    if a["employee_id"] != employee_id:
        raise TrainingError(403, "This Training Assignment belongs to a different Employee")
    defn = await get_training_definition(tenant_id=tenant_id, training_definition_id=a["training_definition_id"])
    questions = defn.get("quiz_questions") or []
    if not questions:
        raise TrainingError(400, "This Training has no quiz questions")
    answer_map = {ans["question_id"]: ans.get("selected_index") for ans in answers}
    correct = sum(1 for q in questions if answer_map.get(q["id"]) == q.get("correct_index"))
    score = round(100 * correct / len(questions))
    passing_score = defn.get("passing_score") or 0
    passed = score >= passing_score
    prior_count = await db.quiz_attempts.count_documents({"tenant_id": tenant_id, "training_assignment_id": assignment_id})
    now = utc_now()
    attempt = QuizAttempt(
        tenant_id=tenant_id, employee_id=employee_id, training_assignment_id=assignment_id,
        attempt_number=prior_count + 1, answers=answers, score=score, passed=passed,
        started_at=datetime.fromisoformat(started_at) if started_at else now, completed_at=now,
    ).model_dump()
    await db.quiz_attempts.insert_one(prepare_for_mongo(dict(attempt)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="quiz_attempt_completed", entity_type="training_assignment", entity_id=assignment_id,
        summary=f"Quiz attempt #{attempt['attempt_number']} scored {score}% ({'passed' if passed else 'failed'})",
    )
    now_iso = utc_now().isoformat()
    if passed:
        # A prior failed attempt may have already set status="failed" — a
        # passing retry must still be able to complete the assignment, so
        # this bypasses complete_assignment()'s terminal-status guard
        # (that guard exists to stop the self-service /complete endpoint
        # from re-firing on an already-finished assignment, not to block
        # a legitimate quiz retry).
        if a.get("practical_signoff_required"):
            new_status, practical_status = "pending_signoff", "pending"
        else:
            new_status, practical_status = "completed", a.get("practical_signoff_status", "not_required")
        fields: dict[str, Any] = {
            "status": new_status, "progress_percent": 100, "updated_at": now_iso,
            "practical_signoff_status": practical_status, "latest_score": score,
        }
        if new_status == "completed":
            fields["completed_at"] = now_iso
        await db.training_assignments.update_one({"id": assignment_id, "tenant_id": tenant_id}, {"$set": fields})
        if new_status == "completed":
            await record_activity_with_audit(
                tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
                module="team", action="training_completed", entity_type="training_assignment", entity_id=assignment_id,
                summary=f"Training completed by employee {employee_id}",
            )
    else:
        await db.training_assignments.update_one(
            {"id": assignment_id, "tenant_id": tenant_id},
            {"$set": {"status": "failed", "latest_score": score, "updated_at": now_iso}},
        )
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="team", action="training_failed", entity_type="training_assignment", entity_id=assignment_id,
            summary=f"Training failed quiz (score {score}%, needed {passing_score}%)", severity="warning",
        )
    attempt.pop("_id", None)
    return serialize_doc(attempt)


async def list_quiz_attempts(*, tenant_id: str, assignment_id: str) -> list[dict]:
    cur = db.quiz_attempts.find({"tenant_id": tenant_id, "training_assignment_id": assignment_id}, {"_id": 0}).sort("attempt_number", 1)
    return [serialize_doc(d) async for d in cur]


# ---------------------------------------------------------------------------
# Practical signoff — manager/trainer only, employees may never self-certify
# ---------------------------------------------------------------------------

async def record_practical_signoff(
    *, tenant_id: str, assignment_id: str, evaluator_user_id: str, actor_email: str,
    result: str, notes: Optional[str] = None, restrictions: Optional[str] = None,
    evidence_document_ids: Optional[list[str]] = None,
) -> dict:
    a = await get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)
    emp = await db.employees.find_one({"id": a["employee_id"], "tenant_id": tenant_id}, {"_id": 0, "linked_user_id": 1})
    if emp and emp.get("linked_user_id") == evaluator_user_id:
        raise TrainingError(400, "An Employee may not sign off their own practical training")
    doc = PracticalSignoff(
        tenant_id=tenant_id, employee_id=a["employee_id"], training_assignment_id=assignment_id,
        equipment_id=a.get("equipment_id"), evaluator_user_id=evaluator_user_id, evaluation_date=_today(),
        result=result, notes=notes, restrictions=restrictions, evidence_document_ids=evidence_document_ids or [],
        created_by=evaluator_user_id,
    ).model_dump()
    await db.practical_signoffs.insert_one(prepare_for_mongo(dict(doc)))
    now_iso = utc_now().isoformat()
    new_status = "completed" if result == "passed" else "failed"
    await db.training_assignments.update_one(
        {"id": assignment_id, "tenant_id": tenant_id},
        {"$set": {"practical_signoff_status": "passed" if result == "passed" else "failed",
                   "status": new_status, "completed_at": now_iso if result == "passed" else a.get("completed_at"),
                   "updated_at": now_iso}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=evaluator_user_id, actor_email=actor_email,
        module="team", action="practical_signoff_completed", entity_type="training_assignment", entity_id=assignment_id,
        summary=f"Practical signoff recorded: {result}",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def list_practical_signoffs(*, tenant_id: str, assignment_id: str) -> list[dict]:
    cur = db.practical_signoffs.find({"tenant_id": tenant_id, "training_assignment_id": assignment_id}, {"_id": 0}).sort("created_at", 1)
    return [serialize_doc(d) async for d in cur]
