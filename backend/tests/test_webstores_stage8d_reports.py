"""Focused Stage 8D canonical Webstore report tests."""
from __future__ import annotations

import uuid

import pytest

from app.core.db import db, ensure_indexes
from app.services.webstore_reports import owner_summary, staff_report
from backend.tests.test_webstores_stage8b_orders_projection import _seed_projection


@pytest.mark.asyncio
async def test_reports_reconcile_canonical_records_and_provider_ledger_only():
    await ensure_indexes()
    ctx = await _seed_projection(uuid.uuid4().hex[:8])
    intent = await db.webstore_purchase_intents.find_one({"canonical_order_id": ctx["order_id"]}, {"_id": 0})
    await db.webstore_ledger_entries.insert_many(
        [
            {
                "id": f"ledger-refund-{ctx['order_id']}",
                "tenant_id": ctx["tenant_id"],
                "webstore_id": ctx["webstore_id"],
                "source_id": intent["id"],
                "source_type": "canonical_refund_payment",
                "entry_type": "refund",
                "amount_cents": -500,
            },
            {
                "id": f"ledger-payout-{ctx['order_id']}",
                "tenant_id": ctx["tenant_id"],
                "webstore_id": ctx["webstore_id"],
                "source_id": intent["id"],
                "source_type": "provider_payout_event",
                "entry_type": "payout",
                "amount_cents": 2500,
            },
        ]
    )

    report = await staff_report(
        {"id": "stage8d-staff", "tenant_id": ctx["tenant_id"], "role": "owner"},
        ctx["webstore_id"],
    )
    assert report["source_of_truth"] == "canonical_orders_payments_and_provider_ledger"
    assert report["order_count"] == 1
    assert report["legacy_order_count"] == 0
    assert report["gross_sales_cents"] == 3200
    assert report["refund_total_cents"] == 500
    assert report["payout_total_cents"] == 2500
    assert report["product_quantities"]["product-1"] == 2
    assert report["production_load"]["orders_awaiting_handoff"] == 1

    owner = await owner_summary(ctx["tenant_id"], ctx["webstore_id"])
    assert owner["order_count"] == 1
    assert owner["gross_sales_cents"] == 3200
    assert owner["refund_total_cents"] == 500
    assert owner["payout_total_cents"] == 2500
    assert "platform_fee_cents" not in owner
    assert "production_load" not in owner
    assert "source_of_truth" in owner
