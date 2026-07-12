"""EC7 phase 7c — Expense + ExpenseCategory models.

Operational Expense tracking. Distinct from customer Payment records — Expenses
capture money the shop *spent*, Payments capture money the shop *received*.

Rules (LOCKED per master plan §12 / owner directive):
- Integer cents only.
- Tenant-scoped on every query.
- Archive instead of destructive delete where appropriate.
- Historical records preserved; category rename NEVER rewrites past Expenses.
- No full accounts-payable system (this is not vendor bill/pay lifecycle).
- Receipts reuse EC2 `FileRecord` + `Attachment` (parent_type="generic", scoped
  by the ExpenseAttachment link table for stable EC2 semantics).
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc


ExpenseState = Literal["active", "archived", "voided"]
ExpenseDeductibleClass = Literal[
    "unknown", "fully_deductible", "partially_deductible", "non_deductible",
    "personal", "capitalized", "not_applicable",
]
ExpensePaymentMethod = Literal[
    "cash", "check", "card", "ach", "bank_transfer", "wire", "other",
]


class ExpenseCategory(BaseDoc):
    """Tenant-configurable expense category.

    - `key` is stable + lower_snake_case and NEVER changes (reports rely on it).
    - `label` is the display string and MAY be renamed at any time; historical
      Expense records still reference `key` and retain their snapshotted
      `category_label_snapshot`.
    - Archived categories remain usable historically but are hidden from the
      "create Expense" picker.
    - `system` = true marks initial catalog rows that ship with every tenant.
    """
    tenant_id: str
    key: str
    label: str
    description: Optional[str] = None
    position: int = 0
    system: bool = False
    archived: bool = False


class Expense(BaseDoc):
    tenant_id: str
    number: int                                    # sequential per-tenant expense number
    expense_date: str                              # ISO date (YYYY-MM-DD) — the actual expense day
    category_key: str
    category_label_snapshot: str                   # frozen at write time so rename never rewrites history
    vendor_id: Optional[str] = None                # linked shop Vendor (EC7 phase 7b) where applicable
    vendor_name_snapshot: Optional[str] = None
    description: str
    amount_cents: int                              # money spent, tax-inclusive convention when tax_cents is 0
    tax_cents: int = 0                             # sales tax paid on this expense (informational)
    total_cents: int                               # backend-derived = amount_cents + tax_cents
    payment_method: ExpensePaymentMethod = "other"
    reference: Optional[str] = None                # check#/last-4/etc.
    deductible_class: ExpenseDeductibleClass = "unknown"
    recurring: bool = False                        # foundation flag for future recurring-expense generator
    recurring_reference: Optional[str] = None      # links generated instances to their parent recurrence
    # Optional links (all tenant-scoped)
    purchase_order_id: Optional[str] = None        # EC7 phase 7b linkage
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    project_reference: Optional[str] = None        # freeform for shop-internal projects
    internal_notes: Optional[str] = None
    # Lifecycle
    state: ExpenseState = "active"
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    archived_at: Optional[datetime] = None
    created_by: str


class ExpenseAttachment(BaseDoc):
    """Link between an Expense and an EC2 FileRecord (receipt / invoice /
    vendor doc). Distinct link table so we can archive an attachment without
    modifying either the Expense or the FileRecord."""
    tenant_id: str
    expense_id: str
    file_id: str
    role: str = "receipt"                          # receipt | vendor_invoice | statement | supporting
    attached_by: str
    note: Optional[str] = None
    archived: bool = False
