"""EC6 — Signature Requests and Signatures.

A SignatureRequest points at a parent record (contract, proof, quote, WOS,
or document). Signatures accumulate against a request; when all required
signers have signed, the request completes and a composite signed PDF is
regenerated (stored as a new file / document).
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field
from .base import BaseDoc

SignatureRequestParentType = Literal[
    "proof", "contract", "work_order_summary", "quote", "document",
]
SignatureRequestStatus = Literal[
    "draft", "sent", "partially_signed", "completed", "cancelled",
]
SignatureType = Literal["drawn", "typed"]


class RequiredSigner(BaseModel):
    name: str
    email: str
    role: Optional[str] = None
    signed: bool = False
    signed_at: Optional[datetime] = None
    signature_id: Optional[str] = None


class SignatureRequest(BaseDoc):
    tenant_id: str
    number: int
    parent_type: SignatureRequestParentType
    parent_id: str
    parent_version: Optional[int] = None
    title: str
    description: Optional[str] = None
    required_signers: list[RequiredSigner] = Field(default_factory=list)
    status: SignatureRequestStatus = "draft"
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None
    signed_pdf_file_id: Optional[str] = None
    signed_pdf_document_id: Optional[str] = None
    created_by: Optional[str] = None


class Signature(BaseDoc):
    tenant_id: str
    request_id: str
    signer_name: str
    signer_email: str
    signature_type: SignatureType
    signature_data_ref: Optional[str] = None   # file_id of drawn/typed signature asset
    typed_text: Optional[str] = None            # captured typed text
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    token_id: Optional[str] = None              # public_action_tokens.id if via public link
