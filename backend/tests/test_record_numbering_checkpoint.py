from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from app.services.sequence import (
    RecordNumberingError,
    backfill_missing_record_numbers,
    next_record_number,
    preview_next_record_number,
)
from app.services.webstores import create_buyer_order
from server import app


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _seed_tenant_user(*, suffix: str | None = None) -> dict:
    suffix = suffix or uuid.uuid4().hex[:8]
    tenant_id = f"t-record-numbering-{suffix}"
    user = {
        "id": f"u-record-numbering-{suffix}",
        "tenant_id": tenant_id,
        "email": f"owner-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": f"Record Numbering {suffix}"})
    await db.users.insert_one(user)
    return {"tenant_id": tenant_id, "user": user}


async def _seed_invoice(tenant_id: str, total_cents: int = 10000) -> dict:
    customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    invoice_id = f"inv-{uuid.uuid4().hex[:8]}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "number": 100, "name": "Invoice Customer"})
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": tenant_id,
            "number": 100,
            "customer_id": customer_id,
            "job_name": "Invoice Order",
            "status": "confirmed",
            "created_by": "seed",
        }
    )
    await db.invoices.insert_one(
        {
            "id": invoice_id,
            "tenant_id": tenant_id,
            "number": 100,
            "order_id": order_id,
            "customer_id": customer_id,
            "title": "Invoice",
            "total_cents": total_cents,
            "balance_due_cents": total_cents,
            "amount_paid_cents": 0,
            "amount_refunded_cents": 0,
            "financial_status": "unpaid",
            "document_status": "issued",
            "status": "sent",
            "created_by": "seed",
        }
    )
    return {"invoice_id": invoice_id, "customer_id": customer_id, "order_id": order_id}


@pytest.mark.asyncio
async def test_record_numbers_are_atomic_per_tenant_and_record_type():
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"t-rn-a-{suffix}"
    tenant_b = f"t-rn-b-{suffix}"

    results = await asyncio.gather(
        *[
            next_record_number(
                tenant_id=tenant_a,
                record_type="quote",
                issued_to_entity_type="quote",
                issued_to_entity_id=f"quote-{idx}",
            )
            for idx in range(20)
        ]
    )
    assert sorted(result.number for result in results) == list(range(1, 21))

    order_number = await next_record_number(tenant_id=tenant_a, record_type="order")
    other_tenant_quote = await next_record_number(tenant_id=tenant_b, record_type="quote")
    assert order_number.number == 1
    assert other_tenant_quote.number == 1

    assert await db.record_number_allocations.count_documents({"tenant_id": tenant_a, "record_type": "quote"}) == 20
    assert await db.record_number_allocations.count_documents({"tenant_id": tenant_b, "record_type": "quote"}) == 1


@pytest.mark.asyncio
async def test_record_number_idempotency_replays_same_allocation_without_duplicate_events():
    tenant_id = f"t-rn-idem-{uuid.uuid4().hex[:8]}"
    key = f"idem-{uuid.uuid4().hex}"

    first = await next_record_number(
        tenant_id=tenant_id,
        record_type="payment",
        idempotency_key=key,
        issued_to_entity_type="payment",
        issued_to_entity_id="pay-1",
        actor_user_id="actor-1",
        actor_email="owner@example.com",
        reason="test",
        context={"invoice_id": "inv-1"},
    )
    second = await next_record_number(
        tenant_id=tenant_id,
        record_type="payment",
        idempotency_key=key,
        issued_to_entity_type="payment",
        issued_to_entity_id="pay-2",
    )

    assert second.id == first.id
    assert second.number == first.number
    assert second.issued_to_entity_id == "pay-1"
    assert await db.record_number_allocations.count_documents(
        {"tenant_id": tenant_id, "record_type": "payment", "idempotency_key": key}
    ) == 1


@pytest.mark.asyncio
async def test_config_preview_exhaustion_and_unsupported_types_are_honest():
    tenant_id = f"t-rn-config-{uuid.uuid4().hex[:8]}"
    await db.record_number_configs.insert_one(
        {
            "id": f"cfg-{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id,
            "record_type": "payment",
            "prefix": "PMT",
            "starting_number": 7,
            "min_digits": 4,
            "suffix": "",
            "date_component": "none",
            "reset_policy": "never",
            "max_number": 7,
            "active": True,
        }
    )

    preview = await preview_next_record_number(tenant_id=tenant_id, record_type="payment")
    assert preview["next_number"] == 7
    assert preview["formatted_number"] == "PMT-0007"
    assert await db.counters.count_documents({"tenant_id": tenant_id, "name": "payment"}) == 0

    issued = await next_record_number(tenant_id=tenant_id, record_type="payment")
    assert issued.number == 7
    assert issued.formatted_number == "PMT-0007"
    with pytest.raises(RecordNumberingError, match="sequence_exhausted"):
        await next_record_number(tenant_id=tenant_id, record_type="payment")
    with pytest.raises(RecordNumberingError, match="unsupported_record_type"):
        await next_record_number(tenant_id=tenant_id, record_type="not_real")


@pytest.mark.asyncio
async def test_backfill_preserves_existing_numbers_and_never_reuses_voided_or_archived_numbers():
    tenant_id = f"t-rn-backfill-{uuid.uuid4().hex[:8]}"
    await db.expenses.insert_many(
        [
            {
                "id": f"exp-old-{uuid.uuid4().hex[:6]}",
                "tenant_id": tenant_id,
                "number": 9,
                "expense_date": "2026-07-01",
                "category_key": "materials",
                "category_label_snapshot": "Materials",
                "description": "Voided legacy expense",
                "amount_cents": 100,
                "tax_cents": 0,
                "total_cents": 100,
                "state": "voided",
                "created_by": "seed",
                "created_at": "2026-07-01T00:00:00+00:00",
            },
            {
                "id": f"exp-new-{uuid.uuid4().hex[:6]}",
                "tenant_id": tenant_id,
                "expense_date": "2026-07-02",
                "category_key": "materials",
                "category_label_snapshot": "Materials",
                "description": "Missing number",
                "amount_cents": 200,
                "tax_cents": 0,
                "total_cents": 200,
                "state": "active",
                "created_by": "seed",
                "created_at": "2026-07-02T00:00:00+00:00",
            },
        ]
    )

    result = await backfill_missing_record_numbers(tenant_id=tenant_id, record_type="expense")
    assert result["preserved_existing_count"] == 1
    assert result["assigned_count"] == 1
    assert result["assigned"][0]["number"] == 10
    assert await db.expenses.count_documents({"tenant_id": tenant_id, "number": 9, "state": "voided"}) == 1
    assert await db.record_number_allocations.count_documents({"tenant_id": tenant_id, "record_type": "expense"}) == 1


@pytest.mark.asyncio
async def test_customer_api_allocates_number_and_ignores_payload_renumbering():
    ctx = await _seed_tenant_user()
    async with await _client_as(ctx["user"]) as client:
        created = await client.post("/api/customers", json={"name": "Numbered Customer", "number": 9999})
        assert created.status_code == 201, created.text
        customer = created.json()
        assert customer["number"] == 1

        patched = await client.patch(f"/api/customers/{customer['id']}", json={"notes": "kept", "number": 2222})
        assert patched.status_code == 200, patched.text
        assert patched.json()["number"] == 1

    _clear_override()


@pytest.mark.asyncio
async def test_manual_payment_and_refund_receive_idempotent_record_numbers():
    ctx = await _seed_tenant_user()
    invoice = await _seed_invoice(ctx["tenant_id"], total_cents=8000)

    async with await _client_as(ctx["user"]) as client:
        headers = {"Idempotency-Key": f"pay-{uuid.uuid4().hex}"}
        first = await client.post(
            f"/api/invoices/{invoice['invoice_id']}/manual-payments",
            json={"amount_cents": 3000, "method": "cash", "paid_on": "2026-07-27"},
            headers=headers,
        )
        assert first.status_code == 201, first.text
        payment = first.json()["payment"]
        assert payment["number"] == 1
        assert payment["record_number_type"] == "payment"

        replay = await client.post(
            f"/api/invoices/{invoice['invoice_id']}/manual-payments",
            json={"amount_cents": 3000, "method": "cash", "paid_on": "2026-07-27"},
            headers=headers,
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["payment"]["number"] == payment["number"]
        assert replay.json()["already_exists"] is True

        source_payment_id = f"stripe-pay-{uuid.uuid4().hex[:8]}"
        await db.payments.insert_one(
            {
                "id": source_payment_id,
                "tenant_id": ctx["tenant_id"],
                "invoice_id": invoice["invoice_id"],
                "customer_id": invoice["customer_id"],
                "order_id": invoice["order_id"],
                "source": "stripe",
                "status": "confirmed",
                "amount_cents": 5000,
                "stripe_payment_intent_id": f"pi_test_{uuid.uuid4().hex[:20]}",
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        refund_headers = {"Idempotency-Key": f"refund-{uuid.uuid4().hex}"}
        with patch("app.services.stripe_core.create_refund", return_value={"id": f"re_test_{uuid.uuid4().hex[:20]}", "status": "pending"}):
            refund = await client.post(
                f"/api/payments/{source_payment_id}/refund",
                json={"amount_cents": 1000, "reason": "Customer requested partial refund"},
                headers=refund_headers,
            )
        assert refund.status_code == 201, refund.text
        refund_body = refund.json()
        assert refund_body["number"] == 1
        assert refund_body["record_number_type"] == "refund"

    _clear_override()


@pytest.mark.asyncio
async def test_webstore_buyer_order_numbers_are_idempotent_and_do_not_affect_canonical_order_sequence():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-rn-webstore-{suffix}"
    webstore_id = f"ws-{suffix}"
    product_id = f"prod-{suffix}"
    slug = f"rn-store-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Webstore Numbering"})
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "owner_id": f"owner-{suffix}",
            "name": "Record Numbering Store",
            "slug": slug,
            "public_slug": f"public-{slug}",
            "store_type": "general",
            "status": "live",
            "checkout_enabled": True,
            "stripe_payment_ready": True,
        }
    )
    await db.webstore_products.insert_one(
        {
            "id": product_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "name": "Fundraiser Shirt",
            "category": "apparel",
            "product_type": "shirt",
            "production_cost_cents": 700,
            "selling_price_cents": 2500,
            "store_owner_share_cents": 300,
            "platform_fee_basis_points": 200,
            "status": "active",
            "public": True,
            "featured": True,
            "variants": [],
        }
    )

    idempotency_key = f"buyer-{uuid.uuid4().hex}"
    payload = {
        "buyer_name": "Webstore Buyer",
        "buyer_email": f"buyer-{suffix}@example.com",
        "line_items": [{"product_id": product_id, "quantity": 2}],
        "idempotency_key": idempotency_key,
    }
    first = await create_buyer_order(f"public-{slug}", payload)
    replay = await create_buyer_order(f"public-{slug}", payload)

    assert first["purchase_intent"]["status"] == "pending_payment"
    assert replay["purchase_intent"]["id"] == first["purchase_intent"]["id"]
    assert await db.webstore_buyer_orders.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.record_number_allocations.count_documents(
        {"tenant_id": tenant_id, "record_type": "webstore_order", "idempotency_key": idempotency_key}
    ) == 0

    order_number = await next_record_number(tenant_id=tenant_id, record_type="order")
    assert order_number.number == 1
