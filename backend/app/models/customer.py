from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from .base import BaseDoc


CustomerType = Literal["individual", "business", "organization"]
CustomerLifecycleStatus = Literal["active", "lead", "inactive", "archived", "merged"]
ContactRole = Literal["primary", "billing", "production", "approval", "other"]
AddressPurpose = Literal["billing", "shipping", "production", "installation", "mailing", "other"]


class CustomerContact(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: ContactRole = "other"
    title: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None


class CustomerAddress(BaseModel):
    label: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    purposes: list[AddressPurpose] = Field(default_factory=list)
    is_default: bool = False
    notes: Optional[str] = None


class Customer(BaseDoc):
    tenant_id: str
    number: Optional[int] = None
    name: str
    company: Optional[str] = None
    customer_type: CustomerType = "business"
    lifecycle_status: CustomerLifecycleStatus = "active"
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    contacts: list[CustomerContact] = Field(default_factory=list)
    addresses: list[CustomerAddress] = Field(default_factory=list)
    notes: Optional[str] = None
    archived: bool = False
    archived_at: Optional[str] = None
    archived_reason: Optional[str] = None
    merged_into: Optional[str] = None
    merged_at: Optional[str] = None
    merge_history: list[dict] = Field(default_factory=list)
