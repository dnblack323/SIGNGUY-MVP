from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.db import db
from app.routers.invoices import PaymentIn, add_payment
from app.services import payment_service
from app.services.payment_service import confirm_stripe_from_webhook, record_manual


async def _seed_invoice(tenant_id: str, total_cents: int) -> str:
    invoice_id = f"inv-cir001-{uuid.uuid4().hex[:10]}"
    await db.invoices.insert_one(
        {
            "id": invoice_id,
            "tenant_id": tenant_id,
            "number": 1,
            "order_id": f"order-{uuid.uuid4().hex[:8]}",
            "customer_id": f"customer-{uuid.uuid4().hex[:8]}",
            "title": "Concurrency test invoice",
            "total_cents": total_cents,
            "amount_paid_cents": 0,
            "amount_refunded_cents": 0,
            "balance_due_cents": total_cents,
            "document_status": "issued",
            "financial_status": "unpaid",
            "status": "sent",
            "created_by": "cir-001-test",
        }
    )
    return invoice_id


def _manual_kwargs(tenant_id: str, invoice_id: str, amount_cents: int, key: str) -> dict:
    return {
        "tenant_id": tenant_id,
        "invoice_id": invoice_id,
        "amount_cents": amount_cents,
        "method": "cash",
        "paid_on": "2026-08-03",
        "reference": None,
        "notes": None,
        "idempotency_key": key,
        "actor_user_id": "cir-001-test",
        "actor_email": "cir-001@example.com",
    }


async def _run_overlapping_guards(monkeypatch, calls):
    original_guard = payment_service._apply_invoice_payment_guard
    entered = 0
    entered_lock = asyncio.Lock()
    all_entered = asyncio.Event()

    async def gated_guard(**kwargs):
        nonlocal entered
        async with entered_lock:
            entered += 1
            if entered == len(calls):
                all_entered.set()
        await all_entered.wait()
        return await original_guard(**kwargs)

    monkeypatch.setattr(payment_service, "_apply_invoice_payment_guard", gated_guard)
    return await asyncio.gather(*calls, return_exceptions=True)


@pytest.mark.asyncio
async def test_two_manual_payments_that_overrun_balance_have_one_authoritative_winner(seeded_users, monkeypatch):
    tenant_id = seeded_users["tenant_a"]["id"]
    invoice_id = await _seed_invoice(tenant_id, 10_000)
    calls = [
        record_manual(**_manual_kwargs(tenant_id, invoice_id, 6_000, "cir001-a")),
        record_manual(**_manual_kwargs(tenant_id, invoice_id, 6_000, "cir001-b")),
    ]

    results = await _run_overlapping_guards(monkeypatch, calls)

    assert sum(isinstance(result, tuple) for result in results) == 1
    errors = [str(result) for result in results if isinstance(result, ValueError)]
    assert errors == ["overpayment_rejected"]
    payments = [row async for row in db.payments.find({"tenant_id": tenant_id, "invoice_id": invoice_id}, {"_id": 0})]
    confirmed = [row for row in payments if row.get("status") == "confirmed"]
    failed = [row for row in payments if row.get("status") == "failed"]
    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})

    assert len(confirmed) == 1
    assert len(failed) == 1
    assert sum(row["amount_cents"] for row in confirmed) == invoice["amount_paid_cents"] == 6_000
    assert invoice["balance_due_cents"] == 4_000
    assert invoice["balance_due_cents"] >= 0


@pytest.mark.asyncio
async def test_exact_balance_concurrent_manual_payments_both_succeed(seeded_users, monkeypatch):
    tenant_id = seeded_users["tenant_a"]["id"]
    invoice_id = await _seed_invoice(tenant_id, 10_000)
    calls = [
        record_manual(**_manual_kwargs(tenant_id, invoice_id, 5_000, "cir001-exact-a")),
        record_manual(**_manual_kwargs(tenant_id, invoice_id, 5_000, "cir001-exact-b")),
    ]

    results = await _run_overlapping_guards(monkeypatch, calls)

    assert all(isinstance(result, tuple) for result in results)
    payments = [row async for row in db.payments.find({"tenant_id": tenant_id, "invoice_id": invoice_id}, {"_id": 0})]
    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})
    assert len([row for row in payments if row.get("status") == "confirmed"]) == 2
    assert invoice["amount_paid_cents"] == 10_000
    assert invoice["balance_due_cents"] == 0


@pytest.mark.asyncio
async def test_concurrent_stripe_confirmations_cannot_overpay(seeded_users, monkeypatch):
    tenant_id = seeded_users["tenant_a"]["id"]
    invoice_id = await _seed_invoice(tenant_id, 10_000)
    payments = []
    for amount_cents, suffix in ((6_000, "a"), (6_000, "b")):
        payments.append(
            {
                "id": f"payment-cir001-{suffix}-{uuid.uuid4().hex[:8]}",
                "tenant_id": tenant_id,
                "invoice_id": invoice_id,
                "customer_id": "customer-cir001",
                "source": "stripe",
                "status": "pending",
                "amount_cents": amount_cents,
                "stripe_payment_intent_id": f"pi-cir001-{suffix}-{uuid.uuid4().hex[:8]}",
            }
        )
    await db.payments.insert_many(payments)

    calls = [
        confirm_stripe_from_webhook(payment_intent_id=row["stripe_payment_intent_id"], provider_event_id=f"evt-{row['id']}")
        for row in payments
    ]
    await _run_overlapping_guards(monkeypatch, calls)

    stored = [row async for row in db.payments.find({"tenant_id": tenant_id, "invoice_id": invoice_id}, {"_id": 0})]
    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})
    assert len([row for row in stored if row.get("status") == "confirmed"]) == 1
    assert len([row for row in stored if row.get("status") == "failed"]) == 1
    assert invoice["amount_paid_cents"] == 6_000
    assert invoice["balance_due_cents"] == 4_000


@pytest.mark.asyncio
async def test_payment_guard_preserves_tenant_isolation(seeded_users):
    invoice_id = await _seed_invoice(seeded_users["tenant_a"]["id"], 5_000)

    with pytest.raises(ValueError, match="invoice_not_found"):
        await record_manual(
            **_manual_kwargs(seeded_users["tenant_b"]["id"], invoice_id, 1_000, "cir001-cross-tenant")
        )

    invoice = await db.invoices.find_one({"id": invoice_id, "tenant_id": seeded_users["tenant_a"]["id"]}, {"_id": 0})
    assert invoice["amount_paid_cents"] == 0
    assert invoice["balance_due_cents"] == 5_000


@pytest.mark.asyncio
async def test_legacy_invoice_payment_route_uses_guarded_service(seeded_users):
    user = seeded_users["user_a"]
    invoice_id = await _seed_invoice(user["tenant_id"], 2_000)

    result = await add_payment(
        invoice_id=invoice_id,
        payload=PaymentIn(amount_cents=2_000, method="card", paid_on="2026-08-03"),
        idempotency_key="cir001-legacy",
        user=user,
    )

    assert result["payment"]["status"] == "confirmed"
    assert result["payment"]["method"] == "card_external"
    invoice = await db.invoices.find_one({"id": invoice_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    assert invoice["amount_paid_cents"] == 2_000
    assert invoice["balance_due_cents"] == 0


@pytest.mark.asyncio
async def test_manual_payment_persistence_failure_rolls_back_invoice_guard(seeded_users, monkeypatch):
    tenant_id = seeded_users["tenant_a"]["id"]
    invoice_id = await _seed_invoice(tenant_id, 5_000)

    async def fail_finalize(**_kwargs):
        return False

    monkeypatch.setattr(payment_service, "_finalize_pending_payment", fail_finalize)
    with pytest.raises(ValueError, match="payment_persistence_failed"):
        await record_manual(**_manual_kwargs(tenant_id, invoice_id, 2_000, "cir001-persistence-failure"))

    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})
    payment = await db.payments.find_one(
        {"tenant_id": tenant_id, "invoice_id": invoice_id, "idempotency_key": "cir001-persistence-failure"},
        {"_id": 0},
    )
    assert invoice["amount_paid_cents"] == 0
    assert invoice["balance_due_cents"] == 5_000
    assert payment["status"] == "failed"

    replay, already_exists = await record_manual(
        **_manual_kwargs(tenant_id, invoice_id, 2_000, "cir001-persistence-failure")
    )
    assert already_exists is True
    assert replay["status"] == "failed"


@pytest.mark.asyncio
async def test_stripe_persistence_failure_releases_claim_for_retry(seeded_users, monkeypatch):
    tenant_id = seeded_users["tenant_a"]["id"]
    invoice_id = await _seed_invoice(tenant_id, 5_000)
    payment_id = f"payment-cir001-failure-{uuid.uuid4().hex[:8]}"
    payment_intent_id = f"pi-cir001-failure-{uuid.uuid4().hex[:8]}"
    await db.payments.insert_one(
        {
            "id": payment_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "customer_id": "customer-cir001",
            "source": "stripe",
            "status": "pending",
            "amount_cents": 2_000,
            "stripe_payment_intent_id": payment_intent_id,
        }
    )

    original_finalize = payment_service._finalize_pending_payment

    async def fail_finalize(**_kwargs):
        return False

    monkeypatch.setattr(payment_service, "_finalize_pending_payment", fail_finalize)
    with pytest.raises(RuntimeError, match="payment_confirmation_persistence_failed"):
        await confirm_stripe_from_webhook(payment_intent_id=payment_intent_id, provider_event_id="evt-failure")

    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})
    payment = await db.payments.find_one({"tenant_id": tenant_id, "id": payment_id}, {"_id": 0})
    assert invoice["amount_paid_cents"] == 0
    assert invoice["balance_due_cents"] == 5_000
    assert payment["status"] == "pending"
    assert "confirmation_claim_id" not in payment

    monkeypatch.setattr(payment_service, "_finalize_pending_payment", original_finalize)
    await confirm_stripe_from_webhook(payment_intent_id=payment_intent_id, provider_event_id="evt-retry")
    invoice = await db.invoices.find_one({"tenant_id": tenant_id, "id": invoice_id}, {"_id": 0})
    payment = await db.payments.find_one({"tenant_id": tenant_id, "id": payment_id}, {"_id": 0})
    assert invoice["amount_paid_cents"] == 2_000
    assert invoice["balance_due_cents"] == 3_000
    assert payment["status"] == "confirmed"
