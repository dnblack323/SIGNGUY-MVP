"""Users management: list, create, deactivate. Owner/Admin only."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.security import hash_password
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..deps import get_current_user, require_permission
from ..models.user import User
from ..services.audit import record_audit

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: Literal["owner", "admin", "staff"] = "staff"
    password: str = Field(min_length=8, max_length=128)


class UserUpdateIn(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Literal["owner", "admin", "staff"]] = None
    is_active: Optional[bool] = None


@router.get("", response_model=None)
async def list_users(user: dict = Depends(require_permission(Perm.USER_READ))) -> list[dict]:
    cursor = db.users.find({"tenant_id": user["tenant_id"]}, {"_id": 0, "password_hash": 0}).sort("created_at", 1)
    return [serialize_doc(doc) async for doc in cursor]


@router.post("", status_code=201)
async def create_user(payload: UserCreateIn, user: dict = Depends(require_permission(Perm.USER_WRITE))) -> dict:
    dup = await db.users.find_one({"tenant_id": user["tenant_id"], "email": payload.email})
    if dup:
        raise HTTPException(status_code=409, detail="Email already in use for this tenant")
    u = User(
        tenant_id=user["tenant_id"],
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    await db.users.insert_one(prepare_for_mongo(u.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="user.create", entity_type="user", entity_id=u.id,
        summary=f"Created user {u.email} ({u.role})",
    )
    out = serialize_doc(u.model_dump())
    out.pop("password_hash", None)
    return out


@router.patch("/{user_id}")
async def update_user(user_id: str, payload: UserUpdateIn, user: dict = Depends(require_permission(Perm.USER_WRITE))) -> dict:
    doc = await db.users.find_one({"id": user_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    await db.users.update_one({"id": user_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="user.update", entity_type="user", entity_id=user_id,
        summary=f"Updated user {doc['email']}", diff={"changes": updates},
    )
    doc = await db.users.find_one({"id": user_id, "tenant_id": user["tenant_id"]}, {"_id": 0, "password_hash": 0})
    return serialize_doc(doc)
