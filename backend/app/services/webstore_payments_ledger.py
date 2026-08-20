"""Immutable ledger write helpers for Webstore payments."""
from __future__ import annotations

from typing import Any

from ..core.db import db
from ..core.time_utils import prepare_for_mongo
from ..models.webstore import WebstoreLedgerEntry

async def _insert_ledger_entry(entry: dict) -> None:
    existing = await db.webstore_ledger_entries.find_one(
        {
            "tenant_id": entry["tenant_id"],
            "webstore_id": entry["webstore_id"],
            "source_type": entry["source_type"],
            "source_id": entry["source_id"],
            "entry_type": entry["entry_type"],
            "reversal_of_ledger_entry_id": entry.get("reversal_of_ledger_entry_id"),
        },
        {"_id": 0, "id": 1},
    )
    if existing:
        return
    await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))


async def _record_purchase_ledger(intent: dict, *, payment_id: str) -> None:
    snapshot = intent.get("immutable_snapshot") or {}
    financial_lines = snapshot.get("financial_lines") or []
    platform_fee = sum(int(line.get("platform_fee_cents") or 0) for line in financial_lines)
    owner_share = sum(int(line.get("store_owner_share_cents") or 0) for line in financial_lines)
    fundraiser_share = sum(int(line.get("fundraiser_share_cents") or 0) for line in financial_lines)
    production_cost = sum(int(line.get("production_cost_cents") or 0) for line in financial_lines)
    subtotal = int(intent.get("product_subtotal_cents") or 0)
    total = int(intent.get("total_cents") or 0)
    shop_gross = subtotal - platform_fee - owner_share - fundraiser_share - production_cost
    rows = [
        ("buyer_payment", total, total, None),
        ("product_subtotal", subtotal, subtotal, None),
        ("donation", int(intent.get("donation_cents") or 0), total, None),
        ("shipping", int(intent.get("shipping_cents") or 0), total, None),
        ("sales_tax", int(intent.get("tax_cents") or 0), total, None),
        ("payment_processing_fee", 0, total, None),
        ("platform_usage_fee", platform_fee, subtotal, None),
        ("store_owner_share", owner_share, subtotal, None),
        ("fundraiser_share", fundraiser_share, subtotal, None),
        ("production_cost_estimate", production_cost, subtotal, None),
        ("shop_gross_estimate", shop_gross, subtotal, None),
    ]
    for entry_type, amount, basis, bps in rows:
        entry = WebstoreLedgerEntry(
            tenant_id=intent["tenant_id"],
            webstore_id=intent["webstore_id"],
            buyer_order_id=intent["id"],
            entry_type=entry_type,  # type: ignore[arg-type]
            amount_cents=amount,
            basis_amount_cents=basis,
            snapshot_basis_points=bps,
            source_type="webstore_purchase_intent",
            source_id=intent["id"],
            notes=f"Posted from canonical payment {payment_id}",
        ).model_dump()
        await _insert_ledger_entry(entry)
