"""Security Correction Checkpoint 2 regressions.

Focused coverage for portal/public-token exposure and EC18 follow-up DB scoping.
"""
from __future__ import annotations

import inspect
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services import business_assistant
from app.services.portal_identity import create_portal_identity
from app.services.portal_tokens import mint_public_action_token
from server import app


@pytest_asyncio.fixture
async def portal_public_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-sec2-{suffix}"
    customer_id = f"cust-sec2-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Security 2 Tenant"})
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Portal Customer", "email": "portal@example.com"})
    identity = await create_portal_identity(
        tenant_id=tenant_id,
        customer_id=customer_id,
        email=f"portal-{suffix}@example.com",
        permissions_preset="owner_full",
    )
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=tenant_id, customer_id=customer_id)
    yield {"tenant_id": tenant_id, "customer_id": customer_id, "identity": identity, "token": token, "suffix": suffix}


def _portal_headers(ctx: dict) -> dict:
    return {"Authorization": f"Bearer {ctx['token']}"}


def _forbidden_keys(payload: object, keys: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys:
                found.add(key)
            found.update(_forbidden_keys(value, keys))
    elif isinstance(payload, list):
        for value in payload:
            found.update(_forbidden_keys(value, keys))
    return found


@pytest.mark.asyncio
async def test_customer_portal_quote_invoice_and_message_responses_are_allowlisted(portal_public_ctx):
    ctx = portal_public_ctx
    quote_id = f"quote-sec2-{ctx['suffix']}"
    invoice_id = f"invoice-sec2-{ctx['suffix']}"
    await db.quotes.insert_one({
        "id": quote_id,
        "tenant_id": ctx["tenant_id"],
        "customer_id": ctx["customer_id"],
        "number": 1001,
        "status": "sent",
        "total_cents": 12000,
        "notes_internal": "hide this",
        "vendor_id": "vendor-secret",
        "profit_cents": 9000,
        "pricing_snapshot": {"internal": True},
    })
    await db.quote_line_items.insert_one({
        "id": f"qli-sec2-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "quote_id": quote_id,
        "revision_number": 1,
        "position": 1,
        "description": "Banner",
        "quantity": 1,
        "line_total_cents": 12000,
        "cost_cents": 1000,
        "margin_percent": 92,
        "vendor_id": "vendor-secret",
    })
    await db.invoices.insert_one({
        "id": invoice_id,
        "tenant_id": ctx["tenant_id"],
        "customer_id": ctx["customer_id"],
        "number": 2001,
        "document_status": "issued",
        "financial_status": "unpaid",
        "total_cents": 12000,
        "balance_due_cents": 12000,
        "notes_internal": "hide this",
        "stripe_payment_intent_id": "pi_internal",
        "provider_reference": "provider-secret",
    })
    await db.email_logs.insert_one({
        "id": f"email-sec2-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "customer_id": ctx["customer_id"],
        "subject": "Visible subject",
        "body": "Visible body",
        "status": "sent",
        "sendgrid_message_id": "sg-internal",
        "smtp_response": "smtp-internal",
        "error_message": "provider diagnostic",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        quote_resp = await client.get(f"/api/portal/quotes/{quote_id}", headers=_portal_headers(ctx))
        invoice_resp = await client.get(f"/api/portal/invoices/{invoice_id}", headers=_portal_headers(ctx))
        message_resp = await client.get("/api/portal/messages", headers=_portal_headers(ctx))

    assert quote_resp.status_code == 200, quote_resp.text
    assert invoice_resp.status_code == 200, invoice_resp.text
    assert message_resp.status_code == 200, message_resp.text
    forbidden = {
        "tenant_id", "customer_id", "notes_internal", "vendor_id", "profit_cents", "pricing_snapshot",
        "cost_cents", "margin_percent", "stripe_payment_intent_id", "provider_reference",
        "sendgrid_message_id", "smtp_response", "error_message",
    }
    assert _forbidden_keys(quote_resp.json(), forbidden) == set()
    assert _forbidden_keys(invoice_resp.json(), forbidden) == set()
    assert _forbidden_keys(message_resp.json(), forbidden) == set()


@pytest.mark.asyncio
async def test_public_token_reads_are_record_bound_and_field_allowlisted(portal_public_ctx):
    ctx = portal_public_ctx
    quote_id = f"quote-public-sec2-{ctx['suffix']}"
    other_quote_id = f"quote-public-other-{ctx['suffix']}"
    proof_id = f"proof-sec2-{ctx['suffix']}"
    sig_id = f"sig-sec2-{ctx['suffix']}"
    await db.quotes.insert_many([
        {
            "id": quote_id,
            "tenant_id": ctx["tenant_id"],
            "customer_id": ctx["customer_id"],
            "number": 3001,
            "status": "sent",
            "total_cents": 9000,
            "notes_internal": "secret",
            "vendor_id": "vendor-secret",
        },
        {"id": other_quote_id, "tenant_id": ctx["tenant_id"], "customer_id": ctx["customer_id"], "number": 3002, "status": "sent"},
    ])
    await db.proofs.insert_one({
        "id": proof_id,
        "tenant_id": ctx["tenant_id"],
        "customer_id": ctx["customer_id"],
        "title": "Proof",
        "status": "sent",
        "current_file_id": "file-visible",
        "internal_notes": "secret",
        "production_notes": "secret",
    })
    await db.signature_requests.insert_one({
        "id": sig_id,
        "tenant_id": ctx["tenant_id"],
        "title": "Sign request",
        "status": "sent",
        "internal_notes": "secret",
        "provider_reference": "secret",
        "required_signers": [
            {"name": "Allowed", "email": "allowed@example.com", "role": "approver", "signed": False, "private_note": "secret"},
            {"name": "Other", "email": "other@example.com", "role": "approver", "signed": False},
        ],
    })
    quote_token, _ = await mint_public_action_token(
        tenant_id=ctx["tenant_id"], action="quote_view", parent_type="quote", parent_id=quote_id, single_use=False,
    )
    proof_token, _ = await mint_public_action_token(
        tenant_id=ctx["tenant_id"], action="proof_approve", parent_type="proof", parent_id=proof_id, single_use=True,
    )
    sig_token, _ = await mint_public_action_token(
        tenant_id=ctx["tenant_id"], action="sign", parent_type="signature_request", parent_id=sig_id,
        audience_email="allowed@example.com", single_use=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        introspect = await client.get("/api/public/token/introspect", params={"t": quote_token})
        quote_resp = await client.get(f"/api/public/quotes/{quote_id}", params={"t": quote_token})
        wrong_quote = await client.get(f"/api/public/quotes/{other_quote_id}", params={"t": quote_token})
        proof_resp = await client.get(f"/api/public/proofs/{proof_id}", params={"t": proof_token})
        sig_resp = await client.get(f"/api/public/signatures/{sig_id}", params={"t": sig_token})

    assert introspect.status_code == 200
    assert "parent_id" not in introspect.json()
    assert quote_resp.status_code == 200, quote_resp.text
    assert wrong_quote.status_code == 403
    assert proof_resp.status_code == 200, proof_resp.text
    assert sig_resp.status_code == 200, sig_resp.text
    forbidden = {"tenant_id", "customer_id", "notes_internal", "vendor_id", "internal_notes", "production_notes", "provider_reference", "private_note"}
    assert _forbidden_keys(quote_resp.json(), forbidden) == set()
    assert _forbidden_keys(proof_resp.json(), forbidden) == set()
    assert _forbidden_keys(sig_resp.json(), forbidden) == set()
    assert [s["email"] for s in sig_resp.json()["request"]["required_signers"]] == ["allowed@example.com"]


@pytest.mark.asyncio
async def test_public_webstore_buyer_response_excludes_internal_commerce_rows():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-web-sec2-{suffix}"
    webstore_id = f"ws-sec2-{suffix}"
    product_id = f"prod-sec2-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Webstore Security Tenant"})
    await db.webstores.insert_one({
        "id": webstore_id,
        "tenant_id": tenant_id,
        "owner_id": f"owner-sec2-{suffix}",
        "name": "Security Store",
        "slug": f"security-store-{suffix}",
        "store_type": "general",
        "status": "live",
        "checkout_enabled": True,
    })
    await db.webstore_products.insert_one({
        "id": product_id,
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "name": "Shirt",
        "description": "Visible",
        "selling_price_cents": 2500,
        "production_cost_cents": 700,
        "store_owner_share_cents": 300,
        "platform_fee_basis_points": 200,
        "production_notes": "internal",
        "status": "active",
        "public": True,
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        storefront = await client.get(f"/api/public/webstores/security-store-{suffix}")
        order = await client.post(
            f"/api/public/webstores/security-store-{suffix}/buyer-orders",
            json={
                "buyer_name": "Buyer",
                "buyer_email": f"buyer-{suffix}@example.com",
                "line_items": [{"product_id": product_id, "quantity": 2}],
                "idempotency_key": f"buyer-sec2-{suffix}",
            },
        )

    assert storefront.status_code == 200, storefront.text
    assert order.status_code == 201, order.text
    product = storefront.json()["products"][0]
    assert _forbidden_keys(product, {"tenant_id", "production_cost_cents", "store_owner_share_cents", "platform_fee_basis_points", "production_notes"}) == set()
    payload = order.json()
    assert _forbidden_keys(payload["buyer_order"], {"tenant_id", "webstore_id", "stripe_connect_checkout_id", "idempotency_key", "bridged_order_id"}) == set()
    assert {row["entry_type"] for row in payload["ledger"]}.isdisjoint({"platform_usage_fee", "store_owner_share", "production_cost_estimate", "shop_gross_estimate"})
    assert await db.webstore_ledger_entries.count_documents({"tenant_id": tenant_id, "buyer_order_id": payload["buyer_order"]["id"], "entry_type": "platform_usage_fee"}) == 1


def test_ec18_followup_database_operations_remain_tenant_scoped():
    source = inspect.getsource(business_assistant)
    forbidden_fragments = [
        'assistant_source_citations.update_one({"id":',
        'assistant_action_proposals.update_one({"id":',
        'assistant_memory_entries.update_one({"id":',
        'assistant_memory_entries.find_one({"id":',
        'assistant_insights.update_one({"id":',
        'assistant_insights.find_one({"id":',
        'assistant_voice_sessions.update_one({"id":',
        'assistant_voice_sessions.find_one({"id":',
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source
