from __future__ import annotations

from typing import Optional

from pydantic import EmailStr, Field

from .base import BaseDoc


class Customer(BaseDoc):
    tenant_id: str
    number: Optional[int] = None
    name: str
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    archived: bool = False
