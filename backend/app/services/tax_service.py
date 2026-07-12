"""EC7 phase 7c — Tax reporting service.

Uses Invoice tax snapshots for historical accuracy. LOCKED per master plan
§12F — historical Invoices MUST use stored tax snapshots; current settings
NEVER retroactively rewrite them.

Provides:
  - tax_collected_by_date_range
  - tax_collected_by_jurisdiction
  - manual_tax_override_report (any Invoice/Order with a manual override flag)
  - exempt_customer_report

Tax jurisdiction is stored on the Invoice's `tax_jurisdiction_snapshot` if set
(future-additive field — falls back to the customer's `state` from address
when not stored).
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.tax_exemption import TaxExemption


# ---------- TaxExemption CRUD ----------
async def upsert_exemption(*, tenant_id: str, customer_id: str, jurisdiction: str,
                           reference: str, effective_from: str,
                           reason: Optional[str] = None,
                           effective_to: Optional[str] = None,
                           notes: Optional[str] = None,
                           actor_user_id: str) -> dict:
    if not customer_id or not reference:
        raise ValueError("customer_id_and_reference_required")
    cust = await db.customers.find_one({"tenant_id": tenant_id, "id": customer_id},
                                        {"_id": 0, "id": 1})
    if not cust:
        raise ValueError("customer_not_found")
    exemption = TaxExemption(
        tenant_id=tenant_id, customer_id=customer_id,
        jurisdiction=jurisdiction, reference=reference,
        reason=reason, effective_from=effective_from,
        effective_to=effective_to, notes=notes,
        archived=False, created_by=actor_user_id,
    ).model_dump()
    await db.tax_exemptions.insert_one(exemption)
    return serialize_doc(exemption)


async def list_exemptions(*, tenant_id: str, customer_id: Optional[str] = None,
                          jurisdiction: Optional[str] = None,
                          include_archived: bool = False) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if not include_archived:
        filt["archived"] = False
    if customer_id: filt["customer_id"] = customer_id
    if jurisdiction: filt["jurisdiction"] = jurisdiction
    cur = db.tax_exemptions.find(filt, {"_id": 0}).sort([("effective_from", -1)])
    return [serialize_doc(d) async for d in cur]


async def archive_exemption(*, tenant_id: str, exemption_id: str) -> dict:
    res = await db.tax_exemptions.update_one(
        {"tenant_id": tenant_id, "id": exemption_id},
        {"$set": {"archived": True, "updated_at": utc_now().isoformat()}}
    )
    if res.matched_count == 0:
        raise ValueError("exemption_not_found")
    return {"archived": True, "id": exemption_id}


async def is_customer_exempt(*, tenant_id: str, customer_id: str,
                             jurisdiction: Optional[str] = None,
                             at_date: Optional[str] = None) -> dict:
    """Return {"exempt": bool, "matching_exemption": <doc or None>}"""
    check_date = at_date or utc_now().date().isoformat()
    filt: dict[str, Any] = {"tenant_id": tenant_id, "customer_id": customer_id,
                            "archived": False, "effective_from": {"$lte": check_date}}
    if jurisdiction:
        filt["jurisdiction"] = jurisdiction
    async for e in db.tax_exemptions.find(filt, {"_id": 0}):
        if e.get("effective_to") and str(e["effective_to"]) < check_date:
            continue
        return {"exempt": True, "matching_exemption": serialize_doc(e)}
    return {"exempt": False, "matching_exemption": None}


# ---------- Tax reports ----------
def _range_iso(date_from: Optional[str], date_to: Optional[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if date_from: out["$gte"] = date_from
    if date_to: out["$lte"] = date_to + "T23:59:59.999999Z" if "T" not in date_to else date_to
    return out


async def tax_collected_by_range(*, tenant_id: str,
                                 date_from: Optional[str] = None,
                                 date_to: Optional[str] = None,
                                 timezone_name: str = "UTC") -> dict:
    """LOCKED: uses Invoice tax snapshots."""
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None,
                             "tax_cents": {"$sum": "$tax_cents"},
                             "subtotal_cents": {"$sum": "$subtotal_cents"},
                             "count": {"$sum": 1}}}]
    r = await db.invoices.aggregate(pipeline).to_list(length=1)
    if not r:
        return {"basis": "tax_collected", "value_cents": 0,
                "subtotal_cents": 0, "invoice_count": 0,
                "date_range": {"from": date_from, "to": date_to},
                "timezone": timezone_name,
                "empty": True,
                "limitations": ["invoice tax snapshots only — historical rates preserved"]}
    return {
        "basis": "tax_collected", "value_cents": int(r[0]["tax_cents"] or 0),
        "subtotal_cents": int(r[0]["subtotal_cents"] or 0),
        "invoice_count": int(r[0]["count"] or 0),
        "date_range": {"from": date_from, "to": date_to},
        "timezone": timezone_name, "empty": False,
        "limitations": ["invoice tax snapshots only — historical rates preserved"],
    }


async def tax_collected_by_jurisdiction(*, tenant_id: str,
                                        date_from: Optional[str] = None,
                                        date_to: Optional[str] = None,
                                        timezone_name: str = "UTC") -> dict:
    """Groups tax by jurisdiction. Jurisdiction is resolved (in priority order):
      1) Invoice.tax_jurisdiction_snapshot (when set — future-additive)
      2) Customer.state (from address)
      3) '__unknown__'
    """
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    by_juris: dict[str, dict[str, int]] = {}
    async for inv in db.invoices.find(match, {"_id": 0}):
        tax = int(inv.get("tax_cents", 0) or 0)
        if tax == 0:
            continue
        juris = inv.get("tax_jurisdiction_snapshot")
        if not juris:
            cust = await db.customers.find_one(
                {"tenant_id": tenant_id, "id": inv.get("customer_id")},
                {"_id": 0, "state": 1, "country": 1}
            )
            if cust:
                st = (cust.get("state") or "").strip()
                cy = (cust.get("country") or "").strip() or "US"
                juris = f"{cy}-{st}" if st else cy
        juris = juris or "__unknown__"
        row = by_juris.setdefault(juris, {"tax_cents": 0, "subtotal_cents": 0,
                                            "invoice_count": 0})
        row["tax_cents"] += tax
        row["subtotal_cents"] += int(inv.get("subtotal_cents", 0) or 0)
        row["invoice_count"] += 1
    items = [{"jurisdiction": j, **v} for j, v in sorted(by_juris.items(),
                                                          key=lambda kv: -kv[1]["tax_cents"])]
    return {
        "basis": "tax_collected", "items": items,
        "date_range": {"from": date_from, "to": date_to},
        "timezone": timezone_name,
        "limitations": [
            "invoice tax snapshots only — historical rates preserved",
            "jurisdiction resolved via Invoice.tax_jurisdiction_snapshot when set, else Customer.state",
        ],
    }


async def manual_tax_override_report(*, tenant_id: str,
                                     date_from: Optional[str] = None,
                                     date_to: Optional[str] = None,
                                     timezone_name: str = "UTC") -> dict:
    """List invoices flagged as having a manual tax override. This looks at
    two flag paths for forward compatibility:
      - Invoice.tax_manual_override == true
      - Invoice.tax_override_reason set to a non-empty string
    """
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued",
                             "$or": [{"tax_manual_override": True},
                                     {"tax_override_reason": {"$ne": None}}]}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    items: list[dict[str, Any]] = []
    async for inv in db.invoices.find(match, {"_id": 0}):
        items.append({
            "invoice_id": inv.get("id"),
            "number": inv.get("number"),
            "customer_id": inv.get("customer_id"),
            "issued_at": inv.get("issued_at"),
            "tax_cents": int(inv.get("tax_cents", 0) or 0),
            "override_reason": inv.get("tax_override_reason"),
        })
    return {"basis": "tax_collected", "items": items,
            "date_range": {"from": date_from, "to": date_to},
            "timezone": timezone_name,
            "limitations": ["snapshotted values, not current settings"]}


async def exempt_customer_report(*, tenant_id: str, jurisdiction: Optional[str] = None,
                                 date_from: Optional[str] = None,
                                 date_to: Optional[str] = None,
                                 timezone_name: str = "UTC") -> dict:
    """List customers marked exempt (any active TaxExemption row) with their
    matching invoice tax totals over the given range."""
    filt: dict[str, Any] = {"tenant_id": tenant_id, "archived": False}
    if jurisdiction:
        filt["jurisdiction"] = jurisdiction
    exemptions_by_customer: dict[str, list[dict]] = {}
    async for e in db.tax_exemptions.find(filt, {"_id": 0}):
        exemptions_by_customer.setdefault(e["customer_id"], []).append(serialize_doc(e))
    if not exemptions_by_customer:
        return {"basis": "tax_collected", "items": [],
                "date_range": {"from": date_from, "to": date_to},
                "timezone": timezone_name,
                "limitations": ["no active exemptions found"]}
    match_inv: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued",
                                  "customer_id": {"$in": list(exemptions_by_customer.keys())}}
    rng = _range_iso(date_from, date_to)
    if rng: match_inv["issued_at"] = rng
    by_customer: dict[str, dict[str, Any]] = {}
    async for inv in db.invoices.find(match_inv, {"_id": 0}):
        c = by_customer.setdefault(inv["customer_id"],
                                    {"invoice_count": 0, "subtotal_cents": 0,
                                     "tax_cents": 0})
        c["invoice_count"] += 1
        c["subtotal_cents"] += int(inv.get("subtotal_cents", 0) or 0)
        c["tax_cents"] += int(inv.get("tax_cents", 0) or 0)
    items: list[dict[str, Any]] = []
    for cid, exempts in exemptions_by_customer.items():
        cust = await db.customers.find_one({"tenant_id": tenant_id, "id": cid},
                                            {"_id": 0, "name": 1, "company": 1})
        stats = by_customer.get(cid, {"invoice_count": 0, "subtotal_cents": 0, "tax_cents": 0})
        items.append({
            "customer_id": cid,
            "customer_name": (cust or {}).get("name"),
            "customer_company": (cust or {}).get("company"),
            "exemptions": exempts,
            **stats,
        })
    return {"basis": "tax_collected", "items": items,
            "date_range": {"from": date_from, "to": date_to},
            "timezone": timezone_name,
            "limitations": [
                "tax_cents shows tax charged on those customers' invoices in the range",
                "if a customer has an exemption but was still charged tax, the row surfaces the discrepancy",
            ]}
